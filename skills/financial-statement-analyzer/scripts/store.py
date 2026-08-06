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
    card_payment_total = 0.0
    account_id = None
    for txn in transactions:
        account_id = txn.get("account_id") or account_id
        if txn.get("matched_rule") == "builtin:credit_card_payment":
            card_payment_total += abs(txn.get("amount") or 0.0)
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

    warnings = []
    if card_payment_total > 0:
        has_card_statement = conn.execute(
            "SELECT 1 FROM transactions WHERE account_kind = 'credit_card' LIMIT 1"
        ).fetchone()
        if not has_card_statement:
            warnings.append(
                f"This import excluded ~R$ {card_payment_total:.2f} in credit card bill payment(s) from "
                "expense totals (treated as a transfer, since the underlying purchases belong on the card's "
                "own statement). No credit card statement has been imported into this database yet, so those "
                "purchases currently aren't showing up anywhere -- import the corresponding card statement(s) "
                "(PDF or OFX) so that spending is captured with real categories."
            )
    conn.commit()
    conn.close()
    return {"inserted": inserted, "duplicates": duplicates, "skipped_file": False, "warnings": warnings}


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
        """SELECT txn_hash, date, description, amount, account_id, account_kind
           FROM transactions WHERE category = 'Nao classificado' ORDER BY date"""
    ).fetchall()
    conn.close()
    return [
        {"txn_hash": r[0], "date": r[1], "description": r[2], "amount": r[3],
         "account_id": r[4], "account_kind": r[5]}
        for r in rows
    ]


def _matching_transactions(conn, match_text):
    norm_match = normalize(match_text)
    rows = conn.execute("SELECT txn_hash, description, category, subcategory FROM transactions").fetchall()
    return [r for r in rows if norm_match in normalize(r[1]) or normalize(r[1]) in norm_match]


def _find_or_create_rule(rules_data, match_text, fallback_category="Nao classificado", fallback_subcategory=""):
    """Return (rule_dict, action) where action is 'updated' or 'created'. Mutates
    rules_data in place -- caller is responsible for writing it back to disk.
    Matching a rule to a free-text merchant string is necessarily fuzzy (rules
    use short substrings like "IFOOD", user input might be "ifood" or "o ifood
    da sexta"), so we match in both directions on the normalized text.

    Deliberately skips regex rules even when one would technically match: the
    seed rules group several unrelated merchants under one shared regex (e.g.
    NETFLIX|SPOTIFY|DISNEY PLUS all under one "Streaming" rule), and editing
    that shared rule because the user corrected just one of them would
    silently reclassify the others too. Creating a new, more specific
    "contains" rule instead -- inserted at the front, so first-match-wins
    puts it ahead of the broader regex -- overrides only the merchant the
    user actually corrected, leaving its former rule-mates alone.
    """
    norm_match = normalize(match_text)
    for rule in rules_data.setdefault("rules", []):
        if rule.get("type", "contains") == "regex":
            continue
        pattern_norm = normalize(rule["pattern"])
        if pattern_norm in norm_match or norm_match in pattern_norm:
            return rule, "updated"

    new_id = "user:" + normalize(match_text).lower().replace(" ", "_")[:40]
    new_rule = {
        "id": new_id,
        "pattern": match_text,
        "type": "contains",
        "flow": "expense",
        "category": fallback_category,
        "subcategory": fallback_subcategory,
        "note": "",
    }
    rules_data["rules"].insert(0, new_rule)
    return new_rule, "created"


def mark_fixed(db_path, rules_path, match_text, is_fixed):
    """Mark every transaction whose description matches `match_text` (accent- and
    case-insensitive substring, in either direction) as a fixed or variable
    expense, and remember it in the rules file so future imports of the same
    merchant are tagged automatically without asking again.

    This is what backs "avisa a skill que esse gasto e fixo" -- one correction
    from the user should stick for that merchant going forward, not just for
    the one transaction they happened to be looking at.
    """
    conn = _connect(db_path)
    matched = _matching_transactions(conn, match_text)
    for txn_hash, _desc, _cat, _sub in matched:
        conn.execute("UPDATE transactions SET is_fixed = ? WHERE txn_hash = ?", (int(bool(is_fixed)), txn_hash))
    conn.commit()
    conn.close()

    rule_action = "not_found_no_rules_path"
    rule_id = None
    if rules_path:
        rules_data = load_rules(rules_path) if Path(rules_path).exists() else {"rules": []}
        inferred_category = matched[0][2] if matched else "Nao classificado"
        inferred_subcategory = matched[0][3] if matched else ""
        rule, rule_action = _find_or_create_rule(rules_data, match_text, inferred_category, inferred_subcategory)
        rule["fixed"] = bool(is_fixed)
        rule_id = rule.get("id", rule["pattern"])
        with open(rules_path, "w", encoding="utf-8") as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)

    return {
        "updated_transactions": len(matched),
        "is_fixed": bool(is_fixed),
        "rule_id": rule_id,
        "rule_action": rule_action,
    }


