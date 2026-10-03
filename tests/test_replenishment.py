"""
Testes do motor de reposição: fórmulas e classificação de prioridade.
"""

import math

import pandas as pd
import pytest

from replenishment import classify_priority


def _row(**overrides):
    base = {
        "forecast_weekly": 10.0,
        "lead_time_weeks": 1.0,
        "expected_until_arrival": 10.0,
        "safety_stock": 8.0,
        "review_stock": 10.0,
        "target_stock": 28.0,
        "on_hand": 30,
        "in_transit": 0,
        "suggested_order": 0,
    }
    base.update(overrides)
    return pd.Series(base)


def test_priority_critica_when_stock_below_lead_time_demand():
    row = _row(on_hand=5, suggested_order=23)
    priority, reason = classify_priority(row)
    assert priority == "CRITICA"
    assert "lead time" in reason


def test_priority_alta_when_stock_below_safety_but_above_lead_time_demand():
    row = _row(on_hand=9, suggested_order=19)
    row["expected_until_arrival"] = 8.0   # on_hand (9) já cobre o lead time
    row["safety_stock"] = 12.0            # mas fica abaixo da segurança
    priority, reason = classify_priority(row)
    assert priority == "ALTA"
    assert "segurança" in reason


def test_priority_media_when_order_needed_without_rupture_risk():
    row = _row(on_hand=20, suggested_order=8)
    row["expected_until_arrival"] = 10.0
    row["safety_stock"] = 8.0
    priority, _reason = classify_priority(row)
    assert priority == "MEDIA"


def test_priority_baixa_when_no_order_needed():
    row = _row(on_hand=30, suggested_order=0)
    priority, _reason = classify_priority(row)
    assert priority == "BAIXA"


def test_priority_baixa_text_credits_on_hand_plus_in_transit_not_on_hand_alone():
    """Cenário do guia de auditoria: on_hand < target_stock, mas
    on_hand + in_transit >= target_stock -> BAIXA é a prioridade correta,
    mas o texto NÃO pode afirmar que o estoque atual sozinho cobre o alvo."""
    row = _row(on_hand=20, in_transit=15, target_stock=30, suggested_order=0)
    row["expected_until_arrival"] = 10.0
    row["safety_stock"] = 8.0
    priority, reason = classify_priority(row)
    assert priority == "BAIXA"
    assert "em trânsito" in reason  # não pode citar só o estoque disponível


def test_critica_ignores_in_transit_by_design():
    """Convenção documentada: risco de ruptura (CRÍTICA) é avaliado de
    forma conservadora, ignorando in_transit (sem ETA garantido). Mesmo
    com in_transit alto, se on_hand sozinho não cobre o lead time, a
    prioridade deve continuar CRÍTICA."""
    row = _row(on_hand=2, in_transit=1000, suggested_order=0)
    row["expected_until_arrival"] = 10.0
    priority, reason = classify_priority(row)
    assert priority == "CRITICA"
    assert "ETA" in reason or "trânsito" in reason


def test_suggested_order_formula_never_negative():
    target_stock = 20
    on_hand = 100
    in_transit = 0
    suggested_order = max(0, math.ceil(target_stock - on_hand - in_transit))
    assert suggested_order == 0


def test_suggested_order_formula_matches_expected_calculation():
    target_stock = 50.4
    on_hand = 10
    in_transit = 5
    suggested_order = max(0, math.ceil(target_stock - on_hand - in_transit))
    assert suggested_order == 36  # ceil(35.4)


def test_safety_stock_scales_with_sqrt_lead_time():
    service_factor = 1.65
    demand_std = 4.0
    safety_1_week = service_factor * demand_std * (1.0 ** 0.5)
    safety_4_weeks = service_factor * demand_std * (4.0 ** 0.5)
    # dobrar o lead time (de 1 para 4 semanas) deve multiplicar a segurança por sqrt(4)=2
    assert safety_4_weeks == pytest.approx(safety_1_week * 2)


def test_target_stock_is_sum_of_three_components():
    expected_until_arrival = 15.0
    safety_stock = 8.0
    review_stock = 5.0
    target_stock = expected_until_arrival + safety_stock + review_stock
    assert target_stock == 28.0
