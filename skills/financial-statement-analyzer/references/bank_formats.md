# Statement format notes

## OFX (bank, credit card, and investment accounts)

`scripts/parse_ofx.py` handles both dialects transparently:

- **OFX 1.x (SGML)** -- what most banks still export. Plain-text header
  block (`OFXHEADER:100` ...), then loosely-closed tags. Leaf tags like
  `<NAME>` are often left unclosed (valid per the OFX SGML spec: only
  *aggregate* elements with children are required to carry an explicit
  closing tag). The parser exploits exactly that rule: it only
  auto-closes a tag when the same line carries real text content, and
  leaves already-explicit container tags (`<STMTTRN>...</STMTTRN>`,
  `<STATUS>...</STATUS>`, etc.) alone. If a new bank's export breaks this
  (rare, but happens with older mainframe-generated files), the symptom is
  an `xml.etree.ElementTree.ParseError` -- open the raw file and check
  whether some aggregate tag is missing its closing tag; patch it or add a
  regex fixup rather than reaching for a heavier dependency.
- **OFX 2.x (XML)** -- proper XML with an `<?xml ...?>` declaration.
  Parsed as-is, no fixup needed.
- **Encoding** -- Brazilian bank exports are frequently `CP1252`/`Latin-1`
  even when the header claims otherwise. The parser sniffs the `CHARSET`
  header and falls back to Latin-1 if UTF-8 decoding fails.
- **Account type detection** -- the parser looks for `BANKACCTFROM`
  (checking/savings), `CCACCTFROM` (credit card), or `INVACCTFROM`
  (brokerage/investment) to tag the whole file's transactions with an
  `account_kind`, since sign conventions and categorization differ by kind
  (see below).
- **Investment statements** -- transactions live inside `BUYSTOCK`,
  `SELLSTOCK`, `BUYMF`, `SELLMF`, `INCOME` (dividends/JCP), `REINVEST`,
  etc., each wrapping an `INVTRAN` with the trade date and an amount in
  `TOTAL`. These are already tagged `flow_hint: investment` by the parser
  so the categorizer routes them to the Investimentos bucket regardless of
  merchant-name rules.

### Sign conventions to double check per bank

- **Checking/savings accounts**: negative `TRNAMT` = money out (expense),
  positive = money in (income). This is the OFX standard and holds for
  essentially every bank.
- **Credit card OFX (`CCSTMTRS`)**: the same negative-out/positive-in
  convention is *supposed* to hold, but some card issuers export purchases
  as positive amounts (a charge increasing what you owe) and
  payments/refunds as negative -- the opposite of a checking account.
  `parse_ofx.py` auto-corrects this using `TRNTYPE` rather than trusting
  the raw sign: `DEBIT`/`POS` are forced negative (a purchase is always
  money leaving the account) and `CREDIT` is forced positive (a payment or
  refund is always money coming back), regardless of what sign the file
  originally used. This is intentionally narrow -- only those two
  unambiguous types get corrected, so a checking account file that already
  has correct signs is left untouched. If you ever see a credit card
  import where every purchase looks like "income," check `raw_type` in the
  parsed output; a `TRNTYPE` the corrector doesn't recognize (e.g. a
  nonstandard value some issuer invented) can still slip through and needs
  a one-off fix.
- When in doubt, check the statement's printed total against the sum of
  parsed transactions before importing -- a sign error shows up
  immediately as a wildly wrong total.

## Credit card statements in PDF

There's no universal library for this -- every bank/card issuer lays out
its PDF differently. The reliable approach, using the `pdf` skill's tools
(`pypdf` for text, `pdfplumber` for tables) as a base:

1. Try `pdfplumber`'s `page.extract_tables()` first. Many issuers render
   the transaction list as an actual PDF table, which extracts cleanly
   into rows of `[date, description, amount]`.
2. If that returns nothing useful, fall back to `page.extract_text()` and
   parse line by line with a regex tuned to the statement's date/amount
   format. Two common shapes to expect:
   - Brazilian: `DD/MM  DESCRICAO ...  1.234,56` (comma decimal, dot
     thousands separator, no currency symbol on each line).
   - US: `MM/DD  DESCRIPTION ...  $1,234.56`.
3. **Always sanity-check the extraction** against the statement's own
   printed subtotal/total before importing -- sum the parsed amounts and
   compare. PDF text extraction silently drops or merges lines far more
   often than OFX parsing does, and a totals mismatch is the cheapest way
   to catch it before bad data goes into the database.
