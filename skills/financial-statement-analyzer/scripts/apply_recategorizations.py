#!/usr/bin/env python3
"""Apply a batch of recategorizations exported from the dashboard's category
drill-down UI.

The dashboard (dashboard.html) is a static, offline file with no server and
no write access to the database -- by design, so it stays safe to open
straight from disk (see privacy_guidelines.md). When the user recategorizes
transactions in the dashboard UI, it stages the edits client-side and lets
them download a small JSON file (default name: recategorizations.json,
usually landing in their Downloads folder) instead of writing anything
itself. This script is the other half of that loop: it reads that file and
actually applies each change to the local database via store.py's
set_category(), the same function the CLI's set-category command uses.

Usage:
    python3 apply_recategorizations.py --db finance-data/finance.db --rules finance-data/category_rules.json --file ~/Downloads/recategorizations.json

Each entry in the JSON file looks like:
    {"scope": "merchant", "match": "IFOOD", "category": "Alimentacao", "subcategory": "Delivery", "flow": "expense"}
or:
    {"scope": "transaction", "txn_hash": "...", "category": "Compras", "subcategory": "Presentes", "flow": "expense"}

"merchant" scope (the default the dashboard produces) updates every
transaction matching that text and teaches the rule file, exactly like
`store.py set-category --match ...`. "transaction" scope touches only that
one row, for a genuine one-off that shouldn't reclassify the whole merchant.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import set_category  # noqa: E402


def apply_all(db_path, rules_path, changes):
    results = []
    for change in changes:
        scope = change.get("scope", "merchant")
        kwargs = dict(
            category=change["category"],
            subcategory=change.get("subcategory", ""),
            explanation=change.get("explanation", ""),
            flow=change.get("flow", "expense"),
            is_fixed=change.get("is_fixed"),
        )
        if scope == "transaction":
            kwargs["txn_hash"] = change["txn_hash"]
        else:
            kwargs["match_text"] = change["match"]
        result = set_category(db_path, rules_path, **kwargs)
        results.append({"input": change, "result": result})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True)
    parser.add_argument("--rules", required=True)
    parser.add_argument("--file", required=True, help="Path to the recategorizations.json downloaded from the dashboard")
    args = parser.parse_args()

    with open(args.file, encoding="utf-8") as f:
        changes = json.load(f)

    results = apply_all(args.db, args.rules, changes)
    total_updated = sum(r["result"]["updated_transactions"] for r in results)
    json.dump({"applied": len(results), "transactions_updated": total_updated, "details": results},
               sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
