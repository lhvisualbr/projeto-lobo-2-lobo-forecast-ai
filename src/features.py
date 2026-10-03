"""
features.py
Cria features de lag/rolling para a série semanal, SEM vazamento temporal.

Regra de ouro: toda feature de uma semana W só pode usar dados até a
semana W-1. Por isso todo rolling() é sempre precedido de shift(1).
"""

import pandas as pd

LAGS = [1, 2, 4, 8, 13, 52]
ROLLING_WINDOWS = [4, 8]


def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["product_id", "week_id"]).copy()
    grouped = df.groupby("product_id")["units_consumed"]

    for lag in LAGS:
        df[f"lag_{lag}"] = grouped.shift(lag)

    # shift(1) SEMPRE antes do rolling: a janela nunca inclui a semana alvo.
    shifted = grouped.shift(1)
    for window in ROLLING_WINDOWS:
        df[f"mean_{window}"] = (
            shifted.groupby(df["product_id"]).rolling(window).mean().reset_index(level=0, drop=True)
        )
        df[f"std_{window}"] = (
            shifted.groupby(df["product_id"]).rolling(window).std().reset_index(level=0, drop=True)
        )

    return df


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    week_start = pd.to_datetime(df["week_start"])
    df["month"] = week_start.dt.month
    df["week_of_year_num"] = df["week_of_year"]
    return df


def build_feature_table(weekly: pd.DataFrame) -> pd.DataFrame:
    df = add_lag_features(weekly)
    df = add_calendar_features(df)
    return df


if __name__ == "__main__":
    from config import DATA_PROCESSED_DIR

    weekly = pd.read_csv(DATA_PROCESSED_DIR / "weekly_series.csv")
    features = build_feature_table(weekly)
    out_path = DATA_PROCESSED_DIR / "weekly_features.csv"
    features.to_csv(out_path, index=False)
    n_missing_lag52 = features["lag_52"].isna().sum()
    print(f"[OK] {out_path} -> {len(features)} linhas, {features.shape[1]} colunas")
    print(f"     linhas sem lag_52 (esperado nas primeiras 52 semanas por produto): {n_missing_lag52}")
