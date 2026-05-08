"""tools/compliance.py — Expiry scanning, PAR compliance, formulary checks."""

from datetime import date, timedelta
from typing import Optional
from langchain_core.tools import tool

from data.database import get_db
from data.models import SKU, InventoryRecord, Location


@tool
def expiry_scan(
    location_id: Optional[str] = None,
    days_ahead: int = 30,
    include_expired: Optional[str] = None,
) -> str:
    """
    Scan inventory for items expiring within the specified window.
    Supports FIFO alerting so oldest stock is consumed first.

    Args:
        location_id: Restrict scan to one location (optional).
        days_ahead: Flag items expiring within this many days.
        include_expired: Include already-expired items in the report.

    Returns:
        Expiry report sorted by urgency (soonest first).
    """
    with get_db() as db:
        today = date.today()
        cutoff = today + timedelta(days=days_ahead)

        query = db.query(InventoryRecord, SKU, Location).join(
            SKU, InventoryRecord.sku_id == SKU.id
        ).join(
            Location, InventoryRecord.location_id == Location.id
        ).filter(
            InventoryRecord.expiry_date.isnot(None),
            InventoryRecord.quantity_on_hand > 0,
        )

        if location_id:
            query = query.filter(InventoryRecord.location_id == location_id)
        if include_expired and str(include_expired).lower() in ("false", "0", "no"):
            query = query.filter(InventoryRecord.expiry_date >= today)
        else:
            query = query.filter(InventoryRecord.expiry_date <= cutoff)

        results = query.order_by(InventoryRecord.expiry_date).limit(20).all()

        if not results:
            return f"✅ No items expiring within {days_ahead} days."

        lines = []
        expired_count = 0
        for inv, sku, loc in results:
            days_left = (inv.expiry_date - today).days
            if days_left < 0:
                status = f"🔴 EXPIRED ({abs(days_left)}d ago)"
                expired_count += 1
            elif days_left <= 7:
                status = f"🔴 CRITICAL ({days_left}d left)"
            elif days_left <= 14:
                status = f"🟠 URGENT ({days_left}d left)"
            else:
                status = f"🟡 WARNING ({days_left}d left)"

            lines.append(
                f"{status} | {sku.id} | {sku.name[:40]} | "
                f"Loc: {loc.name} | Qty: {inv.quantity_on_hand} | "
                f"Expires: {inv.expiry_date.isoformat()} | "
                f"Lot: {inv.lot_number or 'N/A'}"
            )

        header = (
            f"🗓 Expiry scan — {len(lines)} item(s) flagged "
            f"(window: {days_ahead} days, {expired_count} already expired):\n"
        )
        return header + "\n".join(lines)


@tool
def compliance_check(
    sku_id: Optional[str] = None,
    location_id: Optional[str] = None,
    check_type: str = "all",
) -> str:
    """
    Run compliance checks across inventory: PAR levels, controlled substances,
    formulary adherence, and minimum stock requirements.

    Args:
        sku_id: Check a specific SKU (optional).
        location_id: Check a specific location (optional).
        check_type: One of 'par', 'controlled', 'formulary', or 'all'.

    Returns:
        Compliance report with issues flagged by severity.
    """
    with get_db() as db:
        query = db.query(InventoryRecord, SKU, Location).join(
            SKU, InventoryRecord.sku_id == SKU.id
        ).join(
            Location, InventoryRecord.location_id == Location.id
        )

        if sku_id:
            query = query.filter(InventoryRecord.sku_id == sku_id)
        if location_id:
            query = query.filter(InventoryRecord.location_id == location_id)

        results = query.all()
        issues = []

        for inv, sku, loc in results:
            # PAR level check
            if check_type in ("par", "all"):
                if inv.quantity_on_hand == 0:
                    issues.append(
                        f"🔴 STOCKOUT | {sku.id} | {sku.name[:35]} | {loc.name} | "
                        f"QoH: 0 (PAR: {sku.reorder_point})"
                    )
                elif inv.quantity_on_hand < sku.reorder_point:
                    pct = inv.quantity_on_hand / sku.reorder_point * 100
                    issues.append(
                        f"🟡 BELOW PAR | {sku.id} | {sku.name[:35]} | {loc.name} | "
                        f"QoH: {inv.quantity_on_hand} ({pct:.0f}% of PAR: {sku.reorder_point})"
                    )

            # Controlled substance check — flag if no lot number tracked
            if check_type in ("controlled", "all"):
                if sku.is_controlled and not inv.lot_number:
                    issues.append(
                        f"🔴 DEA/CONTROLLED | {sku.id} | {sku.name[:35]} | "
                        f"{loc.name} | Missing lot tracking (DEA required)"
                    )

            # Formulary check
            if check_type in ("formulary", "all"):
                if not sku.is_formulary:
                    issues.append(
                        f"🟠 NON-FORMULARY | {sku.id} | {sku.name[:35]} | "
                        f"{loc.name} | Item not on approved formulary"
                    )

        if not issues:
            return f"✅ All compliance checks passed ({len(results)} records checked)."

        return (
            f"⚠️ Compliance report — {len(issues)} issue(s) across {len(results)} records:\n"
            + "\n".join(issues[:40])
            + (f"\n...and {len(issues)-40} more" if len(issues) > 40 else "")
        )