4. Credit card PDF statements list purchases as positive numbers (amount
   charged). There's no `TRNTYPE` to lean on here like there is for OFX, so
   when building the canonical transaction JSON, store purchases as
   **negative** amounts to match the negative-out/positive-in convention
   the rest of the pipeline assumes (`categorize.py` and
   `build_dashboard.py` both compute spend as `-amount`) -- don't keep the
   PDF's own positive-for-a-charge display convention. Do not import the
   "payment received" line at all as a separate expense or as income; it's
   the same lump-sum bill payment described in the reconciliation section
   below, and `categorize.py`'s `CREDIT_CARD_PAYMENT_KEYWORDS` will catch
   it and tag it as a transfer as long as the description contains
   recognizable phrasing (add a new keyword if a particular issuer's
   wording doesn't match anything in the list).
5. Multi-currency cards (common on Brazilian cards used abroad) sometimes
   print both the foreign-currency amount and the converted local-currency
   amount on the same line -- use the local-currency (settlement) amount
   for the dashboard, and note the original currency/amount in the
   transaction's explanation field if it's easily extractable.

## Investment / brokerage statements

Brazilian brokers (B3-connected corretoras) typically export either OFX
(`INVSTMTRS`, handled above) or a PDF "nota de negociação" / extrato de
custódia. For PDF investment statements, extract:
- Date, operation type (compra/venda/aplicação/resgate/dividendo/JCP),
  asset ticker or fund name, quantity, unit price, and net amount.
- Treat contributions (aplicação/compra) as positive amounts flowing into
  `Investimentos`, and redemptions (resgate/venda) as reducing the
  invested balance -- don't count a redemption as "income" even though
  money moves back into a checking account, since it's just relocating
  capital already tracked as invested. If the redemption includes
  investment income (juros, rendimento, dividendos), split that portion
  into the income flow if the statement breaks it out; otherwise keep the
  whole amount in Investimentos and note the ambiguity in the explanation
  field.

## Reconciling checking account and credit card statements

The most common way to accidentally inflate a user's spending: import the
card's itemized statement (each purchase, correctly categorized) *and* the
checking account statement that includes the lump-sum payment of that same
bill, and count both as expenses. That payment isn't new spending -- it's
just settling debt for spending that was already counted line-by-line on
the card.

`categorize.py`'s `CREDIT_CARD_PAYMENT_KEYWORDS` handles the common
phrasing on both sides of this automatically, tagging matches as
`flow: transfer`, `category: "Transferencia interna"`,
`subcategory: "Pagamento de fatura de cartao"` (excluded from expense/income
totals just like an inter-account transfer):

- From the checking account side: "PAGAMENTO CARTAO", "PAGAMENTO DE
  FATURA", "PGTO FATURA", "PIX FATURA CARTAO," etc.
- From the card statement's own side (a line that reduces what you owe):
  "PAGAMENTO RECEBIDO," "OBRIGADO PELO PAGAMENTO," "AUTOMATIC PAYMENT,"
  "PAYMENT THANK YOU."

If a bank uses phrasing that doesn't match anything in that list, add it --
the keywords are deliberately specific (pairing "pagamento/pgto" with
"cartao/fatura", or matching exact bank boilerplate) to avoid accidentally
sweeping in a legitimate purchase whose description happens to contain
"pagamento."

**This only produces correct totals if both sides eventually get
imported.** Excluding the lump-sum payment as a transfer is only right
*because* the itemized purchases are (or will be) counted separately from
the card's own statement. If only the checking account side ever gets
imported, the exclusion makes that spending disappear from the dashboard
entirely -- silently under-counting instead of double-counting.
`store.py import` guards against exactly this: it checks whether the
database has any `credit_card`-kind transactions at all, and if a
bill-payment transfer was just excluded with none present, returns a
`warnings` entry saying so. Treat that warning as a to-do, not a footnote --
ask the user for the corresponding card statement and import it.

## Multiple accounts, multiple banks

Nothing about the schema assumes a single bank. Every transaction record
carries its own `account_id` (masked to the last 4 digits by default) and
`account_kind`, and `store.py` dedups per file + per transaction, so
importing OFX files from five different banks and two credit cards into
the same `finance.db` is the expected use case, not an edge case.
