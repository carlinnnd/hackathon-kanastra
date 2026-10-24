# Especificação técnica do sistema — Antecipe FIDC

> **Status:** Requisitos consolidados a partir do briefing oficial de 24/10/2026 e inspecionados diretamente nos arquivos de dados reais da raiz (`estoque_antecipe.csv` e `validadores_antecipe.json`).  
> **Nota de conformidade:** O edital completo não foi fornecido como documento isolado; os requisitos aqui descritos refletem fielmente as regras informadas no prompt oficial do usuário e nos arquivos recebidos, com premissas técnicas explicitamente marcadas.

---

## 1. Objetivo do Sistema

O **Antecipe** é uma plataforma modular para antecipação de recebíveis voltada a Fundos de Investimento em Direitos Creditórios (FIDCs).
O sistema permite que empresas cedentes submetam lotes de recebíveis para avaliação de elegibilidade e simulação financeira de aquisição pelo fundo **ANTECIPE FIDC**.

A aplicação executa:
1. Ingestão de arquivos CSV com lotes de títulos.
2. Execução determinística de motor de regras (*Rule Engine*) configurado via JSON versionado.
3. Avaliação individual de cada título (aprovação ou recusa fundamentada).
4. Cálculo financeiro do valor líquido dos títulos elegíveis com precisão decimal (`Decimal`).
5. Proteção antiduplicidade contra todo o estoque histórico da carteira e dentro do próprio lote.
6. Cálculo de concentração por raiz de CNPJ do sacado.
7. Exposição unificada da inteligência de negócio via API REST e Interface Web.

---

## 2. Dados de Entrada e Schema

### 2.1. Arquivo de Carteira Histórica (`estoque_antecipe.csv`)
- **Encoding:** UTF-8
- **Delimitador:** `;` (ponto e vírgula)
- **Formato decimal:** Vírgula `,`
- **Formato de data:** `dd/mm/aaaa`
- **Data-base de referência:** `22/10/2026`
- **Volume auditado:** 100.554 registros distribuídos em 18 fundos.
- **Participação ANTECIPE FIDC:** 10.621 títulos adquiridos, totalizando R$ 53.074.028,00 nominais.
- **Integridade verificada:** 0 duplicidades nas 100.554 identidades compostas; todos os CNPJs possuem 14 dígitos normalizados.
- **Distribuição por tipo no estoque:** Duplicata (77.167), Duplicata de Serviço (13.545), CCB (5.067), Cheque (4.333), Nota Comercial (442).
- **SHA-256 do arquivo:** `313c75f4147e1e851eaaefd15dc035aa895c961434da1a91024fd0764559c2f1`

### 2.2. Cabeçalhos Obrigatórios do CSV
1. `NOME_FUNDO`
2. `DOC_FUNDO`
3. `NOME_CEDENTE`
4. `DOC_CEDENTE`
5. `NOME_SACADO`
6. `DOC_SACADO`
7. `NU_DOCUMENTO`
8. `TIPO_RECEBIVEL`
9. `VALOR_NOMINAL`
10. `DATA_VENCIMENTO_ORIGINAL`
11. `DATA_AQUISICAO`

---

## 3. Motor de Regras e Critérios de Elegibilidade

As políticas de validação são parametrizadas a partir de `validadores_antecipe.json` utilizando o padrão *Strategy + Registry*.

### 3.1. Validadores do ANTECIPE FIDC (Códigos Canônicos do JSON e Sistema)
O arquivo oficial contém 9 validadores (7 ativos e 2 inativos), com seus códigos canônicos exatos:

