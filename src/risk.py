"""
Project FORESIGHT - stockout / overstock risk scoring (D8 methodology, D4 deliverable)

Combines the demand forecast with the current inventory position to score,
for every SKU:
  - stockout risk  (will projected stock fall below a safety level over lead time?)
  - overstock risk (is on-hand stock far more than forecast demand will use?)
  - a recommended action + rupee value at stake

Usage:
    python src/risk.py
Reads data/processed/{analysis_ready_weekly,forecast_output}.csv
Writes data/processed/risk_scores.csv and reports/risk_summary.md
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"

OVERSTOCK_WEEKS_COVER = 8   # holding more than this many weeks of forecast demand = overstocked
SAFETY_MULT = 1.15          # safety buffer over lead-time demand before flagging stockout


def latest_position(wk: pd.DataFrame) -> pd.DataFrame:
    cols = ["sku_id", "category", "subcategory", "on_hand_units", "on_order_units",
            "lead_time_days", "reorder_point", "unit_cost", "list_price"]
    return wk.sort_values("week_start").groupby("sku_id").tail(1)[cols].reset_index(drop=True)


def score(wk: pd.DataFrame, forecast: pd.DataFrame) -> pd.DataFrame:
    pos = latest_position(wk)
    horizon_demand = forecast.groupby("sku_id")["forecast"].sum().rename("forecast_horizon_demand")
    horizon_upper = forecast.groupby("sku_id")["upper_80"].sum().rename("forecast_horizon_upper")
    avg_weekly_fc = forecast.groupby("sku_id")["forecast"].mean().rename("avg_weekly_forecast")

    df = pos.merge(horizon_demand, on="sku_id").merge(horizon_upper, on="sku_id").merge(avg_weekly_fc, on="sku_id")

    df["lead_time_weeks"] = df["lead_time_days"] / 7
    df["lead_time_demand"] = df["avg_weekly_forecast"] * df["lead_time_weeks"] * SAFETY_MULT
    df["available_stock"] = df["on_hand_units"] + df["on_order_units"]

    df["stockout_gap"] = df["lead_time_demand"] - df["available_stock"]
    df["stockout_risk"] = (df["stockout_gap"] / df["lead_time_demand"].replace(0, np.nan)).clip(0, 1).fillna(0)

    cover_weeks_demand = df["avg_weekly_forecast"] * OVERSTOCK_WEEKS_COVER
    df["overstock_excess"] = df["on_hand_units"] - cover_weeks_demand
    df["overstock_risk"] = (df["overstock_excess"] / cover_weeks_demand.replace(0, np.nan)).clip(0, 1).fillna(0)
    # SKUs with near-zero forecast demand and meaningful on-hand stock are maximally overstocked
    df.loc[(df["avg_weekly_forecast"] < 0.5) & (df["on_hand_units"] > 5), "overstock_risk"] = 1.0

    def quadrant(row):
        so, ov = row["stockout_risk"] >= 0.5, row["overstock_risk"] >= 0.5
        if so and ov:
            return "Watch / Volatile"
        if so:
            return "Reorder Now"
        if ov:
            return "Markdown / Clear"
        return "Healthy"

    df["quadrant"] = df.apply(quadrant, axis=1)

    action_map = {
        "Reorder Now": "Raise a replenishment order before stock runs out.",
        "Markdown / Clear": "Promote or discount to free up capital.",
        "Watch / Volatile": "Investigate — demand is erratic; review manually.",
        "Healthy": "No action needed; leave as is.",
    }
    df["recommended_action"] = df["quadrant"].map(action_map)

    # rupee value at stake
    df["sales_at_risk_inr"] = np.where(
        df["quadrant"].isin(["Reorder Now", "Watch / Volatile"]),
        np.clip(df["stockout_gap"], 0, None) * df["list_price"],
        0.0,
    )
    df["capital_locked_inr"] = np.where(
        df["quadrant"].isin(["Markdown / Clear", "Watch / Volatile"]),
        np.clip(df["overstock_excess"], 0, None) * df["unit_cost"],
        0.0,
    )
    df["revenue_at_stake_inr"] = df["sales_at_risk_inr"] + df["capital_locked_inr"]

    return df.sort_values("revenue_at_stake_inr", ascending=False).reset_index(drop=True)


def write_summary(df: pd.DataFrame):
    counts = df["quadrant"].value_counts()
    total_sales_risk = df["sales_at_risk_inr"].sum()
    total_capital_locked = df["capital_locked_inr"].sum()
    top5 = df.head(5)[["sku_id", "category", "quadrant", "revenue_at_stake_inr", "recommended_action"]]

    lines = [
        "# Risk Scoring Summary — Project FORESIGHT",
        "",
        "## SKU counts by quadrant",
        "",
        "| Quadrant | SKUs | Meaning |",
        "|---|---|---|",
        f"| Reorder Now | {counts.get('Reorder Now', 0)} | High stockout risk, low overstock |",
        f"| Markdown / Clear | {counts.get('Markdown / Clear', 0)} | High overstock, low stockout risk |",
        f"| Watch / Volatile | {counts.get('Watch / Volatile', 0)} | High risk on both — investigate |",
        f"| Healthy | {counts.get('Healthy', 0)} | Low risk on both — no action |",
        "",
        "## Business impact",
        "",
        f"- **Sales at risk from stockouts (next {6} weeks):** ₹{total_sales_risk:,.0f}",
        f"- **Capital locked in overstock:** ₹{total_capital_locked:,.0f}",
        f"- **Total revenue at stake:** ₹{(total_sales_risk + total_capital_locked):,.0f}",
        "",
        "## Top 5 SKUs by rupee value at stake",
        "",
        top5.to_markdown(index=False, floatfmt=".0f"),
    ]
    with open(REPORTS / "risk_summary.md", "w") as f:
        f.write("\n".join(lines))


def plot_decisioning_grid(df: pd.DataFrame):
    colors = {
        "Reorder Now": "#D64545", "Watch / Volatile": "#E0A526",
        "Healthy": "#2E9E5B", "Markdown / Clear": "#5C6BC0",
    }
    fig, ax = plt.subplots(figsize=(7, 6))
    for quad, sub in df.groupby("quadrant"):
        size = 30 + 400 * (sub["revenue_at_stake_inr"] / df["revenue_at_stake_inr"].replace(0, np.nan).max().clip(min=1))
        ax.scatter(sub["overstock_risk"], sub["stockout_risk"], s=size.fillna(30), alpha=0.7,
                   color=colors.get(quad, "#888"), label=quad, edgecolor="white", linewidth=0.5)
    ax.axvline(0.5, color="grey", linestyle="--", linewidth=1)
    ax.axhline(0.5, color="grey", linestyle="--", linewidth=1)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("Overstock risk")
    ax.set_ylabel("Stockout risk")
    ax.set_title("Decisioning view — every SKU (bubble size = revenue at stake)")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    (REPORTS / "figures").mkdir(exist_ok=True, parents=True)
    fig.savefig(REPORTS / "figures" / "06_decisioning_grid.png", dpi=140)
    plt.close(fig)


def run():
    wk = pd.read_csv(PROCESSED / "analysis_ready_weekly.csv", parse_dates=["week_start"])
    forecast = pd.read_csv(PROCESSED / "forecast_output.csv", parse_dates=["week_start"])
    df = score(wk, forecast)
    df.to_csv(PROCESSED / "risk_scores.csv", index=False)
    write_summary(df)
    plot_decisioning_grid(df)
    print(df["quadrant"].value_counts())
    print(f"Total revenue at stake: INR {df['revenue_at_stake_inr'].sum():,.0f}")
    return df


if __name__ == "__main__":
    run()
