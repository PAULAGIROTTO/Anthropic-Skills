---
name: financial-statement-analyzer
description: Parses personal bank statements (OFX, from any bank), credit card statements (PDF), and investment/brokerage statements (OFX/PDF/CSV), categorizes every transaction into detailed expense/income/investment categories, and maintains a local, offline, incrementally-updated financial dashboard across months. Use this skill whenever the user wants to import or analyze bank/credit-card/investment statements, categorize their spending, track expenses vs income vs investments over time, or build/update a personal finance dashboard -- including phrases like "extrato", "fatura do cartão", "extrato de investimentos", "quanto eu gastei", "organizar minhas finanças", or "dashboard financeiro". This handles highly sensitive personal financial data: it must run entirely locally and must never publish, upload, or transmit any transaction data to the web -- read the Privacy rules section before doing anything else.
---

# Financial Statement Analyzer

## Overview

This skill turns raw bank/credit-card/investment statements into a
categorized, queryable local database and a self-contained HTML dashboard
that accumulates history month over month. The user never has to re-import
a past month: every statement file and every transaction is deduplicated,
so each session only adds what's genuinely new, and the dashboard always
reflects the full history stored so far.

Four scripts in `scripts/` do the deterministic work; use them rather than
re-implementing parsing/storage/aggregation by hand:

| Script | Purpose |
|---|---|
| `scripts/parse_ofx.py` | Parse OFX 1.x/2.x (any bank) into canonical transactions |
| `scripts/categorize.py` | Apply the user's local rule file to tag flow/category/subcategory |
| `scripts/store.py` | Init the local DB, dedup + persist transactions, query summaries |
| `scripts/build_dashboard.py` | Regenerate the offline HTML dashboard from the full DB history |

PDF statements (credit card and some investment/brokerage statements) don't
have one universal parser -- use the `pdf` skill's tools (`pypdf`,
`pdfplumber`) to extract the transaction table or text, following the
patterns in `references/bank_formats.md`, then feed the resulting
transaction list through `categorize.py` and `store.py` the same way.

## Privacy rules -- read this before touching any file

This is personal financial data: account numbers, balances, salaries,
spending habits. The user has explicitly required that none of it leaves
this local environment. Concretely:

1. **Everything stays local.** Parsing, categorization, storage, and the
   dashboard all run on this machine against local files. Never send raw
   statement contents, parsed transactions, or the dashboard file to a web
   service, a hosting tool, an artifact-publishing tool, email, or any
   other connector.
2. **Never publish the dashboard as a hosted artifact/URL.** Even a
   "private" hosted link is a leak by definition -- it puts the data on a
   remote server. Always write `dashboard.html` to local disk and tell the
   user the file path so they can open it directly in their own browser
   (`file://...`). The dashboard itself is built to be fully self-contained
   (no CDN scripts, no network calls at all) specifically so it's safe to
   open offline.
