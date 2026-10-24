# Registro cronológico de prompts — CARLOS

Gerado a partir dos hooks e de inclusões manuais. Horários em UTC. Texto sanitizado, com SHA-256 do prompt original. Ações são confirmadas separadamente.

> **Registros individuais da equipe:**
> - [Registro de Carlos (Orquestração & Frentes)](REGISTRO_PROMPTS_CARLOS.md)
> - [Registro de Elias](REGISTRO_PROMPTS_ELIAS.md)
> - [Registro de Pina (Leandro)](REGISTRO_PROMPTS_PINA.md)

> *Nota de integridade documental:* O texto integral fiel dos prompts oficiais encontra-se preservado sob `.hackathon/prompts/` (ex: `p0002_user.txt`). Na visualização sanitizada acima, sentenças com mais de duas vírgulas ou ponto-e-vírgula são marcadas como `[LINHA_TABULAR_OMITIDA]` pela rotina de proteção estrita contra vazamento de dados tabulares/CSV.

## P0001 — 2026-10-24T12:45:02+00:00 — user

- Sessão: `session-01`
- SHA-256 do prompt original: `c681fb9725c587ba731c410f70e7de23349b1352c029c4b56c303042bc8cb323`
- Texto do prompt (sanitizado):

```text
inicie o prompt_ledger e crie uma janela já para cada agente ficar a postos
```

- Última mensagem do assistente (prévia, não prova execução):

```text
Prompt ledger iniciado e agentes especializados instanciados e prontos.
```

- **O que foi feito com a resposta:** Iniciado prompt ledger e criados agentes especialistas a postos
- Arquivos/artefatos: scripts/prompt_ledger.py
- Verificação: python scripts/prompt_ledger.py status; python tests/test_kit.py

## P0002 — 2026-10-24T13:27:34+00:00 — user

- Sessão: `manual`
- SHA-256 do prompt original: `c326a99b03e7868ed6ed87113eb71158ed3382156644c99a0e52395827f92c46`
- Texto do prompt (sanitizado):

````text
(utilizando seus sub-agentes)

**PROMPT PARA O ORQUESTRADOR — HACKATHON ANTECIPE**

Você é o **Orquestrador Técnico Principal** do projeto **Hackathon Antecipe**, responsável por coordenar a implementação de uma plataforma de antecipação de recebíveis para fundos de investimento em direitos creditórios (FIDCs).

[LINHA_TABULAR_OMITIDA]

[LINHA_TABULAR_OMITIDA]

[LINHA_TABULAR_OMITIDA]

Não adicione complexidade arquitetural sem benefício concreto para o desafio.

**1. CONTEXTO DO NEGÓCIO**

O Antecipe é um portal de antecipação de recebíveis.

Uma empresa vende produtos ou serviços a prazo e deseja receber antecipadamente. Ela apresenta seus recebíveis a um fundo, que poderá adquiri-los mediante desconto financeiro.

[LINHA_TABULAR_OMITIDA]

- Regularidade e situação cadastral do sacado.
- Tipo de recebível permitido.
- Valor nominal mínimo.
- Prazo até o vencimento.
- Limites de concentração por sacado.
- Existência prévia do título na carteira.
- Duplicidade dentro do lote enviado.

Os recebíveis aprovados recebem uma simulação do valor líquido a ser pago à empresa.

Os recusados devem apresentar justificativas objetivas e compreensíveis.

**2. REQUISITOS OBRIGATÓRIOS DO HACKATHON**

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

[LINHA_TABULAR_OMITIDA]

A entrega funcional tem prioridade absoluta sobre funcionalidades complementares.

**3. STACK E ARQUITETURA**

Utilizar preferencialmente:

CamadaTecnologiaFrontendReact + TypeScript + ViteInterfaceTailwind CSS + shadcn/uiBackendPython + FastAPIValidação de contratosPydanticBanco de dadosPostgreSQLORMSQLAlchemyMigraçõesAlembicMotor de regrasStrategy Pattern + RegistryTestesPytest + httpxAmbiente localDocker Compose

[LINHA_TABULAR_OMITIDA]

[LINHA_TABULAR_OMITIDA]

O estoque tem aproximadamente 100 mil registros, volume que pode ser processado eficientemente com PostgreSQL e Python.

Se o repositório já contiver uma stack funcional diferente, inspecione-a antes de propor mudanças. Não reescreva partes existentes apenas para seguir uma preferência tecnológica.

**Estrutura sugerida**

```
antecipe/
├── frontend/
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── services/
│       └── types/
├── backend/
│   ├── api/
│   ├── domain/
│   │   ├── models/
│   │   ├── rules/
│   │   └── pricing/
│   ├── application/
│   │   ├── simulations/
│   │   └── imports/
│   ├── infrastructure/
│   │   ├── database/
│   │   └── repositories/
│   └── tests/
├── data/
├── docs/
│   ├── architecture.md
│   ├── ai-prompts.md
│   └── decisions.md
├── docker-compose.yml
└── README.md
```

A estrutura poderá ser adaptada caso exista uma organização melhor no repositório.

**4. ARQUIVOS E FORMATO DOS DADOS**

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

