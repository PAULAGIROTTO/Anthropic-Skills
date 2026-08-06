#!/usr/bin/env python3
"""Build a self-contained, offline HTML dashboard from the local finance DB.

The output file has everything inlined (CSS, JS, data) and makes zero network
requests -- no CDN scripts, no fonts, no analytics, nothing. That matters
because this dashboard contains the user's real transaction history: it must
be safe to open straight from disk with no internet connection at all, and it
must never be handed to a tool (like an Artifacts publisher) that would host
it outside the local machine.

It reads the *entire* history already stored in the SQLite DB every time it
runs, so each month you only need to import that month's new statements --
the dashboard automatically includes everything imported before, with no
re-entry of past data.

Usage:
    python3 build_dashboard.py --db finance-data/finance.db --out finance-data/dashboard.html
"""
import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

CATEGORY_PALETTE = [
    "#4C6EF5", "#12B886", "#F59F00", "#E64980", "#7048E8", "#15AABF",
    "#FA5252", "#82C91E", "#FAB005", "#5C7CFA", "#20C997", "#BE4BDB",
    "#FF922B", "#339AF0", "#94D82D", "#F783AC",
]


def fetch_all(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT txn_hash, date, posted_month, description, amount, currency, flow,
                  category, subcategory, explanation, account_id, is_fixed
           FROM transactions ORDER BY date"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_category_options(rows):
    """Distinct (category, subcategory) combinations seen in the data, grouped
    by category, so the dashboard's recategorize form can offer autocomplete
    suggestions instead of the user having to retype an existing category's
    exact spelling from memory.
    """
    by_category = {}
    for r in rows:
        cat = r["category"] or "Nao classificado"
        sub = r["subcategory"] or ""
        subs = by_category.setdefault(cat, set())
        if sub:
            subs.add(sub)
    return {cat: sorted(subs) for cat, subs in sorted(by_category.items())}


def build_aggregates(rows):
    months = sorted({r["posted_month"] for r in rows})
    monthly_totals = {
        m: {"income": 0.0, "expense": 0.0, "investment": 0.0, "fixed": 0.0, "variable": 0.0, "unclassified_fixed": 0.0}
        for m in months
    }
    category_by_month = {}  # month -> category -> abs total (expenses only)
    category_alltime = {}   # category -> abs total (expenses only)
    investment_by_month_cumulative = {}
    txns_by_month = {}

    for r in rows:
        m = r["posted_month"]
        amt = r["amount"] or 0.0
        flow = r["flow"]
        txns_by_month.setdefault(m, []).append(r)

        if flow == "income":
            monthly_totals[m]["income"] += amt
        elif flow == "expense":
            spend = -amt
            monthly_totals[m]["expense"] += spend  # store as positive spend
            cat = r["category"] or "Nao classificado"
            category_by_month.setdefault(m, {}).setdefault(cat, 0.0)
            category_by_month[m][cat] += spend
            category_alltime[cat] = category_alltime.get(cat, 0.0) + spend

            is_fixed = r["is_fixed"]
            if is_fixed == 1:
                monthly_totals[m]["fixed"] += spend
            elif is_fixed == 0:
                monthly_totals[m]["variable"] += spend
            else:
                monthly_totals[m]["unclassified_fixed"] += spend
        elif flow == "investment":
            monthly_totals[m]["investment"] += -amt  # positive = money moved into investments

    running = 0.0
    for m in months:
        running += monthly_totals[m]["investment"]
        investment_by_month_cumulative[m] = round(running, 2)

    for m in monthly_totals:
        for k in monthly_totals[m]:
            monthly_totals[m][k] = round(monthly_totals[m][k], 2)
        monthly_totals[m]["net"] = round(monthly_totals[m]["income"] - monthly_totals[m]["expense"], 2)

    return {
        "months": months,
        "monthly_totals": monthly_totals,
        "category_by_month": category_by_month,
        "category_alltime": {k: round(v, 2) for k, v in category_alltime.items()},
        "investment_cumulative": investment_by_month_cumulative,
        "transactions": txns_by_month,
        "category_options": build_category_options(rows),
    }


HTML_TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard Financeiro</title>
<meta name="robots" content="noindex, nofollow">
<style>
  :root {
    --bg: #f7f8fa; --panel: #ffffff; --text: #1a1d29; --muted: #6b7280;
    --border: #e5e7eb; --income: #12B886; --expense: #E03131; --invest: #4C6EF5;
    --accent: #4C6EF5;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0f1117; --panel:#171923; --text:#e8eaf0; --muted:#9aa1b1; --border:#2a2e3a; }
  }
  :root[data-theme="dark"] { --bg:#0f1117; --panel:#171923; --text:#e8eaf0; --muted:#9aa1b1; --border:#2a2e3a; }
  :root[data-theme="light"] { --bg:#f7f8fa; --panel:#ffffff; --text:#1a1d29; --muted:#6b7280; --border:#e5e7eb; }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    padding: 24px; max-width: 1200px; margin-inline: auto;
  }
  h1 { font-size: 1.5rem; margin-bottom: 4px; }
  .subtitle { color: var(--muted); font-size: 0.85rem; margin-bottom: 24px; }
  .privacy-note {
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 10px 14px; font-size: 0.78rem; color: var(--muted); margin-bottom: 20px;
  }
  .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px; }
  .kpi { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 16px; }
  .kpi .label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
  .kpi .value { font-size: 1.5rem; font-weight: 600; margin-top: 4px; }
  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; overflow-x: auto; }
  .panel h2 { font-size: 1rem; margin: 0 0 14px 0; }
  select, button {
    background: var(--bg); color: var(--text); border: 1px solid var(--border);
    border-radius: 8px; padding: 6px 10px; font-size: 0.85rem; cursor: pointer;
  }
  .controls { display: flex; gap: 10px; align-items: center; margin-bottom: 14px; flex-wrap: wrap; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; min-width: 480px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 500; font-size: 0.75rem; text-transform: uppercase; }
  tr.cat-row { cursor: pointer; }
  tr.cat-row:hover { background: color-mix(in srgb, var(--accent) 8%, transparent); }
  .amount-expense { color: var(--expense); font-variant-numeric: tabular-nums; }
  .amount-income { color: var(--income); font-variant-numeric: tabular-nums; }
  .amount-invest { color: var(--invest); font-variant-numeric: tabular-nums; }
  .bar-track { background: var(--border); border-radius: 4px; height: 8px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; }
  .subrow td { color: var(--muted); font-size: 0.8rem; padding-left: 26px; }
  .legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 0.78rem; color: var(--muted); margin-top: 10px; }
  .legend span.dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; }
  footer { text-align: center; color: var(--muted); font-size: 0.75rem; margin-top: 30px; }
  .expand-icon { display:inline-block; width:14px; color:var(--muted); transition: transform 0.15s; }
  tr.cat-row.expanded .expand-icon { transform: rotate(90deg); }
  .detail-row td { background: color-mix(in srgb, var(--accent) 4%, var(--bg)); padding: 10px 10px 14px 26px; }
  .txn-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
  .txn-table th { font-size: 0.68rem; padding: 4px 8px; }
  .txn-table td { padding: 6px 8px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  .txn-table tr.pending td { background: color-mix(in srgb, var(--income) 10%, transparent); }
  .recat-cell { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
  .recat-cell input[type="text"] {
    background: var(--bg); color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 4px 6px; font-size: 0.78rem; width: 120px;
  }
  .recat-cell label { font-size: 0.68rem; color: var(--muted); display:flex; align-items:center; gap:3px; white-space:nowrap; }
  .recat-cell button { font-size: 0.75rem; padding: 4px 8px; }
  .pending-note { font-size: 0.72rem; color: var(--income); white-space: nowrap; }
  #pending-panel {
    position: fixed; bottom: 18px; right: 18px; background: var(--panel); border: 1px solid var(--border);
    border-radius: 12px; padding: 12px 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); display: none;
    max-width: 320px; z-index: 10;
  }
  #pending-panel.visible { display: block; }
  #pending-panel .count { font-weight: 600; margin-bottom: 4px; }
  #pending-panel .hint { font-size: 0.72rem; color: var(--muted); margin-bottom: 10px; }
  #pending-panel .actions { display: flex; gap: 8px; }
