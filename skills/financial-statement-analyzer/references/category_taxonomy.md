# Category taxonomy

The goal is detail: "Compras" alone tells the user nothing about where
their money went, but "Compras > Marketplace e e-commerce" tied to an
explanation like "iFood is a Brazilian food-delivery app" does. Every
transaction gets a `flow` (which bucket it belongs to), a `category`, a
`subcategory`, and a short `explanation` of what the merchant/transaction
actually is -- not just a label.

The seed rules live in `assets/default_category_rules.json` and get copied
into the user's own data directory on first run (`store.py init`), so they
are meant to be edited and grown over time, per user, per country. What
follows is the taxonomy those seed rules implement, as a reference for
extending it consistently.

## Despesas (expense flow)

| Category | Typical subcategories |
|---|---|
| Moradia | Aluguel, Condomínio, IPTU, Financiamento imobiliário, Manutenção/reparos, Móveis e decoração |
| Contas e utilidades | Energia elétrica, Água e esgoto, Gás, Internet, Telefone e celular, TV por assinatura |
| Alimentação | Supermercado, Restaurante, Delivery, Padaria, Café, Lanche e fast food |
| Transporte | Combustível, Estacionamento, Pedágio, Transporte por aplicativo, Transporte público, Manutenção veicular, Seguro veicular, IPVA |
| Saúde | Plano de saúde, Farmácia, Consultas médicas, Exames, Odontologia, Academia e fitness |
| Educação | Mensalidade escolar ou faculdade, Cursos online, Livros e material didático |
| Lazer e entretenimento | Streaming, Cinema e shows, Viagens e hospedagem, Passagens aéreas, Hobbies, Jogos |
| Compras | Vestuário, Eletrônicos, Casa e decoração, Beleza e cosméticos, Presentes, Marketplace e e-commerce |
| Serviços financeiros | Tarifas bancárias, Juros e IOF, Anuidade de cartão, Seguros (vida, residencial), Empréstimos |
| Impostos e taxas | Imposto de renda a pagar, Taxas governamentais |
| Pets | Veterinário, Pet shop e ração |
| Assinaturas e softwares | SaaS, aplicativos, ferramentas |
| Doações | Doações e contribuições |
| Cuidados pessoais | Salão e barbearia, Cosméticos |
| Filhos e dependentes | Creche/escola, Mesada, Roupas infantis |
| Não classificado | Catch-all -- see below |

**Never silently force a transaction into an existing category just to
avoid "Não classificado."** An unclassified transaction with the raw
description preserved is far more useful than a wrong classification --
the user can review the "uncategorized" list (`store.py uncategorized`)
and either teach the skill a new rule or leave it as a one-off. A
dashboard that's 95% accurately categorized and 5% honestly unclassified
is trustworthy; one that's 100% categorized but partly wrong isn't.

## Receita (income flow)

| Category | Typical subcategories |
|---|---|
| Receita | Salário, Freelance ou autônomo, Rendimentos de investimentos, Reembolso ou estorno, Vendas, Restituição de imposto de renda, Outros |

Watch for the most common false positive: a P2P transfer *received* from
a friend or family member is not automatically income -- if it's a
reimbursement for a shared expense (rent split, a group purchase), it
either nets against the original expense or goes to "Reembolso," not
"Salário" or generic income. When genuinely ambiguous, ask the user rather
than guessing, since income totals feed directly into the dashboard's
"saldo" figure.

## Investimentos (investment flow)

| Category | Typical subcategories |
|---|---|
| Investimentos | Renda fixa (CDB, Tesouro Direto, LCI/LCA), Renda variável (ações, FIIs, ETFs), Fundos de investimento, Previdência privada, Criptoativos, Poupança, Internacional |

Investment flow is tracked separately from income and expense specifically
so contributing to a CDB or buying stock doesn't look like "spending" on
the dashboard, and a redemption doesn't look like "income." See
`bank_formats.md` for how to split out investment *income* (dividends,
JCP, rendimento) from principal moving in and out.

## Transferência interna (excluded from totals)

Money moving between the user's own accounts (checking to savings,
checking to a linked investment account handled elsewhere in the same
statement, paying off your own credit card from your own checking
account) should be tagged `flow: transfer` and excluded from income/expense
totals entirely. Without this, every internal transfer double-counts: once
as an "expense" leaving the checking account, once as "income" entering
the savings account, inflating both sides of the dashboard for money that
never actually left the household. `categorize.py` already flags common
transfer phrasing (`TRANSFERENCIA ENTRE CONTAS`, `MESMO TITULAR`, etc.) --
extend that list per bank as new phrasings show up.

## Extending the taxonomy

When adding a new rule to a user's `category_rules.json`:
- Prefer the most specific subcategory that's still reusable across many
  transactions, not a one-off tied to a single receipt.
- Put more specific patterns before more general ones -- `categorize.py`
  uses first-match-wins.
- Fill in `note`/`explanation` with a short, factual description of what
  the merchant or instrument actually is. That's what makes the dashboard
  explain spending instead of just labeling it.
