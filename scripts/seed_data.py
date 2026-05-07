"""scripts/seed_data.py — Generate realistic demo data for 4,000 healthcare SKUs."""

import random
import uuid
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

from data.database import init_db, get_db
from data.models import (
    SKU, Location, InventoryRecord, Supplier, UsageHistory,
    ABCClass, SKUCategory
)

random.seed(42)

# ── Suppliers ─────────────────────────────────────────────────────────────────
SUPPLIERS = [
    ("SUP-001", "Medline Industries", "Sarah Johnson", "sjohnson@medline.com", "800-633-5463", "CONTRACT-2024-001", 3, True),
    ("SUP-002", "Cardinal Health", "Mike Davis", "mdavis@cardinal.com", "614-757-5000", "CONTRACT-2024-002", 4, True),
    ("SUP-003", "Owens & Minor", "Lisa Chen", "lchen@owensminor.com", "804-723-7000", "CONTRACT-2024-003", 5, True),
    ("SUP-004", "McKesson Medical", "Tom Wilson", "twilson@mckesson.com", "800-625-5766", "CONTRACT-2024-004", 2, False),
    ("SUP-005", "Henry Schein", "Amy Brown", "abrown@henryschein.com", "800-472-4346", "CONTRACT-2024-005", 6, False),
    ("SUP-006", "Baxter International", "Chris Lee", "clee@baxter.com", "224-948-2000", "CONTRACT-2024-006", 7, False),
    ("SUP-007", "Abbott Labs", "Pat Garcia", "pgarcia@abbott.com", "224-667-6100", "CONTRACT-2024-007", 5, False),
    ("SUP-008", "Becton Dickinson", "Sam Martinez", "smartinez@bd.com", "201-847-6800", "CONTRACT-2024-008", 4, True),
]

# ── Locations ─────────────────────────────────────────────────────────────────
LOCATIONS = [
    ("LOC-CS", "Central Supply", "Main", "B1", "CS-01", "central_supply"),
    ("LOC-ICU1", "ICU-1", "Main", "4", "4E", "ICU"),
    ("LOC-ICU2", "ICU-2", "Main", "4", "4W", "ICU"),
    ("LOC-OR1", "OR Suite 1", "Main", "2", "OR-1", "OR"),
    ("LOC-OR2", "OR Suite 2", "Main", "2", "OR-2", "OR"),
    ("LOC-OR3", "OR Suite 3", "Main", "2", "OR-3", "OR"),
    ("LOC-OR4", "OR Suite 4", "Main", "2", "OR-4", "OR"),
    ("LOC-OR5", "OR Suite 5", "Main", "2", "OR-5", "OR"),
    ("LOC-OR6", "OR Suite 6", "Main", "2", "OR-6", "OR"),
    ("LOC-ED", "Emergency Department", "Main", "1", "ED", "ED"),
    ("LOC-PHARM", "Pharmacy", "Main", "1", "PH-01", "pharmacy"),
    ("LOC-3N", "Floor 3 North", "Main", "3", "3N", "floor_stock"),
    ("LOC-4N", "Floor 4 North", "Main", "4", "4N", "floor_stock"),
    ("LOC-5N", "Floor 5 North", "Main", "5", "5N", "floor_stock"),
    ("LOC-RAD", "Radiology", "Annex", "1", "RAD-01", "radiology"),
    ("LOC-LAB", "Laboratory", "Annex", "1", "LAB-01", "lab"),
]

