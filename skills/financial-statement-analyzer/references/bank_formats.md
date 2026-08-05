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
- **Credit card OFX (`CCSTMTRS`)**: purchases are usually *positive*
  amounts representing a charge to the card (increasing what you owe),
  and payments/refunds are negative. This is the opposite convention from
  a checking account. If a credit card import shows "income" for every
  purchase and "expenses" for the payment, the sign is flipped -- treat
  every non-negative amount in a `credit_card` account as an expense
  before applying category rules, and treat payments to the card
  (negative, matching "PAGAMENTO" in the description) as a transfer, not
  income, since it's just moving money you already counted as an expense
  when it was charged.
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
   charged); treat all of them as expenses. Do not import the "payment
   received" line as income -- it's a transfer that pays down what was
   already counted as an expense when the purchase happened.
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

## Multiple accounts, multiple banks

Nothing about the schema assumes a single bank. Every transaction record
carries its own `account_id` (masked to the last 4 digits by default) and
`account_kind`, and `store.py` dedups per file + per transaction, so
importing OFX files from five different banks and two credit cards into
the same `finance.db` is the expected use case, not an edge case.
