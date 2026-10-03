"""
test_regression_numerical.py
Testes de REGRESSÃO NUMÉRICA (V1.1.1) — detectam se uma refatoração
(como a otimização de performance do backtest) alterou os resultados além
de uma tolerância numérica tecnicamente aceitável.

Diferente de um teste unitário ou de integração, estes testes NÃO geram
dados novos — eles leem os artefatos já produzidos por uma execução real
do pipeline (`results/*.csv`) e comparam contra os valores de referência
conhecidos e já auditados da V1.1 (ver docs/MODEL_CARD.md e
docs/PERFORMANCE_AUDIT.md). Por isso, cada teste é PULADO (não falha) se
o artefato correspondente ainda não existir — rodar a suíte inteira em um
clone novo, antes do pipeline, não deve quebrar por causa deles.

Usamos tolerância numérica (`pytest.approx` / diferença absoluta), nunca
comparação de string ou de arquivo byte-a-byte — comparar texto quebraria
por qualquer mudança de formatação irrelevante (ordem de colunas, casas
decimais no print), sem relação com o que realmente importa: os NÚMEROS.
"""

from pathlib import Path

import pandas as pd
import pytest

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

# valores de referência da V1.1 (já auditados) — ver docs/MODEL_CARD.md.
# Tolerância: 0.01 de WAPE (1 ponto percentual) é folgada o suficiente
# para absorver qualquer diferença de arredondamento entre execuções, mas
# apertada o suficiente para pegar uma mudança de metodologia real.
WAPE_TOLERANCE = 0.01
COST_TOLERANCE_RATIO = 0.05  # 5% — custo é uma soma de muitos termos, mais sensível a arredondamento


def _read_or_skip(path: Path, reason: str) -> pd.DataFrame:
    if not path.exists():
        pytest.skip(f"{path.name} ainda não foi gerado — rode `python src/{reason}` primeiro")
    return pd.read_csv(path)


def test_onestep_wape_within_tolerance_of_v11_reference():
    summary = _read_or_skip(RESULTS_DIR / "onestep_model_vs_baselines.csv", "run_evaluation.py")
    by_method = summary.set_index("method")["wape"]

    assert by_method["model"] == pytest.approx(0.2756, abs=WAPE_TOLERANCE)
    assert by_method["moving_average_4"] == pytest.approx(0.2766, abs=WAPE_TOLERANCE)
    # o modelo deve continuar vencendo a melhor baseline no one-step-ahead,
    # como na V1.1 — por margem pequena, mas vencendo.
    assert by_method["model"] < by_method["moving_average_4"]


def test_backtest_multihorizon_shape_matches_v11_reference():
    detail = _read_or_skip(RESULTS_DIR / "backtest_multihorizon_detail.csv", "backtest_multihorizon.py")

    n_origins = detail["origin_week"].nunique()
    n_products = detail["product_id"].nunique()
    n_horizons = detail["horizon"].nunique()

    assert n_origins == 41, f"esperado 41 origens (semanas 60-100), obtido {n_origins}"
    assert n_products == 30, f"esperado 30 SKUs, obtido {n_products}"
    assert n_horizons == 4, f"esperado 4 horizontes (H+1..H+4), obtido {n_horizons}"
    assert len(detail) == n_origins * n_products * n_horizons == 4920

    # nenhum NaN inesperado em nenhuma coluna numérica
    numeric_cols = ["actual", "pred_model", "pred_naive", "pred_moving_average_4", "pred_seasonal_52"]
    assert detail[numeric_cols].isna().sum().sum() == 0

    # nenhuma previsão do modelo negativa (mesma regra de clip do forecast de produção)
    assert (detail["pred_model"] >= 0).all()


def test_backtest_multihorizon_wape_within_tolerance_of_v11_reference():
    summary = _read_or_skip(RESULTS_DIR / "backtest_multihorizon_summary.csv", "backtest_multihorizon.py")

    reference = {
        # (horizon, method): wape esperado (V1.1, auditado)
        ("1", "model"): 0.2414,
        ("2", "model"): 0.2478,
        ("3", "model"): 0.2568,
        ("4", "model"): 0.2581,
        ("ALL", "model"): 0.2510,
        ("3", "moving_average_4"): 0.2538,
        ("4", "moving_average_4"): 0.2534,
        ("ALL", "moving_average_4"): 0.2515,
    }
    by_key = summary.set_index(["horizon", "method"])["wape"]

    for (horizon, method), expected_wape in reference.items():
        actual_wape = by_key.loc[(horizon, method)]
        assert actual_wape == pytest.approx(expected_wape, abs=WAPE_TOLERANCE), (
            f"H+{horizon} {method}: esperado ~{expected_wape}, obtido {actual_wape} "
            f"(fora da tolerância de {WAPE_TOLERANCE}) — investigar antes de aceitar."
        )

    # invariante metodológico da V1.1 que não deve mudar só por causa de
    # otimização de performance: o modelo vence em H+1/H+2, a baseline
    # simples vence em H+3/H+4. Se isso mudou, é uma mudança de resultado
    # real, não um detalhe de arredondamento — precisa de investigação.
    assert by_key.loc[("1", "model")] < by_key.loc[("1", "moving_average_4")]
    assert by_key.loc[("2", "model")] < by_key.loc[("2", "moving_average_4")]
    assert by_key.loc[("3", "moving_average_4")] < by_key.loc[("3", "model")]
    assert by_key.loc[("4", "moving_average_4")] < by_key.loc[("4", "model")]


def test_replenishment_distribution_within_tolerance_of_v11_reference():
    repl = _read_or_skip(RESULTS_DIR / "replenishment_suggestions.csv", "replenishment.py")

    counts = repl["priority"].value_counts()
    reference_counts = {"CRITICA": 3, "ALTA": 1, "MEDIA": 9, "BAIXA": 17}
    for priority, expected in reference_counts.items():
        actual = int(counts.get(priority, 0))
        assert actual == expected, (
            f"prioridade {priority}: esperado {expected} SKUs, obtido {actual} — "
            "investigar antes de aceitar (contagem de SKUs não deveria mudar sem "
            "motivo, já que dados sintéticos são determinísticos)."
        )

    total_cost = repl["estimated_replenishment_cost"].sum()
    reference_cost = 21268.45
    assert total_cost == pytest.approx(reference_cost, rel=COST_TOLERANCE_RATIO), (
        f"custo total estimado: esperado ~R$ {reference_cost}, obtido R$ {total_cost:.2f}"
    )
