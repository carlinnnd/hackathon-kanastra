---
name: prompt-evidence-ledger
description: Use para registrar cronologicamente prompts, respostas, decisões, alterações e testes do hackathon, atendendo às seções 4.1.2 e 5.2.5.
---

# Registro de prompts com evidência

1. Após cada interação, rodar `python3 scripts/prompt_ledger.py status` e identificar entrada pendente.
2. Hooks `UserPromptSubmit` capturam texto e hash; `Stop` captura a última mensagem quando disponível. Cliente sem hook exige `manual --source ... --prompt-file ...`.
3. Após aplicar ou descartar a resposta, rodar `close --id ... --action ... --files ... --verification ...`. A ação deve descrever realmente o que foi feito: modificação, teste, nenhuma alteração ou descarte com motivo.
4. Manter ordem cronológica, inclusive tentativas fracassadas. Guardar `docs/prompts-events.jsonl` versionado e reconciliar `docs/REGISTRO_PROMPTS.md`. Nunca editar/remover eventos para tornar narrativa mais bonita.
5. Antes da submissão rodar `audit` e inspecionar o Markdown. Sanitização de PII/segredos tem prioridade; informar ao júri que trechos confidenciais foram ocultados.

Limite: o hook não comprova se o agente realmente mudou arquivos, não cobre outro aplicativo nem faz retrospectiva. A reconciliação com diffs/testes é parte indispensável do processo.
