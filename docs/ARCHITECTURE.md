# Projeto Lobo 2 — ARCHITECTURE.md (Lobo Forecast AI)

## Regra central do produto
> O modelo prevê. A regra calcula. O dashboard explica. A pessoa responsável decide.

## Visão geral do fluxo (pipeline)

```
GERAR DADOS (generate_data.py)
        ↓
VALIDAR DADOS (validate_data.py)
        ↓
CRIAR BANCO + CARREGAR (database.py)
        ↓
SÉRIE SEMANAL (data_prep.py) + EDA
        ↓
FEATURES SEM LEAKAGE (features.py) + BASELINES (baselines.py)
        ↓
MODELO ML + AVALIAÇÃO ONE-STEP-AHEAD (run_evaluation.py)
        ↓
BACKTEST ROLLING-ORIGIN MULTI-HORIZON H+1..H+4 (backtest_multihorizon.py)
        ↓
MÉTRICAS (evaluate.py) + FORECAST 4 SEMANAS (forecast.py, via recursive_forecast.py)
        ↓
MOTOR DE REPOSIÇÃO (replenishment.py)
        ↓
DASHBOARD (app.py, Streamlit)
```

Todas as etapas do roadmap técnico (seção 13 do guia) até a **V1.1 —
Portfolio Hardening** estão implementadas, testadas e documentadas. A
V1.1.1 (atual) otimizou a engenharia do backtest sem alterar nenhuma
delas — ver `docs/PERFORMANCE_AUDIT.md`.

## Notebooks (`notebooks/`)

Os notebooks não contêm lógica exclusiva — reutilizam os módulos de
`src/` e servem para exploração, aprendizagem e comunicação analítica,
como recomendado no guia:

| Notebook | Conteúdo |
|---|---|
| `01_data_quality.ipynb` | Checagens de integridade e domínio, visualmente |
| `02_eda.ipynb` | Consumo total/por categoria, giro, semanas zero, coeficiente de variação |
| `03_model_analysis.ipynb` | Modelo x baselines (avaliação one-step-ahead), erro por categoria/SKU, viés |

## Componentes desta entrega

| Componente | Arquivo | Responsabilidade |
|---|---|---|
| Configuração central | `src/config.py` | Seeds, caminhos, parâmetros do estudo de caso e do backtest |
| Gerador de dados | `src/generate_data.py` | Cria produtos, calendário, consumo e estoque sintéticos e reprodutíveis |
| Validador | `src/validate_data.py` | Garante integridade e ausência de dados sensíveis antes de qualquer uso |
| Schema SQL | `sql/schema.sql` | Modelo relacional com PK, FK e CHECK constraints |
| Carga do banco | `src/database.py` | Recria o banco SQLite do zero e carrega os CSVs validados |
| Consultas de negócio | `sql/analysis_queries.sql` | 10 consultas que respondem perguntas reais sobre consumo, custo e estoque |
| Série semanal | `src/data_prep.py` | Grade completa produto x semana, preservando zeros reais |
| Features | `src/features.py` | Lags e rolling com `shift(1)` — sem vazamento temporal |
| Baselines | `src/baselines.py` | Naive, média móvel 4 semanas, sazonal 52 semanas |
| Modelo | `src/models.py` | RandomForestRegressor global, categóricas codificadas |
| Avaliação one-step-ahead | `src/evaluate.py`, `src/run_evaluation.py` | MAE, WAPE, viés; teste temporal (últimas 8 semanas); comparação modelo x baselines |
| Forecast recursivo (lógica compartilhada) | `src/recursive_forecast.py` | Recursão de N passos usada pelo forecast de produção; versão em lote (`recursive_forecast_batch`) usada pelo backtest, matematicamente idêntica à versão produto-a-produto (provado por teste) |
| Forecast de produção | `src/forecast.py` | Forecast recursivo de 4 semanas a partir do fim real do histórico |
| Backtest multi-horizon | `src/backtest_multihorizon.py` | Avaliação rolling-origin do forecast recursivo, H+1 a H+4, mesmo protocolo para modelo e baselines |
| Motor de reposição | `src/replenishment.py` | Estoque de segurança, estoque-alvo, quantidade sugerida, prioridade auditável (com convenções de risco documentadas) |
| Dashboard | `src/app.py` | Aplicação Streamlit com 5 páginas, tratamento gracioso de artefatos ausentes |
| Testes | `tests/` | 64 testes automatizados (dados, banco, leakage, semântica de estoque, baselines, métricas, reposição, integração de pipeline, smoke test do dashboard, smoke test + equivalência matemática do backtest, regressão numérica) |
| CI | `.github/workflows/ci.yml` | `fast-suite` (lint + pipeline essencial + testes, todo push/PR) e `full-release-validation` (pipeline + backtest completo, sob demanda) |

## Modelo relacional (resumo)

```
products (1) ───< consumption (N)
products (1) ───< inventory_snapshot (N)
calendar        (usado para ancorar toda a série temporal — sem FK direta)
```

## Decisões de design e por quê

- **SQLite** em vez de um banco gerenciado: o projeto precisa rodar em
  qualquer máquina sem infraestrutura extra, mantendo o foco em SQL e
  modelagem de dados, não em DevOps.
- **`calendar` como tabela própria**: garante que nenhuma semana "some" da
  série, mesmo quando um produto teve consumo zero — requisito central do
  guia para não distorcer o forecasting.
- **Geração transacional em vez de agregada direto na semana**: mais realista
  (várias retiradas por semana, por centro de trabalho) e permite treinar a
  habilidade de agregação em SQL/Pandas, que é parte do aprendizado do
  projeto.
- **Sem ORM e sem microsserviços**: o guia é explícito que o público-alvo
  ainda está construindo a base em Python/SQL — abstrações extras
  atrapalhariam mais do que ajudariam.
