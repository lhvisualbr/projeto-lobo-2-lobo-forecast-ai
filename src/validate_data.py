"""
validate_data.py
Validações de qualidade sobre os dados sintéticos em data/raw/.

Objetivo: falhar ruidosamente (AssertionError) se qualquer regra de negócio
básica for violada, ANTES de os dados chegarem ao banco ou a um modelo.
"""

import sys

import pandas as pd

from config import CRITICALITY_LEVELS, DATA_RAW_DIR


class DataValidationError(Exception):
    """Erro levantado quando um dado sintético viola uma regra do projeto."""


def _load_raw():
    products = pd.read_csv(DATA_RAW_DIR / "products.csv")
    calendar = pd.read_csv(DATA_RAW_DIR / "calendar.csv")
    consumption = pd.read_csv(DATA_RAW_DIR / "consumption.csv")
    inventory = pd.read_csv(DATA_RAW_DIR / "inventory_snapshot.csv")
    return products, calendar, consumption, inventory


def validate_products(products: pd.DataFrame) -> None:
    if products["product_id"].duplicated().any():
        raise DataValidationError("product_id duplicado em products.csv")
    if (products["unit_cost"] <= 0).any():
        raise DataValidationError("unit_cost <= 0 encontrado em products.csv")
    if (products["lead_time_days"] <= 0).any():
        raise DataValidationError("lead_time_days <= 0 encontrado em products.csv")
    invalid_criticality = ~products["criticality"].isin(CRITICALITY_LEVELS)
    if invalid_criticality.any():
        raise DataValidationError("criticality fora do domínio LOW/MEDIUM/HIGH")


def validate_calendar(calendar: pd.DataFrame) -> None:
    if calendar["week_id"].duplicated().any():
        raise DataValidationError("week_id duplicado em calendar.csv")
    starts = pd.to_datetime(calendar["week_start"])
    if not (starts.diff().dropna() == pd.Timedelta(days=7)).all():
        raise DataValidationError("calendar.csv possui semanas não contíguas")


def validate_consumption(consumption: pd.DataFrame, products: pd.DataFrame) -> None:
    if consumption["transaction_id"].duplicated().any():
        raise DataValidationError("transaction_id duplicado em consumption.csv")
    if (consumption["quantity"] <= 0).any():
        raise DataValidationError("quantity <= 0 encontrado em consumption.csv")
    valid_products = set(products["product_id"])
    orphan = ~consumption["product_id"].isin(valid_products)
    if orphan.any():
        raise DataValidationError(
            f"{orphan.sum()} transações referenciam product_id inexistente (FK quebrada)"
        )


def validate_inventory(inventory: pd.DataFrame, products: pd.DataFrame) -> None:
    if (inventory["on_hand"] < 0).any():
        raise DataValidationError("on_hand negativo em inventory_snapshot.csv")
    if (inventory["in_transit"] < 0).any():
        raise DataValidationError("in_transit negativo em inventory_snapshot.csv")
    valid_products = set(products["product_id"])
    orphan = ~inventory["product_id"].isin(valid_products)
    if orphan.any():
        raise DataValidationError(
            f"{orphan.sum()} snapshots referenciam product_id inexistente (FK quebrada)"
        )


def validate_no_pii(products: pd.DataFrame, consumption: pd.DataFrame) -> None:
    """Checagem simples de que nenhum termo real/confidencial vazou para os
    dados sintéticos (ex.: nome da empresa real onde o autor trabalha)."""
    forbidden_terms = ["CBSI"]
    text_blob = " ".join(products.astype(str).values.flatten()) + " ".join(
        consumption["work_center"].astype(str).unique()
    )
    for term in forbidden_terms:
        if term.lower() in text_blob.lower():
            raise DataValidationError(f"Termo proibido encontrado nos dados: {term}")


def run_all_validations() -> None:
    products, calendar, consumption, inventory = _load_raw()

    validate_products(products)
    validate_calendar(calendar)
    validate_consumption(consumption, products)
    validate_inventory(inventory, products)
    validate_no_pii(products, consumption)

    print("[OK] products.csv            -> válido")
    print("[OK] calendar.csv            -> válido")
    print("[OK] consumption.csv         -> válido")
    print("[OK] inventory_snapshot.csv  -> válido")
    print("[OK] nenhum termo confidencial encontrado")
    print("\nTodas as validações passaram.")


if __name__ == "__main__":
    try:
        run_all_validations()
    except DataValidationError as exc:
        print(f"[FALHA] {exc}", file=sys.stderr)
        sys.exit(1)
