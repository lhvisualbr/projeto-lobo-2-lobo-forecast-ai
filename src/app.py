"""
app.py
Dashboard executivo do Lobo Forecast AI (Streamlit).

Responde rapidamente: "o que precisa de atenção agora?"
Não decide nada — apenas explica o que o pipeline (dados -> forecast ->
reposição) já calculou. A decisão final é sempre humana.
"""

import sqlite3

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import DATA_PROCESSED_DIR, DATABASE_PATH, RESULTS_DIR, ROOT_DIR

st.set_page_config(
    page_title="Lobo Forecast AI",
    page_icon="🐺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------
# Estilo (visual industrial / corporativo / limpo)
# --------------------------------------------------------------------------
PRIMARY = "#1c2b4a"
ACCENT = "#3f6fae"
CRITICAL = "#c0392b"
HIGH = "#e67e22"
MEDIUM = "#d4ac0d"
LOW = "#1e8449"
BG = "#f4f6f9"

st.markdown(
    f"""
    <style>
    .stApp {{ background-color: {BG}; }}
    section[data-testid="stSidebar"] {{ background-color: {PRIMARY}; }}
    section[data-testid="stSidebar"] * {{ color: #f0f2f6 !important; }}
    div[data-testid="stMetric"] {{
        background-color: white;
        border: 1px solid #e2e6ee;
        border-radius: 10px;
        padding: 14px 16px 8px 16px;
    }}
    h1, h2, h3 {{ color: {PRIMARY}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

PRIORITY_COLORS = {"CRITICA": CRITICAL, "ALTA": HIGH, "MEDIA": MEDIUM, "BAIXA": LOW}
PRIORITY_LABELS = {"CRITICA": "CRÍTICA", "ALTA": "ALTA", "MEDIA": "MÉDIA", "BAIXA": "BAIXA"}


# --------------------------------------------------------------------------
# Carga de dados (cache para não reler a cada interação)
# --------------------------------------------------------------------------
REQUIRED_FILES = {
    DATABASE_PATH: "python src/generate_data.py && python src/database.py",
    DATA_PROCESSED_DIR / "weekly_series.csv": "python src/data_prep.py",
    RESULTS_DIR / "onestep_model_vs_baselines.csv": "python src/run_evaluation.py",
    RESULTS_DIR / "onestep_by_category.csv": "python src/run_evaluation.py",
    RESULTS_DIR / "onestep_by_product.csv": "python src/run_evaluation.py",
    RESULTS_DIR / "onestep_test_predictions.csv": "python src/run_evaluation.py",
    RESULTS_DIR / "forecast_4weeks.csv": "python src/forecast.py",
    RESULTS_DIR / "replenishment_suggestions.csv": "python src/replenishment.py",
}
# o backtest multi-horizon é opcional no dashboard (página funciona sem ele,
# só omite a seção correspondente) — ver load_all().
BACKTEST_SUMMARY_PATH = RESULTS_DIR / "backtest_multihorizon_summary.csv"


def _check_required_files():
    missing = [(path, cmd) for path, cmd in REQUIRED_FILES.items() if not path.exists()]
    if missing:
        st.error(
            "### Dashboard não pode iniciar — faltam artefatos do pipeline\n\n"
            "Os seguintes arquivos ainda não foram gerados. Execute os comandos "
            "abaixo (na raiz do projeto, com o ambiente virtual ativo) e recarregue "
            "esta página:\n\n"
            + "\n".join(f"- `{path.relative_to(ROOT_DIR)}` → `{cmd}`" for path, cmd in missing)
        )
        st.stop()


@st.cache_data
def load_all():
    conn = sqlite3.connect(DATABASE_PATH)
    products = pd.read_sql("SELECT * FROM products", conn)
    calendar = pd.read_sql("SELECT * FROM calendar", conn)
    consumption = pd.read_sql("SELECT * FROM consumption", conn)
    inventory = pd.read_sql("SELECT * FROM inventory_snapshot", conn)
    conn.close()

    weekly = pd.read_csv(DATA_PROCESSED_DIR / "weekly_series.csv")
    onestep_summary = pd.read_csv(RESULTS_DIR / "onestep_model_vs_baselines.csv")
    onestep_by_category = pd.read_csv(RESULTS_DIR / "onestep_by_category.csv")
    onestep_by_product = pd.read_csv(RESULTS_DIR / "onestep_by_product.csv")
    onestep_test_predictions = pd.read_csv(RESULTS_DIR / "onestep_test_predictions.csv")
    forecast = pd.read_csv(RESULTS_DIR / "forecast_4weeks.csv")
    replenishment = pd.read_csv(RESULTS_DIR / "replenishment_suggestions.csv")

    # backtest multi-horizon é opcional: se ainda não rodou, o dashboard
    # segue funcionando e só omite a seção correspondente (não quebra).
    backtest_summary = (
        pd.read_csv(BACKTEST_SUMMARY_PATH) if BACKTEST_SUMMARY_PATH.exists() else None
    )

    return {
        "products": products, "calendar": calendar, "consumption": consumption,
        "inventory": inventory, "weekly": weekly,
        "model_vs_baselines": onestep_summary,
        "model_by_category": onestep_by_category,
        "model_by_product": onestep_by_product,
        "test_predictions": onestep_test_predictions,
        "backtest_summary": backtest_summary,
        "forecast": forecast, "replenishment": replenishment,
    }


_check_required_files()
try:
    data = load_all()
except Exception as exc:  # noqa: BLE001 — última linha de defesa contra traceback cru na tela
    st.error(
        "### Não foi possível carregar os dados do dashboard\n\n"
        f"Erro técnico: `{exc}`\n\n"
        "Isso costuma acontecer quando um artefato do pipeline está incompleto "
        "ou corrompido. Tente reexecutar o pipeline do zero (ver `README.md`, "
        "seção \"Como rodar\") e recarregue esta página."
    )
    st.stop()

st.sidebar.markdown("# 🐺 Lobo Forecast AI")
st.sidebar.caption("Previsão de Consumo e Reposição Industrial")
page = st.sidebar.radio(
    "Navegação",
    ["Visão Geral", "Forecast", "Estoque", "Qualidade do Modelo", "Dados"],
    label_visibility="collapsed",
)
st.sidebar.markdown("---")
st.sidebar.caption(
    "Todos os dados são sintéticos e fictícios, criados exclusivamente "
    "para fins educacionais e de portfólio."
)
st.sidebar.caption("O modelo prevê. A regra calcula. O dashboard explica. "
                    "A pessoa responsável decide.")


# ==========================================================================
# PÁGINA: VISÃO GERAL
# ==========================================================================
if page == "Visão Geral":
    st.title("Visão Geral")
    st.caption("O que precisa de atenção agora?")

    summary = data["model_vs_baselines"]
    model_row = summary[summary["method"] == "model"].iloc[0]
    best_baseline_row = summary[summary["method"] != "model"].sort_values("wape").iloc[0]

    repl = data["replenishment"]
    forecast_total = data["forecast"]["forecast_qty"].sum()
    n_critical = (repl["priority"] == "CRITICA").sum()
    n_high = (repl["priority"] == "ALTA").sum()
    total_suggested = repl["suggested_order"].sum()
    total_cost = repl["estimated_replenishment_cost"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("WAPE do teste (modelo)", f"{model_row['wape']:.1%}")
    c2.metric("MAE do teste", f"{model_row['mae']:.1f} un.")
    c3.metric("Viés do teste", f"{model_row['bias']:+.2f} un.")
    c4.metric("Demanda prevista (4 semanas)", f"{forecast_total:.0f} un.")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("SKUs críticos", int(n_critical))
    c6.metric("SKUs alta prioridade", int(n_high))
    c7.metric("Qtd. sugerida total", int(total_suggested))
    c8.metric("Custo estimado da reposição", f"R$ {total_cost:,.0f}")

    if model_row["wape"] < best_baseline_row["wape"]:
        st.success(
            f"O modelo de ML superou a melhor baseline "
            f"({best_baseline_row['method']}, WAPE {best_baseline_row['wape']:.1%}) "
            f"por margem pequena — WAPE {model_row['wape']:.1%}."
        )
    else:
        st.warning(
            "Na janela de teste utilizada, a baseline apresentou desempenho "
            f"superior ao modelo (baseline WAPE {best_baseline_row['wape']:.1%} "
            f"vs. modelo WAPE {model_row['wape']:.1%})."
        )

    st.markdown("### Materiais prioritários")
    priority_order = ["CRITICA", "ALTA", "MEDIA", "BAIXA"]
    top_priority = repl[repl["priority"].isin(["CRITICA", "ALTA", "MEDIA"])].copy()
    top_priority["priority"] = pd.Categorical(top_priority["priority"], priority_order, ordered=True)
    top_priority = top_priority.sort_values(["priority", "estimated_replenishment_cost"], ascending=[True, False])

    for _, row in top_priority.head(10).iterrows():
        color = PRIORITY_COLORS[row["priority"]]
        label = PRIORITY_LABELS[row["priority"]]
        st.markdown(
            f"""
            <div style="border-left: 5px solid {color}; background:white;
                        padding:10px 14px; margin-bottom:6px; border-radius:6px;">
                <b>{label}</b> — {row['product_name']} ({row['product_id']})
                &nbsp;|&nbsp; sugestão: <b>{int(row['suggested_order'])} un.</b>
                &nbsp;|&nbsp; {row['priority_reason']}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Real x Previsto — teste one-step-ahead (top 3 SKUs por volume)")
    st.caption(
        "Semanas de teste (últimas 8 conhecidas): valor real vs. previsão do "
        "modelo, gerada com o protocolo one-step-ahead (ver `docs/MODEL_CARD.md`)."
    )
    test_preds = data["test_predictions"]
    top_products = test_preds.groupby("product_id")["actual"].sum().sort_values(ascending=False).head(3).index

    fig = go.Figure()
    palette = [ACCENT, HIGH, LOW]
    for i, pid in enumerate(top_products):
        prod_test = test_preds[test_preds["product_id"] == pid].sort_values("week_id")
        color = palette[i % len(palette)]
        fig.add_trace(go.Scatter(
            x=prod_test["week_id"], y=prod_test["actual"],
            mode="lines+markers", name=f"{pid} — real",
            line={"width": 2, "color": color},
        ))
        fig.add_trace(go.Scatter(
            x=prod_test["week_id"], y=prod_test["pred_model"],
            mode="lines+markers", name=f"{pid} — previsto",
            line={"width": 2, "color": color, "dash": "dash"},
        ))
    fig.update_layout(
        height=380, template="plotly_white",
        xaxis_title="Semana (week_id)", yaxis_title="Unidades consumidas",
        legend={"orientation": "h", "y": -0.25},
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
    )
    st.plotly_chart(fig, use_container_width=True)


# ==========================================================================
# PÁGINA: FORECAST
# ==========================================================================
elif page == "Forecast":
    st.title("Forecast por Produto")

    products = data["products"]
    weekly = data["weekly"]
    forecast = data["forecast"]
    by_product = data["model_by_product"]

    product_options = products["product_id"] + " — " + products["product_name"]
    selected = st.selectbox("Escolha um produto", product_options, index=0)
    pid = selected.split(" — ")[0]

    prod_info = products[products["product_id"] == pid].iloc[0]
    prod_hist = weekly[weekly["product_id"] == pid].sort_values("week_id")
    prod_forecast = forecast[forecast["product_id"] == pid].sort_values("forecast_week")
    prod_metrics = by_product[by_product["product_id"] == pid]

    c1, c2, c3 = st.columns(3)
    c1.metric("Categoria", prod_info["category"])
    c2.metric("Criticidade", prod_info["criticality"])
    if len(prod_metrics):
        c3.metric("WAPE do modelo (teste)", f"{prod_metrics.iloc[0]['wape']:.1%}")

    test_weeks = 8
    max_known_week = prod_hist["week_id"].max()
    train_part = prod_hist[prod_hist["week_id"] < max_known_week - test_weeks + 1]
    test_part = prod_hist[prod_hist["week_id"] >= max_known_week - test_weeks + 1]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=train_part["week_id"], y=train_part["units_consumed"],
        mode="lines", name="TREINO", line={"color": ACCENT, "width": 2},
    ))
    fig.add_trace(go.Scatter(
        x=test_part["week_id"], y=test_part["units_consumed"],
        mode="lines+markers", name="TESTE (real)", line={"color": PRIMARY, "width": 2},
    ))
    future_x = prod_forecast["forecast_week"] + max_known_week
    fig.add_trace(go.Scatter(
        x=future_x, y=prod_forecast["forecast_qty"],
        mode="lines+markers", name="FUTURO (previsto)",
        line={"color": HIGH, "width": 2, "dash": "dash"},
    ))
    fig.update_layout(
        height=420, template="plotly_white",
        xaxis_title="Semana (week_id)", yaxis_title="Unidades",
        legend={"orientation": "h", "y": -0.2},
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        title="Histórico (treino/teste) e forecast futuro",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Previsão para as próximas 4 semanas")
    st.dataframe(
        prod_forecast[["forecast_week", "week_start", "week_end", "forecast_qty"]],
        use_container_width=True, hide_index=True,
    )

    summary = data["model_vs_baselines"]
    st.markdown("### Modelo x baselines — teste one-step-ahead (global)")
    st.caption(
        "Mede a capacidade do modelo de acertar UMA semana à frente, sempre "
        "usando o valor real da semana anterior. Não mede a qualidade do "
        "forecast recursivo de 4 semanas mostrado acima — para isso, veja o "
        "backtest multi-horizon logo abaixo."
    )
    st.dataframe(
        summary[["method", "mae", "wape", "bias"]].sort_values("wape").round(3),
        use_container_width=True, hide_index=True,
    )

    st.markdown("### Backtest multi-horizon (rolling-origin, H+1 a H+4)")
    backtest_summary = data["backtest_summary"]
    if backtest_summary is None:
        st.info(
            "Backtest multi-horizon ainda não foi executado. Rode "
            "`python src/backtest_multihorizon.py` para gerar esta seção — "
            "ela avalia o cenário real de uso (forecast recursivo de 4 "
            "semanas), diferente do teste one-step-ahead acima."
        )
    else:
        st.caption(
            "Mesmo protocolo (rolling-origin) aplicado a Random Forest e às "
            "baselines, avaliando separadamente cada semana de antecedência "
            "da previsão recursiva. Ver docs/MODEL_CARD.md para metodologia."
        )
        horizons_present = [h for h in ["1", "2", "3", "4"] if h in backtest_summary["horizon"].astype(str).unique()]
        pivot = backtest_summary[backtest_summary["horizon"].astype(str).isin(horizons_present)].pivot(
            index="method", columns="horizon", values="wape"
        )
        pivot.columns = [f"H+{c}" for c in pivot.columns]
        pivot = pivot.round(3).sort_values("H+1")
        st.dataframe(pivot, use_container_width=True)
        st.caption("WAPE por horizonte — menor é melhor. Vencedor pode variar por horizonte.")


# ==========================================================================
# PÁGINA: ESTOQUE
# ==========================================================================
elif page == "Estoque":
    st.title("Estoque e Reposição")

    repl = data["replenishment"]

    col1, col2, col3 = st.columns(3)
    with col1:
        cat_filter = st.multiselect("Categoria", sorted(repl["category"].unique()))
    with col2:
        crit_filter = st.multiselect("Criticidade", sorted(repl["criticality"].unique()))
    with col3:
        prio_filter = st.multiselect("Prioridade", ["CRITICA", "ALTA", "MEDIA", "BAIXA"])

    filtered = repl.copy()
    if cat_filter:
        filtered = filtered[filtered["category"].isin(cat_filter)]
    if crit_filter:
        filtered = filtered[filtered["criticality"].isin(crit_filter)]
    if prio_filter:
        filtered = filtered[filtered["priority"].isin(prio_filter)]

    st.caption(f"{len(filtered)} de {len(repl)} SKUs exibidos")

    def highlight_priority(row):
        color = PRIORITY_COLORS.get(row["priority"], "#ffffff")
        return [f"background-color: {color}22"] * len(row)

    display_cols = [
        "product_id", "product_name", "category", "criticality",
        "forecast_weekly", "forecast_4weeks_total", "lead_time_days",
        "on_hand", "in_transit", "safety_stock", "target_stock",
        "suggested_order", "estimated_replenishment_cost", "priority",
    ]
    st.dataframe(
        filtered[display_cols].style.apply(highlight_priority, axis=1),
        use_container_width=True, hide_index=True, height=460,
    )

    with st.expander("Ver razão da prioridade (auditoria completa)"):
        st.dataframe(
            filtered[["product_id", "product_name", "priority", "priority_reason"]],
            use_container_width=True, hide_index=True,
        )


# ==========================================================================
# PÁGINA: QUALIDADE DO MODELO
# ==========================================================================
elif page == "Qualidade do Modelo":
    st.title("Qualidade do Modelo")
    st.caption(
        "Não escondemos onde o modelo erra mais. Números abaixo são do teste "
        "one-step-ahead — o backtest multi-horizon (uso real, recursivo) está "
        "na página Forecast."
    )

    summary = data["model_vs_baselines"].sort_values("wape")
    fig = go.Figure(go.Bar(
        x=summary["wape"], y=summary["method"], orientation="h",
        marker_color=[LOW if m == "model" else ACCENT for m in summary["method"]],
    ))
    fig.update_layout(
        height=320, template="plotly_white",
        xaxis_title="WAPE (menor é melhor)",
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Erro por categoria (modelo)")
    by_cat = data["model_by_category"].sort_values("wape", ascending=False)
    st.dataframe(by_cat.round(3), use_container_width=True, hide_index=True)

    st.markdown("### Produtos mais difíceis de prever (maior WAPE)")
    by_prod = data["model_by_product"].sort_values("wape", ascending=False).head(10)
    products = data["products"][["product_id", "product_name", "criticality"]]
    by_prod = by_prod.merge(products, on="product_id", how="left")
    st.dataframe(
        by_prod[["product_id", "product_name", "criticality", "mae", "wape", "bias"]].round(3),
        use_container_width=True, hide_index=True,
    )

    st.info(
        "Limitação conhecida: SKUs de baixo giro/intermitentes tendem a ter WAPE "
        "alto (às vezes > 100%) porque poucas unidades de erro já representam um "
        "percentual grande sobre um volume real pequeno. Ver `docs/LIMITATIONS.md`."
    )


# ==========================================================================
# PÁGINA: DADOS
# ==========================================================================
elif page == "Dados":
    st.title("Sobre os Dados")

    products = data["products"]
    calendar = data["calendar"]
    consumption = data["consumption"]
    weekly = data["weekly"]

    known_weeks = calendar[calendar["is_known"] == 1]
    future_weeks = calendar[calendar["is_known"] == 0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("SKUs", len(products))
    c2.metric("Semanas conhecidas", len(known_weeks))
    c3.metric("Semanas futuras (forecast)", len(future_weeks))
    c4.metric("Transações de consumo", f"{len(consumption):,}".replace(",", "."))

    st.caption(
        f"Período: {known_weeks['week_start'].min()} a {known_weeks['week_end'].max()}"
    )

    pct_zero = 100 * (weekly["units_consumed"] == 0).mean()
    st.metric("% de combinações produto-semana com consumo zero", f"{pct_zero:.1f}%")

    st.markdown("### Distribuição por categoria")
    st.dataframe(
        products["category"].value_counts().rename_axis("category").reset_index(name="n_skus"),
        use_container_width=True, hide_index=True,
    )

    st.markdown("### Distribuição por criticidade")
    st.dataframe(
        products["criticality"].value_counts().rename_axis("criticality").reset_index(name="n_skus"),
        use_container_width=True, hide_index=True,
    )

    st.markdown(
        "> Todos os dados utilizados neste projeto são sintéticos e foram "
        "criados exclusivamente para fins educacionais e de portfólio."
    )
