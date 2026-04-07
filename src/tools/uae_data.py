"""UAE stock data helpers — DFM/ADX via yfinance .AE suffix."""
import logging
import os

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

AED_USD_RATE = 3.6725  # fixed peg

UAE_EXCHANGES = ("DFM", "ADX", "AE")


def is_uae(exchange: str) -> bool:
    return exchange.upper() in UAE_EXCHANGES


def yf_ticker(ticker: str, exchange: str) -> str:
    """Convert ticker + exchange to the correct Yahoo Finance symbol.
    DFM/ADX stocks use the .AE suffix on Yahoo Finance.
    """
    t = ticker.upper()
    if is_uae(exchange):
        # Already has suffix
        if t.endswith(".AE") or t.endswith(".DFM") or t.endswith(".ADX"):
            base = t.split(".")[0]
            return f"{base}.AE"
        return f"{t}.AE"
    return t  # US stocks as-is


def get_uae_price(ticker: str, exchange: str = "DFM") -> float | None:
    """Get latest price for a UAE stock in AED."""
    try:
        sym = yf_ticker(ticker, exchange)
        info = yf.Ticker(sym).info or {}
        price = (info.get("regularMarketPrice")
                 or info.get("currentPrice")
                 or info.get("previousClose"))
        return float(price) if price else None
    except Exception as exc:
        log.error("get_uae_price(%s): %s", ticker, exc)
        return None


def get_uae_history(ticker: str, exchange: str = "DFM",
                    period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """OHLCV history for UAE stock in AED."""
    try:
        sym = yf_ticker(ticker, exchange)
        df = yf.download(sym, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if not df.empty:
            df = df.reset_index()
        return df
    except Exception as exc:
        log.error("get_uae_history(%s): %s", ticker, exc)
        return pd.DataFrame()


def aed_to_usd(amount: float) -> float:
    return round(amount / AED_USD_RATE, 2)


def usd_to_aed(amount: float) -> float:
    return round(amount * AED_USD_RATE, 2)


def detect_currency(exchange: str) -> str:
    return "AED" if is_uae(exchange) else "USD"


def format_amount(amount: float, currency: str, show_as: str = "native") -> str:
    """Format amount in native currency or converted.
    show_as: 'native' | 'usd' | 'aed'
    """
    if show_as == "usd" and currency == "AED":
        return f"${aed_to_usd(amount):,.2f}"
    if show_as == "aed" and currency == "USD":
        return f"AED {usd_to_aed(amount):,.2f}"
    symbol = "AED " if currency == "AED" else "$"
    return f"{symbol}{amount:,.4f}"
