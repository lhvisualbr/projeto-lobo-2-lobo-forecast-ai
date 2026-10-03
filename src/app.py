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

CRITICALITY_LABELS = {
    "HIGH": "ALTA",
    "MEDIUM": "MÉDIA",
    "LOW": "BAIXA",
}

CATEGORY_LABELS = {
    "ABRASIVOS": "ABRASIVOS",
    "CORTE E USINAGEM": "CORTE E USINAGEM",
    "ELETRICA_BATERIAS": "ELÉTRICA E BATERIAS",
    "EPI_CONSUMIVEIS": "EPIs E CONSUMÍVEIS",
    "SOLDAGEM": "SOLDAGEM",
}

METHOD_LABELS = {
    "model": "Modelo de ML",
    "moving_average_4": "Média móvel (4 semanas)",
    "naive": "Último valor observado",
    "seasonal_52": "Sazonal (52 semanas)",
}


def category_label(value):
    return CATEGORY_LABELS.get(str(value), str(value).replace("_", " "))


def criticality_label(value):
    return CRITICALITY_LABELS.get(str(value), str(value))


def priority_label(value):
    return PRIORITY_LABELS.get(str(value), str(value))


def method_label(value):
    return METHOD_LABELS.get(str(value), str(value).replace("_", " "))


def format_decimal_ptbr(value, decimals=2):
    return f"{float(value):.{decimals}f}".replace(".", ",")


def format_percent_ptbr(value, decimals=1):
    return f"{float(value) * 100:.{decimals}f}%".replace(".", ",")


def format_brl(value):
    formatted = f"{float(value):,.0f}".replace(",", ".")
    return f"R$ {formatted}"


def format_date_ptbr(value):
    parsed = pd.to_datetime(value, errors="coerce")

    if pd.isna(parsed):
        return str(value)

    return parsed.strftime("%d/%m/%Y")


