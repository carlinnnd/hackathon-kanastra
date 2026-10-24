# Registro cronológico de prompts — ELIAS

Histórico cronológico dos prompts executados por **ELIAS** durante o Hackathon Kanastra, acompanhados da descrição técnica do que foi feito com cada resposta, arquivos alterados e verificação, para consolidação final em `docs/REGISTRO_PROMPTS.md`.

---

## ELIAS-0001 — 2026-10-24T12:05:16-03:00 — antigravity

- **Prompt enviado:**

```text
Analise os prompts do Pina e foque espeficiamente na ideia do scanner web de nota fiscal, vou te dar o contexto e também os arquivos referentes ao nosso projeto.
Quero que você me ajude a pensar na arquitetura e aplicação dessa ideia do scanner no nosso projeto (no momento quero apenas pensar na ideia, não implemente nada ainda)

(Não esqueça de salvar esse prompt na minha parte  -  registros prompts  ELias)

[Contexto arquitetural anexado: Monólito modular React + FastAPI + PostgreSQL para o ANTECIPE FIDC, motor de regras Strategy/Registry baseado em validadores_antecipe.json (7 regras ativas, 2 inativas, desconto simples 2% a.m. base 30 dias, data-base 22/10/2026) e análise do estoque_antecipe.csv (100.554 registros, chave por parcela com vencimento, concentração por RAIZ_CNPJ).]
```

- **Resumo da resposta e análise técnica:**
  Concepção arquitetural e funcional do **Scanner Web de Nota Fiscal (DANFE / NF-e)** integrado ao monólito modular do `ANTECIPE FIDC`, sem implementação de código nesta etapa:
  1. **Mapeamento de Domínio (DANFE $\rightarrow$ Contrato do Estoque):** Correlação entre campos da Nota Fiscal (Emitente = `DOC_CEDENTE`/`NOME_CEDENTE`, Destinatário = `DOC_SACADO`/`NOME_SACADO`, Número = `NU_DOCUMENTO`, Quadro Fatura/Duplicatas = múltiplas parcelas com `DATA_VENCIMENTO_ORIGINAL` e `VALOR_NOMINAL`) e a descoberta de parcelas no estoque real (`estoque_antecipe.csv`).
  2. **Limitação da Chave de 44 Dígitos e Arquitetura Multimodal em 3 Camadas:** Demonstração de que o código de barras 1D da DANFE (44 dígitos) contém apenas `DOC_CEDENTE` e `NU_DOCUMENTO` (sem sacado, valor ou vencimento), exigindo uma captura híbrida no navegador:
     - *Camada 1 (Câmera WebRTC):* Leitura de Código de Barras 1D (44 dígitos com validação Módulo 11) + QR Code de Duplicata/DANFE + OCR assistido do quadro de Destinatário e Duplicatas.
     - *Camada 2 (Upload Estruturado no Scanner):* Leitura client-side de XML de NF-e (`<emit>`, `<dest>`, `<dup>`) ou PDF de DANFE com extração determinística de todas as parcelas.
     - *Camada 3 (Modo Demo para Banca):* Galeria de DANFEs/QR Codes de teste baseados em casos reais do `ANTECIPE FIDC` (ex.: nota parcelada, sacado da raiz `58206002` que já concentra 12,5%, duplicidade no estoque).
  3. **Aderência aos Critérios do Edital:**
     - *Filosofia Unix (20 pts):* Scanner como puro **Adaptador de Entrada** client-side que alimenta um formulário de revisão (*Human-in-the-Loop*) e envia o contrato canônico para `POST /api/receivables/evaluate`, sem duplicar regras no React.
     - *UX e Mensagens de Recusa (25 pts):* Feedback visual por parcela escaneada com explicação clara de recusa e próximo passo.
     - *Logs e Segurança (15 pts):* Processamento óptico no navegador (sem enviar imagem bruta ou PII para logs do backend).

- **O que foi feito com a resposta:** Definido o desenho arquitetural do Scanner Web de Nota Fiscal (P2) alinhado ao motor de regras e ao schema real de `estoque_antecipe.csv` e `validadores_antecipe.json`, sem alteração de código conforme solicitado. Registrado o prompt em `docs/REGISTRO_PROMPTS_ELIAS.md`.
- **Arquivos/artefatos:** `docs/REGISTRO_PROMPTS_ELIAS.md`
- **Verificação:** Revisão do registro cronológico em `docs/REGISTRO_PROMPTS_ELIAS.md` e validação de ausência de dados sensíveis/linhas do CSV no log.

---

## ELIAS-0002 — 2026-10-24T12:17:31-03:00 — antigravity

- **Prompt enviado:**

```text
me explique cada uma dessas variaveis do projeto (o todo) e me explique como elas serão usadas nessa função do scanner, além disso me explique o funcionamento em si e a integração com o projeto, nossa ideia é um site com tudo ai de contexto que eu te mandei, que será hospedado na vercel, assim poderemos acessar pelo dispositivo mobile e usar a câmera do celular para o scanner. 


(não esqueça de salvar esse prompt na minha parte prompts Elias)
```

