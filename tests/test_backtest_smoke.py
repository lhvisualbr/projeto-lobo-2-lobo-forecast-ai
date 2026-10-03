"""
test_backtest_smoke.py
SMOKE TEST do backtest multi-horizon — rápido o suficiente para rodar em
todo `pytest tests/` / CI, sem pagar o custo do backtest completo
(~40s otimizado, ~2 min sem otimização, com as 41 origens de produção).

NÃO CONFUNDIR com a avaliação completa do modelo:
- Este arquivo: valida que o CÓDIGO do backtest está correto (formato,
  ausência de erro, equivalência matemática da versão otimizada) usando
  um subconjunto pequeno e metodologicamente válido de origens.
- `docs/PERFORMANCE_AUDIT.md` / execução manual de
  `python src/backtest_multihorizon.py`: validação completa de release,
  com as 41 origens reais — é o que produz os números citados no
  MODEL_CARD.md e no README.
- `tests/test_regression_numerical.py`: compara os números do backtest
  COMPLETO (se já executado) contra os valores de referência da V1.1.

Nenhum destes três substitui os outros.
"""

import importlib

import numpy as np
import pandas as pd

import config
from recursive_forecast import recursive_forecast, recursive_forecast_batch

DATA_PROCESSED_DIR = config.DATA_PROCESSED_DIR


def test_reduced_backtest_runs_end_to_end_and_is_isolated(monkeypatch, tmp_path):
    """Versão REDUZIDA do backtest (poucas origens) para garantir que o
    código roda ponta a ponta sem erro e produz o formato esperado, sem
    pagar o custo total em toda execução de `pytest tests/`.

    IMPORTANTE: escreve em um diretório TEMPORÁRIO (tmp_path), nunca em
    `results/` de verdade — rodar este teste NÃO PODE sobrescrever o
    resultado real do backtest de produção com a versão reduzida. Isso já
    foi um bug real encontrado durante o desenvolvimento da V1.1 (ver
    docs/TEST_REPORT.md, seção "Comportamento inesperado encontrado")."""
    weekly_path = DATA_PROCESSED_DIR / "weekly_series.csv"
    if not weekly_path.exists():
        import pytest
        pytest.skip("weekly_series.csv ainda não foi gerado — rode o pipeline primeiro")

    weekly = pd.read_csv(weekly_path)
    max_known_week = weekly["week_id"].max()
    original_min_train_week = config.BACKTEST_MIN_TRAIN_WEEK
    original_results_dir = config.RESULTS_DIR

    try:
        # só 3 origens: o suficiente para exercitar o loop de rolling-origin
        # (treino, recursão em lote, avaliação, baselines) sem rodar as
        # ~40 origens de produção — continua sendo rolling-origin de verdade,
        # só que com menos pontos.
        monkeypatch.setattr(
            config, "BACKTEST_MIN_TRAIN_WEEK", int(max_known_week) - config.BACKTEST_HORIZONS - 2
        )
        monkeypatch.setattr(config, "RESULTS_DIR", tmp_path)  # nunca os results/ reais

        import backtest_multihorizon
        importlib.reload(backtest_multihorizon)

        summary, detail = backtest_multihorizon.run_backtest()

        # --- formato das saídas ---
        assert (tmp_path / "backtest_multihorizon_summary.csv").exists()
        assert (tmp_path / "backtest_multihorizon_detail.csv").exists()
        expected_cols = {"origin_week", "product_id", "category", "horizon",
                          "actual", "pred_model", "pred_naive",
                          "pred_moving_average_4", "pred_seasonal_52"}
        assert expected_cols <= set(detail.columns)

        # --- execução H+1 a H+4 ---
        assert {"1", "2", "3", "4", "ALL"} == set(summary["horizon"].astype(str))

        # --- número esperado de previsões (origens x produtos x horizontes) ---
        n_origins = detail["origin_week"].nunique()
        n_products = detail["product_id"].nunique()
        assert n_origins >= 3
        assert n_products == 30
        assert len(detail) == n_origins * n_products * config.BACKTEST_HORIZONS

        # --- comparação das baselines: as 4 devem estar presentes e com WAPE válido ---
        assert set(summary["method"]) == {"naive", "moving_average_4", "seasonal_52", "model"}
        assert (summary["wape"] >= 0).all()
        assert detail[["actual", "pred_model", "pred_naive",
                        "pred_moving_average_4", "pred_seasonal_52"]].isna().sum().sum() == 0

        # --- forecast recursivo: previsão nunca negativa (mesmo clip de produção) ---
        assert (detail["pred_model"] >= 0).all()

        # --- ausência de leakage óbvio: a previsão de uma origem não pode
        # depender de nada além do que está disponível até ela. Checagem
        # indireta e barata: o valor "actual" reportado bate exatamente
        # com o valor real da série semanal na semana-alvo (não foi
        # substituído por engano por um valor de outra semana).
        weekly_by_product_week = weekly.set_index(["product_id", "week_id"])["units_consumed"]
        sample = detail.sample(min(20, len(detail)), random_state=0)
        for _, row in sample.iterrows():
            target_week = int(row["origin_week"] + row["horizon"])
            expected_actual = weekly_by_product_week.loc[(row["product_id"], target_week)]
            assert row["actual"] == expected_actual

        # garante que o arquivo REAL de produção não foi tocado por este teste
        real_summary_path = original_results_dir / "backtest_multihorizon_summary.csv"
        if real_summary_path.exists():
            real_n_obs = pd.read_csv(real_summary_path)["n_obs"].iloc[0]
            assert real_n_obs != summary["n_obs"].iloc[0], (
                "o arquivo real de results/ foi sobrescrito pela versão "
                "reduzida do backtest — isolamento via tmp_path falhou"
            )
    finally:
        # restaura o módulo ao valor de produção, para não vazar estado
        # reduzido para qualquer outro código que importe este módulo depois.
        monkeypatch.setattr(config, "BACKTEST_MIN_TRAIN_WEEK", original_min_train_week)
        monkeypatch.setattr(config, "RESULTS_DIR", original_results_dir)
        importlib.reload(backtest_multihorizon)


