# Privacy rules for this skill

This skill exists to handle some of the most sensitive data a person has:
bank statements, credit card statements, and investment statements. The
whole value proposition breaks if any of it leaks. Treat every rule below as
non-negotiable, not a preference to weigh against convenience.

## What must never leave the local environment

- Raw statement files (OFX, PDF, CSV) and anything derived from them:
  transaction descriptions, amounts, dates, balances, account numbers,
  institution names tied to the user's accounts, and the categorized
  transaction data itself.
- The SQLite database and the generated dashboard HTML file. Both contain
  full transaction history and must only ever be written to local disk.

## Tools that are off-limits for this data

- **Never publish the dashboard (or any artifact containing transaction
  data) with a hosting/artifact-publishing tool.** Those tools mint a
  shareable URL on a remote service -- that is a data leak by definition,
  even if the link is technically private. Always write the dashboard to a
  local file and tell the user its path so they can open it directly from
  disk in their own browser.
- Never attach transaction data to a web search query, a fetched URL, an
  email, a calendar event, or any other connector/MCP tool that sends
  content off the machine.
- Never paste transaction data into a subagent prompt that isn't guaranteed
  to stay within this same local environment.

## When web research is genuinely useful

The user explicitly wants richer explanations of what a given expense is
("what is this merchant / this fund / this ticker") even if that requires
looking something up. This is fine, with a hard constraint: **generalize
before you search.**

Good: search for `"iFood" empresa o que e` or `"XPML11" fundo imobiliario` --
just the merchant, ticker, or institution name, stripped of everything else.

Bad: search for anything that includes the amount, the date, the account
holder's name, the account number, or a search string built by concatenating
multiple transactions (which itself starts to look like a spending profile).

Practical checklist before running a web search for this skill:
1. Does the query contain a dollar/real amount? Remove it.
2. Does it contain a date, account number, or the user's name? Remove it.
3. Would the query, on its own, embarrass or expose the user if it leaked in
   a search provider's logs? If yes, generalize further or skip the search
   and just say you're not sure what the merchant is.
4. Is there enough already in the merchant string itself (e.g. "IFOOD
   *IFOOD.COM") to answer without searching at all? Prefer that -- it's
   both faster and strictly safer than a network call.

The result of the search (a one- or two-sentence explanation of what a
business/fund/ticker is) can be stored locally in the category rules or the
transaction's explanation field. The search query itself is the only thing
that ever needs to touch the network -- the answer and all the personal
context stay local.

## Where local data should live

Keep the database, the rules file, and the dashboard inside a data
directory the user controls (see SKILL.md for the default path
convention). Don't scatter copies into temp directories, and don't leave
parsed intermediate JSON files lying around after they've been imported
into the database -- the database is the single source of truth, and fewer
copies of sensitive data on disk is strictly better.