# ── SKU name templates by category ────────────────────────────────────────────
SKU_TEMPLATES = {
    SKUCategory.SURGICAL: [
        ("Surgical Gloves Latex {size}", 8.50, 200, 500),
        ("Surgical Gloves Nitrile {size}", 12.00, 200, 500),
        ("Suture {type} {size}", 45.00, 50, 100),
        ("Surgical Drape {size}", 18.00, 30, 60),
        ("Electrosurgical Pencil", 22.00, 40, 100),
        ("Staple Reloads {size}", 85.00, 20, 40),
        ("Trocar {size}mm", 95.00, 15, 30),
        ("Laparoscopic Scissor", 120.00, 10, 20),
        ("Retractor {type}", 35.00, 20, 40),
        ("Bone Cement {type}", 210.00, 8, 16),
    ],
    SKUCategory.PHARMACEUTICAL: [
        ("Morphine Sulfate {dose}mg", 8.20, 100, 200),
        ("Fentanyl {dose}mcg", 12.50, 80, 160),
        ("Normal Saline 0.9% {vol}mL", 2.10, 500, 1000),
        ("Dextrose 5% {vol}mL", 2.40, 400, 800),
        ("Heparin {dose}units", 18.00, 60, 120),
        ("Vancomycin {dose}g", 24.00, 50, 100),
        ("Piperacillin-Tazobactam {dose}g", 32.00, 40, 80),
        ("Potassium Chloride {dose}mEq", 6.50, 80, 160),
        ("Propofol {vol}mL", 28.00, 60, 120),
        ("Midazolam {dose}mg", 15.00, 70, 140),
    ],
    SKUCategory.PPE: [
        ("N95 Respirator {size}", 2.50, 500, 2000),
        ("Surgical Mask Level {level}", 0.35, 1000, 5000),
        ("Isolation Gown {size}", 1.80, 300, 1000),
        ("Face Shield", 3.20, 200, 500),
        ("Exam Gloves Nitrile {size}", 0.12, 2000, 5000),
        ("Exam Gloves Latex {size}", 0.09, 2000, 5000),
        ("Shoe Cover", 0.18, 500, 2000),
        ("Bouffant Cap", 0.08, 1000, 3000),
        ("Goggles Safety", 4.50, 100, 200),
        ("Chemical Splash Apron", 6.80, 50, 100),
    ],
    SKUCategory.MEDICAL_DEVICE: [
        ("IV Catheter {gauge}G", 1.20, 200, 500),
        ("Foley Catheter {fr}Fr", 3.80, 80, 200),
        ("NG Tube {fr}Fr", 4.20, 60, 120),
        ("Central Line Kit {lumen}-lumen", 45.00, 20, 40),
        ("Pulse Oximeter Probe {type}", 8.50, 100, 200),
        ("Blood Pressure Cuff {size}", 12.00, 50, 100),
        ("Glucose Test Strips {cnt}ct", 28.00, 100, 200),
        ("Wound Dressing {size}", 5.60, 100, 300),
        ("Surgical Tape {width}in", 2.10, 200, 500),
        ("Syringe {vol}mL", 0.45, 1000, 3000),
    ],
    SKUCategory.LAB: [
        ("Blood Culture Bottle Aerobic", 4.20, 200, 500),
        ("Blood Culture Bottle Anaerobic", 4.20, 200, 500),
        ("Vacutainer {color} Top {vol}mL", 0.85, 500, 2000),
        ("Urine Collection Cup", 0.60, 300, 1000),
        ("Swab Culture {type}", 1.80, 200, 500),
        ("Glucose Reagent Strip", 0.35, 500, 2000),
        ("Troponin Reagent Kit", 185.00, 10, 20),
        ("PT/INR Reagent", 95.00, 20, 40),
        ("CBC Reagent Kit", 120.00, 15, 30),
        ("Urinalysis Strips {cnt}ct", 22.00, 50, 100),
    ],
    SKUCategory.NUTRITION: [
        ("Enteral Formula {type} {vol}mL", 8.50, 100, 300),
        ("IV Lipid Emulsion 20% {vol}mL", 32.00, 30, 60),
        ("TPN Base Solution {vol}mL", 45.00, 20, 40),
        ("Feeding Tube Set {fr}Fr", 12.00, 50, 100),
        ("Oral Supplement {flavor}", 4.20, 200, 400),
    ],
    SKUCategory.RADIOLOGY: [
        ("Contrast Medium Iohexol {dose}mL", 28.00, 30, 80),
        ("Barium Sulfate {vol}mL", 15.00, 20, 50),
        ("Radiation Dosimeter", 18.00, 30, 60),
        ("Lead Apron {size}", 245.00, 5, 10),
        ("Film Developer Chemicals", 85.00, 8, 16),
    ],
}

SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
DOSES = ["5", "10", "20", "50", "100", "250", "500"]
VOLS = ["50", "100", "250", "500", "1000"]
TYPES = ["Silk", "Nylon", "Chromic", "Vicryl", "PDS"]
COLORS = ["Red", "Purple", "Blue", "Green", "Gold", "Grey"]


def rand_variant(template: str) -> str:
    return (template
            .replace("{size}", random.choice(SIZES))
            .replace("{dose}", random.choice(DOSES))
            .replace("{vol}", random.choice(VOLS))
            .replace("{type}", random.choice(TYPES))
            .replace("{color}", random.choice(COLORS))
            .replace("{gauge}", str(random.choice([14, 16, 18, 20, 22, 24])))
            .replace("{fr}", str(random.choice([8, 10, 12, 14, 16, 18])))
            .replace("{lumen}", str(random.choice([1, 2, 3])))
            .replace("{level}", str(random.choice([1, 2, 3])))
            .replace("{cnt}", str(random.choice([25, 50, 100, 200])))
            .replace("{width}", str(random.choice([1, 2, 3])))
            .replace("{flavor}", random.choice(["Vanilla", "Chocolate", "Strawberry", "Unflavored"]))
            )


