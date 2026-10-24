# Auditoria Independente: Gabarito 100k vs Regras Derivadas Sem Circularidade

**Data da Auditoria:** 24/10/2026  
**Artefato Auditado:** `resultado_esperado_100k.json`  
**Hash SHA-256 do Gabarito:** `a5e0de969c0cf9d1f37aeea0100d7a4a2ba663da24c1641977f7a68934bc1ae8`  
**Base de Referência:** `estoque_antecipe_100k/estoque_antecipe.csv` (100.554 registros, 18 fundos)  
**Configuração:** `validadores_antecipe.json`  
**Script de Verificação:** `Codex/antecipe/qa/compare_expected_results.py`

---

## 1. Resumo e Metodologia Rigorosa

A presente auditoria decompôs o gabarito oficial em duas dimensões metodológicas distintas:
1. **Validação Independente (4 Regras Derivadas sem Labels):** Avalia as regras puramente determinísticas obtidas dos parâmetros de `validadores_antecipe.json` e dos dados do estoque (sem qualquer uso dos rótulos do gabarito).
2. **Análise Exploratória do Vetor Cadastral (Rotulado):** Mapeia o comportamento estatístico dos 87 documentos sinalizados no gabarito sob a regra `SITUACAO_CADASTRAL_SACADO`, documentando a premissa de origem desconhecida sem induzir validação circular.

| Dimensão Metodológica | Registros Avaliados | Aderência de Status | Concordância de Motivos |
|---|---|---|---|
| **Validação Independente (4 regras)** | 100.554 | **98.362 / 100.554 (97,8201%)** | — |
| **Análise Exploratória (+ vetor cadastral)** | 100.554 | **100.554 / 100.554 (100,0000%)** | **100.554 / 100.554 (100,0000%)** |

### Asserções de Integridade dos Dados:
- Total de linhas CSV (100.554) rigorosamente idêntico ao total de linhas do gabarito (100.554).
- Unicidade estrita de linhas verificada.
- Correspondência exata linha a linha entre o número do documento (`NU_DOCUMENTO`) e o campo `id` do gabarito em 100% dos registros.

---

## 2. Validação Independente das 4 Regras Derivadas (Sem Labels)

### 2.1. `VALOR_MINIMO` (Parâmetro: R$ 100,00)
- **Critério derivado:** `VALOR_NOMINAL < 100.00`.
- **Detecção exata:** Exatamente **34 títulos** no estoque possuem valor abaixo de R$ 100,00 (100% de convergência independente).

### 2.2. `TIPO_RECEBIVEL` (Parâmetro: `Duplicata`, `Duplicata de Serviço`)
- **Composição Real do CSV Auditada:**
  - Tipos aceitos: `Duplicata` (77.167) e `Duplicata de Serviço` (13.545).
  - Tipos não aceitos barrados: `CCB` (5.067), `Cheque` (4.333) e `Nota Comercial` (442).
  - Soma exata: **9.842 títulos barrados** (100% de convergência independente).

### 2.3. `PRAZO_MAXIMO` (Parâmetro: 180 dias)
- **Constatação Temporal:**
  - O gabarito avalia o prazo na concessão histórica:  
    $$\text{prazo} = \text{DATA\_VENCIMENTO\_ORIGINAL} - \text{DATA\_AQUISICAO} > 180 \text{ dias}$$
  - Exatamente **4.671 títulos** do estoque excedem 180 dias nessa métrica. Se comparado contra a data-base de simulação futura `2026-10-22`, seriam 4.502 títulos, evidenciando que o gabarito audita a conformidade do estoque na data de compra histórica.

### 2.4. `CONCENTRACAO_MAXIMA_SACADO` (Parâmetro: 10,0% por raiz do sacado)
- **Cálculo Dinâmico Agregado (Sem Identificadores em Log):**
  - O script calculou dinamicamente a exposição nominal agregada por fundo normalizado e raiz do sacado (8 dígitos) em `Decimal`.
  - Foram identificadas dinamicamente **5 raízes em 4 fundos distintos** cujo somatório de recebíveis históricos ultrapassou 10,0% do saldo total do respectivo fundo (totalizando 3.305 títulos barrados).
  - Soma exata: **3.305 títulos barrados** (100% de convergência dinâmica sem hardcode e sem exposição de identificadores de clientes ou fundos).

---

## 3. Análise Exploratória do Vetor Cadastral (Origem Desconhecida)

- No gabarito, exatamente **2.317 títulos** são barrados por `SITUACAO_CADASTRAL_SACADO`.
- Esses títulos pertencem a um conjunto fechado de **87 documentos de sacados**.
- **Observação Metodológica Crítica:**
  - Como o arquivo `validadores_antecipe.json` define apenas o critério (`"situacoes_aceitas": ["ATIVA"]`), mas não fornece nem referencia a base cadastral de birô ou da Receita Federal, a fonte que classificou esses 87 sacados permanece **externa e desconhecida**.
  - A reutilização desses 87 documentos no comparador é meramente uma **análise exploratória rotulada**, que demonstra que o gabarito aplicou a recusa de forma consistente a 100% das notas desses 87 sacados (interseção zero com os demais 4.122 sacados do estoque).
  - No motor de produção, a política conservadora padrão `NAO_VERIFICADA` é a única escolha segura e auditável na ausência de consulta oficial em tempo real à Receita Federal.

---

## 4. Auditoria de Outros Validadores

- **`CNPJ_SACADO_VALIDO`:** Todos os 100.554 registros possuem CNPJ de sacado com dígitos verificadores matematicamente válidos (zero erros de DV no arquivo). Por isso, não há ocorrências desta recusa no gabarito.
- **`NAO_VENCIDA`:** 1.793 títulos possuem vencimento anterior à data-base `2026-10-22`. Como o gabarito avalia a concessão histórica na data de aquisição (quando nenhum estava vencido), nenhuma linha recebeu a etiqueta `NAO_VENCIDA`.
