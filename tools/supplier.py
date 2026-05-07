"""tools/supplier.py — Supplier lookup and performance queries."""

from typing import Optional
from langchain_core.tools import tool

from data.database import get_db
from data.models import Supplier, SKU


@tool
def supplier_lookup(
    sku_id: Optional[str] = None,
    supplier_id: Optional[str] = None,
    preferred_only: bool = False,
) -> str:
    """
    Look up supplier information and lead times for a SKU or supplier.

    Args:
        sku_id: Find the supplier for this SKU.
        supplier_id: Look up a specific supplier directly.
        preferred_only: Only return preferred/contract suppliers.

    Returns:
        Supplier details including lead time, contact, and performance score.
    """
    with get_db() as db:
        if sku_id:
            sku = db.query(SKU).filter(SKU.id == sku_id).first()
            if not sku:
                return f"SKU {sku_id} not found."
            if not sku.supplier_id:
                return f"No supplier assigned to {sku_id}."
            suppliers = [db.query(Supplier).filter(Supplier.id == sku.supplier_id).first()]
        elif supplier_id:
            suppliers = [db.query(Supplier).filter(Supplier.id == supplier_id).first()]
        else:
            query = db.query(Supplier)
            if preferred_only:
                query = query.filter(Supplier.is_preferred == True)
            suppliers = query.order_by(Supplier.performance_score.desc()).limit(20).all()

        if not suppliers or suppliers[0] is None:
            return "No suppliers found."

        lines = []
        for s in suppliers:
            if s is None:
                continue
            preferred_tag = "⭐ PREFERRED" if s.is_preferred else ""
            lines.append(
                f"{preferred_tag} Supplier: {s.id} — {s.name}\n"
                f"  Contact: {s.contact_name or 'N/A'} | {s.email or 'N/A'} | {s.phone or 'N/A'}\n"
                f"  Contract: {s.contract_number or 'None'}\n"
                f"  Lead time: {s.lead_time_days} days | "
                f"Performance score: {s.performance_score:.2f}/1.00"
            )

        return "\n\n".join(lines)
