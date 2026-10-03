"""
recursive_forecast.py
Lógica de forecast recursivo COMPARTILHADA entre:
  - forecast.py          (previsão final de produção, 4 semanas à frente
                           a partir do fim do histórico conhecido)
  - backtest_multihorizon.py (mesma lógica, mas aplicada a várias origens
                               temporais dentro do histórico, para avaliação)

Extraído para um módulo único para que as DUAS previsões usem exatamente
o mesmo código de recursão — evitando divergência entre "como o projeto
prevê de verdade" e "como o projeto foi avaliado".

Recursivo = a previsão do passo N é usada como pseudo-histórico para
calcular as features (lags/rolling) do passo N+1. Nenhum valor real
futuro (posterior à origem) é utilizado em nenhum passo.
"""

import numpy as np
import pandas as pd

from models import FEATURE_COLUMNS


def compute_step_features(history: list, month: int, week_of_year: int) -> dict:
    """Calcula as mesmas features de lag/rolling usadas no treino, a partir
    de uma lista de consumo histórico (índice 0 = semana mais antiga,
    último elemento = semana mais recente já conhecida ou já prevista)."""
    def lag(n):
        return history[-n] if len(history) >= n else np.nan

    def rolling_mean(n):
        window = history[-n:] if len(history) >= n else None
        return float(np.mean(window)) if window else np.nan

    def rolling_std(n):
        window = history[-n:] if len(history) >= n else None
        return float(np.std(window, ddof=1)) if window and len(window) > 1 else np.nan

    return {
        "lag_1": lag(1), "lag_2": lag(2), "lag_4": lag(4),
        "lag_8": lag(8), "lag_13": lag(13), "lag_52": lag(52),
        "mean_4": rolling_mean(4), "mean_8": rolling_mean(8),
        "std_4": rolling_std(4), "std_8": rolling_std(8),
        "month": month, "week_of_year_num": week_of_year,
    }


def recursive_forecast(
    model,
    history: list,
    product_code: int,
    category_code: int,
    start_date: pd.Timestamp,
    horizon: int,
) -> list:
    """Gera `horizon` previsões recursivas a partir de `start_date`
    (a data da última semana já conhecida/usada como origem).

    `history` é consumido de forma NÃO destrutiva para quem chama (uma
    cópia é feita internamente) e cresce a cada passo com a PRÓPRIA
    previsão anterior — nunca com um valor real futuro.

    Retorna uma lista de dicts: {step, week_start, week_end, qty}.
    """
    hist = list(history)  # cópia — não muta a lista do chamador
    predictions = []

    for step in range(1, horizon + 1):
        future_date = start_date + pd.Timedelta(weeks=step)
        month = future_date.month
        week_of_year = future_date.isocalendar()[1]

        feat = compute_step_features(hist, month, week_of_year)
        feat["product_id_enc"] = product_code
        feat["category_enc"] = category_code

        X = pd.DataFrame([feat])[FEATURE_COLUMNS].fillna(0)
        raw_pred = float(model.predict(X)[0])
        pred = max(0, round(raw_pred))  # nunca negativo; arredondado (unidades inteiras)

        predictions.append(
            {
                "step": step,
                "week_start": (future_date - pd.Timedelta(days=6)).date().isoformat(),
                "week_end": future_date.date().isoformat(),
                "qty": pred,
            }
        )
        hist.append(pred)  # pseudo-histórico para o próximo passo recursivo

    return predictions


def recursive_forecast_batch(
    model,
    histories: dict,
    codes: dict,
    start_date: pd.Timestamp,
    horizon: int,
) -> dict:
    """Versão EM LOTE de `recursive_forecast()` — MESMA matemática, aplicada
    a vários produtos ao mesmo tempo por passo, para reduzir drasticamente
    o número de chamadas a `model.predict()` (uma por PASSO, cobrindo
    todos os produtos de uma vez, em vez de uma por PRODUTO x PASSO).

    Otimização de engenharia pura (V1.1.1): o resultado numérico é
    IDÊNTICO a chamar `recursive_forecast()` produto a produto — a única
    coisa que muda é como o trabalho é agrupado antes de chamar o modelo.
    `RandomForestRegressor.predict()` processa cada linha de forma
    independente (não há interação entre linhas de um mesmo batch), então
    agrupar N produtos em uma chamada produz exatamente as mesmas N
    previsões que N chamadas separadas de 1 linha cada — só com bem menos
    overhead de Python/pandas/joblib por chamada.

    `histories`: dict {chave: lista de consumo histórico}.
    `codes`: dict {chave: (product_code, category_code)}.
    Retorna dict {chave: lista de previsões}, mesmo formato de
    `recursive_forecast()` por chave.
    """
    keys = list(histories.keys())
    hist_copies = {k: list(v) for k, v in histories.items()}  # não muta o histórico do chamador
    predictions = {k: [] for k in keys}

    for step in range(1, horizon + 1):
        future_date = start_date + pd.Timedelta(weeks=step)
        month = future_date.month
        week_of_year = future_date.isocalendar()[1]
        week_start = (future_date - pd.Timedelta(days=6)).date().isoformat()
        week_end = future_date.date().isoformat()

        feats = []
        for k in keys:
            feat = compute_step_features(hist_copies[k], month, week_of_year)
            product_code, category_code = codes[k]
            feat["product_id_enc"] = product_code
            feat["category_enc"] = category_code
            feats.append(feat)

        # UMA chamada a predict() para todos os produtos deste passo -
        # antes eram N chamadas (uma por produto) neste mesmo passo.
        X = pd.DataFrame(feats)[FEATURE_COLUMNS].fillna(0)
        raw_preds = model.predict(X)

        for k, raw_pred in zip(keys, raw_preds):
            pred = max(0, round(float(raw_pred)))  # mesma regra de arredondamento/clip de recursive_forecast()
            predictions[k].append({"step": step, "week_start": week_start, "week_end": week_end, "qty": pred})
            hist_copies[k].append(pred)  # pseudo-histórico do próprio produto para o próximo passo

    return predictions
