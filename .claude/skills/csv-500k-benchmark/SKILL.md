---
name: csv-500k-benchmark
description: Use para construir, otimizar ou validar pipelines de CSV entre 100 mil e 500 mil linhas, medindo throughput, correção, memória e tempo de forma reproduzível.
---

# CSV 500k benchmark

1. Ler `docs/ESPECIFICACAO.md`. Perguntar ou marcar qualquer campo/regra desconhecido; não criar business rules fictícias.
2. Criar casos mínimos com CSV sintético, aspas, UTF-8, quebras de linha em valores, campos ausentes, duplicatas e saídas esperadas aprovadas pelo enunciado.
3. Começar pelo streaming da biblioteca padrão `csv`; só migrar para Polars/DuckDB se benchmarks e semântica justificarem. `Polars.scan_csv` e `collect(engine="streaming")` não tornam toda operação streaming automaticamente. Avaliar planos com joins, ordenações e filtros.
4. Gerar entradas sintéticas com `python3 scripts/generate_fixture.py --rows 100000 --output .hackathon/datasets/100k.csv` e 500000.
5. Rodar `python3 scripts/benchmark.py --rows 100000 500000 --runs 3 --command "COMANDO_A_ADAPTAR --input {input} --output {output}"`. O runner valida execução e saída básica, não conhece a semântica do projeto.
6. Comparar resultados com testes de aceites/recusas, documentar máquina/runtime/commit, aquecimento e valores individuais. Não prometer p95 estatisticamente robusto com apenas 3 execuções; descrevê-lo como p95 amostral quando reportado.
7. Inserir evidências em `docs/EVIDENCIAS.md`.

Fonte técnica: https://docs.pola.rs/user-guide/lazy/execution/ e https://duckdb.org/docs/current/guides/performance/oom
