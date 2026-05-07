"""api/server.py — FastAPI REST server exposing the agent and inventory data."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import logging

from config.settings import settings
from data.database import init_db, get_db_dependency
from data.models import SKU, InventoryRecord, PurchaseOrder
from agent.core import run_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initialising database...")
    init_db()
    logger.info("Agent ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Healthcare Inventory AI Agent API",
    description="AI-powered supply chain management for 4,000+ healthcare SKUs",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response schemas ───────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    response: str
    session_id: Optional[str] = None


class StockSummary(BaseModel):
    total_skus: int
    below_par_count: int
    out_of_stock_count: int
    expiring_30d_count: int


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok", "model": settings.model_name}


@app.post("/query", response_model=QueryResponse)
async def agent_query(request: QueryRequest):
    """
    Send a natural language query to the AI agent.

    Example: {"query": "What's below PAR in ICU-1?"}
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        response = run_query(request.query)
        return QueryResponse(response=response, session_id=request.session_id)
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/inventory/summary", response_model=StockSummary)
def inventory_summary(db=Depends(get_db_dependency)):
    """Quick dashboard summary of inventory health."""
    from datetime import date, timedelta
    from sqlalchemy import func

    total = db.query(func.count(SKU.id)).scalar()

    below_par = db.query(func.count(InventoryRecord.id)).join(SKU).filter(
        InventoryRecord.quantity_on_hand < SKU.reorder_point
    ).scalar()

    out_of_stock = db.query(func.count(InventoryRecord.id)).filter(
        InventoryRecord.quantity_on_hand == 0
    ).scalar()

    cutoff = date.today() + timedelta(days=30)
    expiring = db.query(func.count(InventoryRecord.id)).filter(
        InventoryRecord.expiry_date.isnot(None),
        InventoryRecord.expiry_date <= cutoff,
        InventoryRecord.quantity_on_hand > 0,
    ).scalar()

    return StockSummary(
        total_skus=total or 0,
        below_par_count=below_par or 0,
        out_of_stock_count=out_of_stock or 0,
        expiring_30d_count=expiring or 0,
    )


@app.get("/inventory/below-par")
def items_below_par(
    category: Optional[str] = None,
    location_id: Optional[str] = None,
    limit: int = 50,
    db=Depends(get_db_dependency),
):
    """List all items currently below PAR level."""
    query = db.query(InventoryRecord, SKU).join(SKU).filter(
        InventoryRecord.quantity_on_hand < SKU.reorder_point
    )
    if category:
        query = query.filter(SKU.category == category)
    if location_id:
        query = query.filter(InventoryRecord.location_id == location_id)

    results = query.limit(limit).all()
    return [
        {
            "sku_id": sku.id,
            "name": sku.name,
            "category": sku.category.value,
            "abc_class": sku.abc_class.value,
            "quantity_on_hand": inv.quantity_on_hand,
            "reorder_point": sku.reorder_point,
            "location_id": inv.location_id,
            "gap": sku.reorder_point - inv.quantity_on_hand,
        }
        for inv, sku in results
    ]


@app.get("/orders")
def list_purchase_orders(
    status: Optional[str] = None,
    limit: int = 20,
    db=Depends(get_db_dependency),
):
    """List purchase orders, optionally filtered by status."""
    query = db.query(PurchaseOrder)
    if status:
        query = query.filter(PurchaseOrder.status == status)
    orders = query.order_by(PurchaseOrder.requested_at.desc()).limit(limit).all()
    return [
        {
            "id": o.id,
            "supplier_id": o.supplier_id,
            "status": o.status.value,
            "total_value": o.total_value,
            "expected_delivery": o.expected_delivery.isoformat() if o.expected_delivery else None,
            "requested_at": o.requested_at.isoformat(),
        }
        for o in orders
    ]

@app.post("/admin/seed")
def seed_database():
    """Seed the database with demo data."""
    try:
        from scripts.seed_data import seed
        seed()
        return {"status": "success", "message": "Database seeded with 4000 SKUs"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
