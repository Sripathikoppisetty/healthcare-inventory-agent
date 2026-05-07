"""tools/analytics.py — Demand forecasting, ABC analysis, anomaly detection."""

from datetime import date, timedelta
from typing import Optional
from langchain_core.tools import tool
import numpy as np

from data.database import get_db
from data.models import SKU, UsageHistory, InventoryRecord


@tool
def demand_forecast(
    sku_id: str,
    location_id: Optional[str] = None,
    horizon_days: int = 14,
) -> str:
    """
    Forecast demand for a SKU over the next N days using moving average + trend.

    Args:
        sku_id: SKU to forecast.
        location_id: Specific location (optional; aggregates across all if None).
        horizon_days: Forecast window in days (7, 14, or 30).

    Returns:
        Forecast summary with recommended reorder point.
    """
    with get_db() as db:
        sku = db.query(SKU).filter(SKU.id == sku_id).first()
        if not sku:
            return f"SKU {sku_id} not found."

        cutoff = date.today() - timedelta(days=90)
        query = db.query(UsageHistory).filter(
            UsageHistory.sku_id == sku_id,
            UsageHistory.usage_date >= cutoff,
        )
        if location_id:
            query = query.filter(UsageHistory.location_id == location_id)

        records = query.order_by(UsageHistory.usage_date).all()

        if len(records) < 7:
            return (
                f"Insufficient usage history for {sku_id} (need ≥7 days, "
                f"found {len(records)}). Using default reorder point."
            )

        daily_usage = np.array([r.quantity_used for r in records], dtype=float)

        # 7-day and 30-day moving averages
        ma7 = float(np.mean(daily_usage[-7:]))
        ma30 = float(np.mean(daily_usage[-30:])) if len(daily_usage) >= 30 else ma7

        # Simple linear trend (slope over last 30 days)
        if len(daily_usage) >= 14:
            x = np.arange(len(daily_usage[-30:]))
            y = daily_usage[-30:]
            slope = float(np.polyfit(x, y, 1)[0])
        else:
            slope = 0.0

        # Forecast = MA + trend projection
        forecast_daily = max(0.0, ma7 + slope * (horizon_days / 2))
        forecast_total = round(forecast_daily * horizon_days)

        # Safety stock (1.65σ covers 95% service level)
        sigma = float(np.std(daily_usage[-30:])) if len(daily_usage) >= 7 else ma7 * 0.2
        safety_stock = round(1.65 * sigma * (sku.lead_time_days ** 0.5))

        recommended_par = round(forecast_daily * sku.lead_time_days) + safety_stock

        trend_label = "↑ increasing" if slope > 0.1 else ("↓ decreasing" if slope < -0.1 else "→ stable")

        return (
            f"📈 Demand forecast for {sku_id} — {sku.name}\n"
            f"   Horizon: {horizon_days} days | Trend: {trend_label}\n"
            f"   7-day avg: {ma7:.1f} units/day | 30-day avg: {ma30:.1f} units/day\n"
            f"   Forecast total ({horizon_days}d): {forecast_total} units\n"
            f"   Safety stock (95% SL): {safety_stock} units\n"
            f"   Recommended PAR level: {recommended_par} units\n"
            f"   Current PAR: {sku.reorder_point} units "
            f"({'✅ adequate' if sku.reorder_point >= recommended_par else '⚠️ consider updating'})"
        )


