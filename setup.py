"""Interactive onboarding wizard — runs once to build portfolio.json."""
import json
import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv, set_key
load_dotenv(BASE_DIR / ".env")

PORTFOLIO_PATH = BASE_DIR / "portfolio.json"
ENV_PATH = BASE_DIR / ".env"


def ask(prompt: str, default: str = "") -> str:
    try:
        val = input(f"\n{prompt} ").strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        return default


def ask_float(prompt: str, default: float = 0.0) -> float:
    while True:
        raw = ask(prompt, str(default))
        try:
            return float(raw.replace("$", "").replace(",", ""))
        except ValueError:
            print(f"  Please enter a number (e.g. 150.50)")


def ask_int(prompt: str, default: int = 0) -> int:
    while True:
        raw = ask(prompt, str(default))
        try:
            return int(raw)
        except ValueError:
            print("  Please enter a whole number.")


def detect_exchange(ticker: str) -> str:
    """Auto-detect exchange from ticker suffix, EODHD search, or yfinance lookup."""
    import os
    t = ticker.upper()

    # Explicit suffix in ticker (e.g. EMAAR.DFM)
    if t.endswith(".DFM"):
        return "DFM"
    if t.endswith(".ADX"):
        return "ADX"
    if t.endswith(".LSE") or t.endswith(".L"):
        return "LSE"
    if t.endswith(".TSX"):
        return "TSX"

    # Try EODHD search — best for UAE/international stocks
    eodhd_key = os.getenv("EODHD_API_KEY", "")
    if eodhd_key:
        try:
            import requests as req
            r = req.get(
                "https://eodhd.com/api/search/",
                params={"api_token": eodhd_key, "q": t, "limit": 5, "fmt": "json"},
                timeout=10,
            )
            results = r.json() if r.ok else []
            for item in results:
                code = (item.get("Code") or "").upper()
                exch = (item.get("Exchange") or "").upper()
                if code == t:
                    if exch in ("DFM", "ADX", "NASDAQ", "NYSE", "LSE", "TSX"):
                        return exch
                    # map EODHD exchange codes
                    exch_map = {"US": "NASDAQ", "LSE": "LSE", "TO": "TSX"}
                    return exch_map.get(exch, exch)
        except Exception:
            pass

    # yfinance fallback for US stocks
    try:
        import yfinance as yf
        info = yf.Ticker(t).info or {}
        exch = (info.get("exchange") or "").upper()
        full = (info.get("fullExchangeName") or "").upper()
        if "NASDAQ" in exch or "NASDAQ" in full or "NMS" in exch:
            return "NASDAQ"
        if "NYSE" in exch or "NYSE" in full or "NYQ" in exch:
            return "NYSE"
        if exch and exch not in ("NONE", "N/A"):
            return exch
    except Exception:
        pass

    return "NASDAQ"


def send_test_telegram(token: str, chat_id: str) -> bool:
    try:
        import requests
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": "✅ Stock Signal Bot setup complete. System online."},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as exc:
        print(f"  Telegram test failed: {exc}")
        return False


def get_telegram_chat_id(token: str) -> str | None:
    try:
        import requests
        print("\n  Calling getUpdates to extract your chat ID...")
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=10)
        data = r.json()
        results = data.get("result", [])
        if results:
            chat = results[-1].get("message", {}).get("chat", {})
            cid = str(chat.get("id", ""))
            if cid:
                print(f"  Found chat ID: {cid}")
                return cid
        print("  No messages found. Make sure you sent a message to your bot first.")
    except Exception as exc:
        print(f"  getUpdates failed: {exc}")
    return None


def ocr_screenshot(path: str, ticker: str) -> float | None:
    try:
        from src.tools.screenshot_ocr_tool import extract_price_from_screenshot
        print(f"  Analysing screenshot with Groq Vision...")
        price = extract_price_from_screenshot(path, ticker)
        return price
    except Exception as exc:
        print(f"  OCR failed: {exc}")
        return None


def estimate_entry_date(ticker: str, entry_price: float) -> str:
    try:
        from src.tools.yfinance_tools import estimate_entry_date
        return estimate_entry_date(ticker, entry_price)
    except Exception:
        return ""


