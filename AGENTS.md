# Orientações persistentes — hackathon

1. Leia `docs/CRITERIOS.md`, `docs/ESPECIFICACAO.md` e `docs/EVIDENCIAS.md` antes de alterar código.
2. Priorize pontos verificáveis: escalabilidade (35), UX (25), Unix/organização (20), logs/credenciais (15), prompts (5).
3. Jamais invente regras de recusa, schema CSV, números de throughput, latência, cobertura ou pontos. Registre premissas e teste com o enunciado completo.
4. Alterações de lógica devem ter teste. Para alto volume, medir 100 mil e 500 mil linhas no mesmo ambiente e registrar versão, comando, horário e resultados reais.
5. Nunca coloque credenciais, linhas/dados do CSV, payload bruto ou dados pessoais em logs; adote campos permitidos explícitos. Não faça commit de `.env` nem dados reais.
6. Para cada interação, mantenha `docs/REGISTRO_PROMPTS.md` cronológico. O hook captura a entrada e a resposta; após execução, confirme a ação, arquivos e verificação com `scripts/prompt_ledger.py close`. Caso o hook falhe, use `manual`.
7. Agentes trabalham com escopo e arquivos exclusivos; coordenador integra. Não presuma que skills/CLIs externos estejam instalados.
8. Antes de afirmar conclusão, execute testes e `python3 scripts/check_submission.py` e `python3 scripts/prompt_ledger.py audit`; cite evidências e pendências.
9. Sem mudanças destrutivas em dados ou histórico Git sem autorização. Não use flags que ignorem controles de segurança.
