# Projeto Lobo 2 — CHANGELOG.md (Lobo Forecast AI)

## V0.1 — Foundation
- Geração de dados sintéticos reprodutível (30 SKUs, 24 meses, 4 semanas
  futuras), com perfis de giro, tendência, sazonalidade e intermitência.
- Validador de qualidade de dados (unicidade, FKs, valores não-negativos,
  ausência de termos confidenciais).
- Schema SQLite com PK, FK e CHECK constraints; banco recriável do zero.
- 10 consultas SQL de negócio comentadas.
- 23 testes automatizados (pytest) cobrindo dados e banco.
- Documentação inicial (README, DATA_DICTIONARY, ARCHITECTURE,
  LIMITATIONS, MODEL_CARD parcial, TEST_REPORT, PORTFOLIO_NOTES).

## V0.2 — Analytics
- Série semanal consolidada (produto x semana), preservando zeros reais.
- EDA visual (consumo total semanal, consumo por categoria).
- Baselines implementadas: naive, média móvel de 4 semanas, sazonal 52
  semanas (Croston avaliado e descartado — ver `LIMITATIONS.md`).

## V0.3 — Forecast
- Features de lag/rolling sem vazamento temporal (`shift(1)` antes de
  `rolling()`), testadas explicitamente.
- Modelo RandomForestRegressor global, treino/teste dividido por tempo
  (últimas 8 semanas conhecidas = teste).
- Resultado real: modelo WAPE 0.2756 vs. melhor baseline (média móvel 4
  semanas) WAPE 0.2766 — modelo venceu por margem pequena.
- Forecast recursivo de 4 semanas futuras, sem uso de valores reais
  futuros; negativos cortados em zero.
- 11 novos testes (leakage, baselines, métricas) — total 34 testes.

## V0.4 — Inventory
- Motor de reposição auditável (`src/replenishment.py`): estoque de
  segurança, estoque-alvo, quantidade sugerida e custo estimado por SKU.
- Classificação de prioridade explicável (CRÍTICA/ALTA/MÉDIA/BAIXA), com
  razão em texto para cada SKU — nenhuma sugestão sem cálculo visível.
- Resultado real no cenário atual: 1 SKU crítico, 0 alta, 7 média, 22
  baixa; custo estimado total de reposição fictício de R$ 9.866,72.
- 8 novos testes (fórmulas de safety stock/target stock, classificação de
  prioridade, ordem nunca negativa) — total 42 testes.

## V0.5 — Dashboard
- Aplicação Streamlit (`src/app.py`) com 5 páginas: Visão Geral, Forecast,
  Estoque, Qualidade do Modelo e Dados.
- Visual industrial/corporativo (paleta escura + acentos, sem neon).
- Filtros por categoria/criticidade/prioridade na página de Estoque.
- Screenshots reais capturados (Playwright) em `images/dashboard_*.png`.
- 3 novos testes (smoke test de sintaxe e presença das páginas) — total 45.

## V1.0 — Portfolio Release
- Lint (`ruff`) 100% limpo em `src/` e `tests/` — 33 problemas encontrados
  e corrigidos (nenhum alterou o comportamento; resultado numérico
  confirmado idêntico antes/depois via reexecução completa do pipeline).
- 3 notebooks (`01_data_quality`, `02_eda`, `03_model_analysis`)
  criados e **executados de verdade**, com outputs reais embutidos.
- `LICENSE` (MIT) adicionada.
- README reescrito com foco de portfólio: resultado em destaque logo no
  topo, seção de qualidade/testes, limitações e próximos passos reais
  (fora do escopo desta versão, não mais "planejado").
- Reprodutibilidade confirmada mais uma vez em pasta limpa, do zero,
  incluindo o dashboard subindo corretamente (HTTP 200).
- README final com resultados reais, imagens, revisão completa.

## V1.1 — Portfolio Hardening
Auditoria técnica independente sobre a V1.0 identificou pontos de rigor
metodológico e de engenharia a corrigir. Nenhuma reescrita de arquitetura
— apenas correções e hardening sobre o que já existia.

