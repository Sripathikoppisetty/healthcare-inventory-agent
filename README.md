# Healthcare Supply Chain Inventory Agent

AI agent for managing **4,000 SKU** healthcare inventory (SSM Health scale).  
Built with **LangGraph + Groq (llama-3.3-70b)** in Python.

## Features

- Natural language queries: *"Which surgical gloves are below PAR level in OR-3?"*
- Auto-reorder with configurable rules (PAR level, ABC class, lead time)
- Expiry scanning & FIFO alerting
- Demand forecasting (7/14/30-day windows)
- ABC/VED analysis across 4,000 SKUs
- Compliance checks (FDA, DEA controlled substances, formulary)
- Cross-location stock transfers
- Anomaly detection (usage spikes, shrinkage)
- REST API via FastAPI + scheduled background jobs

## Quick Start

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Set environment variables
cp .env.example .env
# Edit .env → add GROQ_API_KEY

# 3. Seed demo data (4000 SKUs)
python scripts/seed_data.py

# 4. Start the API server
uvicorn api.server:app --reload

# 5. Or run the agent CLI
python -m agent.cli "What items are critically low in ICU-1?"
```

## Architecture

```
healthcare-inventory-agent/
├── agent/
│   ├── core.py          # LangGraph ReAct agent
│   ├── state.py         # Agent state schema
│   ├── prompts.py       # System prompt + few-shot examples
│   └── cli.py           # CLI entry point
├── tools/
│   ├── inventory.py     # check_stock, reorder_item, transfer_sku, bulk_update
│   ├── analytics.py     # demand_forecast, abc_analysis, anomaly_detection
│   ├── compliance.py    # compliance_check, expiry_scan
│   └── supplier.py      # supplier_lookup
├── data/
│   ├── database.py      # SQLite/Postgres ORM (SQLAlchemy)
│   ├── models.py        # SKU, InventoryRecord, PurchaseOrder, Supplier
│   └── seed.py          # Demo data generator
├── api/
│   ├── server.py        # FastAPI app
│   └── routes.py        # /query, /inventory, /orders, /alerts
├── scheduler/
│   └── jobs.py          # APScheduler: daily expiry scan, reorder check
├── config/
│   └── settings.py      # Pydantic settings (env vars)
└── scripts/
    └── seed_data.py     # One-time data seed
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Your Groq API key |
| `DATABASE_URL` | SQLite (default) or Postgres |
| `REDIS_URL` | Optional Redis for caching |
| `LANGCHAIN_API_KEY` | Optional LangSmith tracing |
| `ALERT_EMAIL` | Where to send low-stock alerts |

## Example Queries

```
"Show me all items below PAR level in Building A"
"Reorder all Class A items with less than 3 days of stock"
"Which medications expire within 30 days?"
"Generate ABC analysis for the surgical supply category"
"Flag any SKUs with usage anomalies this week"
"What's the demand forecast for N95 masks next 14 days?"
"Transfer 200 units of SKU-1042 from Central Supply to ICU-2"
```
