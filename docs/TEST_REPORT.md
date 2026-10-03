# Projeto Lobo 2 — TEST_REPORT.md (Lobo Forecast AI)

**Versão avaliada:** V1.1.1 — Performance & Final Verification
**Ferramentas:** pytest, ruff (lint), GitHub Actions (CI), verificação manual do dashboard (Playwright)

## Resultado da execução (pytest)

```
64 passed in 14.77s
```

(59 testes da V1.1 + 1 novo teste de equivalência matemática
lote-vs-produto-a-produto + 4 novos testes de regressão numérica.)

## Resultado do lint (ruff)

```
$ ruff check src/ tests/
All checks passed!
```
Comando executado de fato nesta sessão (não é uma afirmação sem
verificação) — 0 problemas encontrados.

## Novidades de teste na V1.1.1

| Arquivo | Testes | Cobre |
|---|---|---|
| `tests/test_backtest_smoke.py` | 2 | smoke test reduzido e isolado do backtest (extraído de `test_pipeline_integration.py`); **prova de equivalência matemática** entre `recursive_forecast_batch()` (otimizado, em lote) e `recursive_forecast()` (original, produto-a-produto) |
| `tests/test_regression_numerical.py` | 4 | resultados reais do pipeline (one-step-ahead, backtest multi-horizon, reposição) dentro de tolerância numérica dos valores de referência já auditados da V1.1; pulados se o artefato ainda não existir |

## Novidades de teste na V1.1 (herdadas, inalteradas)

| Arquivo | Testes | Cobre |
|---|---|---|
| `tests/test_inventory_semantics.py` | 4 | convenção temporal do `inventory_snapshot` (fechamento pós-movimentos da semana), prova direta de ausência de uso de informação futura (muda consumo futuro e confirma que semanas passadas não mudam), semana de consumo zero não altera estoque |
| `tests/test_pipeline_integration.py` | 8 | fluxo completo dados→validação→SQLite→features→treino→avaliação→forecast→reposição via subprocess; integridade dos artefatos gerados em cada etapa; smoke test do backtest multi-horizon em diretório isolado (`tmp_path`) |
| `tests/test_replenishment.py` (+2) | 2 novos | texto da prioridade BAIXA credita corretamente "disponível + em trânsito" (não só o disponível); CRÍTICA ignora `in_transit` por design mesmo quando ele é alto |

Testes herdados da V1.0 (inalterados): `test_data_quality.py` (15),
`test_database.py` (8), `test_forecasting.py` (11), `test_app_smoke.py` (3),
`test_replenishment.py` (8 originais).

## Comportamento inesperado encontrado durante a implementação da V1.1

Durante o desenvolvimento do smoke test do backtest multi-horizon
(`test_backtest_multihorizon_runs_end_to_end`), a primeira versão do teste
rodava `backtest_multihorizon.run_backtest()` com poucas origens (para ser
rápido) mas gravava a saída no MESMO caminho usado em produção
(`results/backtest_multihorizon_summary.csv`) — ou seja, **rodar a suíte de
testes sobrescrevia silenciosamente o resultado real do backtest de
produção com a versão reduzida de 2 origens**, sem nenhum erro visível.
Isso foi detectado ao comparar o arquivo antes/depois de rodar `pytest` e
notar `n_obs` divergente do esperado. Corrigido isolando a saída do teste
em `tmp_path` (diretório temporário do pytest, via monkeypatch de
`config.RESULTS_DIR`) e adicionando uma asserção explícita que falha caso
o arquivo real de `results/` seja alterado pelo teste. **Lição:** depois de
rodar `pytest`, sempre reexecute `python src/backtest_multihorizon.py`
manualmente antes de considerar os números finais — o `README.md`
documenta essa ordem.

## Verificação manual do dashboard

O Streamlit foi executado localmente (`streamlit run app.py`) e todas as 5
páginas foram reabertas e fotografadas de verdade com Playwright (headless
Chromium) após as mudanças da V1.1 — não são mockups. Screenshots em
`images/dashboard_*.png`: Visão Geral, Forecast, Estoque, Qualidade do
Modelo, Dados. Todas carregaram sem erro e exibiram os números reais
calculados pelo pipeline, incluindo o gráfico "Real x Previsto" corrigido
e a nova seção de backtest multi-horizon na página Forecast.

## Notebooks executados

Os 3 notebooks em `notebooks/` foram reexecutados de ponta a ponta
(`jupyter nbconvert --execute`) após as mudanças da V1.1, sem erro, com
outputs reais embutidos (não são apenas células de código sem saída).

## CI (GitHub Actions)

Workflow em `.github/workflows/ci.yml`, com **dois jobs distintos**
(V1.1.1):
- `fast-suite`: roda em todo push/PR — instala dependências fixas,
  lint (`ruff`), verificação essencial do pipeline (geração + validação
  de dados) e a suíte de testes (`pytest tests/`, ~15s, inclui o smoke
  test reduzido do backtest, não o completo).
- `full-release-validation`: só roda sob demanda (`workflow_dispatch`) —
  pipeline completo + backtest multi-horizon com as 41 origens de
  produção (~50s), como validação de release.

Python fixado em 3.12 (ver `.python-version`). Este workflow ainda não
foi publicado no GitHub — está pronto no repositório local, aguardando a
publicação (fora do escopo desta etapa).

## Performance (medida real, V1.1.1)

Comparação completa antes/depois da otimização do backtest em
`docs/PERFORMANCE_AUDIT.md`. Resumo: backtest multi-horizon completo caiu
de 121,4s para 40,6-40,8s (~2,97x mais rápido), com regressão numérica
verificada como exatamente zero (4.920/4.920 previsões idênticas).
Ambiente da medição: Python 3.12.3, 1 CPU lógica — tempos são uma medição
neste ambiente, não uma garantia universal.

## Como reproduzir

```bash
cd Projeto_Lobo_2_Lobo_Forecast_AI_v1.1.1
pip install -r requirements.txt
cd src
python generate_data.py
python validate_data.py
python database.py
python data_prep.py
python run_evaluation.py          # avaliação one-step-ahead
python backtest_multihorizon.py   # backtest rolling-origin H+1..H+4 (~40s, medido — ver PERFORMANCE_AUDIT.md)
python forecast.py
python replenishment.py
cd ..
pytest tests/ -v                  # ~15s — smoke test reduzido do backtest, não o completo
ruff check src/ tests/
cd src && streamlit run app.py    # verificação manual do dashboard
```

## O que ainda falta

Nada tecnicamente pendente para a V1.1.1 ser submetida à auditoria
independente final antes da publicação. Possíveis evoluções futuras
(fora do escopo desta versão) estão listadas em `README.md` (seção
"Próximos passos") e em `docs/CHANGELOG.md`.

## Teste end-to-end (pasta limpa)

Executado manualmente nesta sessão, em sequência, a partir de uma pasta
recém-criada: geração de dados → validação → criação e carga do banco →
execução das 10 consultas SQL → pipeline completo (incluindo backtest
multi-horizon) → suíte de testes → lint → notebooks → dashboard. Todas as
etapas concluíram sem erro e sem dependência de caminho absoluto, arquivo
oculto ou estado anterior.
