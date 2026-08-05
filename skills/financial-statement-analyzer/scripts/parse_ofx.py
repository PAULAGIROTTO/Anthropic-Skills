#!/usr/bin/env python3
"""Parse OFX 1.x (SGML) and OFX 2.x (XML) bank/credit-card/investment statements
into a canonical list of transaction dicts.

Works entirely offline against a local file -- it never makes a network call.
Handles the loose SGML dialect most banks still export (unclosed tags, no XML
declaration) as well as proper OFX 2.x XML.

Usage:
    python3 parse_ofx.py statement.ofx [--mask-account]

Prints a JSON array of transactions to stdout. Import as a module to get the
`parse_ofx(path)` function directly.
"""
import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Only auto-close *leaf* tags, i.e. lines shaped "<TAG>value" with real content.
# Container tags (e.g. "<STATUS>" with nested children on following lines) must
# already carry an explicit closing tag per the OFX SGML spec -- self-closing
# them here would truncate their children.
CLOSE_TAG_RE = re.compile(r"<([A-Za-z0-9_./]+)>([^<\r\n]+)\r?\n")

# Elements that hold one transaction each, across bank / credit-card / investment statements.
TRANSACTION_TAGS = ("STMTTRN", "INVBANKTRAN")
INVESTMENT_TRANSACTION_TAGS = (
    "BUYSTOCK", "SELLSTOCK", "BUYMF", "SELLMF", "BUYOPT", "SELLOPT",
    "BUYOTHER", "SELLOTHER", "BUYDEBT", "SELLDEBT", "INCOME", "REINVEST",
    "TRANSFER", "CLOSUREOPT",
)


def _detect_encoding(raw: bytes) -> str:
    header = raw[:400].decode("ascii", errors="ignore")
    m = re.search(r"CHARSET:\s*(\S+)", header)
    if m:
        charset = m.group(1).strip().upper()
        if "1252" in charset:
            return "cp1252"
        if "8859" in charset or "LATIN" in charset:
            return "latin-1"
    if b"UTF-8" in raw[:200].upper():
        return "utf-8"
    # Most Brazilian bank exports are Latin-1/CP1252 even when unlabeled.
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def _sgml_to_xml(text: str) -> str:
    """Close unclosed leaf tags so ElementTree can parse the SGML dialect."""
    # Strip the plain-text OFX header block (everything before the first '<').
    start = text.find("<")
    body = text[start:] if start != -1 else text
    return CLOSE_TAG_RE.sub(r"<\1>\2</\1>\n", body)


def _load_tree(path: Path) -> ET.Element:
    raw = path.read_bytes()
    encoding = _detect_encoding(raw)
    text = raw.decode(encoding, errors="replace")
    if text.lstrip().startswith("<?xml"):
        xml_text = text
    else:
        xml_text = _sgml_to_xml(text)
    # Some servers emit a bare ampersand or other invalid XML entities; escape defensively.
    xml_text = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#)", "&amp;", xml_text)
    return ET.fromstring(xml_text)


def _text(el, tag):
    child = el.find(tag)
    return child.text.strip() if child is not None and child.text else None


def _parse_date(value):
    if not value:
        return None
    # OFX dates: YYYYMMDD or YYYYMMDDHHMMSS[.xxx][tz]
    digits = re.match(r"(\d{4})(\d{2})(\d{2})", value)
    if not digits:
        return value
    y, mo, d = digits.groups()
    return f"{y}-{mo}-{d}"


def _mask(acct_id, do_mask):
    if not acct_id:
        return acct_id
    return f"***{acct_id[-4:]}" if do_mask and len(acct_id) > 4 else acct_id


def _account_context(root, mask_account):
    """Find the account container (bank / credit-card / investment) and return
    (account_id, account_kind, currency)."""
    for kind, tag, id_tag in (
        ("checking_or_savings", "BANKACCTFROM", "ACCTID"),
        ("credit_card", "CCACCTFROM", "ACCTID"),
        ("investment", "INVACCTFROM", "ACCTID"),
    ):
        node = root.find(f".//{tag}")
        if node is not None:
            acct_id = _text(node, id_tag)
            bank_id = _text(node, "BANKID")
            currency = None
            stmt = root.find(".//CURDEF")
            if stmt is not None and stmt.text:
                currency = stmt.text.strip()
            return _mask(acct_id, mask_account), kind, bank_id, (currency or "BRL")
    return None, "unknown", None, "BRL"


def parse_ofx(path, mask_account=True):
    root = _load_tree(Path(path))
    account_id, account_kind, bank_id, currency = _account_context(root, mask_account)

    transactions = []

    for trn in root.iter():
        if trn.tag in TRANSACTION_TAGS:
            amount_raw = _text(trn, "TRNAMT")
            try:
                amount = float(amount_raw) if amount_raw is not None else None
            except ValueError:
                amount = None
            name = _text(trn, "NAME") or _text(trn, "PAYEE") or ""
            memo = _text(trn, "MEMO") or ""
            description = " - ".join(p for p in (name, memo) if p) or "(sem descricao)"
            date = _parse_date(_text(trn, "DTPOSTED"))
            fitid = _text(trn, "FITID")
            txn = {
                "date": date,
                "description": description,
                "amount": amount,
                "currency": currency,
                "account_id": account_id,
                "account_kind": account_kind,
                "bank_id": bank_id,
                "source_txn_id": fitid,
                "raw_type": _text(trn, "TRNTYPE"),
                "flow_hint": "investment" if account_kind == "investment" else None,
            }
            key = fitid or f"{date}|{amount}|{description}|{account_id}"
            txn["dedup_key"] = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
            transactions.append(txn)

        elif trn.tag in INVESTMENT_TRANSACTION_TAGS:
            invtran = trn.find(".//INVTRAN")
            date = _parse_date(_text(invtran, "DTTRADE")) if invtran is not None else None
            fitid = _text(invtran, "FITID") if invtran is not None else None
            units = _text(trn, "UNITS")
            unit_price = _text(trn, "UNITPRICE")
            total = _text(trn, "TOTAL")
            secid = trn.find(".//SECID")
            uniqueid = _text(secid, "UNIQUEID") if secid is not None else None
            try:
                amount = float(total) if total is not None else None
            except ValueError:
                amount = None
            description = f"{trn.tag} {uniqueid or ''} qty={units or '?'} @ {unit_price or '?'}".strip()
            txn = {
                "date": date,
                "description": description,
                "amount": amount,
                "currency": currency,
                "account_id": account_id,
                "account_kind": "investment",
                "bank_id": bank_id,
                "source_txn_id": fitid,
                "raw_type": trn.tag,
                "flow_hint": "investment",
            }
            key = fitid or f"{date}|{amount}|{description}|{account_id}"
            txn["dedup_key"] = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
            transactions.append(txn)

    return {
        "account_id": account_id,
        "account_kind": account_kind,
        "bank_id": bank_id,
        "currency": currency,
        "transactions": transactions,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--no-mask-account", action="store_true",
                         help="Keep full account number instead of masking to last 4 digits")
    args = parser.parse_args()

    result = parse_ofx(args.path, mask_account=not args.no_mask_account)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
