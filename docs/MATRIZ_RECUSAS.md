# Matriz de recusas da interface

As causas reais dependem do edital e ainda precisam de confirmação.

| Código sugerido | Condição exata | Texto ao usuário | O que fazer | Como testar | Estado |
| --- | --- | --- | --- | --- | --- |
| `INVALID_SCHEMA` | PENDENTE | O arquivo não tem as colunas esperadas. | Confira o modelo do arquivo e envie novamente. | CSV sintético com cabeçalho diferente | Modelo, não validado |
| `INVALID_ROW` | PENDENTE | Algumas linhas não passaram na validação. | Consulte o total de recusas e corrija os campos indicados sem expor outros dados. | Linhas sintéticas inválidas | Modelo, não validado |
| `PROCESSING_FAILED` | PENDENTE | Não foi possível concluir o processamento. | Tente novamente ou use o identificador do processamento para suporte. | Falha sintética de processo | Modelo, não validado |

Regras: identificar o problema em linguagem simples, não culpar o usuário, informar solução, exibir contagens e status, e garantir que a interface não exponha dados sensíveis. Não mostrar dados brutos da linha rejeitada se o edital proibir.
