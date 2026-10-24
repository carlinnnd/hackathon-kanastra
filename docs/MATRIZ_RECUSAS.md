# Matriz de recusas da interface — Antecipe FIDC

> **Status:** Regras e causas mapeadas com base nas políticas oficiais do `validadores_antecipe.json`, nas restrições de carteira/duplicidade do briefing oficial e nos contratos de API do sistema.

---

## 1. Princípios de UX para Mensagens de Recusa (WCAG 2.2 e Critério 5.2.2)

1. **Linguagem Simples e Direta:** Sem códigos incompreensíveis isolados ou termos jurídicos herméticos.
2. **Não Culpar o Usuário:** Focar no fato objetivo que impediu a aquisição pelo fundo.
3. **Causa Explícita e Próximo Passo Acionável:** Explicar claramente o parâmetro exigido e como sanar ou prosseguir.
4. **Sem Vazamento de Dados Sensíveis:** Nunca expor dados pessoais (PII), credenciais ou conteúdo bruto confidencial do CSV nas mensagens de erro ou logs.

---

## 2. Catálogo Oficial de Recusas de Títulos (Códigos Canônicos e Aliases)

| Código Canônico (`codigo`) | Aliases Suportados | Condição Exata de Disparo | Texto Apresentado ao Usuário | Explicação / Próximo Passo Acionável |
| :--- | :--- | :--- | :--- | :--- |
| **`VALOR_MINIMO`** | - | `valor_nominal < 100.00` | Valor Nominal Inferior ao Mínimo | O fundo adquire recebíveis com valor a partir de R$ 100,00. Confira o valor de face com o documento fiscal original. |
| **`PRAZO_MAXIMO`** | - | `data_vencimento - data_base > 180 dias` | Prazo de Vencimento Superior ao Limite | O prazo máximo aceito é de 180 dias a contar da data-base (22/10/2026). Submeta recebíveis com vencimento compatível com o prazo operacional do fundo. |
| **`NAO_VENCIDA`** | `NAO_VENCIDO` | `data_vencimento < data_base` | Título Já Vencido | Somente recebíveis vigentes ou vencendo na data-base podem ser antecipados. Verifique se o vencimento original está correto. |
| **`TIPO_RECEBIVEL`** | - | `tipo not in ["Duplicata", "Duplicata de Serviço"]` | Tipo de Recebível Não Aceito | O ANTECIPE FIDC adquire exclusivamente Duplicatas e Duplicatas de Serviço (Cheques, CCBs e Notas Comerciais não são aceitos). |
| **`CNPJ_SACADO_VALIDO`** | `CNPJ_VALIDO`, `CNPJ_INVALIDO` | Dígitos verificadores do sacado matematicamente incorretos | CNPJ do Sacado Inválido | O documento do sacado possui dígitos verificadores inconsistentes ou formatação inválida. Verifique o CNPJ e reenvie com a numeração correta de 14 dígitos. |
| **`SITUACAO_CADASTRAL_SACADO`** | `SITUACAO_CADASTRAL` | Situação cadastral diferente de `ATIVA` (incluindo `NAO_VERIFICADA`) | Situação Cadastral Incompatível do Sacado | A política do fundo exige situação cadastral ATIVA confirmada. Títulos não verificados em base oficial são classificados como inelegíveis. |
| **`CONCENTRACAO_MAXIMA_SACADO`** | `CONCENTRACAO_SACADO` | Exposição projetada da raiz do CNPJ $> 10{,}0\%$ | Limite de Concentração por Raiz Excedido | A exposição acumulada deste sacado (mesma raiz de 8 dígitos do CNPJ) ultrapassa o teto permitido de 10% da carteira do fundo. (Nota: exposição exatamente igual a 10,0% é aceita). |
| **`DUPLICIDADE_HISTORICA`** | `DUPLICIDADE_ESTOQUE` | Identidade idêntica já presente no estoque histórico de qualquer fundo da base | Título Já Presente no Estoque Histórico | A chave global do título (cedente, sacado, tipo, documento e vencimento) coincide com título previamente adquirido na carteira histórica global. |
| **`DUPLICIDADE_LOTE`** | - | Mesma identidade composta repetida dentro da mesma remessa enviada | Título Duplicado Dentro do Próprio Lote | Foi detectada mais de uma ocorrência idêntica deste recebível no mesmo arquivo. Apenas a primeira ocorrência foi analisada; as repetições foram descartadas. |
| `PRAZO_MINIMO` | - | `data_vencimento - data_base < 30 dias` (Regra inativa por padrão) | Prazo Inferior ao Mínimo Permitido | O prazo residual entre a data-base e o vencimento é inferior à carência mínima estipulada pelo fundo. |
| `CONCENTRACAO_MAXIMA_CEDENTE` | `CONCENTRACAO_CEDENTE` | Exposição projetada do cedente $> 8{,}0\%$ (Regra inativa por padrão) | Limite de Concentração do Cedente Excedido | A exposição do cedente excede o limite percentual permitido na carteira. |

