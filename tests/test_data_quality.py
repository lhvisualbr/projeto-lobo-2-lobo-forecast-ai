"""
Testes de qualidade dos dados sintéticos (data/raw/).
Rodar com o banco/CSVs já gerados: python src/generate_data.py antes dos testes.
"""

import pandas as pd
import pytest

from config import CRITICALITY_LEVELS, DATA_RAW_DIR


@pytest.fixture(scope="module")
def products():
    return pd.read_csv(DATA_RAW_DIR / "products.csv")


@pytest.fixture(scope="module")
def calendar():
    return pd.read_csv(DATA_RAW_DIR / "calendar.csv")


@pytest.fixture(scope="module")
def consumption():
    return pd.read_csv(DATA_RAW_DIR / "consumption.csv")


@pytest.fixture(scope="module")
def inventory():
    return pd.read_csv(DATA_RAW_DIR / "inventory_snapshot.csv")


# ---------------------------------------------------------------- products
def test_product_id_is_unique(products):
    assert not products["product_id"].duplicated().any()


def test_product_count_is_30(products):
    assert len(products) == 30


def test_unit_cost_is_positive(products):
    assert (products["unit_cost"] > 0).all()


def test_lead_time_is_positive(products):
    assert (products["lead_time_days"] > 0).all()


def test_criticality_domain(products):
    assert products["criticality"].isin(CRITICALITY_LEVELS).all()


# --------------------------------------------------------------- calendar
def test_calendar_week_id_is_unique(calendar):
    assert not calendar["week_id"].duplicated().any()


def test_calendar_weeks_are_contiguous(calendar):
    starts = pd.to_datetime(calendar["week_start"])
    diffs = starts.diff().dropna()
    assert (diffs == pd.Timedelta(days=7)).all()


# ------------------------------------------------------------ consumption
def test_transaction_id_is_unique(consumption):
    assert not consumption["transaction_id"].duplicated().any()


def test_consumption_quantity_is_positive(consumption):
    assert (consumption["quantity"] > 0).all()


def test_consumption_product_id_is_valid_fk(consumption, products):
    valid_ids = set(products["product_id"])
    assert consumption["product_id"].isin(valid_ids).all()


def test_no_confidential_terms_in_work_center(consumption):
    forbidden = {"CBSI"}
    values = set(consumption["work_center"].unique())
    assert not (forbidden & values)


# ------------------------------------------------------------- inventory
def test_on_hand_is_not_negative(inventory):
    assert (inventory["on_hand"] >= 0).all()


def test_in_transit_is_not_negative(inventory):
    assert (inventory["in_transit"] >= 0).all()


def test_inventory_product_id_is_valid_fk(inventory, products):
    valid_ids = set(products["product_id"])
    assert inventory["product_id"].isin(valid_ids).all()


# --------------------------------------------------- semanas zero mantidas
def test_zero_weeks_are_kept_not_removed(consumption, calendar, products):
    """Garante que, para produtos intermitentes, existem semanas conhecidas
    sem nenhuma transação — ou seja, o gerador de fato produz demanda
    intermitente (zeros reais), em vez de eliminar essas semanas da série."""
    known_weeks = calendar[calendar["is_known"] == True]
    assert len(known_weeks) > 0

    consumption["consumption_date"] = pd.to_datetime(consumption["consumption_date"])
    weeks_with_data = consumption.groupby("product_id")["consumption_date"].apply(
        lambda dates: dates.dt.to_period("W").nunique()
    )

    total_known_weeks = len(known_weeks)
    # ao menos um produto deve ter uma cobertura de semanas bem abaixo do total,
    # evidenciando intermitência real nos dados sintéticos.
    assert (weeks_with_data < total_known_weeks * 0.7).any()
