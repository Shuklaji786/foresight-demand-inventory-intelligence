"""
Project FORESIGHT - synthetic data generator
Creates the four raw extracts described in the brief (Section 05):
  sales_daily, sku_master, calendar, inventory_snapshots

The data is deliberately imperfect (missing values, duplicates,
inconsistent category labels) so that cleaning is part of the pipeline,
exactly as the brief states.

Usage:
    python src/generate_data.py
Writes CSVs to data/raw/.
"""
import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(42)
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

N_SKUS = 60
START_DATE = pd.Timestamp("2024-01-01")
END_DATE = pd.Timestamp("2025-12-28")  # ~2 years, ends on a Sunday for clean weekly agg

CATEGORIES = {
    "Furniture": ["Seating", "Tables", "Storage"],
    "Decor": ["Wall Art", "Rugs", "Lighting"],
    "Small Appliances": ["Kitchen", "Climate", "Cleaning"],
}
# deliberately inconsistent label variants injected later for messiness
CATEGORY_LABEL_VARIANTS = {
    "Furniture": ["Furniture", "furniture", "FURNITURE"],
    "Decor": ["Decor", "Décor", "decor"],
    "Small Appliances": ["Small Appliances", "Small Appliance", "small appliances"],
}


def build_sku_master():
    rows = []
    cats = list(CATEGORIES.keys())
    for i in range(1, N_SKUS + 1):
        sku_id = f"SKU{i:04d}"
        cat = RNG.choice(cats, p=[0.4, 0.35, 0.25])
        subcat = RNG.choice(CATEGORIES[cat])
        launch_offset = RNG.integers(0, 500)  # some SKUs launch mid-history
        launch_date = START_DATE + pd.Timedelta(days=int(launch_offset))
        unit_cost = round(RNG.uniform(300, 4000), 2)
        margin_mult = RNG.uniform(1.6, 2.8)
        list_price = round(unit_cost * margin_mult, 2)
        # base weekly demand level varies a lot by SKU (best-sellers vs long tail)
        base_demand = RNG.gamma(shape=2.0, scale=12.0) + 2
        rows.append(dict(
            sku_id=sku_id, category=cat, subcategory=subcat,
            launch_date=launch_date.date().isoformat(),
            unit_cost=unit_cost, list_price=list_price,
            _base_demand=base_demand,  # helper column, dropped before saving raw
        ))
    df = pd.DataFrame(rows)

    # inject messiness: inconsistent category casing/spelling on ~15% of rows
    messy_idx = df.sample(frac=0.15, random_state=1).index
    for idx in messy_idx:
        cat = df.loc[idx, "category"]
        df.loc[idx, "category"] = RNG.choice(CATEGORY_LABEL_VARIANTS[cat])

    # inject a few duplicate sku_master rows (client extract quirk)
    dupes = df.sample(n=3, random_state=2)
    df_out = pd.concat([df, dupes], ignore_index=True)

    # a few missing unit_cost values
    miss_idx = df_out.sample(frac=0.03, random_state=3).index
    df_out.loc[miss_idx, "unit_cost"] = np.nan

    base_demand = df.set_index("sku_id")["_base_demand"]
    df_out = df_out.drop(columns="_base_demand")
    df_out.to_csv(RAW_DIR / "sku_master.csv", index=False)
    return df.set_index("sku_id"), base_demand


def build_calendar():
    dates = pd.date_range(START_DATE, END_DATE, freq="D")
    df = pd.DataFrame({"date": dates})
    df["week"] = df["date"].dt.isocalendar().week.astype(int)
    df["month"] = df["date"].dt.month
    df["season"] = df["month"] % 12 // 3 + 1
    df["season"] = df["season"].map({1: "Winter", 2: "Spring", 3: "Summer", 4: "Autumn"})
    # simple holiday calendar (major shopping-relevant days)
    holidays = set()
    for yr in [2024, 2025]:
        holidays.update([
            f"{yr}-01-01", f"{yr}-01-26", f"{yr}-08-15", f"{yr}-10-02",
            f"{yr}-11-15", f"{yr}-12-25",
        ])
    df["is_holiday"] = df["date"].dt.strftime("%Y-%m-%d").isin(holidays).astype(int)

    # promo events: a "Big Billion-style" sale each quarter + random flash sales
    promo_windows = []
    for yr in [2024, 2025]:
        promo_windows += [
            (f"{yr}-01-15", f"{yr}-01-22", "New Year Sale"),
            (f"{yr}-06-01", f"{yr}-06-08", "Summer Clearance"),
            (f"{yr}-10-20", f"{yr}-10-29", "Festive Sale"),
            (f"{yr}-11-25", f"{yr}-11-30", "Black Friday"),
        ]
    df["promo_event"] = ""
    for start, end, name in promo_windows:
        mask = (df["date"] >= start) & (df["date"] <= end)
        df.loc[mask, "promo_event"] = name

    df["date"] = df["date"].dt.date.astype(str)
    df.to_csv(RAW_DIR / "calendar.csv", index=False)
    out = pd.read_csv(RAW_DIR / "calendar.csv", parse_dates=["date"], keep_default_na=False)
    out["is_holiday"] = out["is_holiday"].astype(int)
    return out


