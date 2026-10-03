"""
backtest_multihorizon.py
BACKTEST ROLLING-ORIGIN MULTI-HORIZON (H+1 a H+4).

METODOLOGIA INALTERADA DESDE A V1.1 (ver docs/MODEL_CARD.md para a
explicação completa do protocolo). Este arquivo passou por uma otimização
de ENGENHARIA na V1.1.1 — nenhuma mudança de metodologia, nenhuma mudança
de resultado numérico esperado. As três otimizações abaixo são todas
"agrupar o mesmo trabalho de forma mais eficiente", nunca "fazer menos
trabalho":

1. **Predição em lote por passo, não por produto** (`recursive_forecast_batch`
   em `recursive_forecast.py`): antes, cada passo de cada produto de cada
   origem chamava `model.predict()` individualmente (41 origens x 30
   produtos x 4 passos = 4.920 chamadas). Agora, cada passo de cada
   origem faz UMA chamada cobrindo os 30 produtos ao mesmo tempo (41 x 4
   = 164 chamadas). `RandomForestRegressor.predict()` trata cada linha de
   forma independente — não há interação entre produtos dentro do mesmo
   lote — então o resultado é bit-a-bit idêntico, só com muito menos
   overhead de Python/pandas/joblib por chamada.
2. **Lookup vetorizado (numpy) em vez de filtragem repetida em pandas**:
   valores reais de consumo (para `actual`, baseline naive, média móvel e
   sazonal) são lidos de uma matriz numpy (semana x produto) pré-calculada
   uma única vez, em vez de fazer um filtro `df[df.week_id == X]` a cada
   uma das 4.920 combinações origem x produto x horizonte.
3. **`dropna` calculado uma única vez**: se uma linha tem features
   incompletas (ex.: falta `lag_52`), isso NÃO depende da origem do
   backtest — é uma propriedade fixa da linha. Antes, o `dropna` sobre
   toda a tabela de features era recalculado a cada uma das 41 origens;
   agora é calculado uma vez, e cada origem só filtra por `week_id` sobre
   esse resultado já pronto (operação bem mais barata).

Retreino do modelo a cada origem (a parte mais cara, e a única que a
metodologia exige) foi MANTIDO exatamente como estava — nenhuma origem
foi removida, nenhum horizonte foi cortado, nenhuma árvore foi reduzida.
Ver docs/PERFORMANCE_AUDIT.md para a comparação real antes/depois.
"""

import numpy as np
import pandas as pd

from config import (
    BACKTEST_HORIZONS,
    BACKTEST_MIN_TRAIN_WEEK,
    DATA_PROCESSED_DIR,
    RESULTS_DIR,
)
from evaluate import evaluate_predictions
from features import build_feature_table
from models import FEATURE_COLUMNS, TARGET_COLUMN, encode_categoricals, train_model
from recursive_forecast import recursive_forecast_batch


def get_valid_origins(weekly: pd.DataFrame) -> list:
    """Origens válidas: semanas com treino suficiente ANTES delas e com
    horizonte completo (O+BACKTEST_HORIZONS) ainda dentro do histórico
    conhecido, para que se possa comparar com o valor real."""
    max_known_week = weekly["week_id"].max()
    last_valid_origin = max_known_week - BACKTEST_HORIZONS
    return list(range(BACKTEST_MIN_TRAIN_WEEK, last_valid_origin + 1))


def _build_consumption_matrix(weekly: pd.DataFrame):
    """Matriz numpy (semana x produto) para lookup O(1) de units_consumed,
    em vez de filtrar o DataFrame repetidamente. `pivot` já é vetorizado
    (calculado uma vez); o ganho está em nunca mais refiltrar depois disso.
    matrix[week_id - 1, product_idx[pid]] = consumo real daquele produto
    naquela semana. Índice de coluna = ordem alfabética de product_id
    (estável e determinística)."""
    pivot = weekly.pivot(index="week_id", columns="product_id", values=TARGET_COLUMN).sort_index()
    product_idx = {pid: i for i, pid in enumerate(pivot.columns)}
    return pivot.values, product_idx


