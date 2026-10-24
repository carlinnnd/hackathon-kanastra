# Requisitos do Usuário — Hackathon Antecipe

> **Origem:** Transcrição documental integral e sanitizada do prompt oficial do usuário submetido em 24/10/2026 para o Orquestrador Técnico Principal.  
> **Hash SHA-256 do prompt original:** `c326a99b03e7868ed6ed87113eb71158ed3382156644c99a0e52395827f92c46`  
> **Arquivo de origem:** `.hackathon/prompts/p0002_user.txt` (ID no Ledger: `P0002`)

---

## 1. Contexto do Negócio

O Antecipe é um portal de antecipação de recebíveis.

Uma empresa vende produtos ou serviços a prazo e deseja receber antecipadamente. Ela apresenta seus recebíveis a um fundo, que poderá adquiri-los mediante desconto financeiro.

Antes da aquisição, o fundo precisa verificar critérios de elegibilidade, incluindo:

- Regularidade e situação cadastral do sacado.
- Tipo de recebível permitido.
- Valor nominal mínimo.
- Prazo até o vencimento.
- Limites de concentração por sacado.
- Existência prévia do título na carteira.
- Duplicidade dentro do lote enviado.

Os recebíveis aprovados recebem uma simulação do valor líquido a ser pago à empresa.

Os recusados devem apresentar justificativas objetivas e compreensíveis.

---

## 2. Requisitos Obrigatórios do Hackathon

A aplicação deve oferecer:

1. Upload de arquivos CSV de recebíveis.
2. Leitura das regras a partir do `validadores_antecipe.json`.
3. Processamento e validação de cada recebível.
4. Resultado individual de aprovação ou recusa.
5. Justificativas compreensíveis para cada recusa.
6. Cálculo do valor líquido de cada recebível aprovado.
7. Cálculo do total líquido do lote.
8. Disponibilização da mesma validação via interface web e API.
9. Repositório acessível aos jurados.
10. README com instruções para execução do zero.
11. Relatório técnico resumido com decisões e limitações.
12. Histórico dos prompts de IA utilizados.
13. Aplicação funcional para apresentação.

**Prazo informado:** sábado, 24/10/2026, às 18h, horário de Brasília.

A entrega funcional tem prioridade absoluta sobre funcionalidades complementares.

---

## 3. Stack e Arquitetura

Utilizar preferencialmente:

- **Frontend:** React + TypeScript + Vite
- **Interface:** Tailwind CSS + shadcn/ui
- **Backend:** Python + FastAPI
- **Validação de contratos:** Pydantic
- **Banco de dados:** PostgreSQL (com SQLite como alternativa local autossuficiente)
- **ORM:** SQLAlchemy
- **Migrações:** Alembic
- **Motor de regras:** Strategy Pattern + Registry
- **Testes:** Pytest + httpx
- **Ambiente local:** Docker Compose (quando disponível)

Arquitetura: **monólito modular com separação clara entre domínio, aplicação, infraestrutura e interfaces**.

Evitar microsserviços, Kafka, Kubernetes, Spark ou infraestrutura distribuída sem necessidade comprovada.

O estoque tem aproximadamente 100 mil registros, volume que pode ser processado eficientemente com PostgreSQL e Python.

---

## 4. Arquivos e Formato dos Dados

Os arquivos fornecidos são:

- `estoque_antecipe.csv`: carteira histórica de recebíveis adquiridos por 18 fundos.
- `validadores_antecipe.json`: regras de elegibilidade do ANTECIPE FIDC.

O CSV utiliza:

- Codificação UTF-8.
- Separador `;`.
- Decimal com vírgula.
- Datas em `dd/mm/aaaa`.
- Cabeçalho na primeira linha.
- Data-base: 22/10/2026.

Campos conhecidos:

```text
NOME_FUNDO
DOC_FUNDO
NOME_CEDENTE
DOC_CEDENTE
NOME_SACADO
DOC_SACADO
NU_DOCUMENTO
TIPO_RECEBIVEL
VALOR_NOMINAL
DATA_VENCIMENTO_ORIGINAL
DATA_AQUISICAO
```

O estoque analisado apresentou:
- 100.554 registros.
- 18 fundos.
- 10.621 recebíveis do ANTECIPE FIDC.
- R$ 53,07 milhões em valor nominal na carteira do ANTECIPE.