```
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

Os campos acima representam o esquema conhecido. Verificar os arquivos reais antes de implementar.

O estoque analisado anteriormente apresentou aproximadamente:

- 100.554 registros.
- 18 fundos.
- 10.621 recebíveis do ANTECIPE FIDC.
- R$ 53,07 milhões em valor nominal na carteira do ANTECIPE.

Essas informações são referências de análise anterior, não substituem a inspeção dos arquivos.

**Requisitos de importação**

- Utilizar `Decimal` para valores monetários.
- Converter datas explicitamente.
- Normalizar CNPJs.
- Validar cabeçalhos obrigatórios.
- Identificar linhas inválidas.
- Evitar perda silenciosa de registros.
- Registrar inconsistências.
- Criar índices adequados.
- Utilizar inserção em lote ou `COPY` para o estoque histórico.

Não utilizar `float` para operações financeiras.

**5. MOTOR DE REGRAS CONFIGURÁVEL**

Implementar um **Configuration-Driven Rule Engine**, combinando Registry e Strategy Pattern.

Separar rigorosamente:

1. Implementação dos validadores.
2. Configuração e parâmetros.
3. Execução e composição dos resultados.
4. Tradução das recusas para linguagem compreensível.
5. Persistência e auditoria.

As regras devem ser carregadas do JSON fornecido, sem parâmetros financeiros fixos no código.

Cada validador deve possuir:

- Código único.
- Indicador de ativação.
- Esquema de parâmetros.
- Implementação independente.
- Resultado estruturado.
- Código de erro, quando aplicável.
- Mensagem amigável.
- Dados utilizados na decisão, quando relevantes.

O executor deve ignorar validadores inativos.

**Importante:** permitir alterar parâmetros e ativar/desativar regras conhecidas sem deploy. Novos tipos de validadores exigem implementação e registro no backend.

Não implementar execução arbitrária de Python, JavaScript ou expressões não confiáveis presentes no JSON.

**5.1. Regras identificadas**

A configuração analisada anteriormente contém nove validadores:

[LINHA_TABULAR_OMITIDA]

Precificação identificada:

- Método: desconto simples.
- Taxa mensal: 2%.
- Base: 30 dias.

**Antes de implementar, conferir os códigos e os nomes exatos dos parâmetros no arquivo real.** Não assumir que os identificadores descritivos deste documento correspondem literalmente aos presentes no JSON.

**5.2. Exemplo conceitual de configuração versionada**

```
{
  "versao": 1,
  "fundo": "ANTECIPE FIDC",
  "data_base": "2026-10-22",
  "validadores": [
    {
      "codigo": "PRAZO_MAXIMO",
      "ativo": true,
      "parametros": {
        "dias": 180
      }
    },
    {
      "codigo": "VALOR_MINIMO",
      "ativo": true,
      "parametros": {
        "valor": "100.00"
      }
    },
    {
      "codigo": "CONCENTRACAO_SACADO",
      "ativo": true,
      "parametros": {
        "percentual_maximo": "10.00",
        "agrupamento": "RAIZ_CNPJ"
      }
    }
  ],
  "precificacao": {
    "metodo": "DESCONTO_SIMPLES",
    "taxa_mensal": "0.02",
    "base_dias": 30
  }
}
```

O exemplo é ilustrativo e incompleto. A implementação deve contemplar todas as regras e adaptar a representação ao JSON real.

**5.3. Fluxo de execução**

```
Receber CSV ou JSON
        ↓
Validar e normalizar os dados
        ↓
Carregar versão fixa das regras
        ↓
Executar validações individuais
        ↓
Consultar carteira histórica
        ↓
Detectar duplicidade
        ↓
Calcular concentração projetada
        ↓
Determinar elegibilidade
        ↓
Calcular valor líquido
        ↓
Persistir resultados e auditoria
        ↓
Retornar resposta estruturada
```

Separar validadores em:

[LINHA_TABULAR_OMITIDA]

**Dependentes da carteira:** concentração e duplicidade.

O processamento em lote deve utilizar consultas agregadas sempre que possível, evitando uma consulta completa ao banco para cada recebível.

**6. VERIFICAÇÃO CADASTRAL**

A validação de dígitos verificadores de um CNPJ não comprova que a empresa está ativa na Receita Federal.

O motor deve distinguir:

- `ATIVA`
- `INATIVA`
- `NAO_VERIFICADA`

Quando não existir fonte cadastral confiável ou a consulta estiver indisponível, não assumir situação `ATIVA`.

Definir explicitamente a política de tratamento de `NAO_VERIFICADA`, preservando a regra do fundo e apresentando uma mensagem adequada.

[LINHA_TABULAR_OMITIDA]

Não apresentar dados simulados como verificação oficial.

**7. CONCENTRAÇÃO POR SACADO**

A concentração deve ser calculada pela **raiz do CNPJ**, correspondente aos oito primeiros dígitos normalizados.

Diferentes filiais com a mesma raiz devem compartilhar a exposição.

Considerar:

1. Estoque existente no fundo.
2. Recebíveis previamente aprovados no lote.
3. Valor nominal do recebível em análise.
4. Carteira projetada após a operação.
5. Limite definido na versão ativa das regras.

Fórmula de referência:

```
concentracao_projetada =
    exposicao_projetada_do_grupo
    / valor_nominal_total_projetado_da_carteira
