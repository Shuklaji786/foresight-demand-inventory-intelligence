# Project FORESIGHT — Demand & Inventory Intelligence

**Client:** NorthBay Living (simulated) · **Engagement:** Zidio Development Data Science Internship
**Role:** Data Scientist on the engagement · **Stack:** Python, pandas, scikit-learn, Streamlit, FastAPI

FORESIGHT turns NorthBay's raw sales, inventory, and calendar extracts into a weekly SKU-level
demand forecast, a stockout/overstock early-warning system, a planning dashboard, and a deployed
scoring service — following the client engagement brief end to end.

## The problem, in one line

NorthBay stocks out of what people want and sits on what they don't, because planning is done on
spreadsheets and gut feel. FORESIGHT tells the ops team, for every SKU: how much they'll likely sell
over the next 6 weeks, whether it's about to run out or is overstocked, and what to do about it —
in rupees, not just probabilities.

## Headline result (backtested, not just claimed)

| Metric | Model | Seasonal-naive baseline |
|---|---|---|
| WAPE (rolling-origin backtest, 6 folds) | **11.6%** | 17.5% |

The model beats the baseline by roughly a third. Full fold-by-fold detail, including bias checks
and the honesty rules followed (no data leakage, no single random split), is in
[`reports/model_backtest_report.md`](reports/model_backtest_report.md).

**Business impact from the current risk scan:**
- 25 of 60 SKUs are flagged **Reorder Now** — ₹5.5 Cr in sales at risk from stockouts over the next 6 weeks.
- 2 SKUs are flagged **Markdown / Clear** — ₹88 L of capital locked in overstock.
- See [`reports/risk_summary.md`](reports/risk_summary.md) for the full breakdown.

## Repository structure

```
foresight/
  data/
    raw/            four simulated client extracts (sales_daily, sku_master, calendar, inventory_snapshots)
    processed/      analysis-ready datasets, forecast output, risk scores
  src/
    generate_data.py   synthetic data generator (stands in for the client's real extracts)
    pipeline.py         D1 — ingestion + cleaning -> analysis-ready dataset
    eda.py              D2 — exploratory analysis, charts, insight memo
    forecast.py         D3 — feature engineering, seasonal-naive baseline, gradient-boosted model,
                         rolling-origin backtest, forecast export, trained model export
    risk.py              D4 — stockout/overstock scoring, decisioning grid, rupee impact
  app/
    app.py              D5 — Streamlit planning dashboard
  service/
    main.py              D6 — FastAPI scoring service (forecast + risk for a SKU or batch)
    model/               trained model + history snapshot used by the service (written by forecast.py)
  reports/
    data_quality_report.md     coded list of issues found and how each was handled
    eda_insight_memo.md        demand patterns and business-relevant findings
    model_backtest_report.md   WAPE vs baseline, per fold, with an honesty check
    risk_summary.md             quadrant counts and rupee impact
    figures/                    all charts referenced above
    executive_readout.pptx      D7 — stakeholder deck (this doc summarised for a non-technical reader)
    build_deck.js               generator for the deck above (pptxgenjs)
  requirements.txt
```

## How to run it end to end

```bash
pip install -r requirements.txt

# 1. Generate the (simulated) client extracts
python src/generate_data.py

# 2. Build the analysis-ready dataset + data-quality report
python src/pipeline.py

# 3. Run EDA -> charts + insight memo
python src/eda.py

# 4. Train + backtest the forecast, export the model
python src/forecast.py

# 5. Score stockout/overstock risk
python src/risk.py

# 6. Launch the planning dashboard
streamlit run app/app.py

# 7. Launch the scoring service (separate terminal)
uvicorn service.main:app --reload --port 8000
curl http://127.0.0.1:8000/score/SKU0001
```

Steps 1–5 are already run and their outputs committed under `data/processed/` and `reports/`, so
you can jump straight to steps 6–7, or re-run everything from scratch — the pipeline is fully
reproducible from the raw extracts with fixed random seeds.

## Methodology (Section 07 of the brief, followed in order)

1. **Frame the metric** — WAPE, 6-week horizon, fixed before any modelling.
2. **Baseline** — seasonal-naive (same week last year, falling back to a 4-week rolling mean for
   SKUs without a full year of history yet).
3. **Features** — lags (1/2/3/4/8/52 weeks), rolling mean/std, ISO week-of-year sin/cos, month,
   promo/holiday flags, weeks-since-launch, category, average price.
4. **Model** — `HistGradientBoostingRegressor` (gradient-boosted trees, Poisson loss — a good fit
   for non-negative count-like demand; LightGBM was the brief's suggestion but wasn't available in
   this offline environment, so scikit-learn's equivalent tree-boosting model was used instead).
5. **Backtest** — rolling-origin cross-validation, 6 origins, retraining at each origin using only
   data available up to that point. No feature ever uses same-week-or-later information.
6. **Evaluate & select** — compared to baseline on every fold; the model wins on all folds shown in
   `reports/model_backtest_report.md`.
7. **Risk score** — forecast demand over lead time vs. on-hand + on-order stock (stockout side);
   on-hand stock vs. an 8-week demand cover window (overstock side). Every SKU lands in one of four
   quadrants (Reorder Now / Markdown / Clear / Watch-Volatile / Healthy) with a rupee value attached.

## Key assumptions & limitations (stated honestly, per the brief's non-negotiable rule)

- Data is simulated (`src/generate_data.py`), built to match the schema and messiness described in
  the brief's Appendix A, since a live client extract wasn't provided. Swap in real extracts with
  the same column names and the pipeline runs unchanged.
- New SKUs with under 12 weeks of history are excluded from backtesting (too little history to
  validate against) but are still forecast in production using category-level fallbacks.
- The forecast's uncertainty interval is a simple residual-based ±1.28σ (80%) band, not a fully
  calibrated quantile model — documented as a stretch-goal upgrade rather than hidden as fact.
- Out of scope, per the brief: live system integrations, price optimization, automated purchase
  orders. FORESIGHT recommends; it does not act on the client's behalf.

## Originality & conduct

This project was built by working through NorthBay's (simulated) data with the methodology above;
no results are fabricated, and the backtest is reported honestly whether or not the model wins.
