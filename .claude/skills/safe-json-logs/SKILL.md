---
name: safe-json-logs
description: Use ao implementar ou revisar logs estruturados e credenciais, especialmente para impedir que conteúdo do CSV, tokens e dados pessoais apareçam em logs e commits.
---

# Logs e secrets seguros

1. Criar schema JSON com allowlist de atributos por evento: `timestamp`, `level`, `event`, `job_id`, `stage`, `rows_*`, `duration_ms`, `error_code`.
2. Proibir conteúdo de CSV, valores de linha, identificadores pessoais, credenciais, prompt sensível, requisições completas e exceções com payload.
3. Usar IDs gerados para correlacionar trabalhos; distinguir estado de rejeição de erro de sistema.
4. Testar com string sentinela em CSV sintético. Procurar a sentinela em stdout/stderr/logs/traces e falhar o teste se houver ocorrência.
5. Verificar segredos em arquivos e histórico Git usando Gitleaks quando disponível (`gitleaks dir .` e `gitleaks git .`) e auditoria manual. Não publicar falsos negativos como certeza de segurança.
6. Revisar política de acesso e retenção dos logs; em caso de segredo vazado, tratar como comprometido e rotacionar, sem mostrar o valor.

Fontes: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html e https://opentelemetry.io/docs/security/handling-sensitive-data/