def seed():
    init_db()

    with get_db() as db:
        # Clear existing data
        for model in [UsageHistory, InventoryRecord, SKU, Location, Supplier]:
            db.query(model).delete()
        db.flush()

        # ── Suppliers ─────────────────────────────────────────────────────────
        for sid, name, contact, email, phone, contract, lead, preferred in SUPPLIERS:
            db.add(Supplier(
                id=sid, name=name, contact_name=contact, email=email,
                phone=phone, contract_number=contract, lead_time_days=lead,
                performance_score=round(random.uniform(0.75, 1.0), 2),
                is_preferred=preferred,
            ))

        # ── Locations ─────────────────────────────────────────────────────────
        for lid, name, building, floor, room, ltype in LOCATIONS:
            db.add(Location(
                id=lid, name=name, building=building,
                floor=floor, room=room, location_type=ltype,
            ))

        db.flush()

        # ── SKUs — generate 4000 ──────────────────────────────────────────────
        sku_ids = []
        sku_count = 0
        target = 4000

        categories = list(SKU_TEMPLATES.keys())
        # Weight distribution roughly matching real healthcare
        weights = [0.25, 0.22, 0.20, 0.15, 0.10, 0.05, 0.03]

        while sku_count < target:
            cat = random.choices(categories, weights=weights)[0]
            templates = SKU_TEMPLATES[cat]
            template, base_price, base_reorder, base_eoq = random.choice(templates)
            name = rand_variant(template)
            sku_id = f"SKU-{sku_count+1:05d}"
            unit_cost = round(base_price * random.uniform(0.8, 1.3), 2)
            reorder_point = int(base_reorder * random.uniform(0.7, 1.5))
            reorder_qty = int(base_eoq * random.uniform(0.8, 1.4))
            lead_time = random.choice([2, 3, 3, 4, 5, 7, 10])
            annual_spend = unit_cost * reorder_qty * (365 / lead_time)

            # ABC by spend
            r = random.random()
            if r < 0.15:
                abc = ABCClass.A
            elif r < 0.40:
                abc = ABCClass.B
            else:
                abc = ABCClass.C

            is_controlled = cat == SKUCategory.PHARMACEUTICAL and random.random() < 0.15
            supplier_id = random.choice([s[0] for s in SUPPLIERS])

            sku = SKU(
                id=sku_id,
                name=name,
                category=cat,
                unit_of_measure="EA",
                unit_cost=unit_cost,
                abc_class=abc,
                reorder_point=reorder_point,
                reorder_quantity=reorder_qty,
                lead_time_days=lead_time,
                supplier_id=supplier_id,
                is_controlled=is_controlled,
                is_formulary=random.random() > 0.05,
            )
            db.add(sku)
            sku_ids.append(sku_id)
            sku_count += 1

        db.flush()

        # ── Inventory records ─────────────────────────────────────────────────
        # Each SKU gets 1-4 location records
        loc_ids = [l[0] for l in LOCATIONS]
        today = date.today()

        for sku_id in sku_ids:
            sku = db.query(SKU).filter(SKU.id == sku_id).first()
            n_locs = random.choices([1, 2, 3, 4], weights=[0.5, 0.3, 0.15, 0.05])[0]
            chosen_locs = random.sample(loc_ids, min(n_locs, len(loc_ids)))

            for loc_id in chosen_locs:
                # Randomly create low/out-of-stock scenarios (~15% of records)
                r = random.random()
                if r < 0.03:
                    qty = 0
                elif r < 0.15:
                    qty = random.randint(1, sku.reorder_point - 1)
                else:
                    qty = random.randint(sku.reorder_point, sku.reorder_point * 3)

                # Some items have expiry dates
                expiry = None
                lot = None
                if sku.category in (SKUCategory.PHARMACEUTICAL, SKUCategory.LAB, SKUCategory.NUTRITION):
                    days_until_expiry = random.randint(-10, 365)
                    expiry = today + timedelta(days=days_until_expiry)
                    lot = f"LOT-{uuid.uuid4().hex[:8].upper()}"

                db.add(InventoryRecord(
                    sku_id=sku_id,
                    location_id=loc_id,
                    quantity_on_hand=qty,
                    quantity_on_order=random.randint(0, sku.reorder_quantity) if r < 0.2 else 0,
                    last_count_date=today - timedelta(days=random.randint(0, 30)),
                    expiry_date=expiry,
                    lot_number=lot,
                ))

        db.flush()

        # ── Usage history — 90 days ───────────────────────────────────────────
        for sku_id in random.sample(sku_ids, min(500, len(sku_ids))):  # Sample for speed
            loc_id = random.choice(loc_ids)
            sku = db.query(SKU).filter(SKU.id == sku_id).first()
            avg_daily = max(1, sku.reorder_point // 30)

            for d in range(90):
                usage_date = today - timedelta(days=d)
                # Occasionally inject anomaly
                if random.random() < 0.03:
                    qty = avg_daily * random.randint(4, 8)  # Spike
                else:
                    qty = max(0, int(random.gauss(avg_daily, avg_daily * 0.3)))

                db.add(UsageHistory(
                    sku_id=sku_id,
                    location_id=loc_id,
                    usage_date=usage_date,
                    quantity_used=qty,
                ))

        print(f"✅ Seeded: {sku_count} SKUs | {len(LOCATIONS)} locations | {len(SUPPLIERS)} suppliers")
        print("   Usage history added for 500 sample SKUs (90 days)")


if __name__ == "__main__":
    seed()
