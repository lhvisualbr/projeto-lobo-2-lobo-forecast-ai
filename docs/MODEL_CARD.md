# Projeto Lobo 2 — MODEL_CARD.md (Lobo Forecast AI)

> Status: **V1.1.1 — Performance & Final Verification**. Modelo e
> metodologia de avaliação **inalterados** desde a V1.1 — esta versão
> apenas otimizou a ENGENHARIA do backtest (ver
> `docs/PERFORMANCE_AUDIT.md`), com regressão numérica verificada como
> exatamente zero. Todos os números abaixo continuam válidos e batem
> bit-a-bit com a execução otimizada. Números são resultado real da
> execução, não estimativas.

## Objetivo
Prever a quantidade semanal consumida por SKU nas próximas 4 semanas, para
apoiar decisões de reposição de estoque em um almoxarifado/ferramentaria
industrial fictícia.

## Horizonte
4 semanas, com granularidade semana × produto.

## Dados de treino
- 104 semanas de histórico sintético (~24 meses), 30 SKUs.
- Fonte: `data/raw/*.csv`, carregados em `database/lobo_forecast.db`.
- Treino: 1.320 observações (semanas anteriores à janela de teste, com
  histórico suficiente para todas as features de lag).
- Teste: 240 observações (30 SKUs x últimas 8 semanas conhecidas).

## Features utilizadas
`lag_1, lag_2, lag_4, lag_8, lag_13, lag_52, mean_4, mean_8, std_4, std_8,
month, week_of_year, product_id (codificado), category (codificada)`.
Todas as features de lag/rolling usam `shift(1)` antes de `rolling()` —
ver testes de leakage em `tests/test_forecasting.py`.

## Baselines avaliadas
1. Naive (repete última semana observada).
2. Média móvel de 4 semanas.
3. Sazonal (mesma semana, 52 semanas atrás).
Croston/SBA não foi implementada nesta versão: a média móvel de 4 semanas
já se mostrou competitiva mesmo nos SKUs intermitentes, então a
complexidade extra não se justificou (ver `LIMITATIONS.md`).

## Modelo
Um único modelo global: `RandomForestRegressor` (scikit-learn,
`n_estimators=300`, `max_depth=10`, `min_samples_leaf=3`,
`random_state=42`), com `product_id`/`category` como variáveis
categóricas codificadas.

## Duas avaliações diferentes (V1.1)

O projeto avalia o modelo de DUAS formas complementares — não misture os
números de uma com os da outra:

1. **One-step-ahead** (`src/run_evaluation.py`, resultados abaixo): sempre
   usa o valor REAL da semana anterior para prever a próxima. Mede a
   capacidade "pura" do modelo de achar padrão nos dados, mas **não**
   reflete o uso real do sistema, que gera 4 semanas seguidas sem ter o
   valor real das semanas intermediárias.
2. **Backtest rolling-origin multi-horizon H+1 a H+4**
   (`src/backtest_multihorizon.py`, seção própria mais abaixo): replica o
   uso real — forecast recursivo a partir de várias origens temporais
   diferentes dentro do histórico, usando a própria previsão como
   pseudo-histórico para os passos seguintes (igual ao `forecast.py` de
   produção). Esta é a avaliação que importa para confiar (ou não) no
   forecast de 4 semanas que o dashboard mostra.

## Protocolo de validação temporal (one-step-ahead)
- Divisão por tempo, nunca aleatória: treino = semanas < semana 97; teste
  = semanas 97 a 104 (últimas 8 semanas conhecidas).
- Todas as features usadas no teste dependem apenas de dados anteriores à
  semana prevista (ver `tests/test_forecasting.py::test_rolling_mean_excludes_target_week`).
- Forecast futuro (4 semanas) feito de forma recursiva em `src/forecast.py`,
  sem usar nenhum valor real futuro (que não existe).

## Métricas — teste temporal (últimas 8 semanas conhecidas)

