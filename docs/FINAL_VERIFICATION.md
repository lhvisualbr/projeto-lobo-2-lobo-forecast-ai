# Projeto Lobo 2 — FINAL_VERIFICATION.md (Lobo Forecast AI)

**Projeto:** Projeto Lobo 2 — Lobo Forecast AI
**Versão:** V1.1.1 — Performance & Final Verification
**Data da verificação:** execução real nesta sessão de desenvolvimento
**Status:** publicada no GitHub, validada por clone público limpo e com `full-release-validation` manual aprovado. Pronta para congelamento final.

Este documento não usa linguagem de marketing — cada item abaixo é uma
medição ou um resultado real desta sessão, não uma estimativa.

## Ambiente

| Item | Valor |
|---|---|
| Python | 3.12.3 (fixado via `.python-version` = 3.12) |
| CPU | 1 CPU lógica disponível (`nproc` = 1) |
| pandas | 3.0.2 |
| numpy | 2.4.4 |
| scikit-learn | 1.8.0 |
| streamlit | 1.64.0 |
| pytest | 9.1.1 |
| ruff | 0.16.8 |
| Dependências | fixadas com `==` em `requirements.txt` (não faixas `>=`) |

## Comandos executados e resultados (pasta limpa, do zero)

| # | Etapa | Comando | Resultado |
|---|---|---|---|
| 1 | Limpeza controlada | `rm -rf data/raw/* data/processed/* database/*.db results/*` | OK |
| 2 | Gerar dados | `python src/generate_data.py` | OK — 30 produtos, 104 semanas, 5.450 transações |
| 3 | Validar | `python src/validate_data.py` | OK — 0 violações |
| 4 | Criar SQLite | `python src/database.py` | OK — 4 tabelas, FKs ativas |
| 5 | Série semanal | `python src/data_prep.py` | OK — grade completa produto x semana |
| 6 | Avaliação one-step | `python src/run_evaluation.py` | OK — ver tabela abaixo |
| 7 | Backtest multi-horizon completo | `python src/backtest_multihorizon.py` | OK — 41 origens, 4.920 previsões, 40,6-46,6s (duas medições nesta sessão) |
| 8 | Forecast H+1..H+4 | `python src/forecast.py` | OK — 120 linhas (30 SKUs x 4 semanas) |
| 9 | Reposição | `python src/replenishment.py` | OK — ver tabela abaixo |
| 10 | Testes | `pytest tests/ -v` | **64 passed** em 14,77-17,30s (duas medições) |
| 11 | Lint | `ruff check src/ tests/` | **All checks passed!** (0 problemas) |
| 12 | Notebooks | `jupyter nbconvert --execute` nos 3 notebooks | OK — outputs reais embutidos |
| 13 | Dashboard | `streamlit run app.py` + `curl` | HTTP 200 |
| 14 | Documentação | revisão manual de README/ARCHITECTURE/MODEL_CARD/LIMITATIONS/TEST_REPORT/CHANGELOG/PERFORMANCE_AUDIT | consistente com os resultados reais acima |

Este fluxo foi executado por completo, em uma cópia nova do projeto
(sem nenhum estado anterior), **duas vezes** durante a V1.1.1 — uma antes
e uma depois da otimização do backtest — com os mesmos resultados
numéricos nas duas.

## Resultados — avaliação one-step-ahead (referência V1.1, inalterada)

| Método | MAE | WAPE | Viés |
|---|---|---|---|
| **model (RandomForest)** | 5,7125 | **0,2756** | +0,46 |
| moving_average_4 | 5,7333 | 0,2766 | +0,38 |
| naive | 7,1250 | 0,3438 | +0,04 |
| seasonal_52 | 7,3000 | 0,3522 | +1,00 |

## Resultados — backtest multi-horizon (H+1 a H+4, referência V1.1, inalterada)

| Horizonte | Vencedor | WAPE vencedor | WAPE model |
|---|---|---|---|
| H+1 | model | 0,2414 | 0,2414 |
| H+2 | model | 0,2478 | 0,2478 |
| H+3 | moving_average_4 | 0,2538 | 0,2568 |
| H+4 | moving_average_4 | 0,2534 | 0,2581 |
| ALL | model | 0,2510 | 0,2510 |

## Resultados — reposição (referência V1.1, inalterada)

| Prioridade | SKUs |
|---|---|
| CRÍTICA | 3 |
| ALTA | 1 |
| MÉDIA | 9 |
| BAIXA | 17 |

Custo estimado total: R$ 21.268,45.

## Performance (V1.1.1 — otimização de engenharia)

| Métrica | ANTES (V1.1) | DEPOIS (V1.1.1) |
|---|---|---|
| Backtest completo | 121,4s | 40,6-46,6s (~2,6-3,0x mais rápido) |
| Chamadas a `model.predict()` no backtest | 4.920 | 164 |
| Regressão numérica | — | **zero** (4.920/4.920 previsões idênticas) |