- **Semântica temporal do estoque corrigida**: `inventory_snapshot`
  registrava o estoque de `week_end` ANTES dos movimentos daquela própria
  semana (consumo/chegada) — desalinhamento entre a data do snapshot e o
  que ele realmente representava. Redefinida a convenção formal ("snapshot
  de week_end = posição APÓS os movimentos da semana"), corrigida a
  implementação e adicionados 4 testes dedicados
  (`tests/test_inventory_semantics.py`), incluindo prova direta de
  ausência de uso de informação futura.
- **Motor de reposição auditado**: texto da prioridade BAIXA corrigido
  para creditar corretamente "disponível + em trânsito" (antes sugeria
  que só o disponível cobria o alvo). Documentada explicitamente a
  convenção de a classificação de risco (CRÍTICA/ALTA) ignorar
  `in_transit` por não haver ETA por pedido, enquanto `suggested_order` o
  desconta — decisão de design, não inconsistência. +2 testes.
- **Backtest rolling-origin multi-horizon (H+1 a H+4)** implementado
  (`src/backtest_multihorizon.py`) — o principal aprimoramento
  metodológico desta versão. Avalia o cenário real de uso (forecast
  recursivo de 4 semanas) em 41 origens temporais diferentes, sob o mesmo
  protocolo para modelo e baselines. Resultado real: o modelo vence em
  H+1/H+2, mas a média móvel de 4 semanas vence em H+3/H+4 por margem
  pequena — reportado sem maquiagem (ver `MODEL_CARD.md`).
- Lógica de forecast recursivo extraída para `src/recursive_forecast.py`,
  compartilhada entre `forecast.py` (produção) e o novo backtest — evita
  divergência entre "como o projeto prevê de verdade" e "como foi avaliado".
- Avaliação one-step-ahead (`run_evaluation.py`) renomeada e documentada
  explicitamente como complementar ao backtest multi-horizon, nunca
  misturada com ele — outputs agora com prefixo `onestep_*`.
- **Dashboard**: "Real x Previsto" corrigido para mostrar de fato valores
  reais e previstos lado a lado (antes só mostrava histórico); nova seção
  de backtest multi-horizon na página Forecast; tratamento gracioso de
  artefatos ausentes (mensagem com o comando exato a rodar, sem traceback).
- **Teste de integração** do pipeline completo adicionado
  (`tests/test_pipeline_integration.py`, 8 testes) — detecta regressões
  entre módulos que os testes unitários não cobrem.
- **CI** com GitHub Actions criada (`.github/workflows/ci.yml`): lint,
  verificação essencial do pipeline e testes em todo push/PR. Ainda não
  publicada no GitHub (fora do escopo desta etapa).
- **Reprodutibilidade**: `.python-version` (3.12) e `requirements.txt`
  com versões fixas (`==`), não mais faixas abertas (`>=`).
- Join redundante removido da consulta SQL nº 1 (`sql/analysis_queries.sql`).
- **Efeito colateral honesto do fix de estoque**: com o `on_hand` agora
  correto (pós-movimentos da semana em vez de pré-movimentos), o cenário
  de reposição ficou mais apertado do que o reportado na V1.0 — de 1
  crítico/0 alta/7 média/22 baixa para **3 crítico/1 alta/9 média/17
  baixa**, e o custo estimado de reposição subiu de R$ 9.866,72 para
  **R$ 21.268,45**. Não foi um ajuste para piorar o resultado — foi a
  correção de um bug real que estava subestimando o risco de ruptura.
- Documentação (README, ARCHITECTURE, MODEL_CARD, LIMITATIONS,
  TEST_REPORT, DATA_DICTIONARY) revisada para refletir exatamente a
  implementação — incluindo a distinção explícita entre as duas
  avaliações (one-step-ahead vs. backtest multi-horizon) e os novos
  números reais de reposição.
- 59 testes automatizados no total (45 da V1.0 + 14 novos).

## V1.1.1 — Performance & Final Verification (atual)
Etapa cirúrgica sobre a V1.1, já aprovada funcionalmente por auditoria
independente. Sem novas funcionalidades, sem mudança de regra de negócio,
sem troca de modelo — apenas engenharia de performance e verificação final.

- **Backtest multi-horizon ~3x mais rápido** (121,4s → 40,6-40,8s),
  através de três otimizações puramente de engenharia: predição em lote
  por passo (`recursive_forecast_batch()` em `recursive_forecast.py`, uma
  chamada a `model.predict()` por passo cobrindo os 30 produtos, em vez
  de uma por produto), lookup vetorizado via matriz numpy (em vez de
  filtrar o DataFrame 4.920 vezes), e `dropna` calculado uma única vez
  (não depende da origem). **Regressão numérica verificada como
  exatamente zero**: as 4.920 previsões do backtest completo batem
  bit-a-bit entre a versão antiga e a otimizada — ver
  `docs/PERFORMANCE_AUDIT.md` para a comparação completa.
- **Smoke test dedicado do backtest** extraído para
  `tests/test_backtest_smoke.py`: roda um rolling-origin reduzido (poucas
  origens, isolado em diretório temporário) e, principalmente, prova
  matematicamente que `recursive_forecast_batch()` (a versão otimizada em
  lote) produz resultado IDÊNTICO a `recursive_forecast()` (a versão
  original produto-a-produto, já usada em produção) — a prova mais direta
  possível de que a otimização não alterou a ciência.
- **Testes de regressão numérica** adicionados
  (`tests/test_regression_numerical.py`, 4 testes): comparam os
  resultados reais do pipeline (one-step-ahead, backtest multi-horizon,
  reposição) contra os valores de referência já auditados da V1.1, com
  tolerância numérica explícita (não comparação textual frágil). Pulados
  automaticamente se os artefatos ainda não existirem.
- **CI dividida em dois workflows** (`fast-suite` e
  `full-release-validation`): a suíte rápida (todo push/PR) usa o smoke
  test reduzido; o backtest completo com as 41 origens de produção agora
  roda apenas sob demanda (`workflow_dispatch`), como validação de
  release — documentado explicitamente no próprio `ci.yml`.
- **Medições reais de performance** documentadas em
  `docs/PERFORMANCE_AUDIT.md` e `docs/FINAL_VERIFICATION.md`: pipeline
  principal (9,2s), backtest completo (40,6s), suíte de testes completa
  (64 testes, 14,77s) — sempre apresentados como medição neste ambiente
  (Python 3.12.3, 1 CPU lógica), nunca como garantia universal.
- 64 testes automatizados no total (59 da V1.1 + 1 teste de equivalência
  matemática lote-vs-produto-a-produto + 4 de regressão numérica).
- Nenhum resultado de negócio mudou: one-step-ahead, backtest
  multi-horizon e reposição permanecem numericamente idênticos à V1.1.