def set_category(db_path, rules_path, category, subcategory="", explanation="", flow="expense", is_fixed=None,
                  match_text=None, txn_hash=None):
    """Manually classify transactions and (usually) remember the merchant ->
    category mapping in the rules file, the same way mark_fixed() remembers
    fixed/variable. This is the path for transactions the automatic rules and
    generalized web research couldn't resolve on their own: the user (or
    Claude, after researching what the merchant actually is) makes the call
    once, and it applies retroactively plus to every future import.

    Pass exactly one of:
    - `match_text`: merchant-wide -- every transaction whose description
      matches (accent/case-insensitive substring, either direction) gets
      updated, and the rules file is taught this merchant permanently. This
      is the default and normal case.
    - `txn_hash`: a single specific transaction only. No rule is written --
      this is for a genuine one-off (e.g. a supermarket trip that happened to
      include a one-time gift purchase) that shouldn't reclassify every other
      transaction from the same merchant.
    """
    if bool(match_text) == bool(txn_hash):
        raise ValueError("set_category requires exactly one of match_text or txn_hash")

    conn = _connect(db_path)
    if txn_hash:
        row = conn.execute(
            "SELECT txn_hash, description, category, subcategory FROM transactions WHERE txn_hash = ?", (txn_hash,)
        ).fetchone()
        matched = [row] if row else []
    else:
        matched = _matching_transactions(conn, match_text)

    for row_hash, _desc, _cat, _sub in matched:
        if is_fixed is None:
            conn.execute(
                "UPDATE transactions SET category=?, subcategory=?, explanation=?, flow=? WHERE txn_hash=?",
                (category, subcategory, explanation, flow, row_hash),
            )
        else:
            conn.execute(
                "UPDATE transactions SET category=?, subcategory=?, explanation=?, flow=?, is_fixed=? WHERE txn_hash=?",
                (category, subcategory, explanation, flow, int(bool(is_fixed)), row_hash),
            )
    conn.commit()
    conn.close()

    rule_action = "skipped_single_transaction"
    rule_id = None
    if match_text and rules_path:
        rules_data = load_rules(rules_path) if Path(rules_path).exists() else {"rules": []}
        rule, rule_action = _find_or_create_rule(rules_data, match_text, category, subcategory)
        rule.update({"category": category, "subcategory": subcategory, "flow": flow})
        if explanation:
            rule["note"] = explanation
        if is_fixed is not None:
            rule["fixed"] = bool(is_fixed)
        rule_id = rule.get("id", rule["pattern"])
        with open(rules_path, "w", encoding="utf-8") as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)
    elif match_text and not rules_path:
        rule_action = "not_found_no_rules_path"

    return {
        "updated_transactions": len(matched),
        "category": category,
        "subcategory": subcategory,
        "rule_id": rule_id,
        "rule_action": rule_action,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=[
        "init", "import", "check-import", "summary", "uncategorized", "mark-fixed", "set-category",
    ])
    parser.add_argument("--db", required=True, help="Path to the SQLite file, e.g. finance-data/finance.db")
    parser.add_argument("--data-dir", help="Directory to seed category_rules.json into (defaults to --db's parent)")
    parser.add_argument("--transactions", help="Path to categorized transactions JSON (for import)")
    parser.add_argument("--source-file", help="Original statement file path, used for import dedup + check-import")
    parser.add_argument("--rules", help="Path to category_rules.json (for mark-fixed / set-category)")
    parser.add_argument("--match", help="Merchant/description substring to target, e.g. 'NETFLIX' (for mark-fixed / set-category)")
    parser.add_argument("--txn-hash", help="Target exactly one transaction by its txn_hash instead of --match (for set-category only)")
    parser.add_argument("--fixed", choices=["true", "false"], help="Whether the match is a fixed expense (for mark-fixed / optionally set-category)")
    parser.add_argument("--category", help="Category to assign, e.g. 'Alimentacao' (for set-category)")
    parser.add_argument("--subcategory", default="", help="Subcategory to assign, e.g. 'Delivery' (for set-category)")
    parser.add_argument("--flow", default="expense", choices=["expense", "income", "investment", "transfer"],
                         help="Flow to assign (for set-category, default expense)")
    parser.add_argument("--explanation", default="", help="Short explanation of what the merchant/transaction is (for set-category)")
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
    elif args.command == "set-category":
        if not args.category or bool(args.match) == bool(args.txn_hash):
            parser.error("set-category requires --category and exactly one of --match / --txn-hash")
        is_fixed = None if args.fixed is None else (args.fixed == "true")
        result = set_category(args.db, args.rules, args.category, args.subcategory, args.explanation,
                               args.flow, is_fixed, match_text=args.match, txn_hash=args.txn_hash)
    else:
        parser.error("unknown command")
        return

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