def test_batched_recursive_forecast_matches_unbatched_version():
    """O CORAÇÃO da otimização de performance da V1.1.1 é
    `recursive_forecast_batch()` — que faz UMA chamada a `model.predict()`
    por passo (cobrindo vários produtos), em vez de uma chamada por
    produto por passo. Este teste prova que isso é uma otimização de
    ENGENHARIA pura: o resultado precisa ser matematicamente idêntico à
    versão original produto-a-produto (`recursive_forecast()`, já usada e
    testada em produção via `forecast.py`)."""
    from sklearn.ensemble import RandomForestRegressor

    from models import FEATURE_COLUMNS

    rng = np.random.default_rng(123)
    n_samples = 200
    X_train = pd.DataFrame(rng.uniform(0, 20, size=(n_samples, len(FEATURE_COLUMNS))), columns=FEATURE_COLUMNS)
    y_train = X_train["lag_1"] * 0.5 + X_train["mean_4"] * 0.3 + rng.normal(0, 1, n_samples)
    model = RandomForestRegressor(n_estimators=20, max_depth=5, random_state=42)
    model.fit(X_train, y_train)

    # três "produtos" fictícios com históricos diferentes
    histories = {
        "A": list(rng.uniform(0, 20, size=60)),
        "B": list(rng.uniform(0, 20, size=60)),
        "C": list(rng.uniform(0, 20, size=60)),
    }
    codes = {"A": (0, 0), "B": (1, 0), "C": (2, 1)}
    start_date = pd.Timestamp("2026-06-01")
    horizon = 4

    # versão original, produto a produto
    expected = {
        key: recursive_forecast(model, hist, codes[key][0], codes[key][1], start_date, horizon)
        for key, hist in histories.items()
    }
    # versão em lote (otimizada)
    actual = recursive_forecast_batch(model, histories, codes, start_date, horizon)

    for key in histories:
        for step in range(horizon):
            assert actual[key][step]["qty"] == expected[key][step]["qty"], (
                f"produto {key}, passo {step + 1}: versão em lote ({actual[key][step]['qty']}) "
                f"diverge da versão original ({expected[key][step]['qty']}) — a otimização "
                "alterou o resultado numérico, o que NUNCA deveria acontecer."
            )
            assert actual[key][step]["week_start"] == expected[key][step]["week_start"]
            assert actual[key][step]["week_end"] == expected[key][step]["week_end"]
