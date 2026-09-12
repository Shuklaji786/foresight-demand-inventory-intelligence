from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

st.set_page_config(page_title="FORESIGHT — NorthBay Living Planning Dashboard", layout="wide")


@st.cache_data
def load_data():
    wk = pd.read_csv(PROCESSED / "analysis_ready_weekly.csv", parse_dates=["week_start"])
    forecast = pd.read_csv(PROCESSED / "forecast_output.csv", parse_dates=["week_start"])
    risk = pd.read_csv(PROCESSED / "risk_scores.csv")
    return wk, forecast, risk


def empty_state(message: str):
    st.info(message)


try:
    wk, forecast, risk = load_data()
except FileNotFoundError:
    st.error(
        "No processed data found. Run the pipeline first:\n\n"
        "```\npython src/pipeline.py\npython src/forecast.py\npython src/risk.py\n```"
    )
    st.stop()

st.title("📦 FORESIGHT — Demand & Inventory Planning Dashboard")
st.caption("NorthBay Living · Client Engagement · Zidio Development")

# ---------------------------------------------------------------- sidebar filters
st.sidebar.header("Filters")
categories = ["All"] + sorted(risk["category"].unique().tolist())
category = st.sidebar.selectbox("Category", categories)

filtered_risk = risk if category == "All" else risk[risk["category"] == category]
sku_options = sorted(filtered_risk["sku_id"].unique().tolist())

if not sku_options:
    empty_state("No SKUs match this filter yet.")
    st.stop()

selected_sku = st.sidebar.selectbox("SKU (for the forecast chart)", sku_options)
quadrant_filter = st.sidebar.multiselect(
    "Risk quadrant", options=sorted(risk["quadrant"].unique()),
    default=sorted(risk["quadrant"].unique()),
)

# ---------------------------------------------------------------- top KPIs
c1, c2, c3, c4 = st.columns(4)
c1.metric("SKUs tracked", f"{risk['sku_id'].nunique()}")
c2.metric("Sales at risk (stockouts)", f"₹{risk['sales_at_risk_inr'].sum():,.0f}")
c3.metric("Capital locked (overstock)", f"₹{risk['capital_locked_inr'].sum():,.0f}")
c4.metric("SKUs needing action", f"{(risk['quadrant'] != 'Healthy').sum()}")

st.divider()

# ---------------------------------------------------------------- decisioning grid
left, right = st.columns([3, 2])
with left:
    st.subheader("Decisioning grid — every SKU")
    grid_df = filtered_risk[filtered_risk["quadrant"].isin(quadrant_filter)]
    if grid_df.empty:
        empty_state("No SKUs match the selected quadrant filter.")
    else:
        fig = px.scatter(
            grid_df, x="overstock_risk", y="stockout_risk", color="quadrant",
            size="revenue_at_stake_inr", hover_name="sku_id",
            hover_data={"category": True, "recommended_action": True, "revenue_at_stake_inr": ":,.0f"},
            color_discrete_map={
                "Reorder Now": "#D64545", "Watch / Volatile": "#E0A526",
                "Healthy": "#2E9E5B", "Markdown / Clear": "#5C6BC0",
            },
        )
        fig.add_vline(x=0.5, line_dash="dash", line_color="grey")
        fig.add_hline(y=0.5, line_dash="dash", line_color="grey")
        fig.update_layout(xaxis_range=[-0.02, 1.02], yaxis_range=[-0.02, 1.02], height=450)
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Prioritised action list")
    action_list = filtered_risk[filtered_risk["quadrant"] != "Healthy"].sort_values(
        "revenue_at_stake_inr", ascending=False
    )[["sku_id", "quadrant", "recommended_action", "revenue_at_stake_inr"]]
    if action_list.empty:
        empty_state("Nothing needs action for this filter — all SKUs are healthy.")
    else:
        st.dataframe(
            action_list.rename(columns={
                "sku_id": "SKU", "quadrant": "Status",
                "recommended_action": "Action", "revenue_at_stake_inr": "₹ at stake",
            }),
            use_container_width=True, hide_index=True, height=420,
        )

st.divider()

# ---------------------------------------------------------------- forecast vs actual
st.subheader(f"Forecast vs actual — {selected_sku}")
hist = wk[wk["sku_id"] == selected_sku].sort_values("week_start")
fc = forecast[forecast["sku_id"] == selected_sku].sort_values("week_start")

if hist.empty:
    empty_state("No sales history for this SKU yet.")
else:
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=hist["week_start"], y=hist["units_sold"], name="Actual demand", mode="lines"))
    if not fc.empty:
        fig2.add_trace(go.Scatter(x=fc["week_start"], y=fc["forecast"], name="Forecast", mode="lines"))
        fig2.add_trace(go.Scatter(
            x=pd.concat([fc["week_start"], fc["week_start"][::-1]]),
            y=pd.concat([fc["upper_80"], fc["lower_80"][::-1]]),
            fill="toself", fillcolor="rgba(76,76,255,0.15)", line=dict(color="rgba(0,0,0,0)"),
            name='80% interval', showlegend=True,
        ))
    fig2.update_layout(height=380, xaxis_title="Week", yaxis_title="Units")
    st.plotly_chart(fig2, use_container_width=True)

sku_risk = risk[risk["sku_id"] == selected_sku]
if not sku_risk.empty:
    r = sku_risk.iloc[0]
    st.write(
        f"**Status:** {r["quadrant"]} · **Recommended action:** {r['recommended_action']} · "
        f"**Revenue at stake:** ₹{r['revenue_at_stake_inr']:,.0f}"
    )

st.caption("Data refreshes when you re-run `python src/pipeline.py && python src/forecast.py && python src/risk.py`.")