</style>
</head>
<body>
  <div style="display:flex; justify-content:space-between; align-items:flex-start;">
    <div>
      <h1>Dashboard Financeiro</h1>
      <div class="subtitle">Atualizado em __GENERATED_AT__ &middot; __MONTH_COUNT__ meses de historico</div>
    </div>
    <button id="theme-toggle" title="Alternar tema">&#9789;</button>
  </div>
  <div class="privacy-note">
    Este arquivo e 100% local: nenhum dado sai deste computador. Abra-o diretamente
    do disco (nao publique em um servico web) para manter seus extratos privados.
  </div>

  <div class="kpi-row" id="kpi-row"></div>

  <div class="panel">
    <h2>Receitas, despesas e investimentos por mes</h2>
    <div id="trend-chart"></div>
  </div>

  <div class="panel">
    <h2>Gastos fixos vs variaveis por mes</h2>
    <div id="fixed-chart"></div>
  </div>

  <div class="panel">
    <div class="controls">
      <h2 style="margin:0;">Gastos por categoria</h2>
      <select id="month-select"></select>
    </div>
    <div id="category-chart"></div>
  </div>

  <div class="panel">
    <h2>Detalhamento por categoria</h2>
    <p style="color:var(--muted); font-size:0.78rem; margin-top:-8px;">
      Clique em uma categoria para ver as transacoes e recategorizar o que estiver errado.
    </p>
    <table id="category-table">
      <thead><tr><th style="width:24px"></th><th>Categoria</th><th>Total</th><th style="width:35%">Participacao</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <datalist id="categories-datalist"></datalist>
  <datalist id="subcategories-datalist"></datalist>

  <div id="pending-panel">
    <div class="count"></div>
    <div class="hint">Baixe o arquivo e peca para o Claude aplicar as mudancas (roda `apply_recategorizations.py` e atualiza o dashboard).</div>
    <div class="actions">
      <button id="pending-download">Baixar alteracoes</button>
      <button id="pending-clear">Limpar</button>
    </div>
  </div>

  <footer>Gerado localmente pela skill financial-statement-analyzer &middot; nenhum dado foi enviado para a internet</footer>

