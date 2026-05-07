"""scheduler/jobs.py — Scheduled background jobs for automated monitoring."""

import logging
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from agent.core import run_query

logger = logging.getLogger(__name__)


def daily_expiry_scan():
    """Run every morning — flag anything expiring within 30 days."""
    logger.info("Running scheduled expiry scan...")
    result = run_query("Scan all locations for items expiring within 30 days and summarise findings.")
    logger.info(f"Expiry scan result:\n{result}")
    # TODO: send result via email/Slack alert


def daily_reorder_check():
    """Check for items below PAR and auto-create draft POs for Class A items."""
    logger.info("Running scheduled reorder check...")
    result = run_query(
        "Check all Class A items that are below PAR level. "
        "For each one, create a purchase order using the default supplier and economic order quantity."
    )
    logger.info(f"Reorder check result:\n{result}")


def weekly_abc_report():
    """Weekly ABC analysis report — runs every Monday morning."""
    logger.info("Running weekly ABC analysis...")
    result = run_query("Run a full ABC analysis across all SKUs and provide a summary report.")
    logger.info(f"ABC report:\n{result}")


def weekly_anomaly_check():
    """Detect usage anomalies over the past 7 days."""
    logger.info("Running weekly anomaly detection...")
    result = run_query(
        "Check for usage anomalies across all SKUs and locations over the past 7 days. "
        "Flag any items with unusual consumption patterns."
    )
    logger.info(f"Anomaly check result:\n{result}")


def start_scheduler() -> BackgroundScheduler:
    """Create and start the APScheduler with all jobs configured."""
    scheduler = BackgroundScheduler(timezone="America/Chicago")  # SSM Health is Central time

    # Daily 6:00 AM — expiry scan
    scheduler.add_job(
        daily_expiry_scan,
        CronTrigger(hour=6, minute=0),
        id="expiry_scan",
        name="Daily expiry scan",
        replace_existing=True,
    )

    # Daily 6:30 AM — reorder check (Class A items only)
    scheduler.add_job(
        daily_reorder_check,
        CronTrigger(hour=6, minute=30),
        id="reorder_check",
        name="Daily reorder check",
        replace_existing=True,
    )

    # Every Monday 7:00 AM — ABC report
    scheduler.add_job(
        weekly_abc_report,
        CronTrigger(day_of_week="mon", hour=7, minute=0),
        id="abc_report",
        name="Weekly ABC analysis",
        replace_existing=True,
    )

    # Every Sunday 8:00 AM — anomaly detection
    scheduler.add_job(
        weekly_anomaly_check,
        CronTrigger(day_of_week="sun", hour=8, minute=0),
        id="anomaly_check",
        name="Weekly anomaly detection",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started with %d jobs.", len(scheduler.get_jobs()))
    return scheduler
