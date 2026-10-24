Edited REGISTRO_PROMPTS_PINA.md

*(Registrado como `PINA-0001` no seu [`docs/REGISTRO_PROMPTS_PINA.md`](file:///c:/Users/leand/Documentos/kanastra-project/docs/REGISTRO_PROMPTS_PINA.md)!)*

Cara, essa sua ideia do **Leitor de Nota Fiscal (DANFE) pela câmera direto no navegador Web (sem precisar baixar app)** é **MUITO BOA**!

Vou te explicar por que ela encaixa como uma luva no desafio da Kanastra e listar **os 5 melhores diferenciais (UX + Arquitetura)** para vocês colocarem no final do projeto e destruírem no Pitch:

---

### 1. Sua Ideia: Scanner Web de Nota Fiscal / Duplicata pela Câmera (Sem App!)
- **Onde pontua no edital:** Item **5.2.2 — Design e UX (25 pontos)**: *"clareza das mensagens de recusa, design, **criatividade** e interface"*.
- **Como funciona na prática (e por que é fácil de fazer em React):**
  - Na arquitetura do Carlos, já vai existir o endpoint `POST /api/receivables/evaluate` (que avalia **1 recebível individual** em tempo real).
  - Na tela de "Simular Nota Individual", a gente coloca um botão **"📷 Escanear DANFE / Nota Fiscal pela Câmera"** (usando a API nativa do navegador `navigator.mediaDevices.getUserMedia` + leitor de código de barras/QR Code ou OCR leve no navegador, além de aceitar arrastar uma foto/PDF/XML de NF-e).
  - Quando você aponta a webcam do notebook (ou a câmera do celular abrindo o link da Vercel!) para uma Nota Fiscal na frente dos jurados da Kanastra, ele lê os dados automaticamente, preenche o CNPJ do Cedente, CNPJ do Sacado, Número, Valor e Vencimento, e **já diz na hora na tela se o fundo ANTECIPE FIDC aprova ou recusa e quanto paga de Valor Líquido (já descontando os 2% ao mês)**!
  - **No Pitch de 5 minutos:** Fazer isso ao vivo na frente da banca da Kanastra tem um "efeito UAU" absurdo porque nenhuma outra equipe vai pensar nisso!

---

### 2. Outros 4 Diferenciais Fortíssimos (Arquitetura + Negócio Kanastra)

Para colocar na reta final depois que o básico (100k/500k linhas) estiver rodando redondo:

#### 🔥 Diferencial A: Simulador "What-If" (E se?) de Regras em Tempo Real
- **O que é:** Na tela onde o gestor do fundo altera as regras do `validadores_antecipe.json` (por exemplo: mudar o limite de concentração por sacado de **10% para 15%**, ou ligar a regra inativa `PRAZO_MINIMO` de 30 dias), antes mesmo de salvar, ele clica em **"Simular Impacto no Lote"**.
- **O que aparece na tela:** Um comparativo instantâneo:
  > *"Com a Regra v1 (Concentração 10%): **1.200 recusadas** | Volume Aprovado: **R$ 4,2M**"*
  > *"Com a Nova Regra v2 (Concentração 15%): **+310 notas passam a ser aprovadas** | Novo Volume: **R$ 5,8M (+R$ 1,6M liberados)**"*
- **Por que a banca da Kanastra vai pirar:** Isso é exatamente o trabalho diário de um gestor de FIDC na Kanastra (calibrar risco vs. retorno da carteira)!

#### 🏢 Diferencial B: Card de "Raio-X do Grupo Econômico (`RAIZ_CNPJ`)" nas Recusas
- **O que é:** Como a pegadinha real do CSV da Kanastra é que o limite de 10% de concentração é calculado pelos **8 primeiros dígitos do CNPJ (`RAIZ_CNPJ`)** — e a raiz `58206002` já tem **3 CNPJs diferentes (matriz e filiais)** que juntos somam **R$ 6,63 milhões (12,5% do fundo ANTECIPE FIDC)** —, quando uma nota for recusada por concentração, a mensagem de recusa mostra um **gráfico/barra visual do Grupo Econômico**:
  - Mostra quanto cada filial daquele grupo (`0001-11`, `0002-...`, `0003-...`) já consumiu do fundo e quanto falta para voltar abaixo dos 10%.
- **Onde pontua:** Garante nota máxima nos **25 pontos de Clareza das Mensagens de Recusa** e mostra pros jurados que vocês dominaram a pegadinha dos dados reais!

#### ⚡ Diferencial C: Botão "Simular Ataque de Concorrência (Race Condition Live)"
- **O que é:** Um botão na tela (ou aba de Auditoria Técnica) chamado **"Testar Proteção Anti-Duplicidade Simultânea"**.
- **O que ele faz:** Dispara **10 requisições simultâneas no mesmo milissegundo** tentando comprar a exata mesma parcela (`DOC_CEDENTE + DOC_SACADO + TIPO + NU_DOCUMENTO + VENCIMENTO`).
- **O que mostra na tela:** Um painel visual mostrando **1 requisição com status `201 Adquirida com Sucesso`** e **9 requisições bloqueadas com `409 Conflict — Duplicidade bloqueada por Lock Transacional`**!
- **Por que é genial:** Prova ao vivo para os engenheiros da Kanastra que a proteção em 3 níveis (Estoque + Unique Constraint + Transação Atômica) funciona de verdade.

#### 🐧 Diferencial D: Dual-Engine Unix (CLI Pipeable + Web API no mesmo Motor)
- **O que é:** Para cravar os **20 pontos de Filosofia Unix** e os **35 pontos de Escalabilidade (100k a 500k linhas)**, o motor de regras em Python funciona tanto chamado pelo site (FastAPI) quanto direto no terminal estilo Linux/Unix:
  ```bash
  python -m backend.cli --input lote_500k.csv --rules validadores_antecipe.json --output resultado.csv
  ```
- **Por que é essencial:** Além de cumprir 100% a Filosofia Unix, permite que o script `scripts/benchmark.py` do Carlos rode os testes de 100 mil e 500 mil linhas automaticamente e gere o relatório oficial de velocidade em `docs/EVIDENCIAS.md`!

---

### Qual a estratégia perfeita para você agora?
Comenta com o Carlos e o Elias sobre:
1. O **Scanner de Nota Fiscal pela câmera na Web** (pra tela de simulação individual).
2. O **Raio-X da Raiz do CNPJ (`58206002`)** na mensagem de recusa.
3. O **Simulador What-If de alteração de regras**.

E assim que o Carlos definir qual parte fica com você agora, é só me dar o comando que a gente já começa a codar!