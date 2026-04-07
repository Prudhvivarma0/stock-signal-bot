"""APScheduler loops for continuous research."""
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.crew import run_deep_scan, run_pulse_scan, run_weekly_debrief
from src.database import save_portfolio_snapshot, upsert_price_snapshot
from src.tools.yfinance_tools import get_latest_price

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
HEALTH_LOG = BASE_DIR / "logs" / "health.log"


def _load_portfolio() -> dict:
    path = BASE_DIR / "portfolio.json"
    with open(path) as f:
        return json.load(f)


def _all_tickers(portfolio: dict) -> list:
    tickers = [h["ticker"] for h in portfolio.get("holdings", [])]
    tickers += portfolio.get("watchlist", [])
    return list(dict.fromkeys(tickers))  # deduplicate, preserve order


def _get_holding(portfolio: dict, ticker: str) -> dict | None:
    for h in portfolio.get("holdings", []):
        if h["ticker"] == ticker:
            return h
    return None


# ── Loop A: Pulse scan every 90 minutes ──────────────────────────────────────
def loop_a_pulse():
    try:
        portfolio = _load_portfolio()
        tickers = _all_tickers(portfolio)
        for ticker in tickers:
            try:
                result = run_pulse_scan(ticker, portfolio)
                if result.get("trigger_emergency"):
                    log.warning("Emergency scan triggered for %s", ticker)
                    loop_c_emergency(ticker)
            except Exception as exc:
                log.error("Pulse scan %s: %s", ticker, exc)
            time.sleep(5)
    except Exception as exc:
        log.error("Loop A error: %s", exc)


# ── Loop B: Deep research twice daily ────────────────────────────────────────
def loop_b_deep():
    try:
        portfolio = _load_portfolio()
        tickers = _all_tickers(portfolio)
        log.info("Starting deep scan cycle — %d tickers", len(tickers))
        for ticker in tickers:
            holding = _get_holding(portfolio, ticker)
            try:
                run_deep_scan(ticker, holding, portfolio)
            except Exception as exc:
                log.error("Deep scan %s: %s", ticker, exc)
            time.sleep(10)
    except Exception as exc:
        log.error("Loop B error: %s", exc)


# ── Loop C: Emergency scan ────────────────────────────────────────────────────
def loop_c_emergency(ticker: str):
    try:
        portfolio = _load_portfolio()
        holding = _get_holding(portfolio, ticker)
        log.info("Emergency scan: %s", ticker)
        run_deep_scan(ticker, holding, portfolio)
    except Exception as exc:
        log.error("Emergency scan %s: %s", ticker, exc)


# ── Loop D: Weekly debrief ────────────────────────────────────────────────────
def loop_d_weekly():
    try:
        portfolio = _load_portfolio()
        run_weekly_debrief(portfolio)
    except Exception as exc:
        log.error("Loop D error: %s", exc)


# ── Price snapshot every 15 minutes ──────────────────────────────────────────
def price_snapshot_loop():
    try:
        portfolio = _load_portfolio()
        tickers = _all_tickers(portfolio)
        total_value = 0.0
        total_invested = 0.0

        for ticker in tickers:
            try:
                price = get_latest_price(ticker)
                if price:
                    upsert_price_snapshot(ticker, price, 0)
                holding = _get_holding(portfolio, ticker)
                if holding and price:
                    total_value += price * holding.get("shares", 0)
                    total_invested += holding.get("entry_price", 0) * holding.get("shares", 0)
            except Exception as exc:
                log.error("Price snapshot %s: %s", ticker, exc)

        if total_invested > 0:
            save_portfolio_snapshot(total_value, total_invested)
    except Exception as exc:
        log.error("Price snapshot loop: %s", exc)


# ── Health ping every hour ────────────────────────────────────────────────────
def health_ping():
    try:
        with open(HEALTH_LOG, "a") as f:
            f.write(f"alive {datetime.utcnow().isoformat()}\n")
    except Exception as exc:
        log.error("Health ping: %s", exc)


# ── Telegram dead letter retry ────────────────────────────────────────────────
def retry_dead_letters():
    try:
        from src.tools.telegram_tool import retry_dead_letters as _retry
        _retry()
    except Exception as exc:
        log.error("Dead letter retry: %s", exc)


def build_scheduler(timezone: str = "Asia/Dubai") -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=timezone)

    # Loop A — pulse every 90 minutes, 24/7
    scheduler.add_job(loop_a_pulse, IntervalTrigger(minutes=90), id="pulse_scan",
                      max_instances=1, coalesce=True)

    # Loop B — deep scan at 7AM and 7PM Dubai time
    scheduler.add_job(loop_b_deep, CronTrigger(hour="7,19", minute=0, timezone=timezone),
                      id="deep_scan", max_instances=1, coalesce=True)

    # Loop D — weekly debrief every Sunday 8AM
    scheduler.add_job(loop_d_weekly, CronTrigger(day_of_week="sun", hour=8, minute=0, timezone=timezone),
                      id="weekly_debrief", max_instances=1, coalesce=True)

    # Price snapshots every 15 minutes
    scheduler.add_job(price_snapshot_loop, IntervalTrigger(minutes=15), id="price_snapshots",
                      max_instances=1, coalesce=True)

    # Health ping every hour
    scheduler.add_job(health_ping, IntervalTrigger(hours=1), id="health_ping",
                      max_instances=1, coalesce=True)

    # Dead letter retry every 30 minutes
    scheduler.add_job(retry_dead_letters, IntervalTrigger(minutes=30), id="dlq_retry",
                      max_instances=1, coalesce=True)

    return scheduler