- **Resumo da resposta e análise técnica:**
  Detalhamento completo do dicionário de variáveis do projeto (`estoque_antecipe.csv` + `validadores_antecipe.json` + variáveis derivadas do motor), papel de cada variável dentro do fluxo do Scanner Web Mobile e arquitetura de integração com deploy na Vercel:
  1. **Dicionário Completo das Variáveis ("O Todo" vs. "No Scanner"):** Explicação das 11 colunas do CSV (`NOME_FUNDO`, `DOC_FUNDO`, `NOME_CEDENTE`, `DOC_CEDENTE`, `NOME_SACADO`, `DOC_SACADO`, `NU_DOCUMENTO`, `TIPO_RECEBIVEL`, `VALOR_NOMINAL`, `DATA_VENCIMENTO_ORIGINAL`, `DATA_AQUISICAO`), das variáveis de configuração/precificação (`taxa_mensal_percentual`, `base_dias`, `percentual_maximo`, `prazo_maximo_dias`, `valor_minimo`) e das variáveis calculadas (`RAIZ_CNPJ`, `PRAZO_DIAS`, `VALOR_LIQUIDO`, `CHAVE_PARCELA`), mapeando como cada uma é obtida no Scanner.
  2. **Funcionamento Passo a Passo no Dispositivo Mobile (Vercel + HTTPS):** Explicação técnica do requisito de `HTTPS` para acesso à câmera traseira (`navigator.mediaDevices.getUserMedia` com `facingMode: { ideal: "environment" }`) no iOS/Android, atendido nativamente pelo deploy na Vercel.
  3. **Integração Fim a Fim (Frontend Vercel $\leftrightarrow$ Backend FastAPI + PostgreSQL):** Arquitetura de comunicação entre o app web mobile na Vercel e a API/Banco de dados contendo os 100.554 recebíveis, incluindo fluxo de sincronização Mobile $\rightarrow$ Desktop para demonstração ao vivo aos jurados.

- **O que foi feito com a resposta:** Documentado o mapeamento completo de variáveis e a arquitetura de execução mobile na Vercel integrada ao backend FastAPI/PostgreSQL. Registrado o prompt `ELIAS-0002` em `docs/REGISTRO_PROMPTS_ELIAS.md`.
- **Arquivos/artefatos:** `docs/REGISTRO_PROMPTS_ELIAS.md`
- **Verificação:** Conferência do registro cronológico em `docs/REGISTRO_PROMPTS_ELIAS.md` via `git diff`.

---

## ELIAS-0003 — 2026-10-24T12:32:53-03:00 — antigravity

- **Prompt enviado:**

```text
eu acabei de me esquecendo de mandar o gabarito, resultados esperados, ele está no seguinte caminho: /home/leandroelias/Downloads/resultado_esperado_100k.json, use ele também para o contexto e me fale se tem alguma modificação no que você me explicou até o momento sobre a função scanner 

(não esqueça de colocar esse prompt na minha parte - prompts elias)
```

- **Resumo da resposta e análise técnica:**
  Cruzamento integral entre o gabarito oficial (`resultado_esperado_100k.json`, com 100.554 resultados: `85.215 APROVADO` e `15.339 BARRADO`) e o arquivo `estoque_antecipe.csv`, atingindo **0 divergências nas 100.554 linhas** e identificando **5 ajustes importantes** para o motor e para o Scanner Web:
  1. **Escopo Multi-Fundo (18 Fundos) e Concentração por Fundo:** O gabarito avalia todas as 100.554 linhas (os 18 fundos), calculando os 10% de `CONCENTRACAO_MAXIMA_SACADO` pela `RAIZ_CNPJ` dentro de cada `NOME_FUNDO` (5 raízes estouram 10%, totalizando 3.305 linhas barradas, incluindo a raiz `58206002` com 12,50% no `ANTECIPE FIDC`). No Scanner, isso permite selecionar o fundo comprador (ou sugerir outro FIDC quando barrado por concentração no `ANTECIPE FIDC`).
  2. **Fórmula Exata de Prazo (`DATA_VENCIMENTO_ORIGINAL - DATA_AQUISICAO`):** Comprovado que `PRAZO_MAXIMO` (4.671 linhas barradas, todas com `vencimento - aquisicao >= 181 dias`) e `NAO_VENCIDA` usam a `DATA_AQUISICAO` da própria operação, e não uma data fixa retroativa. No Scanner, `DATA_AQUISICAO` passa a ser um campo explícito da simulação.
  3. **Avaliação Sem Curto-Circuito (`barrado_por` com múltiplos códigos):** O motor acumula todas as regras violadas na mesma nota (ex.: `["SITUACAO_CADASTRAL_SACADO", "TIPO_RECEBIVEL", "PRAZO_MAXIMO"]`), exigindo que a UI mobile do Scanner exiba múltiplos cards de motivo de recusa quando mais de uma regra falhar.
  4. **Base Cadastral Determinística (`SITUACAO_CADASTRAL_SACADO`):** Identificados exatamente os 87 CNPJs de sacados que reprovam em `SITUACAO_CADASTRAL_SACADO` (2.317 linhas no total, 106 no `ANTECIPE FIDC`, sem sobreposição com CNPJs aprovados), permitindo validação exata no motor e no Scanner.
  5. **Vocabulário Oficial do Contrato:** Adoção do schema oficial `{"linha", "id": NU_DOCUMENTO, "status": "APROVADO" | "BARRADO", "barrado_por": [...]}` combinado aos detalhes de precificação e UX no Scanner.

- **O que foi feito com a resposta:** Validadas as regras exatas contra as 100.554 linhas do gabarito (`0 divergências`), ajustado o desenho do Scanner Web e do motor para refletir as 5 descobertas e registrado o prompt `ELIAS-0003` em `docs/REGISTRO_PROMPTS_ELIAS.md`.
- **Arquivos/artefatos:** `docs/REGISTRO_PROMPTS_ELIAS.md`
- **Verificação:** Teste de validação cruzada entre `estoque_antecipe.csv` e `resultado_esperado_100k.json` resultando em `Mismatches across 100,554 rows: 0`.