<script>
const DATA = __DATA_JSON__;

function fmtBRL(v) {
  const sign = v < 0 ? "-" : "";
  return sign + "R$ " + Math.abs(v).toLocaleString("pt-BR", {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

function el(tag, attrs, children) {
  const e = document.createElement(tag);
  for (const k in (attrs || {})) e.setAttribute(k, attrs[k]);
  (children || []).forEach(c => e.appendChild(typeof c === "string" ? document.createTextNode(c) : c));
  return e;
}

// --- theme toggle ---
const root = document.documentElement;
document.getElementById("theme-toggle").addEventListener("click", () => {
  const current = root.getAttribute("data-theme") ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  root.setAttribute("data-theme", current === "dark" ? "light" : "dark");
});

// --- KPI row (latest month) ---
const months = DATA.months;
const latest = months[months.length - 1];
const kpiRow = document.getElementById("kpi-row");
if (latest) {
  const t = DATA.monthly_totals[latest];
  const kpis = [
    ["Receitas (" + latest + ")", t.income, "amount-income"],
    ["Despesas (" + latest + ")", t.expense, "amount-expense"],
    ["Saldo (" + latest + ")", t.net, t.net >= 0 ? "amount-income" : "amount-expense"],
    ["Investido no mes", t.investment, "amount-invest"],
    ["Total investido acumulado", DATA.investment_cumulative[latest] || 0, "amount-invest"],
  ];
  kpis.forEach(([label, value, cls]) => {
    kpiRow.appendChild(el("div", {class: "kpi"}, [
      el("div", {class: "label"}, [label]),
      el("div", {class: "value " + cls}, [fmtBRL(value)]),
    ]));
  });
  if (t.expense > 0) {
    const fixedPct = Math.round((t.fixed / t.expense) * 100);
    kpiRow.appendChild(el("div", {class: "kpi"}, [
      el("div", {class: "label"}, ["% de gastos fixos"]),
      el("div", {class: "value"}, [fixedPct + "%"]),
    ]));
  }
} else {
  kpiRow.appendChild(el("div", {class: "kpi"}, [el("div", {class: "label"}, ["Sem dados importados ainda"])]));
}

// --- trend chart (simple SVG line chart, no external libs) ---
function renderTrendChart() {
  const container = document.getElementById("trend-chart");
  if (months.length === 0) { container.textContent = "Importe extratos para ver o historico."; return; }
  const W = Math.max(600, months.length * 90), H = 220, PAD = 36;
  const series = {
    income: months.map(m => DATA.monthly_totals[m].income),
    expense: months.map(m => DATA.monthly_totals[m].expense),
    net: months.map(m => DATA.monthly_totals[m].net),
  };
  const allVals = [].concat(series.income, series.expense, series.net, [0]);
  const maxV = Math.max(...allVals), minV = Math.min(...allVals);
  const range = (maxV - minV) || 1;
  const x = i => PAD + (i * (W - 2 * PAD)) / Math.max(1, months.length - 1);
  const y = v => H - PAD - ((v - minV) / range) * (H - 2 * PAD);

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", H);

  const zeroY = y(0);
  const axis = document.createElementNS(svg.namespaceURI, "line");
  axis.setAttribute("x1", PAD); axis.setAttribute("x2", W - PAD);
  axis.setAttribute("y1", zeroY); axis.setAttribute("y2", zeroY);
  axis.setAttribute("stroke", "var(--border)");
  svg.appendChild(axis);

  const colors = {income: "var(--income)", expense: "var(--expense)", net: "var(--invest)"};
  for (const key of ["income", "expense", "net"]) {
    const pts = series[key].map((v, i) => `${x(i)},${y(v)}`).join(" ");
    const poly = document.createElementNS(svg.namespaceURI, "polyline");
    poly.setAttribute("points", pts);
    poly.setAttribute("fill", "none");
    poly.setAttribute("stroke", colors[key]);
    poly.setAttribute("stroke-width", "2.5");
    svg.appendChild(poly);
    series[key].forEach((v, i) => {
      const c = document.createElementNS(svg.namespaceURI, "circle");
      c.setAttribute("cx", x(i)); c.setAttribute("cy", y(v)); c.setAttribute("r", "3");
      c.setAttribute("fill", colors[key]);
      const title = document.createElementNS(svg.namespaceURI, "title");
      title.textContent = `${key} ${months[i]}: ${fmtBRL(v)}`;
      c.appendChild(title);
      svg.appendChild(c);
    });
  }
  months.forEach((m, i) => {
    const t = document.createElementNS(svg.namespaceURI, "text");
    t.setAttribute("x", x(i)); t.setAttribute("y", H - 8);
    t.setAttribute("text-anchor", "middle"); t.setAttribute("font-size", "10");
    t.setAttribute("fill", "var(--muted)");
    t.textContent = m;
    svg.appendChild(t);
  });
  container.innerHTML = "";
  container.appendChild(svg);
  container.appendChild(el("div", {class: "legend"}, [
    el("span", {}, [el("span", {class: "dot", style: "background:var(--income)"}, []), "Receitas"]),
    el("span", {}, [el("span", {class: "dot", style: "background:var(--expense)"}, []), "Despesas"]),
    el("span", {}, [el("span", {class: "dot", style: "background:var(--invest)"}, []), "Saldo"]),
  ]));
}
renderTrendChart();

// --- fixed vs variable stacked bar chart ---
function renderFixedChart() {
  const container = document.getElementById("fixed-chart");
  if (months.length === 0) { container.textContent = "Importe extratos para ver o historico."; return; }
  const hasAnyClassified = months.some(m => (DATA.monthly_totals[m].fixed + DATA.monthly_totals[m].variable) > 0);
  if (!hasAnyClassified) {
    container.innerHTML = "";
    container.appendChild(el("p", {style: "color:var(--muted); font-size:0.85rem;"}, [
      "Nenhuma despesa foi marcada como fixa ou variavel ainda. Peca para marcar um gasto (ex: 'o aluguel e um gasto fixo') e esse grafico passa a mostrar a divisao.",
    ]));
    return;
  }
  const W = Math.max(600, months.length * 70), H = 220, PAD = 36;
  const barW = Math.min(40, (W - 2 * PAD) / months.length - 10);
  const maxTotal = Math.max(...months.map(m => {
    const t = DATA.monthly_totals[m];
    return t.fixed + t.variable + t.unclassified_fixed;
  }), 1);
  const x = i => PAD + (i * (W - 2 * PAD)) / Math.max(1, months.length - 1) - barW / 2;
  const scale = v => (v / maxTotal) * (H - 2 * PAD);

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", H);
  const colors = {fixed: "var(--invest)", variable: "#F59F00", unclassified_fixed: "var(--border)"};

  months.forEach((m, i) => {
    const t = DATA.monthly_totals[m];
    let yCursor = H - PAD;
    [["fixed", t.fixed], ["variable", t.variable], ["unclassified_fixed", t.unclassified_fixed]].forEach(([key, val]) => {
      if (val <= 0) return;
      const h = scale(val);
      const rect = document.createElementNS(svg.namespaceURI, "rect");
      rect.setAttribute("x", x(i)); rect.setAttribute("width", barW);
      rect.setAttribute("y", yCursor - h); rect.setAttribute("height", h);
      rect.setAttribute("fill", colors[key]); rect.setAttribute("rx", "2");
      const title = document.createElementNS(svg.namespaceURI, "title");
      title.textContent = `${key} ${m}: ${fmtBRL(val)}`;
      rect.appendChild(title);
      svg.appendChild(rect);
      yCursor -= h;
    });
    const t2 = document.createElementNS(svg.namespaceURI, "text");
    t2.setAttribute("x", x(i) + barW / 2); t2.setAttribute("y", H - 8);
    t2.setAttribute("text-anchor", "middle"); t2.setAttribute("font-size", "10");
    t2.setAttribute("fill", "var(--muted)");
    t2.textContent = m;
    svg.appendChild(t2);
  });
  container.innerHTML = "";
  container.appendChild(svg);
  container.appendChild(el("div", {class: "legend"}, [
    el("span", {}, [el("span", {class: "dot", style: "background:var(--invest)"}, []), "Fixos"]),
    el("span", {}, [el("span", {class: "dot", style: "background:#F59F00"}, []), "Variaveis"]),
    el("span", {}, [el("span", {class: "dot", style: "background:var(--border)"}, []), "Ainda nao classificado (fixo/variavel)"]),
  ]));
}
renderFixedChart();

// --- month selector + category chart/table ---
const monthSelect = document.getElementById("month-select");
["Ultimos 12 meses"].concat(months.slice().reverse()).forEach((label, idx) => {
  const value = idx === 0 ? "__last12__" : label;
  monthSelect.appendChild(el("option", {value}, [label]));
});

function categoryTotalsFor(selection) {
  if (selection === "__last12__") {
    const recentMonths = months.slice(-12);
    const totals = {};
    recentMonths.forEach(m => {
      const cats = DATA.category_by_month[m] || {};
      for (const c in cats) totals[c] = (totals[c] || 0) + cats[c];
    });
    return totals;
  }
  return DATA.category_by_month[selection] || {};
}

const PALETTE = __PALETTE_JSON__;
function colorFor(category, idx) { return PALETTE[idx % PALETTE.length]; }

function renderCategoryChart(selection) {
  const totals = categoryTotalsFor(selection);
  const entries = Object.entries(totals).filter(([,v]) => v > 0).sort((a,b) => b[1]-a[1]);
  const container = document.getElementById("category-chart");
  container.innerHTML = "";
  if (entries.length === 0) { container.textContent = "Sem despesas categorizadas neste periodo."; return; }
  const max = entries[0][1];
  const list = el("div", {}, []);
  entries.forEach(([cat, val], i) => {
    const pct = Math.round((val / max) * 100);
    const row = el("div", {style: "margin-bottom:10px;"}, [
      el("div", {style: "display:flex; justify-content:space-between; font-size:0.85rem; margin-bottom:3px;"}, [
        el("span", {}, [cat]), el("span", {class: "amount-expense"}, [fmtBRL(val)]),
      ]),
      el("div", {class: "bar-track"}, [
        el("div", {class: "bar-fill", style: `width:${pct}%; background:${colorFor(cat, i)}`}, []),
      ]),
    ]);
    list.appendChild(row);
  });
  container.appendChild(list);

  const tbody = document.querySelector("#category-table tbody");
  tbody.innerHTML = "";
  const grandTotal = entries.reduce((s, [,v]) => s + v, 0) || 1;
  entries.forEach(([cat, val], i) => {
    const share = Math.round((val / grandTotal) * 100);
    const tr = el("tr", {class: "cat-row"}, [
      el("td", {}, [el("span", {class: "expand-icon"}, ["▸"])]),
      el("td", {}, [el("span", {class:"dot", style:`display:inline-block;width:8px;height:8px;border-radius:50%;background:${colorFor(cat,i)};margin-right:8px;`}, []), cat]),
      el("td", {class: "amount-expense"}, [fmtBRL(val)]),
      el("td", {}, [el("div", {class:"bar-track"}, [el("div", {class:"bar-fill", style:`width:${share}%; background:${colorFor(cat,i)}`}, [])])]),
    ]);
    let detailTr = null;
    tr.addEventListener("click", () => {
      if (detailTr) {
        detailTr.remove();
        detailTr = null;
        tr.classList.remove("expanded");
        return;
      }
      tr.classList.add("expanded");
      const td = el("td", {colspan: "4", class: "detail-row-cell"}, [renderCategoryDetail(cat, monthSelect.value)]);
      detailTr = el("tr", {class: "detail-row"}, [td]);
      tr.after(detailTr);
    });
    tbody.appendChild(tr);
  });
}

monthSelect.addEventListener("change", () => renderCategoryChart(monthSelect.value));

// --- category autocomplete (datalists) ---
const allCategories = Object.keys(DATA.category_options).sort();
const categoriesDatalist = document.getElementById("categories-datalist");
allCategories.forEach(cat => categoriesDatalist.appendChild(el("option", {value: cat}, [])));

const subcategoriesDatalist = document.getElementById("subcategories-datalist");
function refreshSubcategoryOptions(category) {
  subcategoriesDatalist.innerHTML = "";
  const subs = DATA.category_options[category] || Object.values(DATA.category_options).flat();
  [...new Set(subs)].sort().forEach(sub => subcategoriesDatalist.appendChild(el("option", {value: sub}, [])));
}
refreshSubcategoryOptions(null);

// --- pending recategorization changes, staged client-side ---
// The dashboard is a static, offline file with no write access to the
// database on purpose (see privacy_guidelines.md) -- edits here never touch
// finance.db directly. Instead they accumulate in this Map and get exported
// as a small JSON file the user hands back to Claude, which applies them
// with apply_recategorizations.py and rebuilds the dashboard.
const pending = new Map(); // txn_hash -> change entry

function pendingPanelRefresh() {
  const panel = document.getElementById("pending-panel");
  const count = pending.size;
  panel.classList.toggle("visible", count > 0);
  panel.querySelector(".count").textContent = count === 1 ? "1 alteracao pendente" : count + " alteracoes pendentes";
}

document.getElementById("pending-download").addEventListener("click", () => {
  const payload = Array.from(pending.values());
  const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const a = el("a", {href: url, download: "recategorizations.json"}, []);
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

document.getElementById("pending-clear").addEventListener("click", () => {
  pending.clear();
  document.querySelectorAll(".txn-table tr.pending").forEach(tr => {
    tr.classList.remove("pending");
    const note = tr.querySelector(".pending-note");
    if (note) note.remove();
  });
  pendingPanelRefresh();
});

function buildRecatCell(txn) {
  const catInput = el("input", {type: "text", list: "categories-datalist", class: "recat-category", value: txn.category || ""}, []);
  const subInput = el("input", {type: "text", list: "subcategories-datalist", class: "recat-subcategory", value: txn.subcategory || ""}, []);
  catInput.addEventListener("input", () => refreshSubcategoryOptions(catInput.value));
  const scopeCheckbox = el("input", {type: "checkbox", checked: "checked"}, []);
  const applyBtn = el("button", {type: "button"}, ["Marcar"]);
  const cell = el("div", {class: "recat-cell"}, [
    catInput, subInput,
    el("label", {}, [scopeCheckbox, "aplicar a todas do estabelecimento"]),
    applyBtn,
  ]);

  applyBtn.addEventListener("click", () => {
    const category = catInput.value.trim();
    const subcategory = subInput.value.trim();
    if (!category) { catInput.focus(); return; }
    const scope = scopeCheckbox.checked ? "merchant" : "transaction";
    const entry = scope === "merchant"
      ? {scope, match: txn.description, category, subcategory, flow: txn.flow || "expense"}
      : {scope, txn_hash: txn.txn_hash, category, subcategory, flow: txn.flow || "expense"};
    pending.set(txn.txn_hash, entry);
    pendingPanelRefresh();

    const row = applyBtn.closest("tr");
    row.classList.add("pending");
    let note = row.querySelector(".pending-note");
    if (!note) {
      note = el("span", {class: "pending-note"}, []);
      cell.appendChild(note);
    }
    note.textContent = scope === "merchant" ? "pendente (todo o estabelecimento)" : "pendente (so esta transacao)";
  });

  return cell;
}

function renderCategoryDetail(category, monthSelection) {
  const relevantMonths = monthSelection === "__last12__" ? months.slice(-12) : [monthSelection];
  const txns = [];
  relevantMonths.forEach(m => {
    (DATA.transactions[m] || []).forEach(t => {
      if (t.flow === "expense" && (t.category || "Nao classificado") === category) txns.push(t);
    });
  });
  txns.sort((a, b) => (a.date < b.date ? 1 : -1));

  const table = el("table", {class: "txn-table"}, [
    el("thead", {}, [el("tr", {}, [
      el("th", {}, ["Data"]), el("th", {}, ["Descricao"]), el("th", {}, ["Valor"]),
      el("th", {}, ["Subcategoria atual"]), el("th", {}, ["Recategorizar"]),
    ])]),
  ]);
  const tbody = el("tbody", {}, []);
  if (txns.length === 0) {
    tbody.appendChild(el("tr", {}, [el("td", {colspan: "5", style: "color:var(--muted);"}, ["Sem transacoes neste periodo."])]));
  }
  txns.forEach(t => {
    tbody.appendChild(el("tr", {}, [
      el("td", {}, [t.date]),
      el("td", {title: t.explanation || ""}, [t.description]),
      el("td", {class: "amount-expense"}, [fmtBRL(-t.amount)]),
      el("td", {}, [t.subcategory || "-"]),
      el("td", {}, [buildRecatCell(t)]),
    ]));
  });
  table.appendChild(tbody);
  return table;
}

renderCategoryChart("__last12__");
</script>
</body>
</html>
"""


def build_dashboard(db_path, out_path):
    rows = fetch_all(db_path)
    agg = build_aggregates(rows)

    data_json = json.dumps(agg, ensure_ascii=False).replace("</", "<\\/")
    palette_json = json.dumps(CATEGORY_PALETTE)

    html = (HTML_TEMPLATE
            .replace("__DATA_JSON__", data_json)
            .replace("__PALETTE_JSON__", palette_json)
            .replace("__GENERATED_AT__", datetime.now().strftime("%d/%m/%Y %H:%M"))
            .replace("__MONTH_COUNT__", str(len(agg["months"]))))

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(html, encoding="utf-8")
    return {"out_path": str(out_path), "months": agg["months"], "transaction_count": len(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = build_dashboard(args.db, args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
