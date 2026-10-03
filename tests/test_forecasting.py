"""
Testes de features (ausência de leakage), baselines e métricas.
"""

import numpy as np
import pandas as pd
import pytest

from baselines import predict_moving_average_4, predict_naive, predict_seasonal_52
from evaluate import bias, mae, wape
from features import add_lag_features


@pytest.fixture
def toy_series():
    """Série simples e conhecida para checar os cálculos manualmente."""
    return pd.DataFrame(
        {
            "product_id": ["MAT001"] * 6,
            "week_id": [1, 2, 3, 4, 5, 6],
            "units_consumed": [10, 20, 30, 40, 50, 60],
        }
    )


# ------------------------------------------------------------- leakage
def test_lag_1_uses_previous_week_only(toy_series):
    result = add_lag_features(toy_series)
    # na semana 3 (índice 2), lag_1 deve ser o valor da semana 2 (20)
    row = result[result["week_id"] == 3].iloc[0]
    assert row["lag_1"] == 20


def test_first_week_has_no_lag(toy_series):
    result = add_lag_features(toy_series)
    first_row = result[result["week_id"] == 1].iloc[0]
    assert pd.isna(first_row["lag_1"])


def test_rolling_mean_excludes_target_week(toy_series):
    """mean_4 na semana 5 deve ser a média das semanas 1-4 (10,20,30,40),
    NUNCA incluindo o valor da própria semana 5 (50)."""
    result = add_lag_features(toy_series)
    row = result[result["week_id"] == 5].iloc[0]
    assert row["mean_4"] == pytest.approx((10 + 20 + 30 + 40) / 4)


# ------------------------------------------------------------ baselines
def test_naive_prediction_equals_lag_1():
    df = pd.DataFrame({"lag_1": [5.0, np.nan, 10.0]})
    preds = predict_naive(df)
    assert preds.tolist() == [5.0, 0.0, 10.0]


def test_moving_average_falls_back_to_lag_1_then_zero():
    df = pd.DataFrame({"mean_4": [np.nan, 8.0], "lag_1": [3.0, np.nan]})
    preds = predict_moving_average_4(df)
    assert preds.tolist() == [3.0, 8.0]


def test_seasonal_falls_back_to_moving_average():
    df = pd.DataFrame({"lag_52": [np.nan], "mean_4": [7.0]})
    preds = predict_seasonal_52(df)
    assert preds.tolist() == [7.0]


# ------------------------------------------------------------- métricas
def test_mae_is_zero_for_perfect_prediction():
    actual = pd.Series([10, 20, 30])
    assert mae(actual, actual) == 0


def test_wape_known_value():
    actual = pd.Series([10, 10, 10, 10])
    predicted = pd.Series([12, 8, 10, 14])
    # erro absoluto total = 2+2+0+4 = 8; volume real total = 40
    assert wape(actual, predicted) == pytest.approx(8 / 40)


def test_bias_detects_overestimation():
    actual = pd.Series([10, 10])
    predicted = pd.Series([12, 14])
    assert bias(actual, predicted) > 0


def test_bias_detects_underestimation():
    actual = pd.Series([10, 10])
    predicted = pd.Series([8, 6])
    assert bias(actual, predicted) < 0


def test_forecast_never_negative_after_clip():
    raw_preds = np.array([-5.0, 3.2, -0.1, 10.0])
    clipped = np.clip(raw_preds, 0, None)
    assert (clipped >= 0).all()