```

A inclusão no numerador e no denominador deve ser consistente.

[LINHA_TABULAR_OMITIDA]

[LINHA_TABULAR_OMITIDA]

Essa concentração histórica não deve provocar rejeição retroativa dos títulos já adquiridos.

**Decisão proposta para o MVP:** impedir novas aquisições que agravem uma concentração já acima do limite, sinalizando separadamente o excesso histórico.

[LINHA_TABULAR_OMITIDA]

**8. ANTIDUPLICIDADE E IDEMPOTÊNCIA**

Distinguir dois conceitos:

**Duplicidade de negócio:** impedir que o mesmo recebível seja adquirido mais de uma vez.

**Idempotência:** garantir que repetir a mesma requisição de aquisição não produza operações financeiras adicionais.

[LINHA_TABULAR_OMITIDA]

Portanto, não usar somente `DOC_CEDENTE + TIPO_RECEBIVEL + NU_DOCUMENTO` como identidade única.

Para o hackathon, utilizar inicialmente a chave composta:

```
DOC_CEDENTE
+ DOC_SACADO
+ TIPO_RECEBIVEL
+ NU_DOCUMENTO
+ DATA_VENCIMENTO_ORIGINAL
```

Normalizar os componentes antes de calcular a chave.

A identidade deve ser independente do fundo comprador, para evitar que trocar o fundo permita revender a mesma parcela.

Essa chave é uma aproximação adequada aos dados fornecidos, mas não substitui um identificador registral juridicamente confiável.

**Proteção obrigatória**

- Detectar duplicidade em relação ao estoque.
- Detectar duplicidade dentro do próprio CSV enviado.
- Permitir parcelas legítimas com vencimentos diferentes.
- Evitar falsos positivos por formatação de CNPJ.
- Informar claramente o motivo da rejeição.

**Proteção transacional, caso exista aquisição**

Se uma funcionalidade de confirmação de compra for implementada:

- Usar chave de idempotência.
- Utilizar transação PostgreSQL.
- Aplicar restrição única aos títulos adquiridos ou reservados.
- Garantir que apenas uma aquisição concorrente seja confirmada.
- Atualizar carteira e exposições de forma atômica.
- Retornar conflito controlado quando necessário.

**Simulação não significa aquisição.**

O escopo obrigatório exige simular recebíveis. Não confundir uma nota simulada como aprovada com uma nota efetivamente comprada.

A confirmação de aquisição é um complemento, condicionado à disponibilidade de tempo.

**9. PRECIFICAÇÃO FINANCEIRA**

Utilizar o método de desconto simples configurado.

Fórmula de referência:

```
valor_liquido =
    valor_nominal * (1 - taxa_mensal * dias / base_dias)
```

Onde:

- `valor_nominal`: valor de face.
[LINHA_TABULAR_OMITIDA]
- `dias`: prazo entre a data-base e o vencimento.
- `base_dias`: inicialmente 30.

Exemplo:

```
Valor nominal: R$ 5.000,00
Prazo: 90 dias
Taxa mensal: 2%

Desconto: R$ 300,00
Valor líquido: R$ 4.700,00
```

Requisitos:

- Utilizar `Decimal`.
- Definir arredondamento consistente para centavos.
- Documentar a convenção financeira.
- Rejeitar resultados financeiros inválidos.
- Somar somente os valores líquidos aprovados.
- Registrar os parâmetros de precificação aplicados.

Não introduzir juros compostos ou taxas adicionais que não estejam previstas na configuração.

**10. VERSIONAMENTO DAS REGRAS**

Implementar versionamento imutável das configurações.

Cada alteração publicada gera uma nova versão, preservando as anteriores.

Exemplo:

```
Versão 1:
Prazo máximo = 180 dias
Concentração = 10%

Versão 2:
Prazo máximo = 120 dias
Concentração = 10%