Detalhe completo em `docs/PERFORMANCE_AUDIT.md`.

## Divergências encontradas

Nenhuma divergência numérica entre a V1.1 e a V1.1.1 em nenhum dos
artefatos de resultado (one-step-ahead, backtest multi-horizon,
reposição) — confirmado por comparação linha a linha do
`backtest_multihorizon_detail.csv` completo (4.920 linhas, diferença
máxima 0,0) e pelos 4 testes de regressão numérica em
`tests/test_regression_numerical.py`.

A única divergência notável ocorreu **durante o desenvolvimento** (não no
resultado final): a primeira versão do smoke test do backtest sobrescrevia
por engano o arquivo real de resultados de produção com uma versão
reduzida. Corrigido isolando a saída em diretório temporário — ver
`docs/TEST_REPORT.md`, seção "Comportamento inesperado encontrado".

## Limitações restantes (sem mudança desde a V1.1)

- Sem ETA por pedido em trânsito — risco de ruptura permanece conservador
  por design (ver `LIMITATIONS.md`).
- `service_factor` único para todos os SKUs, não diferenciado por
  criticidade.
- CI publicada e validada no GitHub. `fast-suite` e
  `full-release-validation` concluíram com sucesso.
- Croston/SBA não implementada — média móvel seguiu competitiva mesmo no
  backtest multi-horizon (vence em H+3/H+4).
- Dados 100% sintéticos — nenhuma métrica valida desempenho em operação
  real.
- Ambiente de desenvolvimento com 1 CPU lógica — otimização de
  performance foi de redução de trabalho redundante, não de
  paralelização; em outra máquina os tempos absolutos mudam.

## Validação pública pós-publicação

A V1.1.1 foi clonada novamente a partir do repositório público:

`https://github.com/lhvisualbr/projeto-lobo-2-lobo-forecast-ai.git`

A validação foi executada em Windows com Python 3.12.10 e uma `.venv`
criada do zero. As dependências foram instaladas exclusivamente pelo
`requirements.txt` e `pip check` retornou `No broken requirements found.`

O fluxo público reproduziu com sucesso:

- geração e validação dos dados sintéticos;
- criação do SQLite;
- série semanal produto x semana;
- avaliação one-step-ahead;
- backtest multi-horizon com 41 origens;
- forecast de 4 semanas;
- motor de reposição;
- 64/64 testes automatizados (`64 passed in 33.84s`);
- Ruff (`All checks passed!`);
- dashboard Streamlit em `http://localhost:8501`.

Os resultados reproduzidos permaneceram consistentes com a referência
documentada, incluindo WAPE consolidado do modelo de 0,250999,
3 SKUs CRÍTICOS, 1 ALTA, 9 MÉDIA, 17 BAIXA e custo fictício estimado de
R$ 21.268,45.

O primeiro `fast-suite` público do GitHub Actions detectou uma lacuna no
workflow: os testes de banco eram executados antes da criação do SQLite.
A correção adicionou `python database.py` antes do pytest no job rápido.
Após essa correção, o segundo `fast-suite` passou no GitHub Actions.

## Critério de conclusão

Todos os critérios da etapa V1.1.1 foram atendidos:

- [x] pipeline completo executa (14/14 passos, pasta limpa, duas vezes)
- [x] backtest completo executa (41 origens, 4.920 previsões)
- [x] backtest otimizado preserva a metodologia (rolling-origin, H+1..H+4,
      recursivo, mesmas features, mesmas baselines, mesmo RandomForest)
- [x] resultados permanecem consistentes (regressão numérica zero)
- [x] smoke test é rápido (~4,5s isolado) e confiável (isolado em
      diretório temporário, nunca sobrescreve resultados reais)
- [x] suíte de testes passa (64/64)
- [x] lint passa (`ruff check` — 0 problemas, comando executado de fato)
- [x] CI está coerente (`fast-suite` rápida + `full-release-validation`
      sob demanda, documentado)
- [x] dependências são reproduzíveis (`requirements.txt` com `==`,
      `.python-version`)
- [x] documentação reflete os resultados reais (revisão cruzada nesta
      sessão)
- [x] tempos documentados são medições reais (não estimativas)
- [x] nenhuma regressão conhecida permanece escondida

## Declaração

**PROJETO LOBO 2 — LOBO FORECAST AI V1.1.1**
**VALIDAÇÃO FINAL CONCLUÍDA — PRONTA PARA CONGELAMENTO**

Repositório publicado e reprodução pública validada a partir de clone limpo.
`full-release-validation` manual concluído com sucesso no GitHub Actions.
Nenhuma pendência técnica conhecida permanece. Nenhuma V1.2 foi iniciada.
