# Sample run — eval 1 (ebook-writer skill)

*This file simulates a single end-to-end Claude Code response to eval prompt #1, following the ebook-writer SKILL.md stage by stage. It stops after one full sample chapter, as instructed — it does not produce the complete 8,000–10,000 word manuscript.*

---

## Resposta simulada ao usuário

Ótimo tema — "renda variável" é uma dor muito específica e muito mal resolvida pelo conteúdo de finanças pessoais padrão, que quase sempre pressupõe salário fixo. Isso já dá ao livro uma tese clara, o que ajuda bastante.

### Etapa 1 — Confirmando o briefing

Pelo que você descreveu, entendi o seguinte — vou seguir com essas premissas e você me avisa se algo estiver errado:

- **Tema e ângulo:** não é "educação financeira" genérica, é especificamente sobre como organizar finanças pessoais *e* profissionais quando a renda varia mês a mês — com foco em sair do ciclo de "guardo reserva no mês bom, gasto tudo no mês ruim".
- **Público:** autônomos e freelancers brasileiros, 25–45 anos, profissões como design e consultoria, já familiarizados com o conceito de reserva de emergência mas que nunca conseguiram mantê-la. Ou seja: não preciso explicar o que é reserva de emergência do zero — o problema deles é execução, não desconhecimento.
- **Tom:** prático, direto, sem jargão de "finanças", tratamento "você" (não "tu"), sem tom de guru.

Duas coisas eu **não** tenho e vou assumir por padrão, mas quero confirmar antes da versão final:
1. **Objetivo do livro** (isca digital gratuita, produto pago, material de portfólio?) — isso muda se cabe um CTA no final e o tom da conclusão. Vou seguir sem CTA por enquanto e você me diz se quer um.
2. **Material próprio** — se você já tem alguma experiência, planilha, método ou casos reais de clientes/alunos que uses nas suas próprias finanças, isso é uma fonte melhor que qualquer busca genérica que eu faça. Se tiver algo, me manda antes de eu escrever os próximos capítulos.

Seguindo com isso, sem transformar em questionário — o briefing já é bom o suficiente para montar o esqueleto do livro.

### Etapa 2 — Pesquisa e verificação (o que chequei, e o que falta checar)

Fiz duas buscas reais para embasar o Capítulo 1 em vez de citar números de memória:

