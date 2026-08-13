#!/usr/bin/env python3
"""
Analisa dados de fluxo operacional de um servico de Neurofisiologia clinica
(aEEG, VEEG 12h, cEEG, EEG 2h) e gera os KPIs, tabela de outliers, tabela de
gargalos e os 5 graficos do dashboard executivo descritos em
references/graficos-dashboard.md.

Uso:
    python analisar_fluxo_eeg.py --exames exames.txt --fluxo fluxo.txt \
        --pacientes pacientes.txt --clinico clinico.txt --outdir saida/

Apenas --exames e --fluxo sao obrigatorios; --pacientes e --clinico sao
opcionais e o script degrada graciosamente sem eles (sem analise por unidade,
sem grafico de crises).
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

VERDE, AMARELO, VERMELHO = "#2E7D32", "#F9A825", "#C62828"
TIPOS_EXAME_ORDEM = ["aEEG", "EEG2h", "VEEG12h", "cEEG"]

# Marco padrao do relogio do SLA por tipo de exame: cEEG e continuo, entao o
# relogio comeca no inicio da gravacao (a leitura precisa acontecer durante o
# exame); os demais sao lidos depois de prontos, entao comeca no fim.
MARCO_PADRAO_POR_TIPO = {
    "cEEG": "inicio",
    "aEEG": "fim",
    "VEEG12h": "fim",
    "EEG2h": "fim",
}


def ler_tabela(caminho):
    if caminho is None:
        return None
    sep = "\t" if Path(caminho).suffix == ".txt" else None
    df = pd.read_csv(caminho, sep=sep, engine="python")
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def parse_datas(df, colunas):
    for c in colunas:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def cor_por_pct(pct, meta=90):
    if pd.isna(pct):
        return "#9E9E9E"
    if pct >= meta:
        return VERDE
    if pct >= meta - 10:
        return AMARELO
    return VERMELHO


def montar_dataset(args):
    exames = ler_tabela(args.exames)
    fluxo = ler_tabela(args.fluxo)
    pacientes = ler_tabela(args.pacientes)
    clinico = ler_tabela(args.clinico)

    exames = parse_datas(exames, ["data_hora_inicio", "data_hora_fim"])
    fluxo = parse_datas(
        fluxo,
        [
            "data_hora_disponivel_leitura",
            "data_hora_inicio_leitura",
            "data_hora_conclusao_relatorio",
        ],
    )

    df = exames.merge(fluxo, on="exame_id", how="left")

    if pacientes is not None:
        df = df.merge(pacientes, on="id_paciente", how="left")
    else:
        df["unidade"] = "desconhecida"
        df["risco_neurologico"] = np.nan

    if clinico is not None:
        df = df.merge(clinico, on="exame_id", how="left")
    else:
        df["numero_crises"] = np.nan
        df["presenca_crises"] = np.nan
        df["eventos_criticos_marcados"] = np.nan

    df["duracao_min"] = (
        df["data_hora_fim"] - df["data_hora_inicio"]
    ).dt.total_seconds() / 60

    if args.marco == "auto":
        marco = df["tipo_exame"].map(MARCO_PADRAO_POR_TIPO).fillna("fim")
    else:
        marco = pd.Series(args.marco, index=df.index)
    df["_marco_ts"] = np.where(
        marco == "inicio", df["data_hora_inicio"], df["data_hora_fim"]
    )
    df["_marco_ts"] = pd.to_datetime(df["_marco_ts"])
    df["marco_sla"] = marco

    df["tempo_ate_1a_analise_min"] = (
        df["data_hora_inicio_leitura"] - df["_marco_ts"]
    ).dt.total_seconds() / 60
    df["fila_para_leitura_min"] = (
        df["data_hora_inicio_leitura"] - df["data_hora_disponivel_leitura"]
    ).dt.total_seconds() / 60
    df["leitura_min"] = (
        df["data_hora_conclusao_relatorio"] - df["data_hora_inicio_leitura"]
    ).dt.total_seconds() / 60
    df["total_ate_laudo_min"] = (
        df["data_hora_conclusao_relatorio"] - df["_marco_ts"]
    ).dt.total_seconds() / 60

    df["dentro_sla"] = df["tempo_ate_1a_analise_min"] <= args.sla_minutes
    return df


def calcular_kpis(df, sla_minutes):
    kpis = {}
    kpis["n_exames"] = int(len(df))
    kpis["periodo"] = {
        "inicio": str(df["data_hora_inicio"].min()),
        "fim": str(df["data_hora_fim"].max()),
    }
    kpis["exames_por_tipo"] = df["tipo_exame"].value_counts().to_dict()
    if "unidade" in df.columns:
        kpis["exames_por_unidade"] = df["unidade"].value_counts().to_dict()

    kpis["pct_sla_geral"] = round(100 * df["dentro_sla"].mean(), 1)
    kpis["pct_sla_por_tipo"] = (
        (100 * df.groupby("tipo_exame")["dentro_sla"].mean()).round(1).to_dict()
    )
    if "unidade" in df.columns:
        kpis["pct_sla_por_unidade"] = (
            (100 * df.groupby("unidade")["dentro_sla"].mean()).round(1).to_dict()
        )

    for etapa in ["fila_para_leitura_min", "leitura_min", "total_ate_laudo_min"]:
        kpis[f"{etapa}_media"] = round(df[etapa].mean(), 1)
        kpis[f"{etapa}_mediana"] = round(df[etapa].median(), 1)
        kpis[f"{etapa}_p90"] = round(df[etapa].quantile(0.9), 1)

    if "numero_crises" in df.columns and df["numero_crises"].notna().any():
        kpis["crises_media_por_tipo"] = (
            df.groupby("tipo_exame")["numero_crises"].mean().round(2).to_dict()
        )
    return kpis


def detectar_outliers(df, sla_minutes):
    df = df.copy()
    p90_por_tipo = df.groupby("tipo_exame")["tempo_ate_1a_analise_min"].transform(
        lambda s: s.quantile(0.9)
    )
    df["_acima_p90"] = df["tempo_ate_1a_analise_min"] > p90_por_tipo

    if "numero_crises" in df.columns and df["numero_crises"].notna().any():
        q1 = df.groupby("tipo_exame")["numero_crises"].transform(
            lambda s: s.quantile(0.25)
        )
        q3 = df.groupby("tipo_exame")["numero_crises"].transform(
            lambda s: s.quantile(0.75)
        )
        limite_crises = q3 + 1.5 * (q3 - q1)
        df["_crises_atipicas"] = df["numero_crises"] > limite_crises
    else:
        df["_crises_atipicas"] = False

    dur_media = df.groupby("tipo_exame")["duracao_min"].transform("mean")
    dur_dp = df.groupby("tipo_exame")["duracao_min"].transform("std")
    df["_duracao_atipica"] = (df["duracao_min"] - dur_media).abs() > 2 * dur_dp

    e_outlier = df["_acima_p90"] | df["_crises_atipicas"] | df["_duracao_atipica"]
    out = df[e_outlier].copy()

    def severidade(row):
        risco_alto = str(row.get("risco_neurologico", "")).lower() in (
            "alto",
            "high",
        )
        marcacao_falha = str(row.get("eventos_criticos_marcados", "")).lower() in (
            "nao",
            "não",
            "no",
            "false",
        )
        fator_clinico = (
            str(row.get("unidade", "")).lower() == "uti" or risco_alto or marcacao_falha
        )
        if not row["dentro_sla"] and fator_clinico:
            return "Alta"
        if not row["dentro_sla"]:
            return "Media"
        return "Baixa"

    if len(out):
        out["severidade"] = out.apply(severidade, axis=1)
    else:
        out["severidade"] = pd.Series(dtype=str)

    cols = [
        "exame_id",
        "tipo_exame",
        "unidade",
        "tempo_ate_1a_analise_min",
        "dentro_sla",
        "severidade",
        "_acima_p90",
        "_crises_atipicas",
        "_duracao_atipica",
    ]
    cols = [c for c in cols if c in out.columns]
    ordem_sev = {"Alta": 0, "Media": 1, "Baixa": 2}
    out = out.sort_values(
        by="severidade", key=lambda s: s.map(ordem_sev)
    )
    return out[cols]


def calcular_gargalos(df, sla_minutes):
    etapas = {
        "Fila para leitura": "fila_para_leitura_min",
        "Leitura": "leitura_min",
        "Laudo (total ate liberacao)": "total_ate_laudo_min",
    }
    linhas = []
    for nome, col in etapas.items():
        serie = df[col].dropna()
        if not len(serie):
            continue
        media = serie.mean()
        p90 = serie.quantile(0.9)
        volume = int(serie.count())
        pct_impacto = round(100 * media / max(df["total_ate_laudo_min"].mean(), 1e-9), 1)
        prioridade_score = media * volume
        linhas.append(
            {
                "etapa": nome,
                "tempo_medio_min": round(media, 1),
                "tempo_p90_min": round(p90, 1),
                "volume": volume,
                "pct_do_tempo_total": pct_impacto,
                "_score": prioridade_score,
            }
        )
    gargalos = pd.DataFrame(linhas).sort_values("_score", ascending=False)
    if len(gargalos):
        gargalos["prioridade"] = ["Alta", "Media", "Baixa"][: len(gargalos)][
            : len(gargalos)
        ]
        # garante rotulo mesmo se houver mais de 3 etapas no futuro
        rotulos = ["Alta", "Media", "Baixa"]
        gargalos["prioridade"] = [
            rotulos[i] if i < len(rotulos) else "Baixa" for i in range(len(gargalos))
        ]
    gargalos = gargalos.drop(columns="_score")
    return gargalos


def grafico_1_sla(df, outdir, sla_minutes, meta_pct=90):
    pct = (100 * df.groupby("tipo_exame")["dentro_sla"].mean()).round(1)
    pct = pct.reindex([t for t in TIPOS_EXAME_ORDEM if t in pct.index])
    cores = [cor_por_pct(v, meta_pct) for v in pct.values]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(pct.index, pct.values, color=cores)
    ax.axhline(meta_pct, linestyle="--", color="gray", linewidth=1)
    ax.set_ylim(0, 100)
    ax.set_ylabel(f"% dentro do SLA de {sla_minutes // 60}h")
    pior = pct.idxmin() if len(pct) else "?"
    pior_val = pct.min() if len(pct) else 0
    ax.set_title(f"{100 - pior_val:.0f}% dos {pior} violam o SLA de {sla_minutes // 60}h")
    fig.tight_layout()
    fig.savefig(outdir / "grafico_1_sla.png", dpi=150)
    plt.close(fig)


def grafico_2_etapas(df, outdir):
    etapas = ["fila_para_leitura_min", "leitura_min"]
    rotulos = ["Fila p/ leitura", "Leitura"]
    tempos = [df[c].mean() for c in etapas]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh(rotulos, tempos, color="#1565C0")
    for i, v in enumerate(tempos):
        ax.text(v, i, f" {v:.0f} min", va="center")
    ax.set_xlabel("Tempo medio (min)")
    etapa_gargalo = rotulos[int(np.argmax(tempos))] if tempos else "?"
    ax.set_title(f"Maior tempo de espera esta em: {etapa_gargalo}")
    fig.tight_layout()
    fig.savefig(outdir / "grafico_2_etapas.png", dpi=150)
    plt.close(fig)


def grafico_3_heatmap(df, outdir):
    d = df.dropna(subset=["data_hora_disponivel_leitura"]).copy()
    if not len(d):
        return
    d["hora"] = d["data_hora_disponivel_leitura"].dt.hour
    d["dia_semana"] = d["data_hora_disponivel_leitura"].dt.dayofweek
    dias_pt = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]

    matriz = np.zeros((7, 24))
    contagem = d.groupby(["dia_semana", "hora"]).size()
    for (dia, hora), n in contagem.items():
        matriz[int(dia), int(hora)] = n

    fig, ax = plt.subplots(figsize=(9, 4))
    im = ax.imshow(matriz, cmap="Reds", aspect="auto")
    ax.set_xticks(range(24))
    ax.set_xticklabels(range(24), fontsize=7)
    ax.set_yticks(range(7))
    ax.set_yticklabels(dias_pt)
    fig.colorbar(im, ax=ax, label="Exames disponibilizados p/ leitura")
    pico_dia, pico_hora = np.unravel_index(np.argmax(matriz), matriz.shape)
    ax.set_title(
        f"Pico de demanda: {dias_pt[pico_dia]} as {pico_hora}h"
        if matriz.max() > 0
        else "Sem dados suficientes para heatmap"
    )
    fig.tight_layout()
    fig.savefig(outdir / "grafico_3_heatmap.png", dpi=150)
    plt.close(fig)


def grafico_4_outliers(df, outdir):
    tipos = [t for t in TIPOS_EXAME_ORDEM if t in df["tipo_exame"].unique()]
    if not tipos:
        return
    grupos = [
        df.loc[df["tipo_exame"] == t, "tempo_ate_1a_analise_min"].dropna().values
        for t in tipos
    ]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.boxplot(grupos, tick_labels=tipos, showfliers=False)

    p90_por_tipo = df.groupby("tipo_exame")["tempo_ate_1a_analise_min"].transform(
        lambda s: s.quantile(0.9)
    )
    acima = df[df["tempo_ate_1a_analise_min"] > p90_por_tipo]
    for t in tipos:
        pts = acima.loc[acima["tipo_exame"] == t, "tempo_ate_1a_analise_min"]
        x = [tipos.index(t) + 1] * len(pts)
        ax.scatter(x, pts, color=VERMELHO, zorder=3, label="Acima do P90" if t == tipos[0] else None)
    ax.set_ylabel("Tempo ate 1a analise (min)")
    ax.set_title(f"{len(acima)} exames acima do P90 de tempo de resposta")
    if len(acima):
        ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "grafico_4_outliers.png", dpi=150)
    plt.close(fig)


def grafico_5_crises(df, outdir):
    if "numero_crises" not in df.columns or df["numero_crises"].isna().all():
        return
    if "unidade" not in df.columns:
        return
    tipos = [t for t in TIPOS_EXAME_ORDEM if t in df["tipo_exame"].unique()]
    unidades = [u for u in ["UTI", "enfermaria", "ambulatorio"] if u in df["unidade"].unique()]
    if not tipos or not unidades:
        return

    tabela = df.groupby(["tipo_exame", "unidade"])["numero_crises"].mean().unstack(
        fill_value=0
    )
    x = np.arange(len(tipos))
    largura = 0.8 / max(len(unidades), 1)

    fig, ax = plt.subplots(figsize=(7, 4))
    for i, unidade in enumerate(unidades):
        valores = [tabela.loc[t, unidade] if t in tabela.index and unidade in tabela.columns else 0 for t in tipos]
        ax.bar(x + i * largura, valores, width=largura, label=unidade)
    ax.set_xticks(x + largura * (len(unidades) - 1) / 2)
    ax.set_xticklabels(tipos)
    ax.set_ylabel("Crises medias por exame")
    unidade_top = tabela.mean(axis=0).idxmax() if len(tabela) else "?"
    ax.set_title(f"Maior carga de crises concentrada em: {unidade_top}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "grafico_5_crises.png", dpi=150)
    plt.close(fig)


def escrever_relatorio(outdir, kpis, outliers, gargalos, sla_minutes):
    linhas = []
    linhas.append("# Relatorio de Fluxo Operacional — Neurofisiologia (rascunho)\n")
    linhas.append(
        "> Gerado automaticamente por `analisar_fluxo_eeg.py`. Revise o framing "
        "clinico e a priorizacao antes de enviar — este e um rascunho, nao o "
        "entregavel final.\n"
    )

    linhas.append("## 1. Resumo Executivo\n")
    linhas.append(f"- {kpis['n_exames']} exames analisados, {kpis['pct_sla_geral']}% dentro do SLA de {sla_minutes // 60}h no geral.")
    for tipo, pct in kpis.get("pct_sla_por_tipo", {}).items():
        linhas.append(f"- **{tipo}**: {pct}% dentro do SLA ({100 - pct:.1f}% em violacao).")
    if len(gargalos):
        pior_etapa = gargalos.iloc[0]
        linhas.append(
            f"- Maior gargalo: **{pior_etapa['etapa']}**, {pior_etapa['tempo_medio_min']} min em media "
            f"(P90 {pior_etapa['tempo_p90_min']} min), volume {pior_etapa['volume']} exames."
        )
    n_alta = int((outliers["severidade"] == "Alta").sum()) if len(outliers) else 0
    linhas.append(f"- {n_alta} exames classificados como outlier de **severidade alta** (violam SLA e envolvem fator de risco clinico).")
    linhas.append("- Acoes recomendadas: ver secao 5.\n")

    linhas.append("## 2. Tabela de Outliers Operacionais\n")
    if len(outliers):
        cols_tabela = [c for c in ["exame_id", "tipo_exame", "unidade", "tempo_ate_1a_analise_min", "severidade"] if c in outliers.columns]
        linhas.append(outliers[cols_tabela].to_markdown(index=False))
    else:
        linhas.append("Nenhum outlier detectado com os critérios atuais.")
    linhas.append("")

    linhas.append("## 3. Tabela de Gargalos por Etapa\n")
    if len(gargalos):
        linhas.append(gargalos.to_markdown(index=False))
    else:
        linhas.append("Dados insuficientes para calcular gargalos por etapa.")
    linhas.append("")

    linhas.append("## 4. Graficos\n")
    linhas.append("Ver `grafico_1_sla.png` a `grafico_5_crises.png` nesta pasta. Descricoes de cada um em `references/graficos-dashboard.md` da skill.\n")

    linhas.append("## 5. Recomendacoes de Acao\n")
    linhas.append("_Preencher com base nos gargalos e outliers acima — nao generalizar sem checar se os dados sustentam a recomendacao._\n")

    (outdir / "relatorio.md").write_text("\n".join(linhas), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exames", required=True)
    ap.add_argument("--fluxo", required=True)
    ap.add_argument("--pacientes", default=None)
    ap.add_argument("--clinico", default=None)
    ap.add_argument("--outdir", default="saida")
    ap.add_argument("--sla-minutes", type=int, default=180)
    ap.add_argument(
        "--marco",
        default="auto",
        choices=["auto", "inicio", "fim"],
        help="Timestamp que inicia o relogio do SLA: 'auto' usa inicio para cEEG e fim para os demais.",
    )
    ap.add_argument("--meta-sla-pct", type=float, default=90.0)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = montar_dataset(args)
    kpis = calcular_kpis(df, args.sla_minutes)
    outliers = detectar_outliers(df, args.sla_minutes)
    gargalos = calcular_gargalos(df, args.sla_minutes)

    (outdir / "kpis.json").write_text(
        json.dumps(kpis, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    outliers.to_csv(outdir / "outliers.csv", index=False)
    gargalos.to_csv(outdir / "gargalos.csv", index=False)

    grafico_1_sla(df, outdir, args.sla_minutes, args.meta_sla_pct)
    grafico_2_etapas(df, outdir)
    grafico_3_heatmap(df, outdir)
    grafico_4_outliers(df, outdir)
    grafico_5_crises(df, outdir)

    escrever_relatorio(outdir, kpis, outliers, gargalos, args.sla_minutes)

    print(f"OK — saida em {outdir}/", file=sys.stderr)
    print(f"  KPIs: {outdir / 'kpis.json'}", file=sys.stderr)
    print(f"  Outliers: {outdir / 'outliers.csv'} ({len(outliers)} linhas)", file=sys.stderr)
    print(f"  Gargalos: {outdir / 'gargalos.csv'} ({len(gargalos)} linhas)", file=sys.stderr)
    print(f"  Relatorio: {outdir / 'relatorio.md'}", file=sys.stderr)


if __name__ == "__main__":
    main()