| Código Canônico (`codigo`) | Status | Parâmetro Configurado | Ação na Recusa |
| :--- | :--- | :--- | :--- |
| **`VALOR_MINIMO`** | Ativo | `valor_minimo: 100.0` | Recusa títulos com valor nominal inferior a R$ 100,00 |
| **`PRAZO_MAXIMO`** | Ativo | `prazo_maximo_dias: 180` | Recusa títulos cujo vencimento exceda 180 dias da data-base |
| **`NAO_VENCIDA`** | Ativo | Sem parâmetro | Recusa títulos com data de vencimento anterior à data-base (22/10/2026) |
| **`TIPO_RECEBIVEL`** | Ativo | `tipos_aceitos: ["Duplicata", "Duplicata de Serviço"]` | Recusa tipos não autorizados (ex: Cheque, CCB, Nota Comercial) |
| **`SITUACAO_CADASTRAL_SACADO`** | Ativo | `situacoes_aceitas: ["ATIVA"]` | Exige situação cadastral `ATIVA`. Trata `NAO_VERIFICADA` como inelegível |
| **`CNPJ_SACADO_VALIDO`** | Ativo | Sem parâmetro | Validação matemática dos dígitos verificadores do CNPJ do sacado |
| **`CONCENTRACAO_MAXIMA_SACADO`**| Ativo | `percentual_maximo: 10.0` (por raiz do CNPJ) | Recusa novas aquisições que façam a exposição ultrapassar 10,0% da carteira |
| `PRAZO_MINIMO` | Inativo | `prazo_minimo_dias: 30` | Ignorado pelo motor (desativado na configuração) |
| `CONCENTRACAO_MAXIMA_CEDENTE` | Inativo | `percentual_maximo: 8.0` | Ignorado pelo motor (desativado na configuração) |

*Nota de interoperabilidade:* Para compatibilidade com consultas e clientes legados, a camada de API e interface suporta os seguintes aliases canônicos:
- `CNPJ_SACADO_VALIDO` (canônico JSON) $\leftrightarrow$ `CNPJ_VALIDO` / `CNPJ_INVALIDO`
- `SITUACAO_CADASTRAL_SACADO` (canônico JSON) $\leftrightarrow$ `SITUACAO_CADASTRAL`
- `NAO_VENCIDA` (canônico JSON) $\leftrightarrow$ `NAO_VENCIDO`
- `CONCENTRACAO_MAXIMA_SACADO` (canônico JSON) $\leftrightarrow$ `CONCENTRACAO_SACADO`
- `CONCENTRACAO_MAXIMA_CEDENTE` (canônico JSON) $\leftrightarrow$ `CONCENTRACAO_CEDENTE`

### 3.2. Verificação Cadastral (Premissa Documentada)
- Validação matemática de CNPJ não atesta situação cadastral na Receita Federal.
- O motor classifica a situação em: `ATIVA`, `INATIVA` e `NAO_VERIFICADA`.
- Correção posterior do usuário em 24/10/2026: novas notas têm somente `APROVADA` ou `RECUSADA`. Ausência de confirmação cadastral (`NAO_VERIFICADA`) recusa por `SITUACAO_CADASTRAL_SACADO`, com mensagem explicativa. Dados malformados também recusam, preservando o motivo específico. Não existe terceiro estado de decisão.
- Para testes e demonstrações, é utilizada uma tabela sintética explicitamente identificada como **SIMULADA** (ativada via `ENABLE_DEMO_CADASTRO=true`).
- O arquivo fornecido `cnpj_situacao_mock.csv` é a fonte simulada configurada. Análise de carteira histórica é descritiva, separada de novas operações. Contrato atualizado, limites e divergências com o gabarito: `Codex/antecipe/docs/RESULTADOS_E_CADASTRO.md`.

### 3.3. Concentração por Sacado e Regra de Limite
- Agrupamento pela **raiz do CNPJ** (8 primeiros dígitos normalizados).
- A concentração projetada é calculada por:
  $$\text{Concentração Projetada} = \frac{\text{Exposição Histórica da Raiz} + \text{Aprovados do Lote da Mesma Raiz} + \text{Título em Análise}}{\text{Total Nominal Histórico da Carteira} + \text{Total Nominal dos Aprovados do Lote} + \text{Título em Análise}}$$
- **Regra de Aceite e Piso:** Um lote que atinja **exatamente 10,0%** de concentração projetada é **aceito**. Apenas exposições estritamente superiores a 10,0% ($> 10{,}0\%$) disparam a recusa.
- *Tratamento de excesso histórico:* A análise da carteira identificou uma raiz de CNPJ com 12,5% de concentração histórica prévia. **Premissa técnica adotada:** Títulos históricos são preservados; novas aquisições para grupos cuja concentração resultante seja superior a 10,0% são recusadas.

### 3.4. Antiduplicidade Global e Identidade do Título
- Identidade única composta global:
  $$\text{ID} = \text{DOC\_CEDENTE} + \text{DOC\_SACADO} + \text{TIPO\_RECEBIVEL} + \text{NU\_DOCUMENTO} + \text{DATA\_VENCIMENTO\_ORIGINAL}$$