3. **Web research is allowed only in generalized form.** The user does
   want good explanations of what a given expense or ticker is, even if
   that means a web search. But the query must never contain amounts,
   dates, account numbers, or the user's identity -- only the generic
   merchant/fund/ticker name (e.g. search "iFood empresa" not "iFood
   R$89,90 debit 03/07"). Full detail and examples are in
   `references/privacy_guidelines.md` -- read it before running any search
   tied to a transaction.
4. **Don't leave stray copies of sensitive data around.** Intermediate
   parsed-transaction JSON is fine as a temporary file while wiring parse
   -> categorize -> import together in one session, but the SQLite database
   is the durable source of truth -- don't scatter extra exports of raw
   transaction data into other directories.

## Data directory convention

All local state lives in one directory the user controls. Default to
`./finance-data/` in the current working directory unless the user already
has one set up or asks for a different location; once chosen, reuse the
same directory on every subsequent run (check for `finance-data/finance.db`
before asking again). Inside it:

```
finance-data/
├── finance.db            SQLite database -- all transactions + import history
├── category_rules.json   User-editable categorization rules (seeded on init)
└── dashboard.html         Generated dashboard (regenerate after every import)
```

## Workflow

### First-time setup (once per data directory)

```bash
python3 scripts/store.py init --db finance-data/finance.db
```

This creates the database and copies `assets/default_category_rules.json`
into `finance-data/category_rules.json` if it doesn't already exist. From
then on, edits to `category_rules.json` (new merchants, corrected
categories) persist and keep improving future imports.

### Importing a statement (repeat per file, every month)

1. **Check if it's already imported** (cheap, avoids duplicate work):
   ```bash
   python3 scripts/store.py check-import --db finance-data/finance.db --source-file path/to/statement.ofx
   ```
   If `already_imported` is true, skip straight to rebuilding the dashboard
   -- nothing new to do for this file.

2. **Parse** into canonical transactions:
   - OFX (any bank, checking/savings/credit-card/investment):
     ```bash
     python3 scripts/parse_ofx.py path/to/statement.ofx > /tmp/txns.json
     ```
   - PDF (credit card, or investment/brokerage statements without OFX):
     follow `references/bank_formats.md` to extract a transaction table
     with the `pdf` skill's tools, then shape the rows into the same
     canonical schema `parse_ofx.py` produces (`date`, `description`,
     `amount`, `currency`, `account_id`, `account_kind`, ...) and write
     them to JSON the same way. **Sanity-check the extracted total against
     the statement's printed total before moving on** -- PDF extraction is
     far more error-prone than OFX parsing.
   - CSV (some investment platforms export CSV): read it directly and map
     columns to the same canonical schema.

3. **Categorize:**
   ```bash
   python3 scripts/categorize.py --rules finance-data/category_rules.json --transactions /tmp/txns.json > /tmp/txns_categorized.json
   ```
   Review anything with `needs_review: true`. For real merchants you can
   identify, either recognize them from the description directly or -- per
   the privacy rules above -- do a *generalized* web search on just the
   merchant name, then add a new rule to `finance-data/category_rules.json`
   (see `references/category_taxonomy.md` for the category list and
   conventions) so future statements auto-categorize it too. Don't force a
   guess into an existing category just to clear the review queue --
   leaving something in "Não classificado" with the raw description intact
   is more useful than a wrong label.

4. **Import into the database** (dedups automatically, both at the
   file level and the individual-transaction level via OFX `FITID` or a
   content hash):
   ```bash
   python3 scripts/store.py import --db finance-data/finance.db --transactions /tmp/txns_categorized.json --source-file path/to/statement.ofx
   ```

5. Repeat steps 1-4 for every statement file the user has for that period
   (checking account, savings, each credit card, each brokerage) -- they
   all accumulate into the same `finance.db`.

### Rebuilding the dashboard

After importing anything new:
```bash
python3 scripts/build_dashboard.py --db finance-data/finance.db --out finance-data/dashboard.html
```
This reads the **entire** history in the database, not just what was just
imported, so old months are automatically still there. Tell the user the
local file path and that they can open it directly in a browser -- do not
publish it anywhere.

### Ongoing monthly use

Once a data directory exists, a typical session is just: user hands over
this month's new statement files -> steps above for each file -> rebuild
the dashboard -> done. Never ask the user to re-supply statements for
months already in `finance.db`; `check-import` and the per-transaction dedup
key exist precisely so that's never necessary.

## Handling multiple banks and account types

Nothing here assumes a single bank or a single account. Every transaction
carries its own `account_id` (masked to the last 4 digits by default) and
`account_kind` (checking_or_savings / credit_card / investment), and
storage dedups per source file and per transaction -- so importing OFX
files from five different banks plus two credit card PDFs into the same
`finance.db` is the normal case. See `references/bank_formats.md` for
sign-convention differences between account types (this matters a lot for
credit cards, where a positive amount is a *charge*, not income) and for
credit-card/investment PDF extraction guidance.

## Reference files

- `references/category_taxonomy.md` -- the full expense/income/investment
  category list, why "Não classificado" is a first-class outcome, and how
  to extend the taxonomy consistently.
- `references/bank_formats.md` -- OFX SGML/XML parsing quirks, sign
  conventions per account type, and PDF statement extraction patterns.
- `references/privacy_guidelines.md` -- exactly what may and may not touch
  the network, with concrete good/bad query examples.