def run_backtest():
    weekly = pd.read_csv(DATA_PROCESSED_DIR / "weekly_series.csv")
    all_features = build_feature_table(weekly)
    all_features, product_enc, category_enc = encode_categoricals(all_features)

    # dropna calculado UMA VEZ (não depende da origem - ver docstring acima)
    all_trainable = all_features.dropna(subset=FEATURE_COLUMNS)

    origins = get_valid_origins(weekly)
    if not origins:
        raise RuntimeError(
            "Nenhuma origem válida para o backtest multi-horizon — histórico "
            "insuficiente. Ajuste BACKTEST_MIN_TRAIN_WEEK/BACKTEST_HORIZONS em config.py."
        )

    products_meta = weekly[["product_id", "category"]].drop_duplicates().reset_index(drop=True)
    consumption_matrix, product_idx = _build_consumption_matrix(weekly)

    # códigos categóricos calculados uma única vez por produto (não a cada origem)
    codes_by_product = {
        row["product_id"]: (
            product_enc.transform([row["product_id"]])[0],
            category_enc.transform([row["category"]])[0],
        )
        for _, row in products_meta.iterrows()
    }

    rows = []
    for origin in origins:
        trainable = all_trainable[all_trainable["week_id"] <= origin]
        model = train_model(trainable)

        # histórico até a origem, para TODOS os produtos de uma vez
        # (fatiamento numpy, sem refiltrar o DataFrame por produto)
        histories = {
            pid: consumption_matrix[:origin, idx].tolist() for pid, idx in product_idx.items()
        }
        codes = {pid: codes_by_product[pid] for pid in product_idx}
        origin_date = pd.to_datetime(weekly.loc[weekly["week_id"] == origin, "week_end"].iloc[0])

        # UMA chamada em lote (todos os produtos, 4 passos) em vez de 30
        # chamadas de recursive_forecast() individuais nesta origem.
        model_preds = recursive_forecast_batch(
            model=model, histories=histories, codes=codes,
            start_date=origin_date, horizon=BACKTEST_HORIZONS,
        )

        for pid, idx in product_idx.items():
            history = histories[pid]
            naive_val = history[-1]
            ma4_val = float(np.mean(history[-4:]))
            category = products_meta.loc[products_meta["product_id"] == pid, "category"].iloc[0]

            for h in range(1, BACKTEST_HORIZONS + 1):
                target_week = origin + h
                if target_week > consumption_matrix.shape[0]:
                    continue  # não deveria acontecer dado get_valid_origins, mas por segurança
                actual = float(consumption_matrix[target_week - 1, idx])

                seasonal_week = target_week - 52
                seasonal_val = (
                    float(consumption_matrix[seasonal_week - 1, idx]) if seasonal_week >= 1 else ma4_val
                )

                rows.append(
                    {
                        "origin_week": origin,
                        "product_id": pid,
                        "category": category,
                        "horizon": h,
                        "actual": actual,
                        "pred_model": float(model_preds[pid][h - 1]["qty"]),
                        "pred_naive": float(naive_val),
                        "pred_moving_average_4": ma4_val,
                        "pred_seasonal_52": seasonal_val,
                    }
                )

    detail = pd.DataFrame(rows)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    detail.to_csv(RESULTS_DIR / "backtest_multihorizon_detail.csv", index=False)

    # consolidação por horizonte x método, + linha "ALL" (todos horizontes juntos)
    methods = {
        "naive": "pred_naive",
        "moving_average_4": "pred_moving_average_4",
        "seasonal_52": "pred_seasonal_52",
        "model": "pred_model",
    }
    summary_rows = []
    for horizon_label, subset in [(str(h), detail[detail["horizon"] == h]) for h in range(1, BACKTEST_HORIZONS + 1)] + [
        ("ALL", detail)
    ]:
        for method_name, pred_col in methods.items():
            metrics = evaluate_predictions(subset, "actual", pred_col)
            metrics["horizon"] = horizon_label
            metrics["method"] = method_name
            summary_rows.append(metrics)

    summary = pd.DataFrame(summary_rows)[["horizon", "method", "mae", "wape", "bias", "n_obs"]]
    summary.to_csv(RESULTS_DIR / "backtest_multihorizon_summary.csv", index=False)

    print(f"=== BACKTEST ROLLING-ORIGIN MULTI-HORIZON ({len(origins)} origens, "
          f"semanas {origins[0]} a {origins[-1]}) ===\n")
    for horizon_label in ["1", "2", "3", "4", "ALL"]:
        block = summary[summary["horizon"] == horizon_label].sort_values("wape")
        title = f"Horizonte H+{horizon_label}" if horizon_label != "ALL" else "TODOS OS HORIZONTES (consolidado)"
        print(f"--- {title} ---")
        print(block[["method", "mae", "wape", "bias", "n_obs"]].to_string(index=False))
        winner = block.iloc[0]["method"]
        print(f"Melhor método: {winner.upper()}\n")

    print(f"[OK] resultados salvos em {RESULTS_DIR}/backtest_multihorizon_summary.csv "
          f"e backtest_multihorizon_detail.csv")
    return summary, detail


if __name__ == "__main__":
    run_backtest()
