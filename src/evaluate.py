"""
evaluate.py
Métricas de avaliação de forecast: MAE, WAPE e viés.
"""

import numpy as np
import pandas as pd


def mae(actual: pd.Series, predicted: pd.Series) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def wape(actual: pd.Series, predicted: pd.Series) -> float:
    """Weighted Absolute Percentage Error: erro absoluto total / volume real total.
    Preferido a MAPE aqui porque lida bem com semanas de consumo zero."""
    total_actual = np.sum(np.abs(actual))
    if total_actual == 0:
        return float("nan")
    return float(np.sum(np.abs(actual - predicted)) / total_actual)


def bias(actual: pd.Series, predicted: pd.Series) -> float:
    """Positivo = modelo tende a superestimar; negativo = tende a subestimar."""
    return float(np.mean(predicted - actual))


def evaluate_predictions(df: pd.DataFrame, actual_col: str, pred_col: str) -> dict:
    return {
        "mae": mae(df[actual_col], df[pred_col]),
        "wape": wape(df[actual_col], df[pred_col]),
        "bias": bias(df[actual_col], df[pred_col]),
        "n_obs": len(df),
    }


def evaluate_by_group(
    df: pd.DataFrame, actual_col: str, pred_col: str, group_col: str
) -> pd.DataFrame:
    rows = []
    for group_value, group_df in df.groupby(group_col):
        metrics = evaluate_predictions(group_df, actual_col, pred_col)
        metrics[group_col] = group_value
        rows.append(metrics)
    return pd.DataFrame(rows).sort_values("wape", ascending=False)
