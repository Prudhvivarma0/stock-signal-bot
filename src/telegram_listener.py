"""Telegram command listener — polls for incoming messages and runs scans.

Supported commands (send these to your bot on Telegram):
  /scan NVDA          — full deep scan, sends alert if warranted
  /scan               — deep scan all holdings
  /pulse NVDA         — quick pulse scan (news + price)
  /status             — current portfolio P&L snapshot
  /help               — list of commands
  anything else       — routed through the AI chat agent
"""
import json
import logging
import os
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

HELP_TEXT = (
    "Stock Signal Bot commands:\n\n"
    "/scan NVDA — deep scan a stock (any ticker, not just portfolio)\n"
    "/scan — deep scan all holdings\n"
    "/pulse NVDA — quick news + price check\n"
    "/status — portfolio P&L snapshot\n"
    "/add TSLA 5 220.50 — add stock (ticker, shares, price)\n"
    "/remove TSLA — remove from portfolio\n"
    "/reset_alerts — clear recent alert history (allows resending)\n"
    "/help — this message\n\n"
    "Or plain English:\n"
    "  'Should I buy EMAAR?'\n"
    "  'Should I buy more SALIK?'\n"
    "  'I bought 5 shares of TSLA at $220'\n"
    "  'what is my total P&L?'"
)


def _reply(text: str, chat_id: str = None):
    """Send a reply back to Telegram."""
    from src.tools.telegram_tool import send_alert
    send_alert(text, chat_id=chat_id or CHAT_ID)


def _load_portfolio() -> dict:
    path = BASE_DIR / "portfolio.json"
    with open(path) as f:
        return json.load(f)


def _handle_message(text: str, chat_id: str):
    """Parse and execute a message from Telegram."""
    text = text.strip()
    lower = text.lower()

    # /help
    if lower in ("/help", "help"):
        _reply(HELP_TEXT, chat_id)
        return

    # /status
    if lower in ("/status", "status"):
        _handle_status(chat_id)
        return

    # /scan [TICKER]
    if lower.startswith("/scan") or lower.startswith("scan "):
        parts = text.split()
        ticker = parts[1].upper() if len(parts) > 1 else None
        threading.Thread(target=_handle_scan, args=(ticker, chat_id), daemon=True).start()
        if ticker:
            _reply(f"Starting deep scan on {ticker}... I'll message you when it's done.", chat_id)
        else:
            _reply("Starting deep scan on all holdings... I'll message you when each one is done.", chat_id)
        return

    # /pulse [TICKER]
    if lower.startswith("/pulse") or lower.startswith("pulse "):
        parts = text.split()
        ticker = parts[1].upper() if len(parts) > 1 else None
        threading.Thread(target=_handle_pulse, args=(ticker, chat_id), daemon=True).start()
        name = ticker or "all holdings"
        _reply(f"Running pulse scan on {name}...", chat_id)
        return

    # /add TICKER SHARES PRICE  e.g. /add TSLA 5 220.50
    if lower.startswith("/add "):
        parts = text.split()
        if len(parts) >= 4:
            try:
                ticker = parts[1].upper()
                shares = float(parts[2])
                price = float(parts[3].replace("$", ""))
                stop = float(parts[4]) if len(parts) > 4 else 8.0
                _handle_add(ticker, shares, price, stop, chat_id)
            except ValueError:
                _reply("Format: /add TICKER SHARES PRICE\nExample: /add TSLA 5 220.50", chat_id)
        else:
            _reply("Format: /add TICKER SHARES PRICE\nExample: /add TSLA 5 220.50", chat_id)
        return

    # /remove TICKER
    if lower.startswith("/remove "):
        parts = text.split()
        if len(parts) >= 2:
            _handle_remove(parts[1].upper(), chat_id)
        else:
            _reply("Format: /remove TICKER\nExample: /remove TSLA", chat_id)
        return

    # /reset_alerts — clear alert history so alerts can be re-sent
    if lower in ("/reset_alerts", "reset_alerts"):
        _handle_reset_alerts(chat_id)
        return

    # Anything else — route through AI chat agent
    threading.Thread(target=_handle_chat, args=(text, chat_id), daemon=True).start()


def _handle_scan(ticker: str | None, chat_id: str):
    try:
        from src.crew import run_deep_scan
        from src.database import init_db
        init_db()
        portfolio = _load_portfolio()

        tickers = (
            [ticker] if ticker
            else [h["ticker"] for h in portfolio.get("holdings", [])]
        )

        for i, t in enumerate(tickers):
            # Look up holding — works for portfolio stocks AND any other ticker
            holding = next((h for h in portfolio.get("holdings", []) if h["ticker"] == t), None)
            _reply(f"Scanning {t}... ({i+1}/{len(tickers)})", chat_id)
            results = run_deep_scan(t, holding, portfolio)
            decision = results.get("manager_decision", "")
            if not decision or "NO_ALERT" in decision.upper():
                _reply(f"{t}: scan complete — no signal worth alerting on right now.", chat_id)
            # If there IS an alert, run_deep_scan already sent it via the normal alert pipeline

    except Exception as exc:
        log.error("Telegram scan error: %s", exc)
        _reply(f"Scan failed: {str(exc)[:200]}", chat_id)