**Requisitos de importação:**
- Utilizar `Decimal` para valores monetários (zero `float`).
- Converter datas explicitamente.
- Normalizar CNPJs.
- Validar cabeçalhos obrigatórios.
- Identificar linhas inválidas sem descartá-las silenciosamente.
- Criar índices adequados.

---

## 5. Motor de Regras Configurável

Implementar um **Configuration-Driven Rule Engine**, combinando Registry e Strategy Pattern.

Separar rigorosamente:
1. Implementação dos validadores.
2. Configuração e parâmetros.
3. Execução e composição dos resultados.
4. Tradução das recusas para linguagem compreensível.
5. Persistência e auditoria.

As regras devem ser carregadas do JSON fornecido, sem parâmetros financeiros fixos no código.
O executor deve ignorar validadores inativos.

### 5.1. Regras Identificadas no JSON:
- **CNPJ válido do sacado:** Dígitos verificadores (Ativa).
- **Situação cadastral do sacado:** `ATIVA` (Ativa).
- **Tipo de recebível:** Duplicata ou Duplicata de Serviço (Ativa).
- **Valor mínimo:** R$ 100,00 (Ativa).
- **Não vencido:** Vencimento a partir da data-base (Ativa).
- **Prazo máximo:** 180 dias (Ativa).
- **Concentração por sacado:** 10%, por raiz do CNPJ (Ativa).
- **Prazo mínimo:** 30 dias (Inativa).
- **Concentração por cedente:** 8% (Inativa).

---

## 6. Verificação Cadastral

O motor deve distinguir:
- `ATIVA`
- `INATIVA`
- `NAO_VERIFICADA`

Quando não existir fonte cadastral confiável ou a consulta estiver indisponível, não assumir situação `ATIVA`. A política padrão do fundo classifica como `NAO_VERIFICADA` e recusa o título. Para demonstração, é permitido utilizar fonte simulada identificada explicitamente como SIMULADA.

---

## 7. Concentração por Sacado

A concentração deve ser calculada pela **raiz do CNPJ** (8 primeiros dígitos normalizados).
Fórmula:
$$\text{concentracao\_projetada} = \frac{\text{exposicao\_projetada\_do\_grupo}}{\text{valor\_nominal\_total\_projetado\_da\_carteira}}$$

**Premissa técnica de excesso histórico:** A carteira histórica possui um grupo com 12,5% de concentração histórica. Títulos históricos são mantidos; novas aquisições que agravem a concentração acima de 10% são recusadas.

---

## 8. Antiduplicidade e Idempotência

Identidade única composta global:
$$\text{DOC\_CEDENTE} + \text{DOC\_SACADO} + \text{TIPO\_RECEBIVEL} + \text{NU\_DOCUMENTO} + \text{DATA\_VENCIMENTO\_ORIGINAL}$$

- Detecta duplicidade em relação ao estoque e dentro do próprio CSV enviado.
- Parcelas com mesmo documento mas vencimentos diferentes são legítimas.
- A primeira ocorrência no lote é avaliada; repetições são rejeitadas como duplicidade.

---

## 9. Precificação Financeira

- Método de Desconto Simples Comercial.
$$\text{valor\_liquido} = \text{valor\_nominal} \times \left(1 - \frac{\text{taxa\_mensal} \times \text{dias}}{30}\right)$$
- Taxa mensal configurada: 2% (`taxa_mensal_percentual: 2.0` / 100 = 0.02).
- Base: 30 dias.
- Exemplo: R$ 5.000,00 em 90 dias a 2% gera R$ 300,00 de desconto e R$ 4.700,00 de valor líquido.
- `Decimal` estrito com arredondamento `ROUND_HALF_UP` a 2 casas decimais.

---

## 10. Priorização e Aceite

- **P0 (Obrigatório):** Aplicação executável, importação de estoque, upload CSV, motor de regras ativo, duplicidade, concentração por raiz, precificação exata, API e Web consistentes, README e histórico de prompts.
- **P1 (Diferenciais):** Versionamento persistente de regras, tela administrativa, testes abrangentes, histórico de simulações.
- **P2 (Opcionais):** Confirmação de aquisição transacional com idempotência.
