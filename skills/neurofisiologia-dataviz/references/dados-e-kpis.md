# Dados esperados, KPIs e regras de outlier/gargalo

## Esquema de dados esperado

Os dados chegam tipicamente em até quatro tabelas (arquivos `.txt`/`.csv` delimitados),
que podem vir separadas ou já unidas em uma única planilha. Nem toda análise terá as
quatro — trabalhe com o que houver e deixe claro no resumo executivo o que ficou de fora.

### 1. Nível paciente (`pacientes.txt`)
| Coluna | Descrição |
|---|---|
| `id_paciente` | Identificador único do paciente |
| `unidade` | `UTI`, `enfermaria` ou `ambulatorio` |
| `diagnostico_principal` | Texto livre ou código |
| `risco_neurologico` | `baixo` / `moderado` / `alto` (se disponível) |

### 2. Nível exame (`exames.txt`)
| Coluna | Descrição |
|---|---|
| `exame_id` | Identificador único do exame |
| `id_paciente` | Chave para juntar com pacientes |
| `tipo_exame` | `aEEG`, `VEEG12h`, `cEEG`, `EEG2h` |
| `data_hora_inicio` | Início da gravação |
| `data_hora_fim` | Fim da gravação |

`duracao_min = data_hora_fim - data_hora_inicio`, em minutos. Durações muito fora do
protocolo esperado (aEEG/EEG2h ≈ 2h; VEEG12h ≈ 12h; cEEG variável e potencialmente
multi-dia) são elas mesmas um outlier a checar — não são datas quebradas, podem indicar
interrupção de gravação, evento técnico ou paciente que saiu do plantão.

### 3. Nível fluxo (`fluxo.txt`)
| Coluna | Descrição |
|---|---|
| `exame_id` | Chave |
| `data_hora_disponivel_leitura` | Quando o exame ficou pronto para leitura |
| `data_hora_inicio_leitura` | Quando um leitor começou a revisar |
| `data_hora_conclusao_relatorio` | Quando o laudo foi liberado |

### 4. Nível clínico (`clinico.txt`)
| Coluna | Descrição |
|---|---|
| `exame_id` | Chave |
| `presenca_crises` | sim/não |
| `numero_crises` | inteiro |
| `tipo_crise` | texto |
| `padrao_de_fundo` | texto |
| `grau_encefalopatia` | texto/escala |
| `eventos_criticos_marcados` | sim/não — se eventos críticos foram marcados a tempo |

## Definindo o marco do SLA de 3h — decisão importante

O enunciado "análise inicial dentro de 3h" é ambíguo até você fixar de qual timestamp o
relógio começa a contar, e a escolha certa **depende da modalidade**:

- **aEEG, VEEG 12h, EEG 2h** (exames com fim definido, lidos depois de prontos): o
  relógio deveria começar em `data_hora_fim` (fim da gravação) — é quando o exame
  realmente fica disponível para leitura completa.
- **cEEG** (monitorização contínua em UTI): a leitura deve acontecer *durante* a
  gravação, não depois — clinicamente, o que importa é que alguém revise as primeiras
  horas rapidamente para não perder um estado de mal não convulsivo em andamento. Aqui
  o relógio deveria começar em `data_hora_inicio`.

O script (`scripts/analisar_fluxo_eeg.py`) implementa isso via `--marco`, com um default
sensato por tipo de exame, mas **confirme com o usuário qual convenção o serviço já usa**
antes de reportar uma taxa de SLA — é o tipo de decisão que muda o número que a gestão vê,
então vale a pena uma frase de confirmação em vez de assumir silenciosamente.

`tempo_ate_1a_analise = data_hora_inicio_leitura - marco`

## KPIs principais

- **% dentro do SLA de 3h** — por tipo de exame e por unidade.
- **Tempo médio de fluxo por etapa**:
  - `fila_para_leitura = data_hora_inicio_leitura - data_hora_disponivel_leitura`
  - `leitura = data_hora_conclusao_relatorio - data_hora_inicio_leitura`
  - `total_ate_laudo = data_hora_conclusao_relatorio - marco`
- **Taxa de crises detectadas** — crises por exame, por tipo de exame.
- **Distribuição de exames por unidade** — volume e mix UTI / enfermaria / ambulatório.

Reporte médias **e** medianas/P90 — tempos de fluxo hospitalar são tipicamente
assimétricos (poucos casos muito longos puxam a média), então a mediana costuma
representar melhor "o caso típico" e o P90 é o que você usa para definir outliers.

## Regras de outlier

Um exame é outlier operacional se qualquer um destes for verdadeiro:

1. `tempo_ate_1a_analise` acima do **P90** daquele tipo de exame (calculado sobre o
   próprio dataset — não um número fixo, porque o volume normal varia por serviço).
2. `numero_crises` muito acima da média para aquele tipo de exame/perfil (o script usa
   IQR: acima de `Q3 + 1.5*IQR` dentro do grupo `tipo_exame`).
3. `duracao_min` muito fora do protocolo esperado da modalidade.

### Classificação de severidade

| Severidade | Critério |
|---|---|
| **Alta** | Viola o SLA de 3h **e** (unidade = UTI **ou** risco_neurologico = alto **ou** suspeita de encefalopatia/crises marcadas incorretamente) |
| **Média** | Viola o SLA de 3h, mas sem os fatores de risco acima — ou está acima do P90 sem violar o SLA |
| **Baixa** | Outlier estatístico (ex. duração atípica) sem violação de SLA nem fator de risco clínico |

A lógica por trás disso: o mesmo atraso de fluxo tem impacto muito diferente dependendo
de quem é o paciente. Um EEG 2h ambulatorial atrasado é um problema de processo; um cEEG
de UTI atrasado num paciente de alto risco é um problema clínico. A tabela de outliers
deve deixar isso óbvio à primeira vista, não exigir que alguém cruze colunas mentalmente.

## Regras de gargalo (bottleneck)

Para cada etapa do fluxo (`fila_para_leitura`, `leitura`, `laudo`), calcule:
- Tempo médio e P90
- Volume de exames que passaram por ali (proxy de carga)
- `% fora do SLA atribuível a essa etapa` — a etapa cujo tempo médio mais se aproxima do
  total do atraso é a que mais "consome" o orçamento de 3h

A etapa com maior tempo médio **e** maior volume é a de maior prioridade — tempo alto
com volume baixo pode ser só ruído de poucos casos raros; tempo alto com volume alto é
um gargalo estrutural que vale redistribuir recursos para resolver.
