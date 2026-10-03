"""
test_pipeline_integration.py
Teste de INTEGRAÇÃO do fluxo principal do pipeline — detecta regressões
entre módulos que os testes unitários (que testam funções isoladas) não
pegam.

Fluxo coberto (via subprocess, exatamente como um usuário rodaria pela
linha de comando):

    dados -> validação -> SQLite -> features -> treino -> avaliação
          -> forecast -> reposição

Cada script roda como processo Python separado (mesmo interpretador do
pytest), então cada um importa seus módulos "do zero" — sem qualquer
estado global (como o `rng` de generate_data.py) vazando de outros
arquivos de teste.

O backtest multi-horizon (o mais custoso, ~2-3 min com todas as origens)
é testado à parte, em versão reduzida (poucas origens) e IN-PROCESS via
run_backtest(), só para garantir que o código roda sem erro — sem pagar
o custo total em todo `pytest tests/`.

NÃO remove nem substitui os testes unitários existentes.
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
DATA_RAW_DIR = SRC_DIR.parent / "data" / "raw"
DATA_PROCESSED_DIR = SRC_DIR.parent / "data" / "processed"
RESULTS_DIR = SRC_DIR.parent / "results"
DATABASE_PATH = SRC_DIR.parent / "database" / "lobo_forecast.db"

PIPELINE_SCRIPTS = [
    "generate_data.py",
    "validate_data.py",
    "database.py",
    "data_prep.py",
    "run_evaluation.py",
    "forecast.py",
    "replenishment.py",
]


def _run_script(script_name: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, script_name],
        cwd=SRC_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.fixture(scope="module")
def pipeline_result():
    """Roda o pipeline completo (exceto backtest multi-horizon) UMA vez
    para todo o módulo de teste, e retorna os resultados de cada etapa
    para as asserções abaixo inspecionarem."""
    results = {}
    for script in PIPELINE_SCRIPTS:
        proc = _run_script(script)
        results[script] = proc
        assert proc.returncode == 0, (
            f"{script} falhou (código {proc.returncode}).\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
    return results


def test_all_pipeline_scripts_run_without_error(pipeline_result):
    # a asserção principal já acontece na fixture; aqui só confirmamos
    # que passamos por todos os scripts esperados.
    assert set(pipeline_result.keys()) == set(PIPELINE_SCRIPTS)


def test_raw_data_files_created(pipeline_result):
    for filename in ["products.csv", "calendar.csv", "consumption.csv", "inventory_snapshot.csv"]:
        path = DATA_RAW_DIR / filename
        assert path.exists(), f"{filename} não foi gerado"
        assert len(pd.read_csv(path)) > 0, f"{filename} está vazio"


def test_database_has_expected_tables_and_rows(pipeline_result):
    import sqlite3

    assert DATABASE_PATH.exists()
    conn = sqlite3.connect(DATABASE_PATH)
    for table in ["products", "calendar", "consumption", "inventory_snapshot"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count > 0, f"tabela {table} está vazia no banco"
    conn.close()


def test_weekly_series_covers_all_products(pipeline_result):
    weekly = pd.read_csv(DATA_PROCESSED_DIR / "weekly_series.csv")
    products = pd.read_csv(DATA_RAW_DIR / "products.csv")
    assert set(weekly["product_id"].unique()) == set(products["product_id"].unique())
    assert weekly["units_consumed"].isna().sum() == 0  # grade completa, sem buracos


def test_onestep_evaluation_outputs_are_consistent(pipeline_result):
    summary = pd.read_csv(RESULTS_DIR / "onestep_model_vs_baselines.csv")
    assert {"naive", "moving_average_4", "seasonal_52", "model"} == set(summary["method"])
    assert (summary["wape"] >= 0).all()
    assert (summary["wape"] <= 5).all()  # sanity check: WAPE não deveria explodir

    test_predictions = pd.read_csv(RESULTS_DIR / "onestep_test_predictions.csv")
    assert len(test_predictions) > 0
    assert (test_predictions["pred_model"] >= 0).all()  # nunca previsão negativa


def test_forecast_output_matches_horizon_and_products(pipeline_result):
    forecast = pd.read_csv(RESULTS_DIR / "forecast_4weeks.csv")
    products = pd.read_csv(DATA_RAW_DIR / "products.csv")
    assert set(forecast["product_id"].unique()) == set(products["product_id"].unique())
    assert set(forecast["forecast_week"].unique()) == {1, 2, 3, 4}
    assert (forecast["forecast_qty"] >= 0).all()


def test_replenishment_output_has_valid_priorities(pipeline_result):
    repl = pd.read_csv(RESULTS_DIR / "replenishment_suggestions.csv")
    products = pd.read_csv(DATA_RAW_DIR / "products.csv")
    assert set(repl["product_id"].unique()) == set(products["product_id"].unique())
    assert set(repl["priority"].unique()) <= {"CRITICA", "ALTA", "MEDIA", "BAIXA"}
    assert (repl["suggested_order"] >= 0).all()
