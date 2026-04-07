"""
main.py — Entry point for the Stock Signal Bot.

Usage:
  python main.py               # Normal start: setup if needed, then dashboard + engine
  python main.py --test --ticker AAPL          # Run test scan, no Telegram
  python main.py --test --ticker AAPL --send   # Run test scan, send Telegram
  python main.py --pulse                       # Run one pulse scan now
  python main.py --deep                        # Run one deep scan now
  streamlit run dashboard.py                   # Dashboard only
"""
import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

# ── Logging setup ─────────────────────────────────────────────────────────────
import logging.handlers

LOG_PATH = BASE_DIR / "logs" / "signals.log"
LOG_PATH.parent.mkdir(exist_ok=True)

root_log = logging.getLogger()
root_log.setLevel(logging.INFO)

file_handler = logging.handlers.RotatingFileHandler(
    LOG_PATH, maxBytes=10 * 1024 * 1024, backupCount=5
)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
root_log.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
root_log.addHandler(console_handler)

log = logging.getLogger(__name__)


def load_portfolio() -> dict:
    path = BASE_DIR / "portfolio.json"
    with open(path) as f:
        return json.load(f)


def has_holdings(portfolio: dict) -> bool:
    return bool(portfolio.get("holdings"))


def launch_dashboard():
    """Start Streamlit dashboard as a subprocess and open browser."""
    log.info("Launching Streamlit dashboard on port 8501...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run",
         str(BASE_DIR / "dashboard.py"),
         "--server.port", "8501",
         "--server.headless", "true",   # must be true in subprocess
         "--server.runOnSave", "false",
         "--browser.gatherUsageStats", "false"],
        stdout=open(BASE_DIR / "logs" / "dashboard.log", "w"),
        stderr=subprocess.STDOUT,
    )
    log.info("Dashboard PID: %d — http://localhost:8501", proc.pid)
    # Wait for Streamlit to bind then open browser
    for _ in range(15):
        time.sleep(1)
        try:
            import urllib.request
            urllib.request.urlopen("http://localhost:8501/_stcore/health", timeout=1)
            break
        except Exception:
            continue
    try:
        import webbrowser
        webbrowser.open("http://localhost:8501")
        log.info("Browser opened at http://localhost:8501")
    except Exception:
        pass
    return proc


def run_test(ticker: str, send_telegram: bool = False):
    """Test mode: run a single deep scan on a ticker."""
    from src.database import init_db
    from src.crew import run_deep_scan

    init_db()
    log.info("TEST MODE: scanning %s (send_telegram=%s)", ticker, send_telegram)

    # Temporarily patch telegram if not sending
    if not send_telegram:
        import src.tools.telegram_tool as tg_mod
        original_send = tg_mod.send_alert
        tg_mod.send_alert = lambda msg, **kw: (log.info("TELEGRAM (suppressed): %s", msg[:100]), True)[1]

    portfolio = {}
    try:
        portfolio = load_portfolio()
    except Exception:
        portfolio = {"user_name": "Test", "budget_usd": 10000, "holdings": [], "watchlist": []}

    holding = next((h for h in portfolio.get("holdings", []) if h["ticker"] == ticker), {})
    results = run_deep_scan(ticker, holding, portfolio)

    print("\n" + "=" * 60)
    print(f"SCAN RESULTS FOR {ticker}")
    print("=" * 60)
    for agent, output in results.items():
        print(f"\n--- {agent.upper()} ---")
        print(str(output)[:400])
    print("=" * 60)

    if not send_telegram:
        import src.tools.telegram_tool as tg_mod
        tg_mod.send_alert = original_send


def main():
    parser = argparse.ArgumentParser(description="Stock Signal Bot")
    parser.add_argument("--test", action="store_true", help="Run test scan (no Telegram)")
    parser.add_argument("--ticker", type=str, help="Ticker for test/pulse/deep")
    parser.add_argument("--send", action="store_true", help="Send Telegram in test mode")
    parser.add_argument("--pulse", action="store_true", help="Run one pulse scan")
    parser.add_argument("--deep", action="store_true", help="Run one deep scan")
    args = parser.parse_args()

    # ── Test mode ────────────────────────────────────────────────────────────
    if args.test:
        ticker = (args.ticker or "AAPL").upper()
        run_test(ticker, send_telegram=args.send)
        return

    # ── Pulse mode ───────────────────────────────────────────────────────────
    if args.pulse:
        from src.database import init_db
        from src.crew import run_pulse_scan
        init_db()
        portfolio = load_portfolio()
        ticker = (args.ticker or portfolio.get("holdings", [{}])[0].get("ticker", "AAPL")).upper()
        result = run_pulse_scan(ticker, portfolio)
        print(json.dumps(result, indent=2))
        return

    # ── Deep mode ────────────────────────────────────────────────────────────
    if args.deep:
        from src.database import init_db
        from src.crew import run_deep_scan
        init_db()
        portfolio = load_portfolio()
        ticker = args.ticker
        if not ticker:
            if portfolio.get("holdings"):
                ticker = portfolio["holdings"][0]["ticker"]
            else:
                print("No ticker specified and no holdings found.")
                return
        holding = next((h for h in portfolio.get("holdings", []) if h["ticker"] == ticker), {})
        run_deep_scan(ticker.upper(), holding, portfolio)
        return

    # ── Normal startup ────────────────────────────────────────────────────────
    from src.database import init_db
    init_db()

    # Check portfolio
    try:
        portfolio = load_portfolio()
    except (FileNotFoundError, json.JSONDecodeError):
        portfolio = {"holdings": []}

    if not has_holdings(portfolio):
        log.info("No holdings found. Running first-time setup...")
        import setup
        setup.main()
        portfolio = load_portfolio()

    # Send startup message
    name = portfolio.get("user_name", "Investor")
    tickers_str = ", ".join(h["ticker"] for h in portfolio.get("holdings", []))
    startup_msg = (
        f"✅ {name}, your Stock Signal Bot is back online.\n"
        f"Monitoring: {tickers_str or 'no holdings yet'}\n"
        f"Running immediate startup scan..."
    )
    try:
        from src.tools.telegram_tool import send_alert
        send_alert(startup_msg, chat_id=portfolio.get("telegram_chat_id") or None)
    except Exception as exc:
        log.warning("Startup Telegram: %s", exc)

    # Launch dashboard
    dash_proc = launch_dashboard()

    # Start scheduler
    from src.scheduler import build_scheduler
    scheduler = build_scheduler(timezone=portfolio.get("timezone", "Asia/Dubai"))
    scheduler.start()
    log.info("Scheduler started.")

    # Immediate deep scan on startup
    log.info("Running immediate startup deep scan...")
    from src.crew import run_deep_scan
    for h in portfolio.get("holdings", []):
        try:
            run_deep_scan(h["ticker"], h, portfolio)
            time.sleep(5)
        except Exception as exc:
            log.error("Startup scan %s: %s", h["ticker"], exc)

    # Keep alive forever
    log.info("System running. Dashboard: http://localhost:8501")
    try:
        while True:
            time.sleep(60)
            # Restart dashboard if it crashed
            if dash_proc.poll() is not None:
                log.warning("Dashboard crashed. Restarting...")
                dash_proc = launch_dashboard()
    except KeyboardInterrupt:
        log.info("Shutting down...")
        scheduler.shutdown()
        dash_proc.terminate()


if __name__ == "__main__":
    main()