1. **Tamanho da força de trabalho por conta própria no Brasil** — segundo o IBGE (PNAD Contínua, dado divulgado em 2025), o país chegou a **26,1 milhões de trabalhadores por conta própria em 2025**, o maior nível da série histórica iniciada em 2012 (que começou em 20,0 milhões — alta de 30,4% no período). Uso isso no Capítulo 1 para normalizar o problema, com atribuição ao IBGE e ao ano.
   - Fonte: [Agência de Notícias IBGE — PNAD Contínua](https://agenciadenoticias.ibge.gov.br/agencia-sala-de-imprensa/2013-agencia-de-noticias/releases/45759-pnad-continua-em-2025-taxa-anual-de-desocupacao-foi-de-5-6-enquanto-taxa-de-subutilizacao-foi-14-5)
2. **Quantos meses de reserva se recomenda para renda variável** — várias fontes de educação financeira (XP, Creditas, CM Capital, MeuTudo) convergem numa faixa de **6 a 12 meses** de custos fixos para autônomos/MEI, contra 3–6 meses para CLT, com a justificativa de que autônomo não tem FGTS nem seguro-desemprego.
   - Fontes: [CM Capital](https://cmcapital.com.br/blog/reserva-de-emergencia-o-que-e-como-montar-a-sua/), [Creditas](https://www.creditas.com/exponencial/reserva-de-emergencia/), [MeuTudo](https://meutudo.com.br/blog/calculadoras/calculadora-de-reserva-de-emergencia/)
   - **Importante:** isso não é um número de um único estudo controlado, é uma convenção de mercado repetida por várias instituições financeiras/plataformas de conteúdo. Por isso, no texto eu atribuo como recomendação de "especialistas em educação financeira", uso a faixa (6–12), e não apresento como fato científico único — é exatamente a distinção fato/opinião/framework do `research-and-factchecking.md`.

**O que eu ainda não verifiquei e vou sinalizar em vez de inventar**, conforme os capítulos forem sendo escritos:
- Valores atuais do DAS-MEI, faixas do Simples Nacional e tabela do Carnê-Leão/IRPF — mudam por ano-calendário; para o Capítulo 8 ("Impostos sem susto") vou precisar buscar os valores vigentes em 2026 antes de publicar, e vou marcar claramente que o leitor deve confirmar com um contador porque a regra pode mudar.
- Taxas de rendimento específicas de Tesouro Selic/CDB — são sensíveis ao momento; no capítulo sobre onde guardar a reserva, vou falar em termos de liquidez e tipo de produto, não em número de rentabilidade, para o texto não ficar desatualizado em pouco tempo.
- Qualquer alegação sobre comportamento/psicologia do gasto ("pessoas gastam X% mais quando...") — não vou usar nada assim sem achar uma fonte real; se não achar, reformulo sem depender do número.

Nada disso trava o rascunho do outline ou do Capítulo 1 abaixo — só está sinalizado aqui para não esquecer antes de fechar o manuscrito completo.

### Etapa 3 — Título e sumário (com a conta de palavras)

**Título:** *Mês Sim, Mês Não*
**Subtítulo:** *Como organizar as finanças quando sua renda de autônomo varia todo mês — um método prático para finalmente construir (e manter) sua reserva de emergência*

**Conta de tamanho, feita antes de escrever qualquer capítulo:**

```
Meta: 30–35 páginas × ~275 palavras/página ≈ 8.250–9.625 palavras de conteúdo
Menos: introdução (~500 palavras) + conclusão (~500 palavras)
Sobra: ~7.250–8.625 palavras distribuídas nos capítulos
÷ 10 capítulos ≈ 725–860 palavras por capítulo
```

Dez capítulos couberam bem dentro da faixa de 600–1.000 palavras por capítulo recomendada — não precisei forçar nem cortar o tema para caber na conta. Ordenação: padrão **problema → framework → aplicação**, com o capítulo de maior risco de precisar de ajuste (o "salário que você paga a si mesmo", que é a ideia central do livro) posicionado cedo, no Capítulo 3, para pegar seu feedback antes de construir os capítulos seguintes em cima dele.

| # | Capítulo | Ideia central | O que o leitor leva |
|---|---|---|---|
| — | **Introdução** (~500 palavras) | Por que este livro existe e para quem é | Sabe se o método é pra ele antes de investir tempo |
| 1 | O problema não é falta de disciplina, é o método | Reformula o "fracasso" como erro de método, não de caráter | Para de se culpar e entende o que vem pela frente |
| 2 | Mapeie seu padrão: mês bom, mês médio, mês fraco | Olhar os últimos 6–12 meses de recebimentos reais | Sabe, com números próprios, qual é seu "mês ruim" típico |
| 3 | O salário que você paga a si mesmo | O framework central: um piso fixo de retirada, não uma % da renda do mês | Entende a mecânica que substitui "guardar a sobra" |
| 4 | PF, MEI ou PJ: separando a pessoa da atividade | Contas separadas e pró-labore, mesmo sem CNPJ formal | Sabe como estruturar o dinheiro entrando, de forma prática |
| 5 | Construindo a reserva sem se sabotar | Quanto guardar e em que ordem de prioridade frente a outras dívidas/metas | Tem um plano de aporte que sobrevive ao mês ruim |
| 6 | Onde guardar (e por que liquidez importa mais que rendimento aqui) | Critérios para escolher onde deixar a reserva | Evita travar a reserva em algo que não resgata rápido |
| 7 | Os dois colchões: reserva pessoal x caixa do negócio | Por que autônomo precisa de duas reservas, não uma | Para de misturar imprevisto pessoal com capital de giro |
| 8 | Impostos sem susto | Separar o que não é seu antes de gastar (DAS, Simples, Carnê-Leão) | Não é pego de surpresa na hora de pagar imposto |
| 9 | Precificando para sobreviver ao mês ruim | Embutir a variação de renda no preço cobrado | Cobra um preço que já contempla os meses fracos |
| 10 | O ritual de 15 minutos por mês | Rotina mínima de revisão que mantém o sistema funcionando | Sai do livro com um hábito, não só com teoria |
| — | **Conclusão** (~500 palavras) | Sintetiza a virada central (guardar sobra → se pagar salário fixo) | Sabe qual é a única coisa para lembrar se esquecer o resto |

Antes de eu escrever os capítulos 2–10 na íntegra: esse sumário faz sentido pra você, ou algum capítulo deveria entrar/sair/mudar de ordem? Também vale confirmar aqui se você tem material próprio (mencionado na Etapa 1) que devesse substituir algum exemplo genérico que eu vá usar.

Abaixo, o Capítulo 1 completo, como amostra do tom e do nível de detalhe que os demais capítulos vão seguir.

---

## Capítulo 1 — O problema não é falta de disciplina, é o método

Marina trabalha com design há sete anos. Em outubro, ela fechou três projetos novos, recebeu um bônus de um cliente satisfeito e, pela primeira vez em meses, sobrou dinheiro de verdade no fim do mês. Ela fez o que qualquer conteúdo sobre finanças pessoais manda fazer: separou uma parte generosa para a reserva de emergência e se sentiu, enfim, no controle. Três meses depois, em janeiro, dois clientes sumiram, um projeto grande atrasou o pagamento e a fatura do cartão chegou do mesmo tamanho de sempre. A reserva que ela tinha construído com tanto orgulho virou capital de giro disfarçado — e sumiu em três semanas. Em fevereiro, ela recomeçou do zero. De novo.

Se essa história soa familiar, não é coincidência — nem falha de caráter. (Marina é uma composição de situações comuns entre autônomos brasileiros, não uma pessoa real, mas o padrão é muito real.) Segundo o IBGE, o Brasil chegou a 26,1 milhões de trabalhadores por conta própria em 2025, o maior número da série histórica iniciada em 2012 — um universo enorme de gente tentando encaixar renda instável em conselhos financeiros pensados para quem recebe salário fixo todo dia 5.

### Por que o conselho padrão não funciona pra você

Quase todo guia de finanças pessoais parte de uma premissa que, para quem tem carteira assinada, é invisível de tão óbvia: você sabe quanto vai entrar mês que vem. A partir dessa certeza, nascem conselhos como "guarde 10% do salário" ou "divida suas despesas em categorias de 50-30-20". É uma matemática limpa quando o numerador — sua renda — é fixo.

Para quem vive de projeto, cliente e nota fiscal avulsa, esse numerador varia — e não pouco: às vezes o dobro num mês, um terço no outro. Aplicar uma regra pensada para renda fixa numa renda que oscila é como tentar seguir um mapa de estrada feito para velocidade constante enquanto seu carro acelera e freia sem aviso. O mapa não está errado. Ele só foi desenhado para outra viagem.

### Não, o problema não é falta de ferramenta

Talvez você já tenha tentado planilha, aplicativo, o método dos potes, ou lido todos os livros de finanças mais vendidos. Se nada disso pegou, o problema provavelmente não é você, nem a ferramenta — é que a maioria delas também assume um fluxo de entrada regular por baixo do capô. Um aplicativo automatiza um cálculo; ele não corrige a pergunta que está sendo feita.

### O ciclo que mantém você travado

O padrão costuma ter três etapas:

1. **Mês bom** — você guarda uma quantia generosa, muitas vezes mais do que consegue sustentar, porque parece "hora de compensar".
2. **Mês ruim** — a reserva vira a fonte de dinheiro mais fácil de acessar, porque, tecnicamente, é sua.
3. **Culpa e reinício** — você se sente em falta, promete ser mais disciplinado e recomeça do zero sem nunca mudar o método que gerou o ciclo.

Especialistas em educação financeira costumam recomendar de 6 a 12 meses de custos fixos guardados para quem tem renda variável — mais que os 3 a 6 meses sugeridos para quem tem carteira assinada, já que o autônomo não conta com FGTS nem seguro-desemprego como colchão adicional. É uma referência útil para saber até onde ir. Não é o motivo pelo qual você ainda não consegue nem começar.

O custo de repetir esse ciclo não é só o dinheiro perdido. É a decisão que você toma sob pressão no mês ruim — aceitar um projeto mal pago porque precisa fechar a conta, atrasar o próprio pagamento de imposto, ou simplesmente evitar abrir o extrato. Cada rodada do ciclo ensina, sem querer, que guardar dinheiro "não funciona pra você" — quando na verdade é o método que não funciona para o seu tipo de renda.

### O verdadeiro obstáculo

Você não trava por falta de força de vontade. Trava porque tenta guardar a "sobra" de um sistema que não tem sobra estável — tem picos e vales. Um sistema pensado para renda variável não parte de quanto sobrou no fim do mês; parte de quanto você precisa para viver, independentemente do que entrou naquele mês específico. É essa virada — de "guardar o que sobra" para "se pagar um salário fixo, não importa a fonte" — que este livro constrói passo a passo, começando no próximo capítulo com o mapeamento do seu próprio padrão de renda.

### Para lembrar

O problema nunca foi o seu comprometimento — foi tentar rodar um sistema de renda fixa numa realidade de renda variável. No Capítulo 2, você vai olhar para os últimos 6 a 12 meses de recebimentos e descobrir, com números reais, qual é o seu mês ruim típico: a base sobre a qual todo o resto deste método é construído.

---

*(760 palavras — dentro da faixa de 725–860 palavras/capítulo calculada na Etapa 3; nenhum ajuste de tamanho necessário.)*

### Próximos passos

1. Você confirma o sumário (ou ajusta ordem/capítulos) e me diz se tem material próprio a incorporar.
2. Eu escrevo os capítulos 2 a 10 um de cada vez, sempre conferindo contagem de palavras contra os 725–860 do orçamento, e paro para seu feedback a cada poucos capítulos em vez de entregar tudo de uma vez.
3. Antes de fechar o manuscrito, faço uma revisão completa (Etapa 5 do processo): confiro se toda alegação ainda bate com o que verifiquei, se os termos são consistentes entre capítulos, se não sobrou nenhum parágrafo denso demais, e se o total ainda está entre 8.000–10.000 palavras.
4. Quando você aprovar o manuscrito final, eu não formato o livro aqui — repasso para a skill `docx` (ou `pdf`) para gerar o arquivo final com capa, sumário navegável e um heading por capítulo, e conferimos a contagem real de páginas depois da formatação (pode exigir ajuste de margem/fonte, não necessariamente reescrever texto).

---

## Notas do avaliador (não faz parte da resposta simulada ao usuário)

Ver relatório enviado ao usuário que pediu este teste para a avaliação da skill (clareza do SKILL.md, qualidade do outline, qualidade do Capítulo 1, sugestões de melhoria).
