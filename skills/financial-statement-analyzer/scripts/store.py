#!/usr/bin/env python3
"""Local, append-only storage for categorized transactions.

Everything here is a plain SQLite file that lives entirely on the user's
machine (default: <data_dir>/finance.db). This is what makes the "don't
re-enter previous months" requirement work: every statement you import gets
recorded by its own file fingerprint, and every transaction gets deduped by
a stable key, so re-running the skill next month only adds what's new and
the dashboard always reflects full history without asking for old files again.

Subcommands:
    init            Create the DB (if needed) and seed default_category_rules.json
    import          Load categorized transactions (from categorize.py) into the DB
    check-import    Report whether a given source file was already imported
    summary         Print monthly totals by flow/category as JSON
    uncategorized   List transactions still needing a rule
"""
import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from categorize import normalize, load_rules  # noqa: E402

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    txn_hash TEXT PRIMARY KEY,
    account_id TEXT,
    account_kind TEXT,
    date TEXT NOT NULL,
    posted_month TEXT NOT NULL,
    description TEXT,
    amount REAL NOT NULL,
    currency TEXT,
    flow TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    explanation TEXT,
    matched_rule TEXT,
    is_fixed INTEGER,
    source_file TEXT,
    imported_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_txn_month ON transactions(posted_month);
CREATE INDEX IF NOT EXISTS idx_txn_flow ON transactions(flow);

CREATE TABLE IF NOT EXISTS imports (
    file_fingerprint TEXT PRIMARY KEY,
    file_name TEXT,
    account_id TEXT,
    txn_count INTEGER,
    imported_at TEXT DEFAULT (datetime('now'))
);
"""

# Columns added after the initial release; ALTER TABLE them in for DBs created
# by an older version of this skill instead of forcing the user to start over.
MIGRATIONS = [
    ("matched_rule", "TEXT"),
    ("is_fixed", "INTEGER"),
]


def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(transactions)")}
    for col_name, col_type in MIGRATIONS:
        if existing_cols and col_name not in existing_cols:
            conn.execute(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}")
    return conn


def init_db(db_path, data_dir):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    rules_path = Path(data_dir) / "category_rules.json"
    if not rules_path.exists():
        seed = Path(__file__).resolve().parent.parent / "assets" / "default_category_rules.json"
        shutil.copy(seed, rules_path)
        return {"db_initialized": True, "rules_seeded": str(rules_path)}
    return {"db_initialized": True, "rules_seeded": None}


def file_fingerprint(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def already_imported(db_path, source_file):
    fp = file_fingerprint(source_file)
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT file_name, imported_at, txn_count FROM imports WHERE file_fingerprint = ?", (fp,)
    ).fetchone()
    conn.close()
    if row:
        return {"already_imported": True, "file_name": row[0], "imported_at": row[1], "txn_count": row[2]}
    return {"already_imported": False}


def import_transactions(db_path, transactions, source_file):
    fp = file_fingerprint(source_file) if source_file else None
    conn = _connect(db_path)

    if fp:
        existing = conn.execute(
            "SELECT txn_count FROM imports WHERE file_fingerprint = ?", (fp,)
        ).fetchone()
        if existing:
            conn.close()
            return {"inserted": 0, "duplicates": 0, "skipped_file": True,
                     "message": f"{source_file} was already imported ({existing[0]} transactions); skipping."}

    inserted, duplicates = 0, 0
    account_id = None
    for txn in transactions:
        account_id = txn.get("account_id") or account_id
        dedup_key = txn.get("dedup_key") or hashlib.sha256(
            f"{txn.get('date')}|{txn.get('amount')}|{txn.get('description')}|{txn.get('account_id')}".encode("utf-8")
        ).hexdigest()[:24]
        date = txn.get("date") or ""
        posted_month = date[:7] if len(date) >= 7 else "unknown"
        is_fixed = txn.get("is_fixed")
        try:
            conn.execute(
                """INSERT INTO transactions
                   (txn_hash, account_id, account_kind, date, posted_month, description,
                    amount, currency, flow, category, subcategory, explanation, matched_rule,
                    is_fixed, source_file)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    dedup_key, txn.get("account_id"), txn.get("account_kind"), date, posted_month,
                    txn.get("description"), txn.get("amount"), txn.get("currency", "BRL"),
                    txn.get("flow"), txn.get("category"), txn.get("subcategory"),
                    txn.get("explanation"), txn.get("matched_rule"),
                    None if is_fixed is None else int(bool(is_fixed)),
                    str(source_file) if source_file else None,
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            duplicates += 1

    if fp:
        conn.execute(
            "INSERT OR REPLACE INTO imports (file_fingerprint, file_name, account_id, txn_count) VALUES (?,?,?,?)",
            (fp, str(source_file), account_id, inserted),
        )
    conn.commit()
    conn.close()
    return {"inserted": inserted, "duplicates": duplicates, "skipped_file": False}


def monthly_summary(db_path):
    conn = _connect(db_path)
    rows = conn.execute(
        """SELECT posted_month, flow, category, subcategory, ROUND(SUM(amount), 2), COUNT(*)
           FROM transactions
           GROUP BY posted_month, flow, category, subcategory
           ORDER BY posted_month, flow, category, subcategory"""
    ).fetchall()
    conn.close()
    summary = {}
    for month, flow, category, subcategory, total, count in rows:
        summary.setdefault(month, {}).setdefault(flow, {}).setdefault(category, {})[subcategory or ""] = {
            "total": total, "count": count
        }
    return summary


