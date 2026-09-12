# Demand Forecast — Backtest Report

**Forecast horizon:** 6 weeks · **Backtest folds:** 6 rolling origins
**Validation method:** rolling-origin cross-validation (never a single random split for time series;
no future data touches any feature).

## Headline result

- Overall WAPE — model: **11.6%**
- Overall WAPE — seasonal-naive baseline: **17.5%**
- The model **beats** the seasonal-naive baseline on backtest.

## Per-fold detail

| origin     |   n_obs |   wape_model |   wape_naive |   bias_model |
|:-----------|--------:|-------------:|-------------:|-------------:|
| 2025-10-06 |     360 |         12.5 |         18.7 |         -5.4 |
| 2025-10-13 |     360 |         13.3 |         19.6 |         -4.5 |
| 2025-10-20 |     360 |         11.6 |         17.3 |         -1.6 |
| 2025-10-27 |     360 |         11.0 |         17.0 |         -0.8 |
| 2025-11-03 |     360 |         10.7 |         16.1 |         -2.3 |
| 2025-11-10 |     360 |         10.6 |         16.1 |         -1.4 |

## Honesty check

- Every feature at a given week is built only from data available before that week
  (lags and rolling stats are shifted by at least one period).
- The model is retrained at each backtest origin using only data up to that origin.
- Bias is reported alongside WAPE to check for systematic over/under-forecasting.