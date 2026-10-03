"""
make_readme_charts.py
Regenera os gráficos estáticos usados no README (images/*.png) a partir
dos artefatos reais do pipeline (data/, results/). Não existia um script
dedicado para isso antes da V1.1 — as imagens eram geradas manualmente,
o que é uma lacuna de reprodutibilidade. Rode depois do pipeline
completo, sempre que os números mudarem (ex.: depois de corrigir um bug
que altera resultados, como aconteceu com o snapshot de estoque na V1.1).

Uso:
    python src/make_readme_charts.py
"""

import matplotlib.pyplot as plt
import pandas as pd

from config import DATA_PROCESSED_DIR, RESULTS_DIR, ROOT_DIR

IMAGES_DIR = ROOT_DIR / "images"

ACCENT = "#3f6fae"
CRITICAL = "#c0392b"
HIGH = "#e67e22"
MEDIUM = "#d4ac0d"
LOW = "#1e8449"

plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})


def chart_eda_consumo_total_semanal():
    weekly = pd.read_csv(DATA_PROCESSED_DIR / "weekly_series.csv")
    total_by_week = weekly.groupby("week_id")["units_consumed"].sum()

    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.plot(total_by_week.index, total_by_week.values, color=ACCENT, linewidth=1.5)
    ax.set_title("Consumo total semanal (todos os SKUs)")
    ax.set_xlabel("Semana (week_id)")
    ax.set_ylabel("Unidades consumidas")
    fig.tight_layout()
    fig.savefig(IMAGES_DIR / "eda_consumo_total_semanal.png", dpi=120)
    plt.close(fig)


def chart_eda_consumo_por_categoria():
    weekly = pd.read_csv(DATA_PROCESSED_DIR / "weekly_series.csv")
    by_category = weekly.groupby("category")["units_consumed"].sum().sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(by_category.index, by_category.values, color=ACCENT)
    ax.set_title("Consumo total por categoria (24 meses)")
    ax.set_xlabel("Unidades consumidas")
    fig.tight_layout()
    fig.savefig(IMAGES_DIR / "eda_consumo_por_categoria.png", dpi=120)
    plt.close(fig)


def chart_model_vs_baselines_wape():
    summary = pd.read_csv(RESULTS_DIR / "onestep_model_vs_baselines.csv").sort_values("wape")
    colors = [LOW if m == "model" else ACCENT for m in summary["method"]]

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.barh(summary["method"], summary["wape"], color=colors)
    ax.set_title("WAPE — modelo x baselines (teste one-step-ahead)")
    ax.set_xlabel("WAPE (menor é melhor)")
    fig.tight_layout()
    fig.savefig(IMAGES_DIR / "model_vs_baselines_wape.png", dpi=120)
    plt.close(fig)


def chart_forecast_4_semanas():
    forecast = pd.read_csv(RESULTS_DIR / "forecast_4weeks.csv")
    totals = forecast.groupby("forecast_week")["forecast_qty"].sum()

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.bar(totals.index, totals.values, color=ACCENT)
    ax.set_title("Demanda total prevista — próximas 4 semanas")
    ax.set_xlabel("Semana futura (H+n)")
    ax.set_ylabel("Unidades previstas")
    ax.set_xticks(totals.index)
    ax.set_xticklabels([f"H+{i}" for i in totals.index])
    fig.tight_layout()
    fig.savefig(IMAGES_DIR / "forecast_4_semanas.png", dpi=120)
    plt.close(fig)


def chart_replenishment_priority():
    repl = pd.read_csv(RESULTS_DIR / "replenishment_suggestions.csv")
    order = ["CRITICA", "ALTA", "MEDIA", "BAIXA"]
    color_map = {"CRITICA": CRITICAL, "ALTA": HIGH, "MEDIA": MEDIUM, "BAIXA": LOW}
    counts = repl["priority"].value_counts().reindex(order).fillna(0).astype(int)

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.bar(counts.index, counts.values, color=[color_map[p] for p in counts.index])
    for i, v in enumerate(counts.values):
        ax.text(i, v + 0.3, str(v), ha="center", fontweight="bold")
    ax.set_title("SKUs por prioridade de reposição")
    ax.set_ylabel("Nº de SKUs")
    fig.tight_layout()
    fig.savefig(IMAGES_DIR / "replenishment_priority.png", dpi=120)
    plt.close(fig)


def main():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    chart_eda_consumo_total_semanal()
    chart_eda_consumo_por_categoria()
    chart_model_vs_baselines_wape()
    chart_forecast_4_semanas()
    chart_replenishment_priority()
    print(f"[OK] 5 gráficos regenerados em {IMAGES_DIR}/")


if __name__ == "__main__":
    main()
