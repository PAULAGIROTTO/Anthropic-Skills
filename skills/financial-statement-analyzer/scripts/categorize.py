#!/usr/bin/env python3
"""Rule-based categorizer for financial transactions.

Design goals:
- Runs 100% locally against a JSON rules file -- no network access, no
  external API calls. Safe to run on raw transaction descriptions.
- The rules file lives in the user's own data directory (not inside the
  skill package), so corrections and new merchants the user teaches it
  persist and improve across months.
- Falls back to an explicit "Nao classificado" bucket instead of guessing
  silently, so nothing gets miscategorized without a trace.

Usage:
    python3 categorize.py --rules rules.json --transactions txns.json

`txns.json` is the JSON produced by parse_ofx.py / parse_pdf_statement.py
(a list of transaction dicts, or {"transactions": [...]}))
Prints the same transactions annotated with flow/category/subcategory.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

TRANSFER_KEYWORDS = (
    "transferencia entre contas", "transf entre contas", "mesma titularidade",
    "mesmo titular", "aplicacao automatica", "resgate automatico",
)

# Lines that represent paying off (or the card issuer receiving payment for) a
# credit card bill -- from a checking account statement ("PAGAMENTO CARTAO...")
# or from inside the card's own statement ("PAGAMENTO RECEBIDO", "AUTOMATIC
# PAYMENT - THANK YOU"). These must NOT be counted as a second expense: the
# real spending was already captured line-by-line when the card statement's
# individual purchases were imported. Counting the lump-sum payment too would
# double the user's apparent spending. Keep these phrases specific (combining
# "pagamento/pgto" with "cartao/fatura", or exact bank boilerplate) so a
# legitimate purchase whose description happens to contain "pagamento" isn't
# swept in by accident.
CREDIT_CARD_PAYMENT_KEYWORDS = (
    "pagamento cartao", "pagamento de fatura", "pagamento fatura cartao",
    "pgto cartao", "pgto fatura", "pagto fatura", "pagamento cartao de credito",
    "debito fatura cartao", "pix fatura cartao", "pagamento recebido",
    "obrigado pelo pagamento", "payment thank you", "automatic payment",
)


def strip_accents(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def normalize(text: str) -> str:
    return strip_accents(text or "").upper().strip()


def load_rules(rules_path):
    path = Path(rules_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Rules file not found: {rules_path}. Run init from store.py first "
            "to seed the default category rules into the user's data directory."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _rule_matches(rule, norm_desc):
    pattern = rule["pattern"]
    match_type = rule.get("type", "contains")
    if match_type == "regex":
        return re.search(pattern, norm_desc, re.IGNORECASE) is not None
    return normalize(pattern) in norm_desc


def categorize_one(txn, rules):
    """Return (flow, category, subcategory, note, matched_rule_id, is_fixed) for one transaction.

    is_fixed marks whether this is a recurring, contractually-committed expense
    (rent, utilities, subscriptions, insurance) versus a variable one (groceries,
    restaurants, discretionary shopping). It's None ("not yet determined") unless
    a rule explicitly sets it -- see mark_fixed() in store.py for how the user
    teaches the skill this per merchant, which is the normal way this gets set.
    """
    desc = txn.get("description", "")
    norm_desc = normalize(desc)
    amount = txn.get("amount") or 0.0
    account_kind = txn.get("account_kind", "checking_or_savings")

    # 1. Investment accounts: everything in them is investment flow by default,
    #    subclassified further by explicit investment rules below if they match.
    forced_flow = txn.get("flow_hint")

    # 2. Internal transfers between the user's own accounts should not count as
    #    income or expense -- they'd otherwise double-count money moving between
    #    a checking and a savings account, for example.
    for kw in TRANSFER_KEYWORDS:
        if normalize(kw) in norm_desc:
            return "transfer", "Transferencia interna", "Entre contas proprias", (
                "Movimentacao entre contas do mesmo titular; excluida dos totais "
                "de receita e despesa para nao distorcer o dashboard."
            ), "builtin:internal_transfer", None

    # 2b. Credit card bill payments (from either side: the checking account
    #    paying it, or the card statement's own "payment received" line) are a
    #    transfer, not a new expense -- the itemized purchases behind that
    #    payment should already be counted once, via the card statement import.
    for kw in CREDIT_CARD_PAYMENT_KEYWORDS:
        if normalize(kw) in norm_desc:
            return "transfer", "Transferencia interna", "Pagamento de fatura de cartao", (
                "Pagamento da fatura do cartao de credito. Os gastos que compoem essa "
                "fatura ja devem estar (ou precisam ser) importados individualmente a "
                "partir do extrato/PDF do cartao -- contar este valor tambem como "
                "despesa duplicaria o gasto."
            ), "builtin:credit_card_payment", None

    # 3. Walk user-editable rules in order; first match wins.
    for rule in rules.get("rules", []):
        if _rule_matches(rule, norm_desc):
            flow = forced_flow or rule.get("flow") or ("income" if amount > 0 else "expense")
            return (
                flow,
                rule.get("category", "Nao classificado"),
                rule.get("subcategory", ""),
                rule.get("note", ""),
                rule.get("id", rule["pattern"]),
                rule.get("fixed"),
            )

    # 4. No rule matched. Fall back to sign-based flow with an explicit
    #    "unclassified" bucket -- never invent a category with no evidence.
    if forced_flow == "investment":
        return "investment", "Investimentos", "Nao classificado", "", None, None
    if account_kind == "credit_card":
        return "expense", "Nao classificado", "", "", None, None
    flow = "income" if amount > 0 else "expense"
    return flow, "Nao classificado", "", "", None, None


def categorize_all(transactions, rules):
    out = []
    for txn in transactions:
        flow, category, subcategory, note, rule_id, is_fixed = categorize_one(txn, rules)
        enriched = dict(txn)
        enriched.update({
            "flow": flow,
            "category": category,
            "subcategory": subcategory,
            "explanation": note,
            "matched_rule": rule_id,
            "is_fixed": is_fixed,
            "needs_review": rule_id is None,
        })
        out.append(enriched)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", required=True)
    parser.add_argument("--transactions", required=True)
    args = parser.parse_args()

    rules = load_rules(args.rules)
    with open(args.transactions, encoding="utf-8") as f:
        data = json.load(f)
    transactions = data["transactions"] if isinstance(data, dict) else data

    result = categorize_all(transactions, rules)
    unresolved = [t for t in result if t["needs_review"]]

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
    if unresolved:
        print(f"\n{len(unresolved)} transaction(s) need manual review / a new rule.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