def localize_priority_reason(value):
    return (
        str(value)
        .replace("lead time", "prazo de reposição")
        .replace("ETA", "previsão de chegada")
    )


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
    ["Visão Geral", "Previsão", "Estoque", "Qualidade do Modelo", "Dados"],
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
    c1.metric("WAPE do teste (modelo)", format_percent_ptbr(model_row["wape"]))
    c2.metric("MAE do teste", f"{format_decimal_ptbr(model_row['mae'], 1)} un.")
    c3.metric("Viés do teste", f"{format_decimal_ptbr(model_row['bias'], 2)} un.")
    c4.metric("Demanda prevista (4 semanas)", f"{forecast_total:.0f} un.")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("SKUs críticos", int(n_critical))
    c6.metric("SKUs alta prioridade", int(n_high))
    c7.metric("Qtd. sugerida total", int(total_suggested))
    c8.metric("Custo estimado da reposição", format_brl(total_cost))

    if model_row["wape"] < best_baseline_row["wape"]:
        st.success(
            "O modelo de aprendizado de máquina superou o melhor método de referência "
            f"({method_label(best_baseline_row['method'])}, "
            f"WAPE {format_percent_ptbr(best_baseline_row['wape'])}) por margem pequena — "
            f"WAPE {format_percent_ptbr(model_row['wape'])}."
        )
    else:
        st.warning(
            "Na janela de teste utilizada, o melhor método de referência apresentou "
            "desempenho superior ao modelo "
            f"(referência WAPE {format_percent_ptbr(best_baseline_row['wape'])} "
            f"vs. modelo WAPE {format_percent_ptbr(model_row['wape'])})."
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
                &nbsp;|&nbsp; {localize_priority_reason(row['priority_reason'])}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Real x Previsto — teste de um passo à frente (3 SKUs com maior volume)")
    st.caption(
        "Semanas de teste (últimas 8 conhecidas): valor real versus previsão do "
        "modelo, gerada pelo protocolo de um passo à frente "
        "(ver `docs/MODEL_CARD.md`)."
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
        xaxis_title="Semana", yaxis_title="Unidades consumidas",
        legend={"orientation": "h", "y": -0.25},
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
    )
    st.plotly_chart(fig, width="stretch")


# ==========================================================================
# PÁGINA: FORECAST
# ==========================================================================
elif page == "Previsão":
    st.title("Previsão por Produto")

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
    c1.metric("Categoria", category_label(prod_info["category"]))
    c2.metric("Criticidade", criticality_label(prod_info["criticality"]))
    if len(prod_metrics):
        c3.metric(
            "WAPE do modelo (teste)",
            format_percent_ptbr(prod_metrics.iloc[0]["wape"]),
        )

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
        xaxis_title="Semana", yaxis_title="Unidades",
        legend={"orientation": "h", "y": -0.2},
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
        title="Histórico (treino/teste) e previsão futura",
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown("### Previsão para as próximas 4 semanas")

    forecast_display = prod_forecast[
        ["forecast_week", "week_start", "week_end", "forecast_qty"]
    ].copy()

    forecast_display["week_start"] = forecast_display["week_start"].map(
        format_date_ptbr
    )
    forecast_display["week_end"] = forecast_display["week_end"].map(
        format_date_ptbr
    )

    forecast_display = forecast_display.rename(
        columns={
            "forecast_week": "Semana prevista",
            "week_start": "Início da semana",
            "week_end": "Fim da semana",
            "forecast_qty": "Quantidade prevista",
        }
    )

    st.dataframe(
        forecast_display,
        width="stretch",
        hide_index=True,
    )

    summary = data["model_vs_baselines"]

    st.markdown(
        "### Modelo x métodos de referência — teste de um passo à frente (global)"
    )

    st.caption(
        "Mede a capacidade do modelo de acertar UMA semana à frente, sempre "
        "usando o valor real da semana anterior. Não mede a qualidade da "
        "previsão recursiva de 4 semanas mostrada acima — para isso, veja a "
        "validação multihorizonte logo abaixo."
    )

    summary_display = summary[
        ["method", "mae", "wape", "bias"]
    ].sort_values("wape").copy()

    summary_display["method"] = summary_display["method"].map(method_label)
    summary_display["mae"] = summary_display["mae"].map(
        lambda value: format_decimal_ptbr(value, 2)
    )
    summary_display["wape"] = summary_display["wape"].map(format_percent_ptbr)
    summary_display["bias"] = summary_display["bias"].map(
        lambda value: format_decimal_ptbr(value, 2)
    )

    summary_display = summary_display.rename(
        columns={
            "method": "Método",
            "mae": "MAE",
            "wape": "WAPE",
            "bias": "Viés",
        }
    )

    st.dataframe(
        summary_display,
        width="stretch",
        hide_index=True,
    )

    st.markdown("### Validação histórica multihorizonte (H+1 a H+4)")
    backtest_summary = data["backtest_summary"]
    if backtest_summary is None:
        st.info(
            "A validação histórica multihorizonte ainda não foi executada. Rode "
            "`python src/backtest_multihorizon.py` para gerar esta seção — "
            "ela avalia o cenário real de uso (previsão recursiva de 4 "
            "semanas), diferente do teste de um passo à frente acima."
        )
    else:
        st.caption(
            "Mesmo protocolo de origem móvel aplicado ao Random Forest e aos "
            "métodos de referência, avaliando separadamente cada semana de "
            "antecedência da previsão recursiva. "
            "Ver `docs/MODEL_CARD.md` para a metodologia."
        )
        horizons_present = [h for h in ["1", "2", "3", "4"] if h in backtest_summary["horizon"].astype(str).unique()]
        pivot = backtest_summary[backtest_summary["horizon"].astype(str).isin(horizons_present)].pivot(
            index="method", columns="horizon", values="wape"
        )
        pivot.columns = [f"H+{c}" for c in pivot.columns]
        pivot = pivot.sort_values("H+1")

        pivot.index = [method_label(value) for value in pivot.index]
        pivot.index.name = "Método"

        pivot_display = pivot.apply(
            lambda column: column.map(format_percent_ptbr)
        )

        st.dataframe(
            pivot_display,
            width="stretch",
        )

        st.caption(
            "WAPE por horizonte — menor é melhor. "
            "O método com menor erro pode variar conforme o horizonte."
        )


# ==========================================================================
# PÁGINA: ESTOQUE
# ==========================================================================
elif page == "Estoque":
    st.title("Estoque e Reposição")

    repl = data["replenishment"]

    col1, col2, col3 = st.columns(3)
    with col1:
        cat_filter = st.multiselect(
            "Categoria",
            sorted(repl["category"].unique()),
            format_func=category_label,
            placeholder="Selecione uma ou mais opções",
        )

    with col2:
        crit_filter = st.multiselect(
            "Criticidade",
            sorted(repl["criticality"].unique()),
            format_func=criticality_label,
            placeholder="Selecione uma ou mais opções",
        )

    with col3:
        prio_filter = st.multiselect(
            "Prioridade",
            ["CRITICA", "ALTA", "MEDIA", "BAIXA"],
            format_func=priority_label,
            placeholder="Selecione uma ou mais opções",
        )

    filtered = repl.copy()
    if cat_filter:
        filtered = filtered[filtered["category"].isin(cat_filter)]
    if crit_filter:
        filtered = filtered[filtered["criticality"].isin(crit_filter)]
    if prio_filter:
        filtered = filtered[filtered["priority"].isin(prio_filter)]

    st.caption(f"{len(filtered)} de {len(repl)} SKUs exibidos")

    display_cols = [
        "product_id", "product_name", "category", "criticality",
        "forecast_weekly", "forecast_4weeks_total", "lead_time_days",
        "on_hand", "in_transit", "safety_stock", "target_stock",
        "suggested_order", "estimated_replenishment_cost", "priority",
    ]

    display_df = filtered[display_cols].copy()

    display_df["category"] = display_df["category"].map(category_label)
    display_df["criticality"] = display_df["criticality"].map(
        criticality_label
    )
    display_df["priority"] = display_df["priority"].map(priority_label)

    for column in [
        "forecast_weekly",
        "safety_stock",
        "target_stock",
    ]:
        display_df[column] = display_df[column].round(2)

    display_df["estimated_replenishment_cost"] = (
        display_df["estimated_replenishment_cost"].map(format_brl)
    )

    display_df = display_df.rename(
        columns={
            "product_id": "ID do Produto",
            "product_name": "Produto",
            "category": "Categoria",
            "criticality": "Criticidade",
            "forecast_weekly": "Previsão Semanal",
            "forecast_4weeks_total": "Previsão em 4 Semanas",
            "lead_time_days": "Prazo de Reposição (dias)",
            "on_hand": "Estoque Disponível",
            "in_transit": "Em Trânsito",
            "safety_stock": "Estoque de Segurança",
            "target_stock": "Estoque-Alvo",
            "suggested_order": "Reposição Sugerida",
            "estimated_replenishment_cost": "Custo Estimado",
            "priority": "Prioridade",
        }
    )

    priority_colors_display = {
        priority_label(key): value
        for key, value in PRIORITY_COLORS.items()
    }

    def highlight_priority_display(row):
        color = priority_colors_display.get(
            row["Prioridade"],
            "#ffffff",
        )

        return [f"background-color: {color}22"] * len(row)

    st.dataframe(
        display_df.style.apply(
            highlight_priority_display,
            axis=1,
        ),
        width="stretch",
        hide_index=True,
        height=460,
    )

    with st.expander("Ver motivo da prioridade (auditoria completa)"):
        audit_df = filtered[
            [
                "product_id",
                "product_name",
                "priority",
                "priority_reason",
            ]
        ].copy()

        audit_df["priority"] = audit_df["priority"].map(priority_label)
        audit_df["priority_reason"] = audit_df["priority_reason"].map(
            localize_priority_reason
        )

        audit_df = audit_df.rename(
            columns={
                "product_id": "ID do Produto",
                "product_name": "Produto",
                "priority": "Prioridade",
                "priority_reason": "Motivo da Prioridade",
            }
        )

        st.dataframe(
            audit_df,
            width="stretch",
            hide_index=True,
        )


# ==========================================================================
# PÁGINA: QUALIDADE DO MODELO
# ==========================================================================
elif page == "Qualidade do Modelo":
    st.title("Qualidade do Modelo")
    st.caption(
        "Não escondemos onde o modelo erra mais. Os números abaixo são do teste "
        "de um passo à frente — a validação histórica multihorizonte "
        "(uso real, recursivo) está na página Previsão."
    )

    summary = data["model_vs_baselines"].sort_values("wape").copy()
    summary["method_display"] = summary["method"].map(method_label)

    fig = go.Figure(
        go.Bar(
            x=summary["wape"],
            y=summary["method_display"],
            orientation="h",
            marker_color=[
                LOW if method == "model" else ACCENT
                for method in summary["method"]
            ],
        )
    )

    fig.update_layout(
        height=320,
        template="plotly_white",
        xaxis_title="WAPE (menor é melhor)",
        xaxis_tickformat=".0%",
        yaxis_title="Método",
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
    )

    st.plotly_chart(
        fig,
        width="stretch",
    )

    st.markdown("### Erro por categoria (modelo)")

    by_cat = data["model_by_category"].sort_values(
        "wape",
        ascending=False,
    ).copy()

    by_cat["category"] = by_cat["category"].map(category_label)
    by_cat["mae"] = by_cat["mae"].map(
        lambda value: format_decimal_ptbr(value, 2)
    )
    by_cat["wape"] = by_cat["wape"].map(format_percent_ptbr)
    by_cat["bias"] = by_cat["bias"].map(
        lambda value: format_decimal_ptbr(value, 2)
    )

    by_cat = by_cat.rename(
        columns={
            "mae": "MAE",
            "wape": "WAPE",
            "bias": "Viés",
            "n_obs": "Nº de Observações",
            "category": "Categoria",
        }
    )

    st.dataframe(
        by_cat,
        width="stretch",
        hide_index=True,
    )

    st.markdown(
        "### Produtos mais difíceis de prever (maior WAPE)"
    )

    by_prod = (
        data["model_by_product"]
        .sort_values("wape", ascending=False)
        .head(10)
    )

    products = data["products"][
        ["product_id", "product_name", "criticality"]
    ]

    by_prod = by_prod.merge(
        products,
        on="product_id",
        how="left",
    )

    by_prod = by_prod[
        [
            "product_id",
            "product_name",
            "criticality",
            "mae",
            "wape",
            "bias",
        ]
    ].copy()

    by_prod["criticality"] = by_prod["criticality"].map(
        criticality_label
    )
    by_prod["mae"] = by_prod["mae"].map(
        lambda value: format_decimal_ptbr(value, 2)
    )
    by_prod["wape"] = by_prod["wape"].map(format_percent_ptbr)
    by_prod["bias"] = by_prod["bias"].map(
        lambda value: format_decimal_ptbr(value, 2)
    )

    by_prod = by_prod.rename(
        columns={
            "product_id": "ID do Produto",
            "product_name": "Produto",
            "criticality": "Criticidade",
            "mae": "MAE",
            "wape": "WAPE",
            "bias": "Viés",
        }
    )

    st.dataframe(
        by_prod,
        width="stretch",
        hide_index=True,
    )

    st.info(
        "Limitação conhecida: SKUs de baixo giro/intermitentes tendem a ter WAPE "
        "alto (às vezes > 100%) porque poucas unidades de erro já representam um "
        "percentual grande sobre um volume real pequeno. Consulte `docs/LIMITATIONS.md` para mais detalhes."
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
    c3.metric("Semanas futuras (previsão)", len(future_weeks))
    c4.metric("Transações de consumo", f"{len(consumption):,}".replace(",", "."))

    st.caption(
        "Período: "
        f"{format_date_ptbr(known_weeks['week_start'].min())} a "
        f"{format_date_ptbr(known_weeks['week_end'].max())}"
    )

    pct_zero = 100 * (weekly["units_consumed"] == 0).mean()
    st.metric("% de combinações produto-semana com consumo zero", f"{pct_zero:.1f}%")

    st.markdown("### Distribuição por categoria")

    category_distribution = (
        products["category"]
        .value_counts()
        .rename_axis("category")
        .reset_index(name="n_skus")
    )

    category_distribution["category"] = (
        category_distribution["category"].map(category_label)
    )

    category_distribution = category_distribution.rename(
        columns={
            "category": "Categoria",
            "n_skus": "Nº de SKUs",
        }
    )

    st.dataframe(
        category_distribution,
        width="stretch",
        hide_index=True,
    )

    st.markdown("### Distribuição por criticidade")

    criticality_distribution = (
        products["criticality"]
        .value_counts()
        .rename_axis("criticality")
        .reset_index(name="n_skus")
    )

    criticality_distribution["criticality"] = (
        criticality_distribution["criticality"].map(
            criticality_label
        )
    )

    criticality_distribution = criticality_distribution.rename(
        columns={
            "criticality": "Criticidade",
            "n_skus": "Nº de SKUs",
        }
    )

    st.dataframe(
        criticality_distribution,
        width="stretch",
        hide_index=True,
    )

    st.markdown(
        "> Todos os dados utilizados neste projeto são sintéticos e foram "
        "criados exclusivamente para fins educacionais e de portfólio."
    )
