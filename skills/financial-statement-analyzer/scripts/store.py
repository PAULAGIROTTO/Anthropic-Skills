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


def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
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
        try:
            conn.execute(
                """INSERT INTO transactions
                   (txn_hash, account_id, account_kind, date, posted_month, description,
                    amount, currency, flow, category, subcategory, explanation, source_file)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    dedup_key, txn.get("account_id"), txn.get("account_kind"), date, posted_month,
                    txn.get("description"), txn.get("amount"), txn.get("currency", "BRL"),
                    txn.get("flow"), txn.get("category"), txn.get("subcategory"),
                    txn.get("explanation"), str(source_file) if source_file else None,
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
    parser.add_argument("command", choices=["init", "import", "check-import", "summary", "uncategorized"])
    parser.add_argument("--db", required=True, help="Path to the SQLite file, e.g. finance-data/finance.db")
    parser.add_argument("--data-dir", help="Directory to seed category_rules.json into (defaults to --db's parent)")
    parser.add_argument("--transactions", help="Path to categorized transactions JSON (for import)")
    parser.add_argument("--source-file", help="Original statement file path, used for import dedup + check-import")
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
    else:
        parser.error("unknown command")
        return

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
