"""
Project FORESIGHT - Deployed Scoring Service (D6)

Returns forecast + stockout/overstock risk for a given SKU (or a batch),
using the model trained by src/forecast.py.

Run locally:
    pip install -r requirements.txt
    python src/pipeline.py && python src/forecast.py && python src/risk.py   # if not already run
    uvicorn service.main:app --reload --port 8000

Then:
    curl http://127.0.0.1:8000/health
    curl http://127.0.0.1:8000/score/SKU0001
    curl -X POST http://127.0.0.1:8000/score/batch -H "Content-Type: application/json" \
         -d '{"sku_ids": ["SKU0001", "SKU0002"]}'

Deploy anywhere that runs a standard ASGI app (Render, Hugging Face Spaces,
Railway, etc.) — no code changes needed, only the start command above.
"""
import sys
from pathlib import Path
from typing import List, Optional

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.forecast import build_features, FEATURE_COLS, HORIZON_WEEKS  # noqa: E402
from src.risk import SAFETY_MULT, OVERSTOCK_WEEKS_COVER  # noqa: E402

MODEL_PATH = ROOT / "service" / "model" / "forecast_model.joblib"
HISTORY_PATH = ROOT / "service" / "model" / "history_snapshot.csv"
RISK_PATH = ROOT / "data" / "processed" / "risk_scores.csv"

app = FastAPI(
    title="FORESIGHT Scoring Service",
    description="Forecast + stockout/overstock risk for NorthBay Living SKUs.",
    version="1.0.0",
)

_bundle = None
_history = None
_risk_cache = None


def _load():
    global _bundle, _history, _risk_cache
    if _bundle is None:
        if not MODEL_PATH.exists():
            raise HTTPException(
                status_code=503,
                detail="Model not found. Run `python src/forecast.py` to train and export it first.",
            )
        _bundle = joblib.load(MODEL_PATH)
        _history = pd.read_csv(HISTORY_PATH, parse_dates=["week_start"])
        _risk_cache = pd.read_csv(RISK_PATH) if RISK_PATH.exists() else None
    return _bundle, _history, _risk_cache


class BatchRequest(BaseModel):
    sku_ids: List[str]


class ForecastPoint(BaseModel):
    week_start: str
    step: int
    forecast: float
    lower_80: float
    upper_80: float


class ScoreResponse(BaseModel):
    sku_id: str
    forecast: List[ForecastPoint]
    stockout_risk: Optional[float] = None
    overstock_risk: Optional[float] = None
    quadrant: Optional[str] = None
    recommended_action: Optional[str] = None
    revenue_at_stake_inr: Optional[float] = None
    note: Optional[str] = None


@app.get("/health")
def health():
    ok = MODEL_PATH.exists()
    return {"status": "ok" if ok else "model_not_trained"}


def _forecast_one(sku_id: str, bundle, history: pd.DataFrame) -> pd.DataFrame:
    sku_hist = history[history["sku_id"] == sku_id]
    if sku_hist.empty:
        raise HTTPException(status_code=404, detail=f"Unknown sku_id: {sku_id}")

    model = bundle["model"]
    feature_cols = bundle["feature_cols"]
    last_week = sku_hist["week_start"].max()
    hist = sku_hist.copy()
    rows = []

    for step in range(1, HORIZON_WEEKS + 1):
        target_week = last_week + pd.Timedelta(weeks=step)
        last = hist.sort_values("week_start").iloc[-1]
        new_row = {
            "sku_id": sku_id, "week_start": target_week,
            "category": last["category"], "subcategory": last["subcategory"],
            "avg_price": last["avg_price"], "promo_days": 0, "holiday_days": 0,
            "on_hand_units": last["on_hand_units"], "on_order_units": last["on_order_units"],
            "lead_time_days": last["lead_time_days"], "reorder_point": last["reorder_point"],
            "unit_cost": last["unit_cost"], "list_price": last["list_price"], "units_sold": np.nan,
        }
        combined = pd.concat([hist, pd.DataFrame([new_row])], ignore_index=True)
        feat = build_features(combined)
        cur = feat[feat["week_start"] == target_week].copy()
        pred = float(np.clip(model.predict(cur[feature_cols].fillna(0))[0], 0, None))
        cur["units_sold"] = pred
        hist = pd.concat([hist, cur[hist.columns]], ignore_index=True)
        rows.append({"week_start": target_week.date().isoformat(), "step": step, "forecast": pred})

    resid_sigma = max(sku_hist["units_sold"].std() * 0.3, 1.0)  # simple, service-side interval
    out = pd.DataFrame(rows)
    out["lower_80"] = (out["forecast"] - 1.28 * resid_sigma).clip(lower=0)
    out["upper_80"] = out["forecast"] + 1.28 * resid_sigma
    return out


@app.get("/score/{sku_id}", response_model=ScoreResponse)
def score_sku(sku_id: str):
    bundle, history, risk_cache = _load()
    fc = _forecast_one(sku_id, bundle, history)

    risk_row = None
    if risk_cache is not None:
        match = risk_cache[risk_cache["sku_id"] == sku_id]
        if not match.empty:
            risk_row = match.iloc[0]

    return ScoreResponse(
        sku_id=sku_id,
        forecast=[ForecastPoint(**r) for r in fc.to_dict("records")],
        stockout_risk=float(risk_row["stockout_risk"]) if risk_row is not None else None,
        overstock_risk=float(risk_row["overstock_risk"]) if risk_row is not None else None,
        quadrant=str(risk_row["quadrant"]) if risk_row is not None else None,
        recommended_action=str(risk_row["recommended_action"]) if risk_row is not None else None,
        revenue_at_stake_inr=float(risk_row["revenue_at_stake_inr"]) if risk_row is not None else None,
        note=None if risk_row is not None else "Risk score not precomputed for this SKU; run src/risk.py to refresh.",
    )


@app.post("/score/batch", response_model=List[ScoreResponse])
def score_batch(req: BatchRequest):
    if not req.sku_ids:
        raise HTTPException(status_code=400, detail="sku_ids must not be empty.")
    return [score_sku(sku_id) for sku_id in req.sku_ids]