---

## 3. Recusas Estruturais de Arquivo e Ingestão

| Código Canônico | Aliases / Nomes | Condição de Disparo | Mensagem ao Usuário | Ação Recomendada |
| :--- | :--- | :--- | :--- | :--- |
| **`CABECALHO_INVALIDO`** | `ARQUIVO_CABECALHO_INVALIDO` | Cabeçalho CSV ausente ou com nomes de colunas divergentes dos 11 oficiais | Estrutura de Cabeçalho Inválida | Baixe a planilha modelo de demonstração (`demo.csv`) e confira se os 11 cabeçalhos estão presentes com separador ponto e vírgula (`;`). |
| **`FORMATO_ARQUIVO_INVALIDO`** | `ARQUIVO_FORMATO_INVALIDO` | Extensão diferente de `.csv` ou codificação inválida (não UTF-8) | Formato de Arquivo Inválido | Salve seu arquivo como CSV delimitado por ponto e vírgula com codificação UTF-8 e tente novamente. |
| **`PAYLOAD_VAZIO`** | `ARQUIVO_VAZIO` | Arquivo sem linhas de recebíveis além do cabeçalho | O arquivo selecionado está vazio | Certifique-se de que o arquivo contém ao menos uma linha de recebível além do cabeçalho. |
| **`FORMATO_INVALIDO_VALOR`** | - | Valor nominal com caracteres inválidos ou frações além de centavos | Formato do Valor Nominal Inválido | Informe valores com separador decimal correto e precisão máxima de 2 casas decimais (ex: 1500,00). Frações adicionais são rejeitadas (ADR-008). |
| **`CAMPOS_OBRIGATORIOS_VAZIOS`** | - | Linha com campos essenciais em branco | Campos Obrigatórios em Branco | Preencha todas as colunas obrigatórias da planilha antes do envio. |
| **`LINHA_MALFORMADA_COLUNAS`** | - | Quantidade de colunas da linha difere de 11 | Linha com Número Divergente de Colunas | Verifique se não há delimitadores de ponto e vírgula extras ou aspas não fechadas na linha. |
| **`VALOR_EXCEDE_CAPACIDADE`** | - | Valor nominal acima do teto técnico `Numeric(15,2)` (`R$ 9.999.999.999.999,99`) | Valor Nominal Acima da Capacidade Técnica | O valor nominal excede a capacidade máxima de precisão centesimal exata suportada pelo sistema. |
| **`SESSAO_EXPIRADA`** | - | Sessão autenticada expirada ou inválida na conexão WebSocket/HTTP | Sessão Expirada ou Não Autenticada | Saia e realize login novamente para renovar sua sessão antes de enviar o arquivo. |

---

## 4. Contrato Binário Vigente (`APROVADA` ou `RECUSADA`) — 24/10/2026

Para novas notas submetidas à simulação (via CSV, API JSON ou WebSocket), o sistema adota **exclusivamente decisão binária (`APROVADA` ou `RECUSADA`)**:
- **Ausência de confirmação cadastral (`NAO_VERIFICADA`):** Recusa determinística pelo código canônico `SITUACAO_CADASTRAL_SACADO`, com mensagem explicando que não foi possível confirmar que o sacado está ativo e orientando confirmar/atualizar o cadastro antes de reenviar.
- **Erros de formatação ou dados insuficientes:** Recusam o item preservando o código e motivo específico (`FORMATO_INVALIDO_VALOR`, `CAMPOS_OBRIGATORIOS_VAZIOS`, `VALOR_EXCEDE_CAPACIDADE`, etc.), sem precificar como zero.
- **Análise descritiva da carteira histórica:** Exibida separadamente sem simular nova aquisição. Fontes e conferências detalhadas em `Codex/antecipe/docs/RESULTADOS_E_CADASTRO.md`.
