#!/usr/bin/env python3
"""Calculate a *directional* Year-1 ROI from explicitly supplied financial values.

Usage: python3 scripts/roi.py assets/roi-input.example.json
Never fill missing values with invented inputs; None means unavailable.
"""
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

BENEFITS = (
    "annual_cash_savings",
    "annual_validated_capacity_value",
    "annual_expected_loss_avoided",
    "annual_incremental_contribution_profit",
)
COSTS = ("one_time_cost", "annual_new_operating_cost")
KEYS = BENEFITS + COSTS

def money(value, key):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{key}: expected numeric value or null")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError(f"{key}: expected numeric value or null")
    if not number.is_finite() or number < 0:
        raise ValueError(f"{key}: expected finite non-negative value")
    return number

def calculate(data):
    values = {key: money(data.get(key), key) for key in KEYS}
    missing = [key for key, value in values.items() if value is None]
    if missing:
        return {"status": "insufficient_data", "missing_fields": missing}
    benefits = sum((values[k] for k in BENEFITS), Decimal(0))
    costs = sum((values[k] for k in COSTS), Decimal(0))
    net = benefits - costs
    ongoing_margin = benefits - values["annual_new_operating_cost"]
    payback = (values["one_time_cost"] * 12 / ongoing_margin) if ongoing_margin > 0 else None
    return {
        "status": "calculated",
        "currency": data.get("currency", "unspecified"),
        "horizon": "12 months, steady-state assumption",
        "annual_gross_quantified_benefits": str(benefits),
        "year1_total_cost": str(costs),
        "year1_net_value": str(net),
        "year1_roi_percent": str((net / costs * 100).quantize(Decimal("0.01"))) if costs else None,
        "simple_payback_months": str(payback.quantize(Decimal("0.1"))) if payback is not None else None,
        "warnings": [
            "Treat capacity value as zero unless monetization is validated.",
            "Do not double-count savings, incident costs or contribution profit.",
            "Payback ignores ramp-up, timing and discounting; inspect assumptions.",
        ],
    }

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 scripts/roi.py <input.json>")
    try:
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Input must be one JSON object")
        print(json.dumps(calculate(data), ensure_ascii=False, indent=2))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        sys.exit(f"Error: {error}")