@tool
def abc_analysis(
    category: Optional[str] = None,
    top_n: int = 20,
) -> str:
    """
    Run ABC analysis on inventory SKUs by annual spend value.

    Args:
        category: Filter to a specific category (optional).
        top_n: Number of top items to show in the report.

    Returns:
        ABC classification summary with spend breakdown.
    """
    with get_db() as db:
        query = db.query(SKU)
        if category:
            query = query.filter(SKU.category == category)

        skus = query.all()
        if not skus:
            return "No SKUs found."

        # Estimate annual spend = unit_cost × reorder_qty × (365 / lead_time)
        items = []
        for sku in skus:
            annual_spend = sku.unit_cost * sku.reorder_quantity * (365 / max(1, sku.lead_time_days))
            items.append((sku, annual_spend))

        items.sort(key=lambda x: x[1], reverse=True)
        total_spend = sum(v for _, v in items)

        # Classify A/B/C by cumulative spend
        cum = 0.0
        report_lines = []
        a_count = b_count = c_count = 0
        a_spend = b_spend = c_spend = 0.0

        for sku, spend in items:
            cum += spend
            pct = cum / total_spend * 100
            if pct <= 70:
                cls = "A"; a_count += 1; a_spend += spend
            elif pct <= 90:
                cls = "B"; b_count += 1; b_spend += spend
            else:
                cls = "C"; c_count += 1; c_spend += spend

            if len(report_lines) < top_n:
                report_lines.append(
                    f"  {cls} | {sku.id} | {sku.name[:35]:35s} | "
                    f"${spend:>10,.0f}/yr | {sku.category.value}"
                )

        summary = (
            f"📊 ABC Analysis — {len(items)} SKUs"
            + (f" in '{category}'" if category else "")
            + f" | Total annual spend: ${total_spend:,.0f}\n\n"
            f"  Class A: {a_count} SKUs ({a_count/len(items)*100:.0f}%) → ${a_spend:,.0f}/yr (70% of spend)\n"
            f"  Class B: {b_count} SKUs ({b_count/len(items)*100:.0f}%) → ${b_spend:,.0f}/yr\n"
            f"  Class C: {c_count} SKUs ({c_count/len(items)*100:.0f}%) → ${c_spend:,.0f}/yr\n\n"
            f"Top {min(top_n, len(items))} by annual spend:\n" + "\n".join(report_lines)
        )
        return summary


@tool
def anomaly_detection(
    sku_id: Optional[str] = None,
    location_id: Optional[str] = None,
    lookback_days: int = 30,
    sensitivity: float = 2.0,
) -> str:
    """
    Detect usage anomalies (spikes or drops) using z-score analysis.

    Args:
        sku_id: Specific SKU to check (optional; checks all if None).
        location_id: Specific location (optional).
        lookback_days: Days of history to analyse.
        sensitivity: Z-score threshold (default 2.0 = 2 standard deviations).

    Returns:
        List of anomalous usage events with severity.
    """
    with get_db() as db:
        cutoff = date.today() - timedelta(days=lookback_days)
        query = db.query(UsageHistory).filter(UsageHistory.usage_date >= cutoff)

        if sku_id:
            query = query.filter(UsageHistory.sku_id == sku_id)
        if location_id:
            query = query.filter(UsageHistory.location_id == location_id)

        records = query.all()
        if not records:
            return "No usage data found for the specified parameters."

        # Group by (sku_id, location_id)
        from collections import defaultdict
        groups = defaultdict(list)
        for r in records:
            groups[(r.sku_id, r.location_id)].append(r.quantity_used)

        anomalies = []
        for (sid, lid), usages in groups.items():
            if len(usages) < 5:
                continue
            arr = np.array(usages, dtype=float)
            mean, std = arr.mean(), arr.std()
            if std == 0:
                continue
            z_scores = (arr - mean) / std
            for i, z in enumerate(z_scores):
                if abs(z) >= sensitivity:
                    direction = "SPIKE 📈" if z > 0 else "DROP 📉"
                    anomalies.append(
                        f"  {direction} | {sid} @ {lid} | "
                        f"Usage: {usages[i]} (avg: {mean:.1f}, z={z:.1f})"
                    )

        if not anomalies:
            return f"✅ No usage anomalies detected (z-threshold: {sensitivity}) over {lookback_days} days."

        return (
            f"⚠️ {len(anomalies)} anomaly event(s) detected (z ≥ {sensitivity}):\n"
            + "\n".join(anomalies[:30])
            + (f"\n  ...and {len(anomalies)-30} more" if len(anomalies) > 30 else "")
        )
