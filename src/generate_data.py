"""
generate_data.py
Gerador de dados 100% sintéticos do Lobo Forecast AI.

IMPORTANTE: depois de aprovado, este gerador deve ser CONGELADO.
Não alterar a lógica para "melhorar" resultados de modelos treinados
sobre estes dados — isso invalidaria qualquer avaliação honesta.

Saída: CSVs em data/raw/
    - products.csv
    - calendar.csv
    - consumption.csv
    - inventory_snapshot.csv
"""

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from config import (
    CATEGORIES,
    CRITICALITY_LEVELS,
    DATA_RAW_DIR,
    FORECAST_HORIZON_WEEKS,
    HISTORY_MONTHS,
    N_PRODUCTS,
    RANDOM_SEED,
    SIMULATED_TODAY,
    SUPPLIERS,
    UNITS,
    WORK_CENTERS,
)

rng = np.random.default_rng(RANDOM_SEED)


# --------------------------------------------------------------------------
# 1. CALENDÁRIO
# --------------------------------------------------------------------------
def build_calendar() -> pd.DataFrame:
    """Cria uma semana-calendário (segunda a domingo) cobrindo o histórico
    completo mais o horizonte futuro de forecast. Toda a série temporal do
    projeto é ancorada nesta tabela para garantir que nenhuma semana "some".
    """
    today = date.fromisoformat(SIMULATED_TODAY)
    # volta para a segunda-feira da semana de "hoje"
    last_known_monday = today - timedelta(days=today.weekday())

    n_history_weeks = int(HISTORY_MONTHS * 4.345)  # aprox. semanas em 24 meses
    first_monday = last_known_monday - timedelta(weeks=n_history_weeks - 1)

    total_weeks = n_history_weeks + FORECAST_HORIZON_WEEKS
    rows = []
    for i in range(total_weeks):
        week_start = first_monday + timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        rows.append(
            {
                "week_id": i + 1,
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "year": week_start.isocalendar()[0],
                "week_of_year": week_start.isocalendar()[1],
                "is_known": week_end <= last_known_monday + timedelta(days=6),
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 2. PRODUTOS
# --------------------------------------------------------------------------
_NAME_POOL = {
    "ABRASIVOS": [
        "Disco de Corte 4,5 pol", "Disco de Desbaste 7 pol", "Disco Flap 4,5 pol",
        "Lixa Grão 80", "Escova de Aço Rotativa", "Rebolo de Bancada",
    ],
    "SOLDAGEM": [
        "Eletrodo Revestido 3,25mm", "Arame de Solda MIG", "Bico de Contato MIG",
        "Máscara de Solda Filtro Escuro", "Vareta de Solda TIG",
    ],
    "CORTE E USINAGEM": [
        "Broca de Aço Rápido 8mm", "Lâmina de Serra Fita", "Pastilha de Torno",
        "Fresa de Topo 10mm", "Broca de Aço Rápido 5mm",
    ],
    "ELETRICA_BATERIAS": [
        "Bateria para Ferramenta 18V", "Cabo Flexível 2,5mm", "Fita Isolante",
        "Terminal Elétrico Prensado", "Lâmpada de Sinalização Industrial",
    ],
    "EPI_CONSUMIVEIS": [
        "Luva de Proteção Nitrílica", "Óculos de Segurança Incolor",
        "Protetor Auricular Tipo Plug", "Máscara Descartável PFF2",
        "Avental de Raspa de Couro",
    ],
}

_UNIT_BY_CATEGORY = {
    "ABRASIVOS": "UN",
    "SOLDAGEM": "KG",
    "CORTE E USINAGEM": "UN",
    "ELETRICA_BATERIAS": "UN",
    "EPI_CONSUMIVEIS": "PAR",
}


def build_products() -> pd.DataFrame:
    """Cria o catálogo de 30 SKUs fictícios distribuídos entre categorias
    industriais plausíveis. Nenhum nome, marca ou código real é utilizado.
    """
    rows = []
    product_counter = 1
    per_category = N_PRODUCTS // len(CATEGORIES)
    remainder = N_PRODUCTS % len(CATEGORIES)

    for cat_idx, category in enumerate(CATEGORIES):
        count = per_category + (1 if cat_idx < remainder else 0)
        names = _NAME_POOL[category]
        for i in range(count):
            base_name = names[i % len(names)]
            suffix = "" if i < len(names) else f" (Lote {i // len(names) + 1})"
            product_id = f"MAT{product_counter:03d}"
            unit = _UNIT_BY_CATEGORY.get(category, rng.choice(UNITS))
            unit_cost = round(float(rng.uniform(2.5, 180.0)), 2)
            lead_time_days = int(rng.choice([3, 5, 7, 10, 14, 21]))
            criticality = rng.choice(CRITICALITY_LEVELS, p=[0.35, 0.40, 0.25])
            supplier = rng.choice(SUPPLIERS)

            rows.append(
                {
                    "product_id": product_id,
                    "product_name": base_name + suffix,
                    "category": category,
                    "unit": unit,
                    "unit_cost": unit_cost,
                    "lead_time_days": lead_time_days,
                    "supplier": supplier,
                    "criticality": criticality,
                }
            )
            product_counter += 1

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 3. PERFIS DE DEMANDA (por produto) - define o comportamento sintético
# --------------------------------------------------------------------------
_TURNOVER_PROFILES = {
    "ALTO": {"base_range": (35, 70), "noise_ratio": 0.18, "share": 0.20},
    "MEDIO": {"base_range": (12, 30), "noise_ratio": 0.25, "share": 0.35},
    "BAIXO": {"base_range": (3, 10), "noise_ratio": 0.35, "share": 0.25},
    "INTERMITENTE": {"base_range": (4, 15), "noise_ratio": 0.45, "share": 0.20},
}


def assign_demand_profiles(products: pd.DataFrame) -> pd.DataFrame:
    """Atribui a cada produto um perfil de demanda (giro, tendência,
    sazonalidade e intermitência) que será usado pelo gerador de consumo.
    Isso garante variedade realista: nem tudo é ruído puro.
    """
    n = len(products)
    turnover_labels = []
    for label, cfg in _TURNOVER_PROFILES.items():
        turnover_labels += [label] * round(cfg["share"] * n)
    while len(turnover_labels) < n:
        turnover_labels.append("MEDIO")
    turnover_labels = turnover_labels[:n]
    rng.shuffle(turnover_labels)

    profiles = []
    for turnover in turnover_labels:
        cfg = _TURNOVER_PROFILES[turnover]
        base = rng.uniform(*cfg["base_range"])
        has_trend = rng.random() < 0.30
        trend_slope = rng.uniform(-0.003, 0.006) if has_trend else 0.0
        has_seasonality = rng.random() < 0.40
        seasonal_amplitude = rng.uniform(0.10, 0.30) if has_seasonality else 0.0
        seasonal_phase = rng.uniform(0, 2 * math.pi)
        is_intermittent = turnover == "INTERMITENTE"
        active_prob = rng.uniform(0.30, 0.55) if is_intermittent else 1.0

        profiles.append(
            {
                "turnover": turnover,
                "base_weekly_qty": base,
                "trend_slope": trend_slope,
                "seasonal_amplitude": seasonal_amplitude,
                "seasonal_phase": seasonal_phase,
                "is_intermittent": is_intermittent,
                "active_prob": active_prob,
                "noise_ratio": cfg["noise_ratio"],
            }
        )
    return pd.DataFrame(profiles, index=products["product_id"].values)


# --------------------------------------------------------------------------
# 4. CONSUMO SEMANAL -> TRANSAÇÕES
# --------------------------------------------------------------------------
def simulate_weekly_quantity(profile: pd.Series, week_index: int) -> int:
    """Calcula a quantidade consumida (inteira, >= 0) de um produto em uma
    semana específica, combinando nível base, tendência, sazonalidade,
    intermitência e ruído.
    """
    trend_component = 1 + profile["trend_slope"] * week_index
    seasonal_component = 1 + profile["seasonal_amplitude"] * math.sin(
        2 * math.pi * week_index / 52 + profile["seasonal_phase"]
    )
    expected = profile["base_weekly_qty"] * trend_component * seasonal_component
    expected = max(expected, 0.0)

    noise = rng.normal(0, profile["noise_ratio"] * max(expected, 1.0))
    quantity = expected + noise

    if profile["is_intermittent"] and rng.random() > profile["active_prob"]:
        return 0

    return max(0, round(quantity))


def build_consumption(
    products: pd.DataFrame, calendar: pd.DataFrame, profiles: pd.DataFrame
) -> pd.DataFrame:
    """Gera transações de consumo (retiradas de material) a partir da
    quantidade semanal alvo de cada produto, distribuída em 1 a 3 retiradas
    ao longo da semana e associada a um centro de trabalho.
    """
    known_weeks = calendar[calendar["is_known"]].reset_index(drop=True)
    rows = []
    transaction_counter = 1

    for _, product in products.iterrows():
        profile = profiles.loc[product["product_id"]]
        for week_index, week in known_weeks.iterrows():
            qty = simulate_weekly_quantity(profile, week_index)
            if qty <= 0:
                continue

            n_splits = int(rng.integers(1, 4)) if qty >= 3 else 1
            n_splits = min(n_splits, qty)
            split_qtys = np.array_split(np.arange(qty), n_splits)
            week_start = date.fromisoformat(week["week_start"])

            for part in split_qtys:
                if len(part) == 0:
                    continue
                day_offset = int(rng.integers(0, 5))  # seg a sex
                work_center = rng.choice(WORK_CENTERS)
                rows.append(
                    {
                        "transaction_id": transaction_counter,
                        "consumption_date": (week_start + timedelta(days=day_offset)).isoformat(),
                        "product_id": product["product_id"],
                        "quantity": len(part),
                        "work_center": work_center,
                    }
                )
                transaction_counter += 1

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 5. ESTOQUE (inventory_snapshot)
# --------------------------------------------------------------------------
def build_inventory_snapshot(
    products: pd.DataFrame,
    calendar: pd.DataFrame,
    consumption: pd.DataFrame,
    profiles: pd.DataFrame,
) -> pd.DataFrame:
    """Simula uma posição de estoque semanal coerente com o consumo gerado:
    quando o estoque projetado cai perto do ponto de reposição, uma
    quantidade "em trânsito" é agendada para chegar após o lead time.
    Não é um motor de reposição sofisticado - é apenas o suficiente para
    que os dados de estoque façam sentido frente ao consumo.

    CONVENÇÃO TEMPORAL (formal, ver docs/DATA_DICTIONARY.md):
    O snapshot registrado em `snapshot_date = week_end` representa a
    posição de estoque APÓS todos os movimentos daquela semana — ou seja,
    depois de subtrair o consumo da própria semana e de somar qualquer
    chegada programada para essa mesma semana. Isso é análogo a um saldo
    bancário de fim de dia, que já reflete as transações daquele dia:
    nenhuma informação de semanas FUTURAS é usada, apenas o fechamento da
    própria semana do snapshot. `in_transit` reportado é o que ainda resta
    em aberto IMEDIATAMENTE APÓS esse fechamento (não inclui a chegada que
    acabou de ser processada nesta mesma semana).
    """
    known_weeks = calendar[calendar["is_known"]].reset_index(drop=True)
    consumption_by_week = (
        consumption.assign(
            week_start=pd.to_datetime(consumption["consumption_date"])
            .dt.to_period("W-SUN")
            .apply(lambda p: p.start_time.date().isoformat())
        )
        .groupby(["product_id", "week_start"])["quantity"]
        .sum()
    )

    rows = []
    for _, product in products.iterrows():
        pid = product["product_id"]
        profile = profiles.loc[pid]
        lead_time_weeks = max(1, round(product["lead_time_days"] / 7))
        avg_weekly_demand = profile["base_weekly_qty"]
        reorder_point = avg_weekly_demand * (lead_time_weeks + 1)
        order_size = avg_weekly_demand * 4

        on_hand = avg_weekly_demand * rng.uniform(3, 6)
        pending_arrivals = {}  # week_index de chegada -> quantidade

        for week_index, week in known_weeks.iterrows():
            week_start_str = week["week_start"]
            qty_consumed = consumption_by_week.get((pid, week_start_str), 0)

            # 1) processa PRIMEIRO os movimentos da própria semana: chegada
            #    agendada para esta semana (se houver) e o consumo da semana.
            arrival_qty = pending_arrivals.pop(week_index, 0)
            on_hand = max(0.0, on_hand - qty_consumed + arrival_qty)

            # 2) só ENTÃO registra o snapshot de fechamento da semana —
            #    em_transito = pedidos ainda em aberto após este fechamento.
            in_transit = sum(
                q for arrival_week, q in pending_arrivals.items() if arrival_week > week_index
            )

            rows.append(
                {
                    "snapshot_date": week["week_end"],
                    "product_id": pid,
                    "on_hand": max(0, round(on_hand)),
                    "in_transit": max(0, round(in_transit)),
                }
            )

            # 3) só depois de fechar a semana é que avaliamos se é preciso
            #    disparar um novo pedido (usa o on_hand JÁ atualizado).
            if on_hand < reorder_point and not any(
                aw > week_index for aw in pending_arrivals
            ):
                arrival_week = week_index + lead_time_weeks
                pending_arrivals[arrival_week] = order_size

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# EXECUÇÃO PRINCIPAL
# --------------------------------------------------------------------------
def main() -> None:
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

    calendar = build_calendar()
    products = build_products()
    profiles = assign_demand_profiles(products)
    consumption = build_consumption(products, calendar, profiles)
    inventory = build_inventory_snapshot(products, calendar, consumption, profiles)

    calendar.to_csv(DATA_RAW_DIR / "calendar.csv", index=False)
    products.to_csv(DATA_RAW_DIR / "products.csv", index=False)
    consumption.to_csv(DATA_RAW_DIR / "consumption.csv", index=False)
    inventory.to_csv(DATA_RAW_DIR / "inventory_snapshot.csv", index=False)

    print(f"[OK] calendar.csv            -> {len(calendar)} semanas")
    print(f"[OK] products.csv            -> {len(products)} SKUs")
    print(f"[OK] consumption.csv         -> {len(consumption)} transações")
    print(f"[OK] inventory_snapshot.csv  -> {len(inventory)} registros")


if __name__ == "__main__":
    main()