def _handle_pulse(ticker: str | None, chat_id: str):
    try:
        from src.crew import run_pulse_scan
        from src.database import init_db
        init_db()
        portfolio = _load_portfolio()

        tickers = (
            [ticker] if ticker
            else [h["ticker"] for h in portfolio.get("holdings", [])]
        )

        for t in tickers:
            result = run_pulse_scan(t, portfolio)
            price_change = result.get("price_change_pct")
            news_score = result.get("news_score", 0)
            urgent = result.get("news_urgent", [])

            lines = [f"Pulse: {t}"]
            if price_change is not None:
                lines.append(f"Price change: {price_change:+.2f}%")
            if news_score:
                lines.append(f"News sentiment: {news_score:+.2f}")
            if urgent:
                lines.append(f"Urgent flags: {', '.join(urgent[:3])}")
            if result.get("trigger_emergency"):
                lines.append("Emergency scan triggered.")
            else:
                lines.append("Nothing urgent detected.")

            _reply("\n".join(lines), chat_id)

    except Exception as exc:
        log.error("Telegram pulse error: %s", exc)
        _reply(f"Pulse scan failed: {str(exc)[:200]}", chat_id)


def _handle_status(chat_id: str):
    try:
        from src.tools.uae_data import aed_to_usd, is_uae
        from src.chart_data import get_latest_price

        portfolio = _load_portfolio()
        holdings = portfolio.get("holdings", [])
        name = portfolio.get("user_name", "Investor")

        lines = [f"Portfolio — {name}\n"]
        total_val_usd = total_cost_usd = 0.0

        for h in holdings:
            t = h["ticker"]
            exchange = h.get("exchange", "US")
            native = h.get("currency", "AED" if is_uae(exchange) else "USD")
            shares = h.get("shares", 0)
            entry = h.get("entry_price", 0)

            price = get_latest_price(t, exchange) or entry
            val_n = shares * price
            cost_n = shares * entry
            pnl_pct = (val_n - cost_n) / cost_n * 100 if cost_n else 0

            # Convert to USD for total
            if native == "AED":
                val_usd = aed_to_usd(val_n)
                cost_usd = aed_to_usd(cost_n)
                price_str = f"AED {price:.4f}"
            else:
                val_usd = val_n
                cost_usd = cost_n
                price_str = f"${price:.4f}"

            total_val_usd += val_usd
            total_cost_usd += cost_usd

            sign = "+" if pnl_pct >= 0 else ""
            lines.append(f"{t}: {price_str} ({sign}{pnl_pct:.1f}%)")

        total_pnl = total_val_usd - total_cost_usd
        total_pnl_pct = total_pnl / total_cost_usd * 100 if total_cost_usd else 0
        sign = "+" if total_pnl >= 0 else ""
        lines.append(f"\nTotal: ${total_val_usd:,.2f} ({sign}{total_pnl_pct:.1f}%)")
        lines.append(f"P&L: ${total_pnl:+,.2f}")

        _reply("\n".join(lines), chat_id)

    except Exception as exc:
        log.error("Telegram status error: %s", exc)
        _reply(f"Status failed: {str(exc)[:200]}", chat_id)


def _handle_add(ticker: str, shares: float, price: float, stop_pct: float, chat_id: str):
    try:
        import json
        from setup import detect_exchange
        from src.tools.uae_data import is_uae
        portfolio = _load_portfolio()
        exchange = detect_exchange(ticker)
        currency = "AED" if is_uae(exchange) else "USD"
        # Remove existing entry if present
        portfolio["holdings"] = [h for h in portfolio.get("holdings", []) if h["ticker"] != ticker]
        portfolio["holdings"].append({
            "ticker": ticker, "exchange": exchange, "currency": currency,
            "shares": shares, "entry_price": price,
            "entry_date_estimated": "", "stop_loss_pct": stop_pct,
            "thesis": "", "screenshot_path": "",
        })
        path = BASE_DIR / "portfolio.json"
        with open(path, "w") as f:
            json.dump(portfolio, f, indent=2)
        _reply(
            f"Added {ticker}\n"
            f"  {shares} shares @ {currency} {price:.4f}\n"
            f"  Exchange: {exchange}\n"
            f"  Stop loss: {stop_pct}%",
            chat_id,
        )
    except Exception as exc:
        log.error("Telegram add error: %s", exc)
        _reply(f"Failed to add {ticker}: {str(exc)[:150]}", chat_id)


def _handle_reset_alerts(chat_id: str):
    """Clear recent alert history so alerts can be resent."""
    try:
        from src.database import Session, AlertSent
        with Session() as s:
            deleted = s.query(AlertSent).delete()
            s.commit()
        _reply(f"Alert history cleared ({deleted} entries). Next scan will resend alerts if there are signals.", chat_id)
    except Exception as exc:
        log.error("reset_alerts error: %s", exc)
        _reply(f"Failed to reset alerts: {str(exc)[:150]}", chat_id)


