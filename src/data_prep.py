"""
data_prep.py
Constrói a série semanal (produto x semana) a partir do banco SQL.

Regra central: toda combinação produto x semana conhecida deve existir na
série, mesmo quando o consumo foi zero. Isso é feito com um "cross join"
completo entre products e calendar (is_known = 1), preenchendo com 0 onde
não houver transação.
"""

import sqlite3

import pandas as pd

from config import DATA_PROCESSED_DIR, DATABASE_PATH


def load_weekly_series() -> pd.DataFrame:
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        products = pd.read_sql("SELECT * FROM products", conn)
        calendar = pd.read_sql(
            "SELECT * FROM calendar WHERE is_known = 1 ORDER BY week_id", conn
        )
        consumption = pd.read_sql("SELECT * FROM consumption", conn)
    finally:
        conn.close()

    # agrega transações -> quantidade por produto x semana
    consumption["consumption_date"] = pd.to_datetime(consumption["consumption_date"])
    calendar["week_start_dt"] = pd.to_datetime(calendar["week_start"])
    calendar["week_end_dt"] = pd.to_datetime(calendar["week_end"])

    # associa cada transação à sua semana via merge_asof (mais rápido que BETWEEN linha a linha)
    consumption = consumption.sort_values("consumption_date")
    cal_sorted = calendar.sort_values("week_start_dt")
    merged = pd.merge_asof(
        consumption,
        cal_sorted[["week_id", "week_start_dt"]],
        left_on="consumption_date",
        right_on="week_start_dt",
        direction="backward",
    )
    weekly_actual = (
        merged.groupby(["product_id", "week_id"])["quantity"].sum().reset_index()
    )
    weekly_actual = weekly_actual.rename(columns={"quantity": "units_consumed"})

    # grade completa produto x semana (garante zeros reais preservados)
    full_grid = pd.MultiIndex.from_product(
        [products["product_id"], calendar["week_id"]], names=["product_id", "week_id"]
    ).to_frame(index=False)

    weekly = full_grid.merge(weekly_actual, on=["product_id", "week_id"], how="left")
    weekly["units_consumed"] = weekly["units_consumed"].fillna(0).astype(int)

    weekly = weekly.merge(
        calendar[["week_id", "week_start", "week_end", "year", "week_of_year"]],
        on="week_id",
        how="left",
    )
    weekly = weekly.merge(
        products[["product_id", "category", "criticality"]], on="product_id", how="left"
    )

    weekly = weekly.sort_values(["product_id", "week_id"]).reset_index(drop=True)
    return weekly


def main() -> None:
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    weekly = load_weekly_series()
    out_path = DATA_PROCESSED_DIR / "weekly_series.csv"
    weekly.to_csv(out_path, index=False)

    n_products = weekly["product_id"].nunique()
    n_weeks = weekly["week_id"].nunique()
    zero_pct = 100 * (weekly["units_consumed"] == 0).mean()

    print(f"[OK] {out_path}")
    print(f"     linhas: {len(weekly)} ({n_products} produtos x {n_weeks} semanas)")
    print(f"     % de semanas com consumo zero: {zero_pct:.1f}%")


if __name__ == "__main__":
    main()
