"""
baselines.py
Baselines de previsão. Todas usam apenas colunas já calculadas com
shift(1)/rolling() em features.py — portanto, sem vazamento temporal.

- naive: repete o valor da última semana (lag_1).
- moving_average_4: média das 4 semanas anteriores (mean_4).
- seasonal_52: repete o valor de 52 semanas atrás (lag_52).
"""

import numpy as np
import pandas as pd


def predict_naive(df: pd.DataFrame) -> pd.Series:
    return df["lag_1"].fillna(0)


def predict_moving_average_4(df: pd.DataFrame) -> pd.Series:
    return df["mean_4"].fillna(df["lag_1"]).fillna(0)


def predict_seasonal_52(df: pd.DataFrame) -> pd.Series:
    # quando não há histórico de 52 semanas atrás, cai para a média móvel de 4
    return df["lag_52"].fillna(df["mean_4"]).fillna(0)


BASELINES = {
    "naive": predict_naive,
    "moving_average_4": predict_moving_average_4,
    "seasonal_52": predict_seasonal_52,
}


def apply_all_baselines(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for name, fn in BASELINES.items():
        result[f"pred_{name}"] = np.round(fn(df)).clip(lower=0)
    return result
