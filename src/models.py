"""
models.py
Modelo global de Machine Learning para previsão de consumo semanal.

Um único modelo (RandomForestRegressor) treinado com todos os produtos
juntos, usando product_id e category como variáveis categóricas
(codificadas). random_state fixo para reprodutibilidade.
"""

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

FEATURE_COLUMNS = [
    "lag_1", "lag_2", "lag_4", "lag_8", "lag_13", "lag_52",
    "mean_4", "mean_8", "std_4", "std_8",
    "month", "week_of_year_num",
    "product_id_enc", "category_enc",
]

TARGET_COLUMN = "units_consumed"


def encode_categoricals(df):
    df = df.copy()
    product_encoder = LabelEncoder()
    category_encoder = LabelEncoder()
    df["product_id_enc"] = product_encoder.fit_transform(df["product_id"])
    df["category_enc"] = category_encoder.fit_transform(df["category"])
    return df, product_encoder, category_encoder


def train_model(train_df, random_state: int = 42) -> RandomForestRegressor:
    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=10,
        min_samples_leaf=3,
        random_state=random_state,
        n_jobs=-1,
    )
    X = train_df[FEATURE_COLUMNS]
    y = train_df[TARGET_COLUMN]
    model.fit(X, y)
    return model


def predict_model(model: RandomForestRegressor, df) -> np.ndarray:
    X = df[FEATURE_COLUMNS]
    preds = model.predict(X)
    return np.round(np.clip(preds, 0, None))
