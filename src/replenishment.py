"""
replenishment.py
Motor de APOIO à decisão de reposição — não decide, não compra
automaticamente. Toda sugestão é auditável: mostra os números que a
originaram.

REGRA CENTRAL DO PRODUTO:
    O modelo prevê. A regra calcula. O dashboard explica.
    A pessoa responsável decide.

Fórmula (definida no guia):
    expected_until_arrival = forecast_weekly * lead_time_weeks
    safety_stock            = service_factor * demand_std * sqrt(lead_time_weeks)
    review_stock            = forecast_weekly * review_period_weeks
    target_stock            = expected_until_arrival + safety_stock + review_stock
    suggested_order         = max(0, ceil(target_stock - on_hand - in_transit))

Prioridade:
    CRÍTICA -> risco de ruptura antes do prazo de reposição chegar.
    ALTA    -> estoque projetado abaixo da segurança.
    MÉDIA   -> há reposição sugerida, sem ruptura imediata.
    BAIXA   -> estoque cobre demanda, segurança e período de revisão.
"""

import math
import sqlite3

import pandas as pd

from config import (
    DATABASE_PATH,
    DEFAULT_SERVICE_FACTOR,
    RESULTS_DIR,
    REVIEW_PERIOD_WEEKS,
)


def _load_inputs():
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        products = pd.read_sql("SELECT * FROM products", conn)
        inventory = pd.read_sql("SELECT * FROM inventory_snapshot", conn)
    finally:
        conn.close()

    weekly = pd.read_csv(RESULTS_DIR.parent / "data" / "processed" / "weekly_series.csv")
    forecast = pd.read_csv(RESULTS_DIR / "forecast_4weeks.csv")
    return products, inventory, weekly, forecast


def _latest_inventory(inventory: pd.DataFrame) -> pd.DataFrame:
    latest_date = inventory["snapshot_date"].max()
    return inventory[inventory["snapshot_date"] == latest_date][
        ["product_id", "on_hand", "in_transit"]
    ]


def _historical_std(weekly: pd.DataFrame) -> pd.DataFrame:
    std_by_product = (
        weekly.groupby("product_id")["units_consumed"].std().fillna(0).reset_index()
    )
    std_by_product.columns = ["product_id", "demand_std"]
    return std_by_product


def _forecast_weekly_avg(forecast: pd.DataFrame) -> pd.DataFrame:
    avg = forecast.groupby("product_id")["forecast_qty"].mean().reset_index()
    avg.columns = ["product_id", "forecast_weekly"]
    total = forecast.groupby("product_id")["forecast_qty"].sum().reset_index()
    total.columns = ["product_id", "forecast_4weeks_total"]
    return avg.merge(total, on="product_id")


def classify_priority(row) -> tuple:
    """Retorna (prioridade, razão) de forma explícita e auditável.

    CONVENÇÃO DOCUMENTADA (ver docs/LIMITATIONS.md): como o projeto não
    possui ETA (data de chegada) por pedido em trânsito — apenas uma
    quantidade agregada — a classificação de RISCO (CRÍTICA/ALTA) é
    deliberadamente CONSERVADORA e ignora `in_transit`: não há garantia
    de que ele chegue dentro da janela de risco avaliada. Já o cálculo de
    `suggested_order` (quanto pedir a MAIS) desconta `in_transit`, pois
    ele representa quantidade já comprometida que eventualmente chegará —
    mesmo sem se saber exatamente quando. Essas duas óticas são
    propositalmente diferentes e ambas estão documentadas aqui e em
    LIMITATIONS.md; não é uma inconsistência não intencional.
    """
    in_transit_caveat = (
        " (estoque em trânsito não é considerado nesta checagem de risco "
        "por não haver ETA disponível por pedido)"
    )

    if row["on_hand"] < row["expected_until_arrival"]:
        return "CRITICA", (
            f"estoque disponível ({row['on_hand']}) não cobre a demanda esperada "
            f"durante o lead time ({row['expected_until_arrival']:.1f})" + in_transit_caveat
        )
    if row["on_hand"] < row["safety_stock"]:
        return "ALTA", (
            f"estoque disponível ({row['on_hand']}) abaixo do estoque de segurança "
            f"({row['safety_stock']:.1f})" + in_transit_caveat
        )
    if row["suggested_order"] > 0:
        return "MEDIA", (
            f"estoque-alvo ({row['target_stock']:.1f}) acima do disponível + "
            f"em trânsito ({row['on_hand'] + row['in_transit']:.0f}), sem risco imediato de ruptura"
        )
    return "BAIXA", (
        f"estoque disponível ({row['on_hand']:.0f}) + em trânsito ({row['in_transit']:.0f}) "
        f"cobre o estoque-alvo calculado ({row['target_stock']:.1f}); nenhuma reposição "
        f"adicional sugerida"
    )


def build_replenishment_table(
    products, inventory, weekly, forecast, service_factor: float = DEFAULT_SERVICE_FACTOR
) -> pd.DataFrame:
    latest_inv = _latest_inventory(inventory)
    std_df = _historical_std(weekly)
    fc_df = _forecast_weekly_avg(forecast)

    df = products.merge(latest_inv, on="product_id", how="left")
    df = df.merge(std_df, on="product_id", how="left")
    df = df.merge(fc_df, on="product_id", how="left")

    df["lead_time_weeks"] = df["lead_time_days"] / 7.0
    df["expected_until_arrival"] = df["forecast_weekly"] * df["lead_time_weeks"]
    df["safety_stock"] = (
        service_factor * df["demand_std"] * df["lead_time_weeks"].pow(0.5)
    )
    df["review_stock"] = df["forecast_weekly"] * REVIEW_PERIOD_WEEKS
    df["target_stock"] = df["expected_until_arrival"] + df["safety_stock"] + df["review_stock"]
    df["suggested_order"] = (
        (df["target_stock"] - df["on_hand"] - df["in_transit"]).apply(
            lambda x: max(0, math.ceil(x))
        )
    )
    df["estimated_replenishment_cost"] = round(
        df["suggested_order"] * df["unit_cost"], 2
    )

    priorities = df.apply(classify_priority, axis=1, result_type="expand")
    df["priority"] = priorities[0]
    df["priority_reason"] = priorities[1]

    audit_cols = [
        "product_id", "product_name", "category", "criticality",
        "forecast_weekly", "forecast_4weeks_total", "lead_time_days",
        "on_hand", "in_transit", "safety_stock", "target_stock",
        "suggested_order", "estimated_replenishment_cost",
        "priority", "priority_reason",
    ]
    return df[audit_cols].round(2)


def main():
    products, inventory, weekly, forecast = _load_inputs()
    table = build_replenishment_table(products, inventory, weekly, forecast)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "replenishment_suggestions.csv"
    table.to_csv(out_path, index=False)

    print(f"[OK] {out_path} -> {len(table)} SKUs avaliados\n")
    print("Distribuição de prioridade:")
    print(table["priority"].value_counts().to_string())

    total_cost = table["estimated_replenishment_cost"].sum()
    print(f"\nCusto estimado total de reposição (fictício): R$ {total_cost:,.2f}")

    print("\nSKUs CRÍTICOS:")
    critical = table[table["priority"] == "CRITICA"].sort_values(
        "estimated_replenishment_cost", ascending=False
    )
    if len(critical):
        print(critical[["product_id", "product_name", "on_hand", "suggested_order", "priority_reason"]].to_string(index=False))
    else:
        print("(nenhum SKU crítico neste cenário)")

    return table


if __name__ == "__main__":
    main()