- Títulos com mesmo número de documento mas vencimentos distintos são parcelas legítimas e permitidas.
- **Escopo Global de Duplicidade:** A duplicidade é verificada contra **todo o estoque histórico global** (abrangendo todos os fundos da base, garantindo que nenhum título previamente adquirido em qualquer carteira seja readquirido) sob o código `DUPLICIDADE_HISTORICA`.
- **Duplicidade Intra-Lote:** Repetições idênticas dentro da mesma submissão são recusadas sob o código `DUPLICIDADE_LOTE` (a primeira ocorrência é avaliada; repetições subsequentes são rejeitadas mesmo que a primeira falhe por outro critério).

---

## 4. Precificação Financeira

- **Método:** Desconto Comercial Simples.
- **Fórmula:**
  $$\text{Valor Líquido} = \text{Valor Nominal} \times \left(1 - \frac{\text{Taxa Mensal} \times \text{Dias}}{30}\right)$$
- **Taxa mensal configurada:** 2,0% a.m. (`taxa_mensal_percentual: 2.0` no JSON $\to$ $0{,}02$).
- **Regras de cálculo:**
  - Uso estrito de `decimal.Decimal` (zero uso de `float`).
  - Arredondamento comercial `ROUND_HALF_UP` a 2 casas decimais por título individual aprovado (não bancário `ROUND_HALF_EVEN`).
  - **Representação Centesimal Estrita (ADR-008):** Qualquer valor de face com frações além de duas casas decimais não nulas é recusado na ingestão como `FORMATO_INVALIDO_VALOR`.
  - O valor total líquido da simulação é a soma aritmética exata dos valores líquidos dos títulos aprovados.

---

## 5. Arquitetura e Contratos

- **Padrão:** Monólito modular limpo em Python (`backend`) e React + TypeScript (`frontend`).
- **Persistência:** SQLite para execução local autossuficiente (sem necessidade de orquestração Docker) e suporte para PostgreSQL configurado via `DATABASE_URL`.
- **APIs:**
  - `POST /api/simulations`: Upload de CSV e simulação com retorno estruturado.
  - `GET /api/simulations/{id}`: Consulta paginada com filtros por status e motivo (com suporte a códigos canônicos e aliases).
  - `POST /api/receivables/evaluate`: Avaliação síncrona direta via payload JSON.
  - `GET /api/rules`: Exibição da versão ativa das regras.
  - `POST /api/rules/versions`: Criação de nova versão imutável de regras.
  - `POST /api/rules/versions/{id}/activate`: Ativação atômica de versão.
  - `GET /api/demo.csv`: Lote sintético para demonstração imediata.

---

## 6. Verificação e Critérios de Aceite

1. **Reprodutibilidade:** Execução a partir de clone limpo via comandos descritos no `Codex/antecipe/README.md`.
2. **Correção:** 100% de conformidade com os testes automatizados cobrindo os 20 casos de negócio e suíte R3 de segurança.
3. **Escalabilidade:** Throughput comprovado acima de 10.000 linhas/s com pico de memória Win32 de ~36,8 MB em 100k e ~92,5 MB em 500k.
4. **Governança:** Trilha de auditoria integral e sanitizada registrada em `docs/REGISTRO_PROMPTS_CARLOS.md`.

## 7. Requisito posterior de capacidade — P0013

O usuário exige processamento de CSV com até **1.000.000 de registros** e reportou 413 no envio de 100 mil. O estoque conhecido tem 100.554 registros e 20.276.472 bytes. A publicação anterior de demonstração aceitava apenas 4.000.000 bytes por POST; esse limite não demonstrava a capacidade de volume pedida.

Na Vercel, o corpo de uma requisição HTTP tem limite próprio de 4,5 MB. A correção em homologação separa limite do transporte HTTP de capacidade do processamento: arquivos grandes são enviados em frames por uma única conexão WebSocket FastAPI, reutilizando o motor e a transação. O teto técnico configurado é 1.000.000 de registros e 512 MiB, sem alterar regras financeiras. Na demonstração pública, o banco da sessão é isolado e efêmero; não há promessa de persistência entre conexões.

O caminho HTTP `POST /api/simulations` permanece para lotes menores. Abrir esse caminho por GET deve responder 405 com `Allow: POST`, não ser interpretado como falha de avaliação de um CSV. O suporte efetivo de 100 mil, 500 mil e 1 milhão exige medição real no mesmo ambiente, verificação das decisões persistidas, contagens e totais; não deve ser declarado concluído apenas pela configuração desses limites.
