---
name: financial-statement-analyzer
description: >
  Parses personal bank statements (OFX, from any bank), credit card statements (PDF), and investment/brokerage statements (OFX/PDF/CSV), categorizes every transaction into detailed expense/income/investment categories, and maintains a local, offline, incrementally-updated financial dashboard across months. Use this skill whenever the user wants to import or analyze bank/credit-card/investment statements, categorize their spending, track expenses vs income vs investments over time, or build/update a personal finance dashboard -- including phrases like "extrato", "fatura do cartão", "extrato de investimentos", "quanto eu gastei", "organizar minhas finanças", or "dashboard financeiro". This handles highly sensitive personal financial data, so it must run entirely locally and must never publish, upload, or transmit any transaction data to the web -- read the Privacy rules section before doing anything else.
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
| `scripts/store.py` | Init the local DB, dedup + persist transactions, query summaries, mark expenses fixed/variable, manually set a category |
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
   Anything with `needs_review: true` needs a human-readable answer to "what
   is this and where does it belong" before it gets imported as-is. Work
   through it in this order, and don't stop at step (a) just because it's
   the cheapest one:

   a. **Recognize it yourself first.** Plenty of unmatched merchants are
      obvious from the raw description (a slightly different spelling of a
      chain already in the rules, a CNPJ suffix, an abbreviation) -- no
      search needed.
   b. **Research harder before giving up.** If the merchant genuinely isn't
      recognizable, do a *generalized* web search (per the privacy rules
      above -- merchant name only, never amounts/dates/account info). Don't
      settle for one query that comes back empty: try the name as-is, try
      it without trailing store/location codes, try it alongside "empresa"
      or "CNPJ" if one is present in the description. The goal is a real
      answer often enough that "Não classificado" is the exception, not the
      default landing spot for anything unfamiliar.
   c. **Ask the user when research still comes up empty or ambiguous.**
      List the remaining unclear transactions (date, description, amount --
      `scripts/store.py uncategorized` gives you this list straight from
      the database for anything already imported) and ask the user to
      classify them. This is the normal, expected path for one-off local
      merchants, informal transfers, or anything a web search can't
      identify -- it is not a fallback to be embarrassed about.
   d. **Persist whatever you land on** so it never has to be asked again --
      see "Manually classifying a transaction" below. Never force a guess
      into an existing category just to clear the review queue: a
      transaction still sitting in "Não classificado" with its raw
      description intact is more useful than a confidently wrong label,
      and the dashboard treats it as an honest, visible bucket rather than
      hiding it.

4. **Import into the database** (dedups automatically, both at the
   file level and the individual-transaction level via OFX `FITID` or a
   content hash):
   ```bash
   python3 scripts/store.py import --db finance-data/finance.db --transactions /tmp/txns_categorized.json --source-file path/to/statement.ofx
   ```
   Check the `warnings` field in the result -- see "Reconciling credit card
   statements" below for the most common one.

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

### Marking an expense as fixed or variable

Beyond category, expenses also carry an independent `is_fixed` flag: fixed
means a recurring, contractually-committed cost (rent, utilities,
subscriptions, insurance); variable means it fluctuates or is discretionary
(groceries, restaurants, shopping). This split is what lets the dashboard
answer "how much am I actually committed to spending every month, versus
how much is up to me." The default rules already set this for common,
unambiguous cases (see `assets/default_category_rules.json`), but plenty of
transactions are ambiguous until the user says otherwise -- a gym
membership might be fixed for one person and a pay-per-visit variable cost
for another.

When the user says something like "o aluguel é um gasto fixo" or "a
academia não é fixa, eu pago por sessão," don't just edit that one
transaction -- teach the skill the merchant so every past and future
transaction from it is tagged consistently:

```bash
python3 scripts/store.py mark-fixed --db finance-data/finance.db --rules finance-data/category_rules.json --match "ALUGUEL" --fixed true
```

`--match` is matched the same accent/case-insensitive way categorization
works, against transaction descriptions already in the database. This
updates every matching transaction retroactively and also updates (or
creates) the corresponding rule in `category_rules.json` with a `fixed`
field, so every future import of that merchant is tagged automatically --
the user should only ever have to say this once per merchant. Rebuild the
dashboard afterward so the "Gastos fixos vs variáveis" chart picks up the
change. Transactions nobody has classified yet show up in the dashboard as
an explicit "ainda não classificado" slice rather than being guessed into
fixed or variable -- treat that the same way as "Não classificado" for
category: an honest unknown beats a wrong guess.

### Manually classifying a transaction

When automated rules and research (step 3 above) can't resolve a
transaction, or the user simply disagrees with a category, fix it with
`set-category` -- it works exactly like `mark-fixed`: one correction
updates every matching transaction already in the database *and* teaches
the rule file, so it's genuinely a one-time fix per merchant, not a
per-transaction chore repeated every month.

```bash
python3 scripts/store.py set-category --db finance-data/finance.db --rules finance-data/category_rules.json \
  --match "LOJA DO SEU JOAO" --category "Compras" --subcategory "Armarinho e miudezas" \
  --explanation "Loja de bairro, confirmado pelo usuario" --flow expense
```

`--match` uses the same accent/case-insensitive substring matching as
`mark-fixed`. Omit `--subcategory`/`--explanation` if there's nothing
useful to add. Use `--flow transfer` for things like a P2P payment to a
friend that should stay out of the income/expense totals entirely. Rebuild
the dashboard afterward.

### Reconciling credit card statements with the checking account (avoid double-counting)

A credit card bill payment shows up in *two* places if you're not careful:
once as the individual purchases on the card's own statement, and again as
one lump-sum payment on the checking account that pays that bill. Counting
both would inflate spending by roughly 2x for anyone who pays their card in
full each month. `categorize.py` already detects common bill-payment
phrasing (`PAGAMENTO CARTAO`, `PAGAMENTO DE FATURA`, and the card
statement's own "payment received" line) on either side and tags it as an
internal transfer, excluded from expense/income totals -- so as long as you
import **both** the checking account statement and the card's own itemized
statement for the same period, the math works out with nothing double
counted and nothing missing.

The failure mode to watch for is importing *only* the checking account
side: the lump-sum payment gets correctly excluded as a transfer, but if
the card's itemized statement was never imported, that spending vanishes
from the dashboard entirely instead of being double-counted -- silently
wrong in the other direction. `store.py import` catches this for you: when
a bill-payment transfer is detected and the database has no `credit_card`
account transactions in it at all yet, the `warnings` field in the import
result says so explicitly. Always surface that warning to the user and ask
for the corresponding card statement -- don't just note it and move on.

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
`finance.db` is the normal case. `parse_ofx.py` auto-corrects sign
convention for OFX files using `TRNTYPE` (some card issuers export
purchases as positive amounts, which would otherwise silently break the
expense totals) -- see `references/bank_formats.md` for the details, and
for how to handle sign correctly when extracting from a PDF, where there's
no `TRNTYPE` to lean on and it has to be done by hand.

## Reference files

- `references/category_taxonomy.md` -- the full expense/income/investment
  category list, why "Não classificado" is a first-class outcome, and how
  to extend the taxonomy consistently.
- `references/bank_formats.md` -- OFX SGML/XML parsing quirks, sign
  conventions per account type, and PDF statement extraction patterns.
- `references/privacy_guidelines.md` -- exactly what may and may not touch
  the network, with concrete good/bad query examples.
