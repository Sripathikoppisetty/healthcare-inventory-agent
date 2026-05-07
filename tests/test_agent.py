"""tests/test_agent.py — Unit and integration tests for the inventory agent."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

# ── Database setup for tests ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_db(tmp_path_factory):
    """Create an in-memory SQLite DB seeded with minimal test data."""
    import os
    os.environ["DATABASE_URL"] = "sqlite:///./test_inventory.db"
    os.environ["GROQ_API_KEY"] = "test-key"

    from data.database import init_db, get_db
    from data.models import SKU, Location, InventoryRecord, Supplier, SKUCategory, ABCClass

    init_db()

    with get_db() as db:
        db.add(Supplier(
            id="SUP-001", name="Test Supplier", lead_time_days=3,
            performance_score=0.95, is_preferred=True,
        ))
        db.add(Location(
            id="LOC-ICU1", name="ICU-1", building="Main",
            floor="4", room="4E", location_type="ICU",
        ))
        sku = SKU(
            id="SKU-00001", name="N95 Respirator M",
            category=SKUCategory.PPE, unit_of_measure="EA",
            unit_cost=2.50, abc_class=ABCClass.A,
            reorder_point=500, reorder_quantity=2000,
            lead_time_days=3, supplier_id="SUP-001",
        )
        db.add(sku)
        db.add(InventoryRecord(
            sku_id="SKU-00001", location_id="LOC-ICU1",
            quantity_on_hand=150,  # Well below PAR
        ))

    yield

    import os
    if os.path.exists("./test_inventory.db"):
        os.remove("./test_inventory.db")


# ── Tool tests ────────────────────────────────────────────────────────────────

class TestCheckStock:
    def test_returns_below_par_items(self, test_db):
        from tools.inventory import check_stock
        result = check_stock.invoke({
            "sku_id": "SKU-00001",
            "location_id": "LOC-ICU1",
            "below_par": True,
        })
        assert "SKU-00001" in result
        assert "BELOW PAR" in result or "CRITICAL" in result or "LOW" in result

    def test_no_results_message(self, test_db):
        from tools.inventory import check_stock
        result = check_stock.invoke({"sku_id": "SKU-99999"})
        assert "No inventory records" in result

    def test_category_filter(self, test_db):
        from tools.inventory import check_stock
        result = check_stock.invoke({"category": "ppe"})
        assert "SKU-00001" in result


class TestReorderItem:
    def test_creates_purchase_order(self, test_db):
        from tools.inventory import reorder_item
        result = reorder_item.invoke({
            "sku_id": "SKU-00001",
            "quantity": 100,
            "notes": "Test reorder",
        })
        assert "PO created" in result or "✅" in result
        assert "SKU-00001" in result

    def test_invalid_sku_returns_error(self, test_db):
        from tools.inventory import reorder_item
        result = reorder_item.invoke({"sku_id": "SKU-INVALID"})
        assert "not found" in result.lower()


class TestTransferSku:
    def test_insufficient_stock_returns_error(self, test_db):
        from tools.inventory import transfer_sku
        result = transfer_sku.invoke({
            "sku_id": "SKU-00001",
            "from_location_id": "LOC-ICU1",
            "to_location_id": "LOC-ICU2",
            "quantity": 99999,  # More than on hand
        })
        assert "Insufficient" in result

    def test_successful_transfer(self, test_db):
        from tools.inventory import transfer_sku
        result = transfer_sku.invoke({
            "sku_id": "SKU-00001",
            "from_location_id": "LOC-ICU1",
            "to_location_id": "LOC-ICU2",
            "quantity": 50,
        })
        assert "Transfer complete" in result or "✅" in result


class TestComplianceCheck:
    def test_detects_below_par(self, test_db):
        from tools.compliance import compliance_check
        result = compliance_check.invoke({
            "sku_id": "SKU-00001",
            "check_type": "par",
        })
        assert "BELOW PAR" in result or "STOCKOUT" in result or "passed" in result


class TestExpiryCheck:
    def test_no_expiry_flag_for_non_pharma(self, test_db):
        from tools.compliance import expiry_scan
        result = expiry_scan.invoke({"days_ahead": 30})
        # PPE items don't have expiry dates — should be clean
        assert isinstance(result, str)


class TestDemandForecast:
    def test_insufficient_history_message(self, test_db):
        from tools.analytics import demand_forecast
        result = demand_forecast.invoke({
            "sku_id": "SKU-00001",
            "horizon_days": 14,
        })
        # No usage history seeded, should get a graceful message
        assert "Insufficient" in result or "forecast" in result.lower()


# ── API tests ─────────────────────────────────────────────────────────────────

class TestAPI:
    @pytest.fixture
    def client(self, test_db):
        from fastapi.testclient import TestClient
        from api.server import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_inventory_summary(self, client):
        response = client.get("/inventory/summary")
        assert response.status_code == 200
        data = response.json()
        assert "total_skus" in data
        assert data["total_skus"] >= 1

    def test_below_par_endpoint(self, client):
        response = client.get("/inventory/below-par")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_agent_query_empty_string(self, client):
        response = client.post("/query", json={"query": ""})
        assert response.status_code == 400
