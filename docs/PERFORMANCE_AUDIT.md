# Projeto Lobo 2 — PERFORMANCE_AUDIT.md (Lobo Forecast AI, V1.1.1)

Este documento registra a otimização de **engenharia** feita no backtest
multi-horizon na V1.1.1, com medições reais (não estimadas) antes e
depois. Nenhuma mudança de metodologia foi feita — ver `MODEL_CARD.md`
para o protocolo (inalterado) e `backtest_multihorizon.py` /
`recursive_forecast.py` para o detalhe técnico de cada otimização.

## Ambiente da medição

- Python 3.12.3
- 1 CPU lógica disponível (`nproc` = 1) — não há ganho a esperar de
  paralelismo entre origens neste ambiente; as otimizações abaixo são
  sobre REDUZIR trabalho redundante, não sobre paralelizar.
- pandas 3.0.2, numpy 2.4.4, scikit-learn 1.8.0 (ver `requirements.txt`
  para a lista completa, com versões fixas)
- Mesma máquina/execução usada para medir "antes" e "depois", em
  sequência, sem outras cargas concorrentes.
- Estes tempos são um **resultado medido neste ambiente específico**, não
  uma garantia de performance universal — noutra máquina (mais núcleos,
  outro processador) os valores absolutos mudam, mas o ganho relativo
  entre versões deve se manter, já que a otimização é estrutural
  (menos chamadas, não computação mais barata por chamada).

## O que foi otimizado (resumo — detalhe completo nos docstrings do código)

1. **Predição em lote por passo** (`recursive_forecast_batch` em
   `recursive_forecast.py`): uma chamada a `model.predict()` cobrindo os
   30 produtos por passo, em vez de uma chamada por produto por passo.
   Reduz de 4.920 chamadas (41 origens x 30 produtos x 4 passos) para 164
   (41 origens x 4 passos).
2. **Lookup vetorizado (numpy)** para valores reais de consumo (`actual`,
   naive, média móvel, sazonal): uma matriz semana x produto pré-calculada
   uma vez, em vez de filtrar o DataFrame a cada uma das 4.920 combinações.
3. **`dropna` calculado uma única vez**, fora do laço de origens, já que
   não depende da origem (propriedade fixa da linha).

O retreino do modelo a cada origem (41 treinos de RandomForest) foi
**mantido exatamente como estava** — é a parte cara que a própria
metodologia (retreinar só com dados <= origem) exige, e não foi tocado.

## Medição real — ANTES x DEPOIS

| Métrica | ANTES (V1.1) | DEPOIS (V1.1.1) | Ganho |
|---|---|---|---|
| Tempo do backtest completo | 121,4 s | 40,6–40,8 s | **~2,97x mais rápido** (-66%) |
| Nº de origens | 41 | 41 | inalterado |
| Nº de SKUs | 30 | 30 | inalterado |
| Horizontes | H+1 a H+4 | H+1 a H+4 | inalterado |
| Nº total de previsões (detail) | 4.920 | 4.920 | inalterado |
| Chamadas a `model.predict()` | 4.920 | 164 | -96,7% de chamadas |

## Resultado numérico — ANTES x DEPOIS (verificação de regressão zero)

Comparação linha a linha do `backtest_multihorizon_detail.csv` completo
(4.920 linhas): **maior diferença absoluta em `pred_model`: 0,0** —
4.920/4.920 linhas idênticas bit a bit.

| Horizonte | Método | WAPE antes | WAPE depois | Diferença |
|---|---|---|---|---|
| H+1 | model | 0,241449 | 0,241449 | 0,0 |
| H+1 | moving_average_4 | 0,248388 | 0,248388 | 0,0 |
| H+1 | naive | 0,293655 | 0,293655 | 0,0 |
| H+1 | seasonal_52 | 0,305209 | 0,305209 | 0,0 |
| H+2 | model | 0,247757 | 0,247757 | 0,0 |
| H+2 | moving_average_4 | 0,250201 | 0,250201 | 0,0 |
| H+3 | model | 0,256762 | 0,256762 | 0,0 |
| H+3 | moving_average_4 | 0,253848 | 0,253848 | 0,0 |
| H+4 | model | 0,258050 | 0,258050 | 0,0 |
| H+4 | moving_average_4 | 0,253410 | 0,253410 | 0,0 |
| ALL | model | 0,250999 | 0,250999 | 0,0 |
| ALL | moving_average_4 | 0,251460 | 0,251460 | 0,0 |

**Conclusão da auditoria:** ganho de performance de ~3x, com regressão
numérica de exatamente zero em todas as 4.920 previsões e nas 20
combinações horizonte x método verificadas. A conclusão metodológica da
V1.1 permanece válida sem qualquer ressalva: o modelo vence em H+1/H+2, a
média móvel de 4 semanas vence em H+3/H+4, resultado consolidado quase
empatado.

## Outras medições de performance (pipeline e testes)

| Etapa | Tempo medido |
|---|---|
| Pipeline principal (gerar → validar → banco → série → avaliação one-step → forecast → reposição, 7 scripts) | 9,2 s |
| Backtest multi-horizon completo (41 origens) | 40,6 s |
| **Total pipeline + backtest** | **49,8 s** |
| Suíte de testes completa (64 testes) | 14,77 s |
| Smoke test multi-horizon isolado (`tests/test_backtest_smoke.py`) | ~4,5 s |

A suíte de testes NÃO depende do backtest completo — o smoke test usa um
subconjunto reduzido (poucas origens), isolado em diretório temporário
(nunca sobrescreve `results/` real). O backtest completo continua
existindo como validação de release, rodado manualmente ou via o job
`full-release-validation` da CI (`workflow_dispatch`).

## Como reproduzir esta auditoria

```bash
cd Projeto_Lobo_2_Lobo_Forecast_AI_v1.1.1/src
python data_prep.py   # garante weekly_series.csv atualizado

# mede o backtest completo
python -c "
import time
t0 = time.time()
import backtest_multihorizon
summary, detail = backtest_multihorizon.run_backtest()
print(f'tempo: {time.time()-t0:.1f}s | origens: {detail[\"origin_week\"].nunique()} | obs: {len(detail)}')
"
```