def uncategorized(db_path):
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT date, description, amount, account_id FROM transactions WHERE category = 'Nao classificado' ORDER BY date"
    ).fetchall()
    conn.close()
    return [{"date": r[0], "description": r[1], "amount": r[2], "account_id": r[3]} for r in rows]


def mark_fixed(db_path, rules_path, match_text, is_fixed):
    """Mark every transaction whose description matches `match_text` (accent- and
    case-insensitive substring, in either direction) as a fixed or variable
    expense, and remember it in the rules file so future imports of the same
    merchant are tagged automatically without asking again.

    This is what backs "avisa a skill que esse gasto e fixo" -- one correction
    from the user should stick for that merchant going forward, not just for
    the one transaction they happened to be looking at.
    """
    norm_match = normalize(match_text)
    conn = _connect(db_path)
    rows = conn.execute("SELECT txn_hash, description, category, subcategory FROM transactions").fetchall()

    matched = [r for r in rows if norm_match in normalize(r[1]) or normalize(r[1]) in norm_match]
    for txn_hash, _desc, _cat, _sub in matched:
        conn.execute("UPDATE transactions SET is_fixed = ? WHERE txn_hash = ?", (int(bool(is_fixed)), txn_hash))
    conn.commit()
    conn.close()

    rule_action = "not_found_no_rules_path"
    rule_id = None
    if rules_path:
        rules_data = load_rules(rules_path) if Path(rules_path).exists() else {"rules": []}
        rules_data.setdefault("rules", [])

        target_rule = None
        for rule in rules_data["rules"]:
            pattern_norm = normalize(rule["pattern"])
            if rule.get("type", "contains") != "regex" and (
                pattern_norm in norm_match or norm_match in pattern_norm
            ):
                target_rule = rule
                break

        if target_rule is not None:
            target_rule["fixed"] = bool(is_fixed)
            rule_id = target_rule.get("id", target_rule["pattern"])
            rule_action = "updated"
        else:
            # No existing rule covers this merchant yet -- create one, inheriting
            # the category the transactions already carry so we don't lose
            # categorization while adding the fixed/variable flag.
            inferred_category, inferred_subcategory = "Nao classificado", ""
            if matched:
                inferred_category = matched[0][2] or inferred_category
                inferred_subcategory = matched[0][3] or inferred_subcategory
            new_id = "user:" + normalize(match_text).lower().replace(" ", "_")[:40]
            rules_data["rules"].insert(0, {
                "id": new_id,
                "pattern": match_text,
                "type": "contains",
                "flow": "expense",
                "category": inferred_category,
                "subcategory": inferred_subcategory,
                "note": "",
                "fixed": bool(is_fixed),
            })
            rule_id = new_id
            rule_action = "created"

        with open(rules_path, "w", encoding="utf-8") as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)

    return {
        "updated_transactions": len(matched),
        "is_fixed": bool(is_fixed),
        "rule_id": rule_id,
        "rule_action": rule_action,
    }


def recategorize(db_path, txn_hash, category, subcategory, explanation, flow=None):
    conn = _connect(db_path)
    if flow:
        conn.execute(
            "UPDATE transactions SET category=?, subcategory=?, explanation=?, flow=? WHERE txn_hash=?",
            (category, subcategory, explanation, flow, txn_hash),
        )
    else:
        conn.execute(
            "UPDATE transactions SET category=?, subcategory=?, explanation=? WHERE txn_hash=?",
            (category, subcategory, explanation, txn_hash),
        )
    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["init", "import", "check-import", "summary", "uncategorized", "mark-fixed"])
    parser.add_argument("--db", required=True, help="Path to the SQLite file, e.g. finance-data/finance.db")
    parser.add_argument("--data-dir", help="Directory to seed category_rules.json into (defaults to --db's parent)")
    parser.add_argument("--transactions", help="Path to categorized transactions JSON (for import)")
    parser.add_argument("--source-file", help="Original statement file path, used for import dedup + check-import")
    parser.add_argument("--rules", help="Path to category_rules.json (for mark-fixed)")
    parser.add_argument("--match", help="Merchant/description substring to mark, e.g. 'NETFLIX' (for mark-fixed)")
    parser.add_argument("--fixed", choices=["true", "false"], help="Whether the match is a fixed expense (for mark-fixed)")
    args = parser.parse_args()

    data_dir = args.data_dir or str(Path(args.db).parent)

    if args.command == "init":
        result = init_db(args.db, data_dir)
    elif args.command == "check-import":
        result = already_imported(args.db, args.source_file)
    elif args.command == "import":
        with open(args.transactions, encoding="utf-8") as f:
            data = json.load(f)
        transactions = data["transactions"] if isinstance(data, dict) else data
        result = import_transactions(args.db, transactions, args.source_file)
    elif args.command == "summary":
        result = monthly_summary(args.db)
    elif args.command == "uncategorized":
        result = uncategorized(args.db)
    elif args.command == "mark-fixed":
        if not args.match or args.fixed is None:
            parser.error("mark-fixed requires --match and --fixed true|false")
        result = mark_fixed(args.db, args.rules, args.match, args.fixed == "true")
    else:
        parser.error("unknown command")
        return

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
