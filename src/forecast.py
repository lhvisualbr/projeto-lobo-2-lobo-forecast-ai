"""
forecast.py
Gera o forecast recursivo das próximas FORECAST_HORIZON_WEEKS semanas,
produto a produto, usando o modelo final (treinado com TODO o histórico
conhecido).

A lógica de recursão em si vive em recursive_forecast.py, compartilhada
com backtest_multihorizon.py — aqui só aplicamos essa lógica UMA vez, a
partir do fim real do histórico conhecido (a previsão de produção).
"""

import pandas as pd

from config import DATA_PROCESSED_DIR, FORECAST_HORIZON_WEEKS, RESULTS_DIR
from features import build_feature_table
from models import FEATURE_COLUMNS, encode_categoricals, train_model
from recursive_forecast import recursive_forecast


def run_forecast():
    weekly = pd.read_csv(DATA_PROCESSED_DIR / "weekly_series.csv")
    all_features = build_feature_table(weekly)
    all_features, product_enc, category_enc = encode_categoricals(all_features)

    # modelo final: treinado com TODO o histórico conhecido e completo (sem NaN)
    trainable = all_features.dropna(subset=FEATURE_COLUMNS)
    final_model = train_model(trainable)

    products_meta = weekly[["product_id", "category", "criticality"]].drop_duplicates()
    last_week_date = pd.to_datetime(weekly["week_end"]).max()

    forecast_rows = []
    for _, prod in products_meta.iterrows():
        pid = prod["product_id"]
        hist = (
            weekly[weekly["product_id"] == pid]
            .sort_values("week_id")["units_consumed"]
            .tolist()
        )
        product_code = product_enc.transform([pid])[0]
        category_code = category_enc.transform([prod["category"]])[0]

        preds = recursive_forecast(
            model=final_model,
            history=hist,
            product_code=product_code,
            category_code=category_code,
            start_date=last_week_date,
            horizon=FORECAST_HORIZON_WEEKS,
        )

        for p in preds:
            forecast_rows.append(
                {
                    "product_id": pid,
                    "category": prod["category"],
                    "criticality": prod["criticality"],
                    "forecast_week": p["step"],
                    "week_start": p["week_start"],
                    "week_end": p["week_end"],
                    "forecast_qty": p["qty"],
                }
            )

    forecast_df = pd.DataFrame(forecast_rows)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "forecast_4weeks.csv"
    forecast_df.to_csv(out_path, index=False)

    print(f"[OK] {out_path} -> {len(forecast_df)} linhas ({len(products_meta)} SKUs x {FORECAST_HORIZON_WEEKS} semanas)")
    totals = forecast_df.groupby("forecast_week")["forecast_qty"].sum()
    print("\nDemanda total prevista por semana futura:")
    print(totals.to_string())
    return forecast_df


if __name__ == "__main__":
    run_forecast()
