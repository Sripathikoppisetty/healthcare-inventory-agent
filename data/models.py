"""data/models.py — SQLAlchemy ORM models for healthcare inventory."""

from datetime import datetime, date
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Date, DateTime,
    ForeignKey, Text, Enum, Index
)
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


class ABCClass(str, enum.Enum):
    A = "A"   # High value, ~70% spend
    B = "B"   # Medium value, ~20% spend
    C = "C"   # Low value, ~10% spend


class SKUCategory(str, enum.Enum):
    SURGICAL = "surgical"
    PHARMACEUTICAL = "pharmaceutical"
    MEDICAL_DEVICE = "medical_device"
    PPE = "ppe"
    LAB = "lab"
    NUTRITION = "nutrition"
    RADIOLOGY = "radiology"
    OTHER = "other"


class OrderStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class SKU(Base):
    """Master item record — one row per unique product."""
    __tablename__ = "skus"

    id = Column(String(20), primary_key=True)           # e.g. "SKU-00042"
    name = Column(String(200), nullable=False)
    description = Column(Text)
    category = Column(Enum(SKUCategory), nullable=False)
    unit_of_measure = Column(String(20), default="EA")  # EA, BX, CS, etc.
    unit_cost = Column(Float, nullable=False)
    abc_class = Column(Enum(ABCClass), default=ABCClass.C)
    is_controlled = Column(Boolean, default=False)       # DEA controlled substance
    is_formulary = Column(Boolean, default=True)
    reorder_point = Column(Integer, nullable=False)      # PAR level (units)
    reorder_quantity = Column(Integer, nullable=False)   # Economic order qty
    lead_time_days = Column(Integer, default=3)
    supplier_id = Column(String(20), ForeignKey("suppliers.id"))
    manufacturer = Column(String(100))
    manufacturer_part_number = Column(String(50))
    ndc_number = Column(String(20))                     # For pharmaceuticals
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    supplier = relationship("Supplier", back_populates="skus")
    inventory_records = relationship("InventoryRecord", back_populates="sku")
    purchase_order_lines = relationship("PurchaseOrderLine", back_populates="sku")

    __table_args__ = (
        Index("idx_sku_category", "category"),
        Index("idx_sku_abc", "abc_class"),
    )


class Location(Base):
    """Physical storage location (OR suite, ICU, central supply, etc.)."""
    __tablename__ = "locations"

    id = Column(String(20), primary_key=True)
    name = Column(String(100), nullable=False)
    building = Column(String(50))
    floor = Column(String(10))
    room = Column(String(20))
    location_type = Column(String(30))  # OR, ICU, floor_stock, central_supply

    inventory_records = relationship("InventoryRecord", back_populates="location")


class InventoryRecord(Base):
    """Real-time stock level per SKU per location."""
    __tablename__ = "inventory_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_id = Column(String(20), ForeignKey("skus.id"), nullable=False)
    location_id = Column(String(20), ForeignKey("locations.id"), nullable=False)
    quantity_on_hand = Column(Integer, default=0)
    quantity_on_order = Column(Integer, default=0)
    quantity_reserved = Column(Integer, default=0)
    last_count_date = Column(Date)
    last_received_date = Column(Date)
    expiry_date = Column(Date)                  # Earliest expiry in this lot
    lot_number = Column(String(50))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sku = relationship("SKU", back_populates="inventory_records")
    location = relationship("Location", back_populates="inventory_records")

    __table_args__ = (
        Index("idx_inv_sku_loc", "sku_id", "location_id"),
        Index("idx_inv_expiry", "expiry_date"),
    )


class UsageHistory(Base):
    """Daily consumption records — used for demand forecasting."""
    __tablename__ = "usage_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_id = Column(String(20), ForeignKey("skus.id"), nullable=False)
    location_id = Column(String(20), ForeignKey("locations.id"), nullable=False)
    usage_date = Column(Date, nullable=False)
    quantity_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_usage_sku_date", "sku_id", "usage_date"),
    )


class Supplier(Base):
    """Vendor/supplier master."""
    __tablename__ = "suppliers"

    id = Column(String(20), primary_key=True)
    name = Column(String(150), nullable=False)
    contact_name = Column(String(100))
    email = Column(String(100))
    phone = Column(String(20))
    contract_number = Column(String(50))
    lead_time_days = Column(Integer, default=3)
    performance_score = Column(Float, default=1.0)  # 0.0–1.0
    is_preferred = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    skus = relationship("SKU", back_populates="supplier")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")


class PurchaseOrder(Base):
    """Purchase order header."""
    __tablename__ = "purchase_orders"

    id = Column(String(30), primary_key=True)
    supplier_id = Column(String(20), ForeignKey("suppliers.id"), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.DRAFT)
    requested_by = Column(String(100), default="AI-Agent")
    requested_at = Column(DateTime, default=datetime.utcnow)
    expected_delivery = Column(Date)
    total_value = Column(Float, default=0.0)
    notes = Column(Text)

    supplier = relationship("Supplier", back_populates="purchase_orders")
    lines = relationship("PurchaseOrderLine", back_populates="purchase_order")


class PurchaseOrderLine(Base):
    """Individual line item within a purchase order."""
    __tablename__ = "purchase_order_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    po_id = Column(String(30), ForeignKey("purchase_orders.id"), nullable=False)
    sku_id = Column(String(20), ForeignKey("skus.id"), nullable=False)
    quantity_ordered = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    line_total = Column(Float)

    purchase_order = relationship("PurchaseOrder", back_populates="lines")
    sku = relationship("SKU", back_populates="purchase_order_lines")