| Método | MAE | WAPE | Viés |
|---|---|---|---|
| **RandomForest (modelo)** | **5.71** | **0.2756** | +0.46 |
| Média móvel 4 semanas | 5.73 | 0.2766 | +0.38 |
| Naive (última semana) | 7.13 | 0.3438 | +0.04 |
| Sazonal (52 semanas) | 7.30 | 0.3522 | +1.00 |

- **Baseline vencedora entre as baselines:** média móvel de 4 semanas.
- **O modelo superou a melhor baseline?** Sim, mas por **margem muito
  pequena** (WAPE 0.2756 vs. 0.2766 — diferença de ~0,1 ponto percentual).
  Honestamente, isso significa que a média móvel de 4 semanas já captura
  quase todo o sinal previsível nesta base sintética; o ganho do modelo de
  ML é marginal e não deve ser vendido como "grande avanço".
- Viés: todos os métodos tendem a **superestimar levemente** a demanda no
  teste (viés positivo), exceto o naive, que fica quase neutro por
  construção. O sazonal superestima mais porque a base tem apenas ~2 anos
  de histórico e captura menos variação estrutural entre anos.

## Onde o modelo falha (honestamente)
Avaliando por SKU (`results/onestep_by_product.csv`), os piores WAPEs
concentram-se nos produtos de perfil **INTERMITENTE/BAIXO giro** — alguns
chegam a WAPE > 1 (erro maior que o próprio volume real), porque poucas
unidades de erro já representam um percentual grande sobre uma base
pequena. Isso é esperado e documentado — não foi escondido nem corrigido
ajustando dados.

## Backtest rolling-origin multi-horizon (H+1 a H+4)

Protocolo: 41 origens temporais (semanas 60 a 100 do histórico conhecido),
retreinando o modelo em cada origem apenas com dados anteriores a ela, e
gerando recursivamente 4 semanas de previsão (mesma lógica de
`recursive_forecast.py` usada em produção). Baselines avaliadas sob o
mesmo protocolo. Resultado real, sem arredondar para favorecer nenhum
método:

> **Nota de performance (V1.1.1):** a implementação foi otimizada
> (predição em lote, lookup vetorizado) e o backtest completo caiu de
> ~121s para ~41s. Isso é ENGENHARIA pura — os números abaixo são
> idênticos, bit-a-bit, aos da V1.1. Ver `docs/PERFORMANCE_AUDIT.md`.

| Horizonte | Método vencedor (menor WAPE) | WAPE do modelo | WAPE do vencedor |
|---|---|---|---|
| H+1 | **model** | 0.2414 | 0.2414 |
| H+2 | **model** | 0.2478 | 0.2478 |
| H+3 | **moving_average_4** | 0.2568 | 0.2538 |
| H+4 | **moving_average_4** | 0.2581 | 0.2534 |
| ALL (consolidado) | **model** | 0.2510 | 0.2510 |

Tabela completa (todos os métodos, todos os horizontes) em
`results/backtest_multihorizon_summary.csv`.

**Leitura honesta:** o modelo é melhor nos horizontes mais próximos
(H+1, H+2), mas a média móvel de 4 semanas o ultrapassa levemente em H+3 e
H+4 — por margem pequena (~0,3 a 0,5 ponto percentual de WAPE), não uma
diferença que justifique preferir uma ou outra com grande confiança. Isso
é consistente com a intuição de que erros recursivos se acumulam ao longo
do horizonte, corroendo a vantagem do modelo à medida que a previsão se
afasta da origem. Não fizemos nenhum ajuste para "salvar" o modelo neste
resultado — ele está reportado como saiu.

## Uso pretendido
Apoio à decisão de reposição de estoque em um estudo de caso de portfólio.

## Uso não pretendido
- Decisão automática de compra sem revisão humana.
- Aplicação a um cenário real de empresa (dados são 100% fictícios).
- Uso como "otimizador empresarial definitivo".
