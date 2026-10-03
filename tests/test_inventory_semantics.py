"""
Testes da CONVENÇÃO TEMPORAL do inventory_snapshot:
"snapshot de week_end = posição APÓS todos os movimentos daquela semana",
e nunca usando informação de semanas futuras.

Usamos um cenário controlado (consumo alto o bastante para nunca disparar
reposição) para poder verificar a aritmética exata sem depender dos
valores aleatórios internos do gerador.
"""

import numpy as np
import pandas as pd

import generate_data as gd


def _make_scenario(week4_consumption: int):
    """Monta um cenário determinístico de 1 produto e 4 semanas conhecidas.
    base_weekly_qty é propositalmente grande para que o estoque inicial
    fique muito acima do ponto de reposição e NUNCA dispare uma nova
    ordem — assim in_transit permanece 0 durante todo o teste e a
    aritmética de on_hand fica 100% previsível: apenas subtração de
    consumo, sem chegadas."""
    products = pd.DataFrame(
        [{
            "product_id": "MATTEST", "product_name": "Item de Teste",
            "category": "TESTE", "unit": "UN", "unit_cost": 10.0,
            "lead_time_days": 7, "supplier": "Fornecedor Teste",
            "criticality": "MEDIUM",
        }]
    )
    calendar = pd.DataFrame(
        [
            {"week_id": 1, "week_start": "2026-01-05", "week_end": "2026-01-11", "is_known": True},
            {"week_id": 2, "week_start": "2026-01-12", "week_end": "2026-01-18", "is_known": True},
            {"week_id": 3, "week_start": "2026-01-19", "week_end": "2026-01-25", "is_known": True},
            {"week_id": 4, "week_start": "2026-01-26", "week_end": "2026-02-01", "is_known": True},
        ]
    )
    consumption = pd.DataFrame(
        [
            {"transaction_id": 1, "consumption_date": "2026-01-06", "product_id": "MATTEST", "quantity": 100, "work_center": "MANUTENCAO"},
            {"transaction_id": 2, "consumption_date": "2026-01-13", "product_id": "MATTEST", "quantity": 250, "work_center": "MANUTENCAO"},
            {"transaction_id": 3, "consumption_date": "2026-01-26", "product_id": "MATTEST", "quantity": week4_consumption, "work_center": "MANUTENCAO"},
            # semana 3 (2026-01-19) fica SEM transação de propósito: testa consumo zero real.
        ]
    )
    profiles = pd.DataFrame(
        [{"base_weekly_qty": 1000.0, "trend_slope": 0.0, "seasonal_amplitude": 0.0,
          "seasonal_phase": 0.0, "is_intermittent": False, "active_prob": 1.0,
          "noise_ratio": 0.0}],
        index=["MATTEST"],
    )
    return products, calendar, consumption, profiles


def _run_with_fixed_seed(week4_consumption: int) -> pd.DataFrame:
    gd.rng = np.random.default_rng(42)  # reseta o gerador global antes de cada chamada
    products, calendar, consumption, profiles = _make_scenario(week4_consumption)
    return gd.build_inventory_snapshot(products, calendar, consumption, profiles)


def test_never_triggers_reorder_in_this_scenario():
    """Pré-condição do cenário controlado: in_transit deve ficar em 0 a
    semana inteira, senão os testes de aritmética abaixo não são válidos."""
    result = _run_with_fixed_seed(week4_consumption=50)
    assert (result["in_transit"] == 0).all()


def test_on_hand_reflects_own_week_consumption():
    """on_hand(semana N) deve refletir a subtração do consumo da PRÓPRIA
    semana N (fechamento de semana), não o valor de antes do consumo."""
    result = _run_with_fixed_seed(week4_consumption=50).sort_values("snapshot_date").reset_index(drop=True)

    on_hand_before_any_movement = result.loc[0, "on_hand"] + 100  # desfaz a semana 1
    week1 = result.loc[0, "on_hand"]
    week2 = result.loc[1, "on_hand"]
    week3 = result.loc[2, "on_hand"]  # semana sem consumo (zero real)
    week4 = result.loc[3, "on_hand"]

    assert week1 == on_hand_before_any_movement - 100
    assert week2 == week1 - 250
    assert week3 == week2  # semana 3 não teve consumo -> estoque não muda
    assert week4 == week3 - 50


def test_snapshot_never_uses_future_consumption():
    """MUDAR o consumo de semanas futuras (semana 4) não pode alterar o
    snapshot já fechado de semanas anteriores (1, 2 e 3). Essa é a prova
    direta de que nenhuma informação futura é usada."""
    result_a = _run_with_fixed_seed(week4_consumption=50).sort_values("snapshot_date").reset_index(drop=True)
    result_b = _run_with_fixed_seed(week4_consumption=999).sort_values("snapshot_date").reset_index(drop=True)

    for week in [0, 1, 2]:  # semanas 1, 2 e 3 (índices 0-based)
        assert result_a.loc[week, "on_hand"] == result_b.loc[week, "on_hand"], (
            f"Semana índice {week} mudou ao alterar consumo futuro — "
            "possível uso de informação futura no snapshot!"
        )
        assert result_a.loc[week, "in_transit"] == result_b.loc[week, "in_transit"]

    # a semana 4 (a que de fato mudou) pode legitimamente ser diferente
    assert result_a.loc[3, "on_hand"] != result_b.loc[3, "on_hand"]


def test_zero_consumption_week_keeps_stock_unchanged():
    """Uma semana sem nenhuma transação de consumo não deve alterar
    on_hand (nem para mais, nem para menos) neste cenário sem chegadas."""
    result = _run_with_fixed_seed(week4_consumption=50).sort_values("snapshot_date").reset_index(drop=True)
    week2 = result.loc[1, "on_hand"]
    week3 = result.loc[2, "on_hand"]
    assert week2 == week3