def _handle_remove(ticker: str, chat_id: str):
    try:
        import json
        portfolio = _load_portfolio()
        before = len(portfolio.get("holdings", []))
        portfolio["holdings"] = [h for h in portfolio.get("holdings", []) if h["ticker"] != ticker]
        if len(portfolio["holdings"]) < before:
            path = BASE_DIR / "portfolio.json"
            with open(path, "w") as f:
                json.dump(portfolio, f, indent=2)
            _reply(f"Removed {ticker} from your portfolio.", chat_id)
        else:
            _reply(f"{ticker} not found in your portfolio.", chat_id)
    except Exception as exc:
        log.error("Telegram remove error: %s", exc)
        _reply(f"Failed to remove {ticker}: {str(exc)[:150]}", chat_id)


def _execute_action(action: dict, chat_id: str):
    """Execute a single parsed action."""
    act = action.get("action", "unknown")

    if act == "answer_question":
        _reply(action.get("answer", "I'm not sure about that."), chat_id)

    elif act == "show_performance":
        _handle_status(chat_id)

    elif act == "run_scan":
        t = (action.get("ticker") or "").upper() or None
        scan_type = action.get("type", "deep")
        label = t or "all holdings"
        _reply(f"Starting {scan_type} scan on {label}...", chat_id)
        threading.Thread(target=_handle_scan, args=(t, chat_id), daemon=True).start()

    elif act == "add_stock":
        t = (action.get("ticker") or "").upper()
        sh = float(action.get("shares") or 0)
        ep = float(action.get("entry_price") or 0)
        sl = float(action.get("stop_loss_pct") or 8)
        if t and sh > 0 and ep > 0:
            _handle_add(t, sh, ep, sl, chat_id)
        else:
            _reply(
                f"Got '{t}' but need shares and price.\n"
                f"Format: /add {t or 'TICKER'} SHARES PRICE",
                chat_id,
            )

    elif act == "remove_stock":
        t = (action.get("ticker") or "").upper()
        if t:
            _handle_remove(t, chat_id)
        else:
            _reply("Which stock do you want to remove?", chat_id)

    elif act == "add_watchlist":
        t = (action.get("ticker") or "").upper()
        if t:
            try:
                import json as _json
                portfolio = _load_portfolio()
                if t not in portfolio.get("watchlist", []):
                    portfolio.setdefault("watchlist", []).append(t)
                    with open(BASE_DIR / "portfolio.json", "w") as f:
                        _json.dump(portfolio, f, indent=2)
                    _reply(f"Added {t} to your watchlist.", chat_id)
                else:
                    _reply(f"{t} is already on your watchlist.", chat_id)
            except Exception as exc:
                _reply(f"Failed: {exc}", chat_id)

    else:
        clarification = action.get("clarification", "")
        _reply(
            (f"Not sure what you mean. {clarification}" if clarification
             else "Try /help to see what I can do."),
            chat_id,
        )


def _handle_chat(text: str, chat_id: str):
    """Route free-form text through the AI chat agent, execute all returned actions."""
    try:
        from src.crew import run_chat_command
        from src.database import init_db
        init_db()
        portfolio = _load_portfolio()
        actions = run_chat_command(text, portfolio)
        log.info("Chat parsed %d action(s) from: %s", len(actions), text[:80])
        for action in actions:
            _execute_action(action, chat_id)
    except Exception as exc:
        log.error("Telegram chat error: %s", exc)
        _reply(f"Something went wrong: {str(exc)[:150]}", chat_id)


def _is_authorised(chat_id: str) -> bool:
    """Only respond to the configured chat ID."""
    return str(chat_id) == str(CHAT_ID)


def start_polling():
    """Long-poll Telegram for incoming messages. Runs forever in a thread."""
    if not BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN not set — listener not started")
        return

    log.info("Telegram listener started (polling)")
    import requests

    offset = None
    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message"]}
            if offset:
                params["offset"] = offset

            r = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params=params,
                timeout=35,
            )
            data = r.json()

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "").strip()
                chat_id = str(msg.get("chat", {}).get("id", ""))

                if not text or not chat_id:
                    continue

                if not _is_authorised(chat_id):
                    log.warning("Ignoring message from unauthorised chat_id: %s", chat_id)
                    continue

                log.info("Telegram command from %s: %s", chat_id, text[:80])
                # Handle in a thread so polling loop stays responsive
                threading.Thread(
                    target=_handle_message, args=(text, chat_id), daemon=True
                ).start()

        except Exception as exc:
            log.error("Telegram polling error: %s", exc)
            time.sleep(5)


def start_listener_thread():
    """Start the polling loop in a background daemon thread."""
    t = threading.Thread(target=start_polling, daemon=True, name="telegram-listener")
    t.start()
    return t
