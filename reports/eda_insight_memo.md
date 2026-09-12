# Data-Quality & EDA Insight Memo — Project FORESIGHT

Prepared for: Head of Operations, NorthBay Living

## What we found in the data

Data-quality issues (missing values, duplicate rows, inconsistent category labels) were
found and corrected in the pipeline — see `reports/data_quality_report.md` for the full,
coded list. None of the issues were severe enough to drop a SKU or a time period from the
analysis.

## Demand patterns

1. **Demand is seasonal, not flat.** Weekly sales peak around month 6, and
   promotional weeks lift demand well above the surrounding baseline — see
   `figures/01_total_weekly_demand.png`.
2. **Promotions work, but not equally everywhere.** Units sold in promo weeks run about
   **49% higher** than non-promo weeks on average
   (`figures/04_promo_effect.png`). This lift should be modelled explicitly rather than
   averaged away, or the forecast will systematically miss promo weeks.
3. **Demand concentration is high.** The top 10 SKUs account for roughly
   **40% of units sold** in the last 12 weeks (`figures/03_top_movers.png`),
   while a long tail of SKUs sell in single digits — these are the dead-stock candidates.
4. **Decor is currently the strongest category** by weekly units
   (`figures/02_demand_by_category.png`); category mix should inform how aggressively
   FORESIGHT flags reorders versus markdowns.
5. **Volatility varies a lot by SKU** — about **0% of SKUs** have a
   coefficient of variation above 1.0 (`figures/05_demand_volatility.png`), meaning a single
   point forecast will understate risk for these SKUs; the model should carry an uncertainty
   interval and the risk layer should treat these as 'volatile / watch' rather than
   confidently healthy or at-risk.

## Business-relevant takeaways

- A small set of best-sellers drives most volume and deserves the tightest stockout
  monitoring — a single missed reorder on a top-10 SKU is a materially larger revenue hit
  than the same miss on a long-tail SKU.
- Roughly 0 SKUs sold one unit or fewer in the trailing 12 weeks and are dead-stock
  candidates for markdown, independent of any forecasting model.
- Promotions materially change demand shape; the forecasting model (Section 07 of the brief)
  must use promo/calendar features rather than a naive time trend alone.

*Charts referenced above are saved under `reports/figures/`.*