Versão 3:
Prazo máximo = 120 dias
Concentração = 8%
```

O sistema deverá:

1. Armazenar o JSON completo de cada versão.
2. Registrar data e responsável pela alteração.
3. Registrar justificativa, quando fornecida.
4. Identificar a versão ativa de cada fundo.
5. Permitir consultar versões anteriores.
6. Validar o JSON antes de publicá-lo.
7. Impedir modificações em versões já publicadas.
8. Manter uma versão fixa durante cada simulação.
9. Vincular toda simulação à versão aplicada.
10. Proteger a ativação contra alterações concorrentes.

Estrutura sugerida para `rule_versions`:

```
id
fund_id
version_number
configuration_json
configuration_hash
created_at
created_by
change_reason
```

A seleção da versão ativa poderá ser armazenada em referência separada no cadastro do fundo.

Uma simulação iniciada com a versão 1 deverá continuar usando a versão 1, mesmo que a versão 2 seja ativada durante o processamento.

Para auditoria completa, registrar também:

- Data-base.
- Referência ao estado da carteira.
- Origem ou snapshot dos dados cadastrais.
- Parâmetros de precificação.
- Versão do motor de validação, quando necessário.

O JSON das regras não é suficiente para reproduzir decisões se o estoque ou as informações cadastrais tiverem mudado.

**11. MODELAGEM DO BANCO**

Entidades recomendadas:

```
funds
rule_versions
receivables
simulations
simulation_items
acquisition_requests
audit_events
```

Responsabilidades:

- `funds`: fundos e configuração ativa.
- `rule_versions`: versões imutáveis das políticas.
- `receivables`: carteira de títulos adquiridos.
- `simulations`: processamento de lotes.
- `simulation_items`: resultado individual de cada recebível.
- `acquisition_requests`: idempotência das aquisições, se implementadas.
- `audit_events`: eventos administrativos relevantes.

Criar índices para:

- Identidade normalizada do recebível.
- Fundo.
- Sacado.
- Raiz do CNPJ.
- Simulação.
- Versão da regra.

Evitar carregar todo o estoque na memória para cada requisição.

**12. API**

Endpoints sugeridos:

```
POST /api/simulations
GET  /api/simulations/{id}

POST /api/receivables/evaluate

GET  /api/rules
GET  /api/rules/versions

POST /api/rules/versions
POST /api/rules/versions/{id}/activate