def build_sales_daily(sku_df, base_demand, calendar_df):
    all_rows = []
    dates = calendar_df["date"]
    n_days = len(dates)
    day_of_year = dates.dt.dayofyear.values
    dow = dates.dt.dayofweek.values  # 0=Mon
    promo_mask = (calendar_df["promo_event"] != "").values
    holiday_mask = calendar_df["is_holiday"].values.astype(bool)

    weekly_season = 1 + 0.35 * np.sin(2 * np.pi * (day_of_year / 365.25) * 1)  # annual cycle
    weekend_boost = np.where(np.isin(dow, [5, 6]), 1.25, 1.0)

    for sku_id, row in sku_df.iterrows():
        launch = pd.Timestamp(row["launch_date"])
        lvl = base_demand.loc[sku_id]
        trend = RNG.normal(0.00015, 0.0004)  # slight growth/decline per SKU
        noise = RNG.normal(0, 0.18, size=n_days)
        active = (dates >= launch).values

        demand = (lvl * weekly_season * weekend_boost
                  * (1 + trend * np.arange(n_days))
                  * (1 + noise))
        demand = np.where(promo_mask, demand * RNG.uniform(1.6, 2.4), demand)
        demand = np.where(holiday_mask, demand * RNG.uniform(1.1, 1.5), demand)
        demand = np.clip(demand, 0, None)
        units_sold = RNG.poisson(demand)
        units_sold = np.where(active, units_sold, 0)

        list_price = sku_df.loc[sku_id, "list_price"]
        unit_price = np.where(promo_mask, list_price * RNG.uniform(0.75, 0.9, n_days), list_price)
        revenue = units_sold * unit_price

        sku_rows = pd.DataFrame({
            "date": dates.dt.date.astype(str),
            "sku_id": sku_id,
            "units_sold": units_sold,
            "revenue": np.round(revenue, 2),
            "unit_price": np.round(unit_price, 2),
            "promo_flag": promo_mask.astype(int),
        })
        sku_rows = sku_rows[active]
        all_rows.append(sku_rows)

    df = pd.concat(all_rows, ignore_index=True)

    # inject messiness: a few duplicate rows, a few missing units_sold
    dupes = df.sample(n=25, random_state=4)
    df = pd.concat([df, dupes], ignore_index=True)
    miss_idx = df.sample(frac=0.01, random_state=5).index
    df.loc[miss_idx, "units_sold"] = np.nan

    df.to_csv(RAW_DIR / "sales_daily.csv", index=False)
    return pd.read_csv(RAW_DIR / "sales_daily.csv", parse_dates=["date"])


def build_inventory_snapshots(sku_df, sales_df, calendar_df):
    # weekly snapshots (Mondays) per SKU
    snap_dates = calendar_df.loc[calendar_df["date"].dt.dayofweek == 0, "date"]
    rows = []
    sales_by_sku = {
        sku: g.groupby("date")["units_sold"].sum().fillna(0).sort_index()
        for sku, g in sales_df.groupby("sku_id")
    }

    for sku_id, row in sku_df.iterrows():
        lead_time = int(RNG.choice([7, 10, 14, 21], p=[0.3, 0.3, 0.25, 0.15]))
        avg_weekly = base_demand_lookup(sales_by_sku.get(sku_id))
        on_hand = max(RNG.normal(avg_weekly * RNG.uniform(1.5, 4.0), avg_weekly * 0.3), 0)
        reorder_point = round(avg_weekly * (lead_time / 7) * 1.3, 0)

        for d in snap_dates:
            if pd.Timestamp(row["launch_date"]) > d:
                continue
            recent = sales_by_sku.get(sku_id)
            recent_avg = recent.loc[:d].tail(28).mean() if recent is not None and len(recent.loc[:d]) else avg_weekly / 7
            recent_avg = recent_avg if pd.notna(recent_avg) else avg_weekly / 7
            consumption = recent_avg * 7 * RNG.uniform(0.85, 1.15)
            on_hand = max(on_hand - consumption, 0)
            on_order = 0
            if on_hand < reorder_point and RNG.random() < 0.6:
                on_order_units = round(reorder_point * RNG.uniform(1.2, 2.0), 0)
                on_order = on_order_units
                on_hand += on_order_units * RNG.choice([0, 1], p=[0.7, 0.3])  # sometimes arrives same week
            rows.append(dict(
                date=d.date().isoformat(), sku_id=sku_id,
                on_hand_units=round(on_hand, 0), on_order_units=round(on_order, 0),
                lead_time_days=lead_time, reorder_point=reorder_point,
            ))

    df = pd.DataFrame(rows)
    # inject messiness: a few missing on_order_units
    miss_idx = df.sample(frac=0.02, random_state=6).index
    df.loc[miss_idx, "on_order_units"] = np.nan
    df.to_csv(RAW_DIR / "inventory_snapshots.csv", index=False)
    return df


def base_demand_lookup(series):
    if series is None or len(series) == 0:
        return 5.0
    return max(series.mean() * 7, 1.0)


if __name__ == "__main__":
    sku_df, base_demand = build_sku_master()
    calendar_df = build_calendar()
    sales_df = build_sales_daily(sku_df, base_demand, calendar_df)
    inv_df = build_inventory_snapshots(sku_df, sales_df, calendar_df)
    print("Generated raw extracts in", RAW_DIR)
    for f in ["sku_master.csv", "calendar.csv", "sales_daily.csv", "inventory_snapshots.csv"]:
        p = RAW_DIR / f
        print(f"  {f}: {sum(1 for _ in open(p)) - 1} rows")
