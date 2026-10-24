---
name: ux-rejection-messages
description: Use ao desenhar interface de processamento CSV e mensagens de recusa, com UX clara, acessibilidade e estados de erro validados.
---

# UX de recusas

1. Obter motivos oficiais de recusa. Não inferir regra inexistente.
2. Preencher `docs/MATRIZ_RECUSAS.md` com código, condição, texto simples, próximo passo, teste e screenshot/inspeção real.
3. Criar fluxo completo: pré-upload, validação, processando, sucesso parcial, recusa, erro geral, retry, download e estados vazios.
4. Aplicar consistência visual e responsividade. Não maquiar erros com estética; medir legibilidade e recuperação de tarefa.
5. Testar teclado, foco, descrição textual do erro, labels, live region de progresso, contraste e acessibilidade básica WCAG 2.2.
6. Fazer teste manual de ao menos três cenários sintéticos: arquivo aceito, recusa tratável e erro inesperado.

Referência: https://www.w3.org/WAI/WCAG22/Understanding/error-identification e https://www.w3.org/WAI/WCAG22/Understanding/error-suggestion.html
