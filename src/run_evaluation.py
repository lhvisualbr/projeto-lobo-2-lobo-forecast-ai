"""
run_evaluation.py
AVALIAÇÃO ONE-STEP-AHEAD (diagnóstico complementar).

Testa a previsão de UMA semana à frente, sempre usando o histórico REAL
completo até a semana anterior à prevista (nunca embaralhado). Isso é
diferente do uso real de produção do sistema, que gera forecast
RECURSIVO de até 4 semanas (ver backtest_multihorizon.py para a avaliação
que reflete esse uso real).

Protocolo:
- Teste = últimas 8 semanas conhecidas.
- Treino = todas as semanas conhecidas anteriores ao teste.
- Todas as features usadas em treino e teste já foram calculadas com
  shift(1) antes de rolling() em features.py -> nenhuma linha usa
  informação da própria semana ou do futuro.
- IMPORTANTE: para H+2, H+3... este teste "trapaceia" comparado ao uso
  real, pois usa o valor REAL da semana anterior (não a própria previsão)
  para calcular lag_1 etc. Por isso ele mede apenas a capacidade
  one-step-ahead do modelo, não a qualidade do forecast recursivo de
  produção — ver docs/MODEL_CARD.md, seção "Duas avaliações diferentes".
"""

import pandas as pd

from baselines import apply_all_baselines
from config import DATA_PROCESSED_DIR, RESULTS_DIR, TEST_WEEKS
from evaluate import evaluate_by_group, evaluate_predictions
from features import build_feature_table
from models import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    encode_categoricals,
    predict_model,
    train_model,
)


def load_and_prepare():
    weekly = pd.read_csv(DATA_PROCESSED_DIR / "weekly_series.csv")
    features = build_feature_table(weekly)
    features, _product_enc, _category_enc = encode_categoricals(features)
    features = apply_all_baselines(features)
    return features


def split_train_test(df: pd.DataFrame):
    max_week = df["week_id"].max()
    test_start_week = max_week - TEST_WEEKS + 1

    # linhas sem lag_52 (primeiras 52 semanas de cada produto) saem do treino
    # do modelo de ML - o modelo não pode aprender com features incompletas.
    trainable = df.dropna(subset=FEATURE_COLUMNS)

    train_df = trainable[trainable["week_id"] < test_start_week].copy()
    test_df = df[df["week_id"] >= test_start_week].copy()
    return train_df, test_df, test_start_week


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = load_and_prepare()
    train_df, test_df, test_start_week = split_train_test(df)

    print(f"Treino: {len(train_df)} linhas (semanas < {test_start_week})")
    print(f"Teste:  {len(test_df)} linhas (últimas {TEST_WEEKS} semanas conhecidas)\n")

    model = train_model(train_df)
    test_df["pred_model"] = predict_model(model, test_df)

    methods = ["naive", "moving_average_4", "seasonal_52", "model"]
    pred_cols = {
        "naive": "pred_naive",
        "moving_average_4": "pred_moving_average_4",
        "seasonal_52": "pred_seasonal_52",
        "model": "pred_model",
    }

    summary_rows = []
    for method in methods:
        metrics = evaluate_predictions(test_df, TARGET_COLUMN, pred_cols[method])
        metrics["method"] = method
        summary_rows.append(metrics)

    summary = pd.DataFrame(summary_rows).sort_values("wape")
    summary.to_csv(RESULTS_DIR / "onestep_model_vs_baselines.csv", index=False)

    winner = summary.iloc[0]["method"]
    model_wape = summary[summary["method"] == "model"]["wape"].values[0]
    best_baseline = summary[summary["method"] != "model"].sort_values("wape").iloc[0]

    print("=== AVALIAÇÃO ONE-STEP-AHEAD (últimas 8 semanas conhecidas) ===\n")
    print(summary[["method", "mae", "wape", "bias", "n_obs"]].to_string(index=False))

    print(f"\nMétodo com menor WAPE: {winner.upper()}")
    if winner == "model":
        print(
            f"O modelo de ML SUPEROU a melhor baseline "
            f"({best_baseline['method']}, WAPE={best_baseline['wape']:.3f}) "
            f"com WAPE={model_wape:.3f}."
        )
    else:
        print(
            "Na janela de teste utilizada, a baseline apresentou desempenho "
            f"superior ao modelo (baseline WAPE={summary.iloc[0]['wape']:.3f} "
            f"vs. modelo WAPE={model_wape:.3f})."
        )

    # avaliação por categoria e por SKU (usando o modelo)
    by_category_model = evaluate_by_group(test_df, TARGET_COLUMN, "pred_model", "category")
    by_category_model.to_csv(RESULTS_DIR / "onestep_by_category.csv", index=False)

    by_product_model = evaluate_by_group(test_df, TARGET_COLUMN, "pred_model", "product_id")
    by_product_model.to_csv(RESULTS_DIR / "onestep_by_product.csv", index=False)

    # previsões linha a linha do período de teste (usado no dashboard para
    # o gráfico "Real x Previsto" mostrar exatamente o que o nome promete)
    test_predictions = test_df[
        ["product_id", "category", "week_id", "week_start", "week_end",
         TARGET_COLUMN, "pred_naive", "pred_moving_average_4", "pred_seasonal_52", "pred_model"]
    ].rename(columns={TARGET_COLUMN: "actual"})
    test_predictions.to_csv(RESULTS_DIR / "onestep_test_predictions.csv", index=False)

    print(f"\n[OK] resultados salvos em {RESULTS_DIR}/ (prefixo onestep_*)")
    return summary, test_df, model


if __name__ == "__main__":
    main()
