# Formato do entregável

Use exatamente esta estrutura em markdown. `scripts/analisar_fluxo_eeg.py` gera um
`relatorio.md` já preenchido com os números reais nesse formato — trate-o como
rascunho a revisar (framing clínico, agrupamento de causas, priorização), não como
texto final para colar sem ler.

## 1. Resumo Executivo (até 5 bullets)

Cobrir, nessa ordem de prioridade:
- % de exames fora do SLA (por tipo e por unidade)
- Principal gargalo de tempo identificado
- Risco clínico potencial mais relevante (ex. "cEEG de UTI aguardando leitura > 3h em X% dos casos")
- 2–3 ações recomendadas de alto impacto

Cada bullet deve ter um número. "O SLA está sendo violado com frequência" não é
aceitável; "42% dos cEEGs de UTI violaram o SLA de 3h na última semana" é.

## 2. Tabela de Outliers Operacionais

| Exame_ID | Tipo | Unidade | Tempo até 1ª análise (min) | Limite SLA | Severidade | Comentário |
|----------|------|---------|----------------------------|------------|------------|------------|
| ... | ... | ... | ... | 180 | Alta/Média/Baixa | ... |

O comentário deve ser uma frase clínica/operacional, não uma repetição dos números já
nas outras colunas — é o espaço para dizer *por que* aquele caso importa.

## 3. Tabela de Gargalos por Etapa

| Etapa | Tempo Médio (min) | Tempo P90 (min) | Volume na Fila | Impacto no SLA | Prioridade |
|------|--------------------|-----------------|----------------|----------------|-----------|
| ...  | ...                | ...             | ...            | ...            | ...       |

Ordene por prioridade (maior tempo × maior volume primeiro).

## 4. Descrição dos 5 Gráficos

Para cada um dos cinco gráficos do dashboard (ver `graficos-dashboard.md`), inclua:
- **Título** (o título acionável usado no gráfico, não um nome genérico)
- **Tipo** (barras, heatmap, boxplot, etc.)
- **Variáveis** (o que está em cada eixo/cor)
- **Insight principal** (uma frase, o "e daí?")
- **Código exemplo**, se o usuário pedir para reproduzir ou ajustar o gráfico

## 5. Recomendações de Ação

Ações concretas e específicas ao que os dados mostraram — não genéricas. Exemplos do
tipo de recomendação esperada (adapte ao que os dados realmente indicarem, não copie
estes se não forem o que os dados suportam):
- Escalonar leitura de cEEG de UTI em horários de pico identificados no heatmap
- Criar fila prioritária para suspeita de estado de mal não convulsivo (NCSE)
- Ajustar escala de tecnólogos/médicos leitores nos horários/turnos críticos
- Revisar protocolo de duração para o tipo de exame com mais outliers de duração

## Princípios gerais

- Todo o documento em português (idioma de trabalho da equipe), a menos que pedido o
  contrário.
- Quantifique sempre — tempo, %, volume, impacto.
- Evite jargão técnico excessivo; quando necessário (NCSE, surto-supressão, etc.),
  explique em poucas palavras na primeira ocorrência.
- O documento inteiro deve ser lido e compreendido em poucos minutos — é para uso
  durante decisão clínica/gestora, não para leitura aprofundada depois.
