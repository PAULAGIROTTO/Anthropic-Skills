# Os 5 gráficos do dashboard executivo

Regra dura: **no máximo 5 gráficos**. Cada um precisa de um título que já responde
"e daí?" (ex. "35% dos cEEGs de UTI excedem o SLA de 3h", não "SLA por tipo de exame"),
e cada um precisa ligar diretamente a uma decisão clínica ou operacional — se você não
consegue dizer em uma frase o que alguém faz de diferente depois de ver o gráfico, ele
não deveria estar nos cinco.

`scripts/analisar_fluxo_eeg.py` já gera esses cinco automaticamente a partir dos dados;
o código abaixo é para referência/ajuste manual, não para reescrever do zero.

## Convenção de cor (vale para os 5 gráficos)

Nesse dashboard a cor comunica **status**, não categoria — é uma exceção deliberada à
prática usual de paletas categóricas neutras, porque o objetivo aqui é deixar alguém
triar por cor sozinho, sem ler número nenhum.

- Verde `#2E7D32` — dentro da meta/SLA
- Amarelo `#F9A825` — limítrofe (dentro de ~10% da meta)
- Vermelho `#C62828` — violação clara de SLA ou risco alto

Onde fizer sentido, desenhe uma linha horizontal tracejada marcando a meta (ex. 90% de
cumprimento de SLA) para que o desvio salte aos olhos sem precisar ler o eixo.

## 1. Cumprimento do SLA de 3h por tipo de exame

- **Tipo:** barras
- **Eixo X:** tipo_exame (aEEG, VEEG 12h, cEEG, EEG 2h)
- **Eixo Y:** % de exames dentro do SLA
- **Cor:** verde/amarelo/vermelho pela própria taxa de cumprimento
- **Linha de meta:** 90% (ajustável)
- **Insight:** qual modalidade mais viola o SLA — normalmente cEEG, por ser o mais
  volumoso e crítico.

```python
import matplotlib.pyplot as plt

def cor_sla(pct, meta=90):
    if pct >= meta:
        return "#2E7D32"
    if pct >= meta - 10:
        return "#F9A825"
    return "#C62828"

fig, ax = plt.subplots(figsize=(6, 4))
cores = [cor_sla(p) for p in pct_sla_por_tipo.values]
ax.bar(pct_sla_por_tipo.index, pct_sla_por_tipo.values, color=cores)
ax.axhline(90, linestyle="--", color="gray", linewidth=1)
ax.set_ylabel("% dentro do SLA de 3h")
ax.set_title(titulo_que_ja_responde_e_dai)  # gerado a partir dos próprios dados
```

## 2. Distribuição do tempo total de processamento por etapa

- **Tipo:** barras empilhadas (ou waterfall se a biblioteca disponível suportar bem)
- **Eixo X:** etapa (fila_para_leitura, leitura, laudo)
- **Eixo Y:** tempo médio em minutos
- **Dimensão opcional:** cor por tipo_exame ou unidade, se ajudar a comparar
- **Insight:** onde o tempo realmente se acumula no fluxo — normalmente não é a leitura
  em si, é a fila de espera antes dela.

```python
etapas = ["fila_para_leitura", "leitura", "laudo"]
tempos = [tempo_medio[e] for e in etapas]
fig, ax = plt.subplots(figsize=(6, 4))
ax.barh(etapas, tempos, color="#1565C0")
ax.set_xlabel("Tempo médio (min)")
```

## 3. Heatmap de fila e carga de exames ao longo do tempo

- **Tipo:** heatmap
- **Eixo X:** hora do dia (0–23)
- **Eixo Y:** dia da semana
- **Valor:** número de exames em fila/execução naquele intervalo
- **Insight:** horários críticos para dimensionar equipe — tipicamente noite e
  madrugada, quando o volume de UTI continua mas a equipe de leitura é menor.

```python
import numpy as np
fig, ax = plt.subplots(figsize=(8, 4))
im = ax.imshow(matriz_hora_x_dia, cmap="Reds", aspect="auto")
ax.set_xticks(range(24)); ax.set_xticklabels(range(24))
ax.set_yticks(range(7)); ax.set_yticklabels(dias_semana_pt)
fig.colorbar(im, ax=ax, label="Exames em fila")
```

## 4. Outliers de tempo de resposta (por exame)

- **Tipo:** boxplot ou scatter, um ponto por exame
- **Eixo X:** tipo_exame (ou unidade)
- **Eixo Y:** tempo até 1ª análise (min)
- **Destaque:** pontos acima do P90 em vermelho, com um marcador diferente
- **Insight:** casos individuais que merecem revisão de processo — é o único dos cinco
  gráficos que aponta para exames específicos, não para uma média.

```python
fig, ax = plt.subplots(figsize=(6, 4))
ax.boxplot([grupo[col].values for _, grupo in df.groupby("tipo_exame")],
           tick_labels=tipos_exame, showfliers=False)
outliers = df[df["tempo_ate_1a_analise"] > df.groupby("tipo_exame")["tempo_ate_1a_analise"].transform(lambda s: s.quantile(0.9))]
ax.scatter(outliers["tipo_exame_x"], outliers["tempo_ate_1a_analise"], color="#C62828", zorder=3, label="Acima do P90")
```

## 5. Carga de crises detectadas por tipo de exame e unidade

- **Tipo:** barras agrupadas
- **Eixo X:** tipo_exame
- **Eixo Y:** número médio de crises por exame
- **Cor:** unidade (UTI, enfermaria, ambulatório)
- **Insight:** onde a severidade clínica se concentra — geralmente justifica priorizar
  recursos de leitura para UTI mesmo quando o volume bruto é menor que ambulatório.

```python
import numpy as np
larg = 0.25
x = np.arange(len(tipos_exame))
fig, ax = plt.subplots(figsize=(7, 4))
for i, unidade in enumerate(["UTI", "enfermaria", "ambulatorio"]):
    ax.bar(x + i * larg, crises_media[unidade], width=larg, label=unidade)
ax.set_xticks(x + larg); ax.set_xticklabels(tipos_exame)
ax.legend()
```

## Anotações

Onde os dados suportarem, anote diretamente no gráfico (não só na legenda):
- O turno/unidade com pior desempenho (ex. seta ou texto apontando a barra da UTI no
  gráfico 1 se for o pior).
- Pontos de melhora após uma intervenção conhecida (ex. linha vertical na data em que a
  escala noturna mudou, se o usuário mencionar esse contexto).