def main():
    print("\n" + "=" * 60)
    print("  Stock Signal Bot — First-Time Setup")
    print("=" * 60)

    # Q1: Name
    name = ask("What's your name?", "Investor")

    # Q2: Budget
    budget = ask_float("What's your total investment budget in USD? (e.g. 5000):", 1000.0)

    # Q3: Telegram chat ID (offer auto-detect)
    print("\n--- Telegram Setup ---")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        token = ask("Enter your TELEGRAM_BOT_TOKEN (from @BotFather):")
        if token:
            set_key(str(ENV_PATH), "TELEGRAM_BOT_TOKEN", token)

    chat_id = ""
    if token:
        chat_id = ask(
            "Send any message to your Telegram bot NOW, then press Enter to auto-detect your chat ID.\n"
            "(Or type your chat ID manually if you already know it):",
        )
        if not chat_id:
            detected = get_telegram_chat_id(token)
            if detected:
                chat_id = detected
            else:
                chat_id = ask("Could not auto-detect. Enter your chat ID manually:", "")

        if chat_id:
            set_key(str(ENV_PATH), "TELEGRAM_CHAT_ID", chat_id)

    # Q4: Holdings
    holdings = []
    has_holdings = ask("Do you currently hold any stocks? (yes/no):", "no").lower()

    if has_holdings in ("yes", "y"):
        while True:
            ticker = ask("Enter ticker (e.g. AAPL, EMAAR.DFM) or 'done' to finish:").upper()
            if ticker in ("DONE", ""):
                break

            shares = ask_float(f"How many shares of {ticker} do you hold? (fractional ok, e.g. 1.5):", 1.0)

            # Screenshot or manual price
            price_input = ask(
                f"Do you have a screenshot showing your average price for {ticker}?\n"
                f"  Drag and drop the image path here, or type the price directly:",
            )
            entry_price = 0.0
            screenshot_path = ""

            # Check if it looks like a file path
            if price_input and (
                price_input.startswith("/") or price_input.startswith("~") or
                "\\" in price_input or price_input.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
            ):
                path = price_input.strip("'\"")
                ocr_price = ocr_screenshot(path, ticker)
                if ocr_price:
                    confirm = ask(f"I read ${ocr_price:.4f}. Correct? (yes/no):", "yes").lower()
                    if confirm in ("yes", "y"):
                        entry_price = ocr_price
                        screenshot_path = path
                    else:
                        entry_price = ask_float(f"Type the correct price for {ticker}:", 0.0)
                else:
                    print("  Could not read price from screenshot.")
                    entry_price = ask_float(f"Enter {ticker} average price manually:", 0.0)
            else:
                try:
                    entry_price = float(price_input.replace("$", "").replace(",", "")) if price_input else 0.0
                except ValueError:
                    entry_price = ask_float(f"Enter {ticker} average price:", 0.0)

            # Exchange — auto-detect
            print(f"  Detecting exchange for {ticker}...")
            exchange = detect_exchange(ticker)
            print(f"  Detected: {exchange}")

            thesis = ""

            # Stop loss
            stop_loss = ask_float(f"Stop-loss % for {ticker}? (default 8):", 8.0)

            # Estimate entry date
            entry_date = ""
            if entry_price > 0:
                print(f"  Estimating entry date from price history...")
                entry_date = estimate_entry_date(ticker, entry_price)
                if entry_date:
                    print(f"  Estimated entry date: {entry_date}")

            holdings.append({
                "ticker": ticker,
                "exchange": exchange,
                "shares": float(shares),
                "entry_price": entry_price,
                "entry_date_estimated": entry_date,
                "stop_loss_pct": stop_loss,
                "thesis": thesis,
                "screenshot_path": screenshot_path,
            })
            print(f"  ✓ {ticker} added.")

    # Q5: Watchlist
    watchlist_input = ask("Add watchlist tickers (comma-separated, press Enter to skip):", "")
    watchlist = [t.strip().upper() for t in watchlist_input.split(",") if t.strip()]

    # Q6: Summary + confirm
    print("\n" + "=" * 60)
    print(f"  Name: {name}")
    print(f"  Budget: ${budget:,.0f}")
    print(f"  Telegram chat ID: {chat_id or 'not set'}")
    print(f"  Holdings: {len(holdings)}")
    for h in holdings:
        print(f"    • {h['ticker']}: {h['shares']} shares @ ${h['entry_price']}")
    print(f"  Watchlist: {watchlist}")
    print("=" * 60)

    confirm = ask("Correct? (yes/no):", "yes").lower()
    if confirm not in ("yes", "y"):
        print("Setup cancelled. Run setup.py again to restart.")
        sys.exit(0)

    # Build portfolio.json
    portfolio = {
        "user_name": name,
        "budget_usd": budget,
        "telegram_chat_id": chat_id,
        "timezone": "Asia/Dubai",
        "holdings": holdings,
        "watchlist": watchlist,
        "global_stop_loss_pct": 8,
    }
    with open(PORTFOLIO_PATH, "w") as f:
        json.dump(portfolio, f, indent=2)
    print(f"\n  ✓ Saved to portfolio.json")

    # Q7: Test Telegram
    if token and chat_id:
        print("\n  Sending test Telegram message...")
        ok = send_test_telegram(token, chat_id)
        if ok:
            print("  ✓ Telegram working!")
        else:
            print("  ✗ Telegram test failed. Check your bot token and chat ID.")

    print("\n  ✓ Setup complete! Launching dashboard and research engine...\n")


if __name__ == "__main__":
    main()
