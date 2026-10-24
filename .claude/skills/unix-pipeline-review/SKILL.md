---
name: unix-pipeline-review
description: Use para projetar, separar ou auditar módulos de ingestão, validação, transformação e saída conforme filosofia Unix e código limpo.
---

# Unix pipeline review

1. Mapear entrada, saída, contrato de erros e efeitos colaterais de cada componente.
2. Limitar cada módulo a responsabilidade coesa. Prefira funções que aceitem iteradores/lotes a carregar tudo na memória.
3. Verificar que stdout para dados e stderr para diagnóstico não se misturam; CLI expõe `--input`, `--output`, código de saída e `--help`.
4. Revisar testes unitários isolados e teste de integração compondo todas as etapas.
5. Medir gargalo antes de adicionar filas, microserviços, threads ou workers. Documentar trade-offs em `docs/DECISOES_TECNICAS.md`.
6. Registrar arquivos e comandos de prova em `docs/EVIDENCIAS.md`.

Não exigir pipes Unix físicos quando o desafio pede web app; os princípios principais são componentes pequenos, interfaces claras e composição.
