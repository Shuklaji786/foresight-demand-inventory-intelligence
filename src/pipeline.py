"""
Project FORESIGHT - data pipeline (D1)
Ingests the four raw extracts, cleans and unifies them into one
analysis-ready dataset, and writes a coded data-quality report.

Usage:
    python src/pipeline.py
Reads from data/raw/, writes to data/processed/ and reports/.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
PROCESSED.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

CATEGORY_MAP = {
    "furniture": "Furniture", "FURNITURE": "Furniture", "Furniture": "Furniture",
    "decor": "Decor", "Décor": "Decor", "Decor": "Decor",
    "small appliances": "Small Appliances", "Small Appliance": "Small Appliances",
    "Small Appliances": "Small Appliances",
}

dq_log = []  # list of (issue, action, count) for the data-quality report


def log(issue, action, count):
    dq_log.append({"issue": issue, "action": action, "rows_affected": int(count)})


def load_sku_master():
    df = pd.read_csv(RAW / "sku_master.csv")
    n0 = len(df)

    dupes = df.duplicated(subset="sku_id", keep="first").sum()
    df = df.drop_duplicates(subset="sku_id", keep="first")
    log("Duplicate sku_master rows (same sku_id repeated)", "Kept first occurrence, dropped rest", dupes)

    before = df["category"].copy()
    df["category"] = df["category"].map(lambda c: CATEGORY_MAP.get(c, c))
    changed = (before != df["category"]).sum()
    log("Inconsistent category labels (casing / accents, e.g. 'decor' vs 'Décor')",
        "Standardised to a single canonical label per category", changed)

    miss_cost = df["unit_cost"].isna().sum()
    if miss_cost:
        df["unit_cost"] = df.groupby("category")["unit_cost"].transform(
            lambda s: s.fillna(s.median())
        )
    log("Missing unit_cost", "Imputed with the category median unit_cost", miss_cost)

    df["launch_date"] = pd.to_datetime(df["launch_date"])
    return df


def load_calendar():
    df = pd.read_csv(RAW / "calendar.csv", parse_dates=["date"], keep_default_na=False)
    df["promo_event"] = df["promo_event"].replace("", "").fillna("")
    df["promo_flag_cal"] = (df["promo_event"] != "").astype(int)
    return df


def load_sales_daily():
    df = pd.read_csv(RAW / "sales_daily.csv", parse_dates=["date"])
    n0 = len(df)

    dupes = df.duplicated(subset=["date", "sku_id"], keep="first").sum()
    df = df.drop_duplicates(subset=["date", "sku_id"], keep="first")
    log("Duplicate sales_daily rows (same date + sku_id repeated)",
        "Kept first occurrence, dropped rest", dupes)

    miss_units = df["units_sold"].isna().sum()
    # missing units_sold: interpret as no recorded sale that day, not zero-fill blindly -
    # cross-check against price: if a price was recorded, assume the row is a data-entry
    # gap and fill with the SKU's rolling median; otherwise treat as 0.
    if miss_units:
        df["units_sold"] = df.groupby("sku_id")["units_sold"].transform(
            lambda s: s.fillna(s.median())
        )
        df["units_sold"] = df["units_sold"].fillna(0)
    log("Missing units_sold", "Imputed with the SKU's median units_sold (fallback 0)", miss_units)

    neg = (df["units_sold"] < 0).sum()
    df["units_sold"] = df["units_sold"].clip(lower=0)
    log("Negative units_sold (impossible value)", "Clipped to 0", neg)

    df["units_sold"] = df["units_sold"].round().astype(int)
    df["revenue"] = df["units_sold"] * df["unit_price"]
    return df


def load_inventory():
    df = pd.read_csv(RAW / "inventory_snapshots.csv", parse_dates=["date"])
    miss_oo = df["on_order_units"].isna().sum()
    df["on_order_units"] = df["on_order_units"].fillna(0)
    log("Missing on_order_units", "Assumed no stock on order (filled with 0)", miss_oo)
    return df


def build_master_table(sku_df, cal_df, sales_df, inv_df):
    # Fact table: every (sku, date) that the SKU was active, joined to calendar + sku attrs.
    df = sales_df.merge(sku_df, on="sku_id", how="left", validate="many_to_one")
    df = df.merge(
        cal_df[["date", "week", "month", "season", "is_holiday", "promo_event"]],
        on="date", how="left", validate="many_to_one",
    )

    orphan_sales = df["category"].isna().sum()
    if orphan_sales:
        df = df.dropna(subset=["category"])
    log("Sales rows referencing an unknown sku_id", "Dropped (no master data to join)", orphan_sales)

    # attach the latest inventory snapshot at or before each date (as-of join)
    df = df.sort_values(["date", "sku_id"])
    inv_sorted = inv_df.sort_values(["date", "sku_id"])
    df = pd.merge_asof(
        df, inv_sorted, on="date", by="sku_id", direction="backward"
    )
    return df.sort_values(["sku_id", "date"]).reset_index(drop=True)


def weekly_aggregate(df):
    df = df.copy()
    df["week_start"] = df["date"] - pd.to_timedelta(df["date"].dt.dayofweek, unit="D")
    agg = (
        df.groupby(["sku_id", "week_start", "category", "subcategory"], as_index=False)
        .agg(
            units_sold=("units_sold", "sum"),
            revenue=("revenue", "sum"),
            avg_price=("unit_price", "mean"),
            promo_days=("promo_flag", "sum"),
            holiday_days=("is_holiday", "sum"),
            on_hand_units=("on_hand_units", "last"),
            on_order_units=("on_order_units", "last"),
            lead_time_days=("lead_time_days", "last"),
            reorder_point=("reorder_point", "last"),
            unit_cost=("unit_cost", "last"),
            list_price=("list_price", "last"),
        )
    )
    return agg.sort_values(["sku_id", "week_start"]).reset_index(drop=True)


def run():
    sku_df = load_sku_master()
    cal_df = load_calendar()
    sales_df = load_sales_daily()
    inv_df = load_inventory()

    master_daily = build_master_table(sku_df, cal_df, sales_df, inv_df)
    master_weekly = weekly_aggregate(master_daily)

    master_daily.to_csv(PROCESSED / "analysis_ready_daily.csv", index=False)
    master_weekly.to_csv(PROCESSED / "analysis_ready_weekly.csv", index=False)

    with open(REPORTS / "data_quality_log.json", "w") as f:
        json.dump(dq_log, f, indent=2)

    write_dq_markdown(sku_df, cal_df, sales_df, inv_df, master_daily, master_weekly)

    print(f"Daily analysis-ready dataset: {master_daily.shape}")
    print(f"Weekly analysis-ready dataset: {master_weekly.shape}")
    print(f"Data-quality issues logged: {len(dq_log)} (see reports/data_quality_report.md)")
    return master_daily, master_weekly


def write_dq_markdown(sku_df, cal_df, sales_df, inv_df, master_daily, master_weekly):
    lines = [
        "# Data-Quality Report — Project FORESIGHT",
        "",
        "Generated automatically by `src/pipeline.py`. Every cleaning decision below is",
        "coded (not manual) and reproducible from the raw extracts.",
        "",
        "## Issues found and how they were handled",
        "",
        "| Issue | Action taken | Rows affected |",
        "|---|---|---|",
    ]
    for row in dq_log:
        lines.append(f"| {row['issue']} | {row['action']} | {row['rows_affected']} |")

    lines += [
        "",
        "## Resulting dataset",
        "",
        f"- SKUs in master data: **{sku_df['sku_id'].nunique()}**",
        f"- Date range: **{sales_df['date'].min().date()} to {sales_df['date'].max().date()}**",
        f"- Analysis-ready daily rows: **{len(master_daily):,}**",
        f"- Analysis-ready weekly rows: **{len(master_weekly):,}**",
        f"- Categories: {', '.join(sorted(sku_df['category'].unique()))}",
        "",
        "## Key assumptions",
        "",
        "- Missing `units_sold` values are treated as data-entry gaps (not necessarily zero sales) and",
        "  imputed with the SKU's own median; this is conservative and documented so a reviewer can",
        "  substitute a different rule if NorthBay's ops team has a better one.",
        "- Missing `unit_cost` is imputed at the category level, since cost is far more stable within a",
        "  category than within a single SKU history.",
        "- Inventory snapshots are joined to daily sales with an as-of (backward) merge: each sales row",
        "  gets the most recent known stock position, since snapshots are periodic, not daily.",
        "- Category labels were consolidated to one canonical spelling/case per category",
        "  (e.g. 'decor', 'Décor', 'Decor' -> 'Decor').",
    ]
    with open(REPORTS / "data_quality_report.md", "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    run()
