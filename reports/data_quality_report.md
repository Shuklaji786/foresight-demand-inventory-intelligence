# Data-Quality Report — Project FORESIGHT

Generated automatically by `src/pipeline.py`. Every cleaning decision below is
coded (not manual) and reproducible from the raw extracts.

## Issues found and how they were handled

| Issue | Action taken | Rows affected |
|---|---|---|
| Duplicate sku_master rows (same sku_id repeated) | Kept first occurrence, dropped rest | 3 |
| Inconsistent category labels (casing / accents, e.g. 'decor' vs 'Décor') | Standardised to a single canonical label per category | 8 |
| Missing unit_cost | Imputed with the category median unit_cost | 2 |
| Duplicate sales_daily rows (same date + sku_id repeated) | Kept first occurrence, dropped rest | 25 |
| Missing units_sold | Imputed with the SKU's median units_sold (fallback 0) | 294 |
| Negative units_sold (impossible value) | Clipped to 0 | 0 |
| Missing on_order_units | Assumed no stock on order (filled with 0) | 83 |
| Sales rows referencing an unknown sku_id | Dropped (no master data to join) | 0 |

## Resulting dataset

- SKUs in master data: **60**
- Date range: **2024-01-11 to 2025-12-28**
- Analysis-ready daily rows: **29,403**
- Analysis-ready weekly rows: **4,226**
- Categories: Decor, Furniture, Small Appliances

## Key assumptions

- Missing `units_sold` values are treated as data-entry gaps (not necessarily zero sales) and
  imputed with the SKU's own median; this is conservative and documented so a reviewer can
  substitute a different rule if NorthBay's ops team has a better one.
- Missing `unit_cost` is imputed at the category level, since cost is far more stable within a
  category than within a single SKU history.
- Inventory snapshots are joined to daily sales with an as-of (backward) merge: each sales row
  gets the most recent known stock position, since snapshots are periodic, not daily.
- Category labels were consolidated to one canonical spelling/case per category
  (e.g. 'decor', 'Décor', 'Decor' -> 'Decor').