GET  /api/health
```

A interface web e os consumidores externos devem utilizar o mesmo serviço de avaliação.

Não duplicar a lógica das regras no frontend.

As operações administrativas devem exigir autorização.

A API deverá produzir respostas estruturadas, com códigos estáveis e explicações amigáveis.

Exemplo:

```
{
  "simulation_id": "sim_001",
  "rule_version": 1,
  "data_base": "2026-10-22",
  "resultados": [
    {
      "documento": "NF-1024",
      "aprovado": true,
      "valor_nominal": "5000.00",
      "valor_liquido": "4700.00",
      "motivos": []
    },
    {
      "documento": "NF-1025",
      "aprovado": false,
      "valor_nominal": "2500.00",
      "valor_liquido": null,
      "motivos": [
        {
          "codigo": "PRAZO_MAXIMO",
          "mensagem": "Esta nota vence em 200 dias, mas o fundo aceita recebíveis com prazo máximo de 180 dias."
        }
      ]
    }
  ],
  "total_liquido": "4700.00"
}
```

**13. FRONTEND E EXPERIÊNCIA DO USUÁRIO**

[LINHA_TABULAR_OMITIDA]

A jornada principal será:

1. Acessar o portal.
2. Enviar CSV.
3. Visualizar progresso ou estado do processamento.
4. Consultar o resumo financeiro.
5. Identificar recebíveis aprovados e recusados.
6. Inspecionar os motivos das recusas.
7. Consultar o valor líquido de cada nota.
8. Visualizar o total disponível para antecipação.

**Elementos recomendados**

- Área de upload com arrastar e soltar.
- Validação de extensão e estrutura do arquivo.
- Resumo com quantidade de notas.
- Total nominal.
- Total líquido aprovado.
- Quantidade de aprovações e recusas.
- Tabela paginada ou virtualizada.
- Filtros por status e motivo.
- Explicação individual das recusas.
- Feedback para carregamento e erros.
- Identificação da versão das regras usada.

A mensagem para o usuário deve priorizar clareza.

Evitar apresentar somente:

```
CONCENTRATION_LIMIT_EXCEEDED
```

Preferir:

```
Este cliente já representa uma parcela elevada
da carteira do fundo. Por isso, a nota não pode
ser antecipada nas condições atuais.
```

Quando possível, apresentar o limite e o valor calculado.

**Administração**

Caso o tempo permita, criar uma tela administrativa para:

- Consultar regras.
- Ativar e desativar validadores.
- Alterar parâmetros.
- Validar um rascunho.
- Publicar nova versão.
- Consultar histórico.

Não permitir alteração direta de versões publicadas.

**14. TESTES OBRIGATÓRIOS**

Criar testes automatizados para, no mínimo:

1. CSV com separador `;`.
2. Decimal com vírgula.
3. Datas `dd/mm/aaaa`.
4. Arquivo com cabeçalho inválido.
5. CNPJ com dígitos verificadores inválidos.
6. Situação cadastral não verificada.
7. Tipo de recebível não permitido.
8. Valor abaixo do mínimo.
9. Nota vencida.
10. Prazo acima do máximo.
11. Validador desativado.
12. Alteração de parâmetro entre versões.
13. Concentração por raiz de CNPJ.
14. Concentração acumulada dentro do lote.
15. Duas parcelas legítimas com vencimentos diferentes.
16. Mesma parcela enviada duas vezes.
17. Duplicidade em relação ao estoque.
18. Cálculo financeiro e arredondamento.
19. Soma do total líquido.
20. Consistência entre API e interface web, preferencialmente por teste de integração ou E2E.

Se implementar aquisição, acrescentar teste concorrente demonstrando que apenas uma tentativa consegue adquirir o mesmo recebível.

Testar principalmente os limites: valores exatamente iguais ao mínimo, prazos exatamente iguais ao máximo e concentração exatamente igual ao percentual permitido.

**15. DOCUMENTAÇÃO E PROMPTS DE IA**

Manter os seguintes documentos:

**README.md**

Deve conter:

- Objetivo da aplicação.
- Tecnologias utilizadas.
- Pré-requisitos.
- Configuração de variáveis de ambiente.
- Comandos de instalação.
- Comandos para executar a aplicação.
- Inicialização do banco.
- Importação do estoque.
- Execução dos testes.
- Exemplos de uso da API.
- Principais decisões.
- Limitações conhecidas.

O projeto deverá ser executável do zero pelos jurados.

**docs/architecture.md**

Explicar:

- Arquitetura.
- Fluxo de dados.
- Motor de regras.
- Versionamento.
- Persistência.
- Concentração.
- Antiduplicidade.
- Idempotência.
- Decisões financeiras.

**docs/decisions.md**

Registrar decisões arquiteturais relevantes, justificativas e alternativas descartadas.

**docs/ai-prompts.md**

Registrar cronologicamente os prompts de IA utilizados durante o desenvolvimento.

Para cada interação, documentar:

```
Identificador:
Data/hora:
Agente ou ferramenta:
Objetivo:
Prompt enviado:
Resumo da resposta:
Arquivos afetados:
Decisão adotada:
Resultado/verificação:
```

Preservar o texto integral dos prompts relevantes.

Não inventar interações anteriores nem afirmar que um histórico está completo quando existirem ferramentas externas sem exportação disponível.

Sempre que possível, automatizar o registro de novas interações.

**16. COORDENAÇÃO DOS AGENTES**

Caso existam agentes especializados disponíveis, distribuir responsabilidades por domínio:

- **Arquitetura:** modelagem, integração entre módulos e decisões técnicas.
[LINHA_TABULAR_OMITIDA]
[LINHA_TABULAR_OMITIDA]
- **Frontend:** telas, componentes e integração com API.
[LINHA_TABULAR_OMITIDA]
- **QA:** testes, casos-limite e integração.
- **Segurança:** validação de entradas, permissões e integridade.
- **Documentação:** README, decisões e histórico dos prompts.

Estabelecer contratos de API e modelos compartilhados antes de executar implementações paralelas.

Evitar que dois agentes modifiquem simultaneamente o mesmo arquivo sem coordenação.

Cada responsável deverá informar:

- O que implementou.
- Quais arquivos alterou.
- Como verificou a implementação.
- Quais problemas permanecem.
- Quais decisões precisam de aprovação.

O orquestrador continua responsável pela integração e pela qualidade final.

**17. PRIORIZAÇÃO**

Adotar a seguinte ordem:

**P0 — Obrigatório**

- Aplicação executável.
- Importação do estoque.
- Upload CSV.
- Normalização correta.
- Leitura do JSON.
- Execução de todos os validadores ativos.
- Detecção de duplicidades.
- Cálculo da concentração.
- Precificação financeira.
- Motivos de recusa.
- Resultado por nota.
- Total líquido.
- API funcional.
- Interface web funcional.
- README.
- Histórico de prompts.

**P1 — Diferenciais**

- Versionamento persistente das regras.
- Interface de administração.
- Auditoria.
- Testes abrangentes.
- Histórico de simulações.
- Melhorias avançadas de UX.

**P2 — Opcionais**

- Confirmação de aquisição.
- Teste demonstrável de concorrência.
- Dashboard administrativo avançado.
- Exportação de relatórios.
- Integrações cadastrais adicionais.

Nunca comprometer os requisitos P0 para implementar funcionalidades P2.

**18. CRITÉRIOS DE ACEITE**

A implementação só poderá ser considerada concluída quando:

- Um usuário conseguir iniciar a aplicação seguindo o README.
- O sistema aceitar um CSV válido no formato fornecido.
- Todas as regras ativas forem executadas corretamente.
- Regras desativadas não influenciarem o resultado.
- O sistema impedir duplicidades na simulação.
- A concentração utilizar a raiz do CNPJ.
- Os valores financeiros forem calculados com precisão decimal.
- Cada recusa apresentar uma justificativa compreensível.
- A interface e a API retornarem decisões consistentes.
- O total líquido corresponder à soma dos recebíveis aprovados.
- Os testes críticos forem executados.
- O histórico dos prompts estiver documentado.
- A aplicação puder ser demonstrada aos jurados.

Para o versionamento, demonstrar adicionalmente:

1. Simulação realizada com versão 1.
2. Alteração e publicação da versão 2.
3. Nova simulação produzindo resultado diferente quando aplicável.
4. Simulação anterior preservando a referência à versão 1.

**19. INSTRUÇÕES DE EXECUÇÃO PARA O ORQUESTRADOR**

Ao receber este prompt:

**Primeiro — Inspecione o projeto.**

- Examine a estrutura existente do repositório.
- Leia os arquivos do desafio.
- Identifique implementações já concluídas.
- Confirme os parâmetros e códigos exatos do JSON.
- Detecte conflitos entre requisitos e código existente.

**Segundo — Planeje a execução.**

- Identifique tarefas P0 pendentes.
- Estabeleça dependências.
- Defina contratos entre frontend e backend.
- Distribua responsabilidades quando houver agentes disponíveis.
- Estime os riscos que ameaçam a entrega.

**Terceiro — Implemente incrementalmente.**

- Construa primeiro o fluxo ponta a ponta.
- Garanta que o motor usa a configuração real.
- Integre a carteira.
- Implemente concentração e antiduplicidade.
- Conecte o frontend.
- Adicione os diferenciais somente após estabilizar P0.

**Quarto — Verifique.**

- Execute testes.
- Identifique erros de integração.
- Valide cálculos financeiros.
- Inspecione o fluxo completo.
- Corrija falhas reproduzíveis.
- Confirme que o README corresponde ao funcionamento real.

**Quinto — Prepare a demonstração.**

Organize um roteiro curto com:

1. Upload de um CSV.
2. Exibição de recebíveis aprovados e recusados.
3. Explicação de uma recusa.
4. Demonstração do cálculo de desconto.
5. Demonstração de concentração ou duplicidade.
6. Alteração de uma regra, caso o versionamento esteja concluído.
7. Explicação da arquitetura e dos mecanismos de consistência.

**20. DIRETRIZES FINAIS**

- Priorize simplicidade funcional.
- Não invente requisitos.
- Não crie regras financeiras sem fundamento.
- Não ignore validadores ativos.
- Não use valores financeiros fixos no código.
- Não trate CNPJ válido como prova de situação cadastral ativa.
- Não confunda simulação com aquisição.
- Não trate parcelas distintas como títulos duplicados.
- Não descarte registros inválidos silenciosamente.
- Não altere versões publicadas.
- Não afirme que testes passaram sem executá-los.
- Não invente histórico de prompts.
- Não introduza dependências desnecessárias.
- Não reestruture código funcional sem motivo concreto.
- Não realize deploy ou publicações externas sem autorização.

[LINHA_TABULAR_OMITIDA]

O resultado precisa funcionar de verdade, ser reproduzível pelos jurados e permitir explicar tecnicamente cada decisão tomada.

[LINHA_TABULAR_OMITIDA]
````

- Última mensagem do assistente (prévia, não prova execução):

```text
Base local do Antecipe funcional em http://127.0.0.1:3000 com API em 8000. O usuario priorizou lancamento da base e testes manuais incrementais. Demo atualizada confirmou nove notas e liquido 4700.00. Foram preservados os testes existentes e reduzida a validacao a regressao critica. Instalacao limpa do frontend nao foi comprovada por bloqueio npm e ausencia de cache. PostgreSQL e Docker nao executados. Benchmarks anteriores sao historicos. Nenhum commit ou push realizado.
```

- **O que foi feito com a resposta:** Entregue base LOCAL funcional de simulacao conforme corte de escopo do usuario. Corrigidos centavos e capacidade monetaria cumulativa. Frontend local validado com dependencias controladas. Integracao em copia apos pull e0c5349 preservou staging original e registros da equipe. Revisao do diff preservou hooks remotos com python disponivel. Instalacao limpa frontend e diferenciais ficam no proximo ciclo. Sem commit ou push.
- Arquivos/artefatos: Codex/antecipe/backend Codex/antecipe/frontend Codex/antecipe/qa Codex/antecipe/README.md Codex/antecipe/docs/TASK_STATE.md docs/EVIDENCIAS.md docs/prompts-events.jsonl docs/REGISTRO_PROMPTS_CARLOS.md .claude/settings.json .codex/hooks.json
- Verificação: Seis testes financeiros aprovados. Dois cenarios independentes criticos validados com reteste apenas da assercao textual corrigida. Frontend test lint build aprovados na arvore local controlada com build em 1.49s. Smoke nove notas confirmou um aprovado oito recusados e liquido 4700.00. Navegador conectado sem erros observados. Kit oito testes aprovado. JSON dos hooks e disponibilidade de python conferidos. Reproducibilidade npm ci nao comprovada. Benchmarks anteriores historicos. Sem PostgreSQL Docker ou Gitleaks executados.

## P0003 — 2026-10-24T13:35:31+00:00 — user

- Sessão: `manual`
- SHA-256 do prompt original: `6d171fb42b32ed7a8626f693cf3be0e0c237c4c27019880a8ca4c49efc892a53`
- Texto do prompt (sanitizado):

```text
repositório git atualizado, nossos prompts ficam dentro da pasta docs no registry de Carlos
```

- Última mensagem do assistente (prévia, não prova execução):

```text
Roteamento e sincronização com docs/REGISTRO_PROMPTS_CARLOS.md configurados no prompt ledger sem conflitos no git
```

- **O que foi feito com a resposta:** Ajustado prompt_ledger.py para manter sincronizados docs/REGISTRO_PROMPTS_CARLOS.md e docs/REGISTRO_PROMPTS.md
- Arquivos/artefatos: [LINHA_TABULAR_OMITIDA]
- Verificação: python scripts/prompt_ledger.py status; python tests/test_kit.py

## P0004 — 2026-10-24T14:07:00+00:00 — orchestrator

- Sessão: `manual`
- SHA-256 do prompt original: `13614c8892456982f7c7181e49049d38b7f183ea1eeb48a64b87e145b0e84288`
- Texto do prompt (sanitizado):

```text
Delegação técnica do Orquestrador (Carlos) para o Agente Motor de Domínio (5c877889):
- Escopo exclusivo: Codex/antecipe/backend/domain/** e backend/tests/test_domain*.py
[LINHA_TABULAR_OMITIDA]
- Verificação: 24 testes unitários e de integração iniciais em test_domain_engine.py.
```

- Última mensagem do assistente (prévia, não prova execução):

```text
Implementação do motor concluída em Codex/antecipe/backend/domain/ com 37 testes automatizados passando
```

- **O que foi feito com a resposta:** Implementação modular de regras e domínio em backend/domain/
- Arquivos/artefatos: [LINHA_TABULAR_OMITIDA]
- Verificação: python -m unittest Codex/antecipe/backend/tests/test_domain_engine.py

## P0005 — 2026-10-24T14:07:39+00:00 — orchestrator

- Sessão: `manual`
- SHA-256 do prompt original: `c788d81eecb0d9fe1dca2746ad3082701fdf3d12b6ab3094806048f6ec027238`
- Texto do prompt (sanitizado):

```text
Delegação técnica do Orquestrador (Carlos) para o Agente Backend/API/Persistência (f333df74):
[LINHA_TABULAR_OMITIDA]
[LINHA_TABULAR_OMITIDA]
- Verificação: 20 testes de API cobrindo contratos HTTP e execução integrada.
```

- Última mensagem do assistente (prévia, não prova execução):

```text
[LINHA_TABULAR_OMITIDA]
```

- **O que foi feito com a resposta:** Implementação da camada de API e persistência em backend/
- Arquivos/artefatos: [LINHA_TABULAR_OMITIDA]
- Verificação: python -m pytest Codex/antecipe/backend/tests -q

## P0006 — 2026-10-24T14:07:58+00:00 — orchestrator

- Sessão: `manual`
- SHA-256 do prompt original: `56582089508113bf72cb38bc980b456cbb19cee4fbf9bd00d16fe066f6102934`
- Texto do prompt (sanitizado):

```text
Delegação técnica do Orquestrador (Carlos) para o Agente Frontend/UX (bc5051a0):
- Escopo exclusivo: Codex/antecipe/frontend/**.
[LINHA_TABULAR_OMITIDA]
- Verificação: Typecheck estrito (tsc --noEmit), build de produção (vite build) e inspeção via browser preview.
```

- Última mensagem do assistente (prévia, não prova execução):

```text
Frontend React 19 + TypeScript + Vite implementado, validado com tsc e build de produção sem erros
```

- **O que foi feito com a resposta:** Desenvolvimento do frontend com acessibilidade WCAG 2.2 AA
- Arquivos/artefatos: [LINHA_TABULAR_OMITIDA]
- Verificação: npm --prefix Codex/antecipe/frontend run build; npm --prefix Codex/antecipe/frontend run lint

## P0007 — 2026-10-24T14:11:33+00:00 — user

- Sessão: `manual`
- SHA-256 do prompt original: `405b8cb762dd99c251212a758071b6b2eb2b80d64e206034fb4dfc9724ced838`
- Texto do prompt (sanitizado):

```text
para subagentes use somente gemini 3.8 flash via omp. Susbstitua sol 5.6 para sol 6.1 quando
```

- Última mensagem do assistente (prévia, não prova execução):

```text
Política de subagentes restrita exclusivamente ao Gemini 3.8 Flash via OMP registrada; agentes Sol 5.6 e Kimi arquivados sem alteração de diretrizes globais para a sentença incompleta
```

- **O que foi feito com a resposta:** Registro do steering do usuário sobre modelos de subagentes (Gemini 3.8 Flash via OMP exclusivo)
- Arquivos/artefatos: docs/REGISTRO_PROMPTS_CARLOS.md,docs/REGISTRO_PROMPTS.md
- Verificação: python scripts/prompt_ledger.py status; python tests/test_kit.py

## P0008 — 2026-10-24T14:23:01+00:00 — user

- Sessão: `manual`
- SHA-256 do prompt original: `a7ff4f51db6e6535d36ea006be174cf9522c39f24a82ca064380431e9f282da7`
- Texto do prompt (sanitizado):

```text
[LINHA_TABULAR_OMITIDA]
```

- Última mensagem do assistente (prévia, não prova execução):

```text
Diretriz de Git registrada: ao concluir a base do desenvolvimento e antes de qualquer envio ao Git, realizar pull da versão mais recente do remoto preservando o trabalho local; workers proibidos de executar comandos Git destrutivos
```

- **O que foi feito com a resposta:** Registro do steering do usuário sobre atualização prévia via pull antes de subir para o Git
- Arquivos/artefatos: docs/REGISTRO_PROMPTS_CARLOS.md,docs/REGISTRO_PROMPTS.md
- Verificação: python scripts/prompt_ledger.py status; python tests/test_kit.py

## P0009 — 2026-10-24T14:45:10+00:00 — user

- Sessão: `manual`
- SHA-256 do prompt original: `c3cb6fcb0cb86b6723039d69e5b4bb38799670bd3526d082cc65d1ae45d1bc97`
- Texto do prompt (sanitizado):

```text
"C:\hackathon_kanastra\resultado_esperado_100k.json"
```

- Última mensagem do assistente (prévia, não prova execução):

```text
[LINHA_TABULAR_OMITIDA]
```

- **O que foi feito com a resposta:** [LINHA_TABULAR_OMITIDA]
- Arquivos/artefatos: docs/EVIDENCIAS.md,docs/ESPECIFICACAO.md
- Verificação: python scripts/prompt_ledger.py status; python tests/test_kit.py

## P0010 — 2026-10-24T14:58:05+00:00 — user

- Sessão: `manual`
- SHA-256 do prompt original: `2738dc27f5a11c3556e508214b63d6256da56749813184d5514165ee12df1a32`
- Texto do prompt (sanitizado):

```text
[LINHA_TABULAR_OMITIDA]
```

- Última mensagem do assistente (prévia, não prova execução):

```text
[LINHA_TABULAR_OMITIDA]
```

- **O que foi feito com a resposta:** Registro do alinhamento de retomada pós-troca de provider: atualização factual de gabarito e limites técnicos de precisão
- Arquivos/artefatos: [LINHA_TABULAR_OMITIDA]
- Verificação: python scripts/prompt_ledger.py status

## P0011 — 2026-10-24T15:12:51+00:00 — traycer-coordenador

- Sessão: `manual`
- SHA-256 do prompt original: `ba9da98898f3ef56875e9a9ac8801bb057202a28094bc6c2bf20c403880bad97`
- Texto do prompt (sanitizado):

```text
`diferenciais.md`  diminua a quantidade de testes para lançarmos a versão base logo e poder continuar as melhoriase testes manuasi a partir dela
```

- Última mensagem do assistente (prévia, não prova execução):

```text
Diferenciais lidos e mantidos como backlog. Suspensa a expansão de testes e os novos benchmarks. Preservados os testes existentes. Executadas somente regressões monetárias críticas e smoke da demonstração; instalação frontend ainda em correção. Nenhum commit ou push realizado.
```

- **O que foi feito com a resposta:** [LINHA_TABULAR_OMITIDA]
- Arquivos/artefatos: [LINHA_TABULAR_OMITIDA]
- Verificação: [LINHA_TABULAR_OMITIDA]

## P0012 — 2026-10-24T15:34:40+00:00 — traycer-coordenador

- Sessão: `manual`
- SHA-256 do prompt original: `2e4e805c2c7fa7051d0eb81d669f59dad944288f0901a63fdc77268e219ba25f`
- Texto do prompt (sanitizado):

```text
pode subir no github e atualizar no vercel
```

- Última mensagem do assistente (prévia, não prova execução):

```text
Base publicada em https://github.com/carlinnnd/hackathon-kanastra e https://hackathon-kanastra.vercel.app. Vercel READY em Python 3.12. Demo publica usa cinco titulos sinteticos e resultados temporarios. Navegador confirmou nove notas com uma aprovada e oito recusadas. Liquido 4700.00. Filtro mostrou oito linhas e restaurou nove sem GET por ID. Dados reais e banco local nao publicados. Persistencia entre instancias nao foi implementada.
```

- **O que foi feito com a resposta:** Executados pulls antes dos pushes em worktree separado. Publicada base na main e preservada atualizacao remota de Elias por merge. Criados entrada ASGI e manifesto Vercel com demo sintetica isolada. Primeira build falhou no include requirements e foi corrigida com pins planos existentes. Corrigido filtro da demo com snapshot em memoria sem alterar regras financeiras. Publicacao final pronta e verificada. Nenhum servico de banco pago criado. Staging original preservado.
- Arquivos/artefatos: app.py requirements.txt .python-version vercel.json .vercelignore .gitignore public Codex/antecipe/backend/vercel_app.py Codex/antecipe/backend/config.py Codex/antecipe/backend/api/routes.py Codex/antecipe/backend/tests/test_vercel_demo.py Codex/antecipe/frontend Codex/antecipe/README.md README.md docs/EVIDENCIAS.md docs/prompts-events.jsonl
- Verificação: Wrapper smoke dirigido aprovado em 2.26s. Guard recusou banco fora de TMP sem cria-lo. Kit 8 testes aprovado em 1.207s. Frontend test lint build aprovado com build 2.42s apos corrigir carregamento de helper no runner. Deploy dpl_Cj1UA5ksJt3pAgFLGT3uM8CasH27 READY. HTTP publico health e carteira OK. Arquivos privados .env.local e antecipe.db retornaram404. Navegador bundle index-CnKj22BH.js exibiu9notas1aprovado8recusados nominal30050.00 liquido4700.00. Filtro8restauracao9 semalertas e semGETporID. Instalacao limpa npm e persistencia entre instancias continuam limitacoes documentadas.

