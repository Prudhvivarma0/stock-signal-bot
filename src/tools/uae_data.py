"""UAE stock data helpers — DFM/ADX via yfinance .AE suffix."""
import logging
import os

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

AED_USD_RATE = 3.6725  # fixed peg

UAE_EXCHANGES = ("DFM", "ADX", "AE")

# Known UAE tickers for auto-detection (DFM + ADX)
KNOWN_UAE_TICKERS = {
    # DFM
    "EMAAR", "SALIK", "DIB", "DFM", "DAMAC", "DEWA", "TECOM", "PARKIN",
    "AMANAT", "GGICO", "GFH", "GFHMICRO", "SHUAA", "TAKAFUL", "UNION",
    "ARZAN", "BPCC", "SALAMA", "AJMANBANK", "MASB",
    # ADX
    "ETISALAT", "EAND", "FAB", "ADCB", "ADNOCDIST", "ADNOC", "ALDAR",
    "IHC", "TAQA", "FERTIGLOBE", "ADIB", "NBAD", "NBF", "NMDC",
    "ALPHADHABI", "MULTIPLY", "NOURA", "GHITHA", "AGTHIA",
}


def is_uae_ticker(ticker: str) -> bool:
    """Auto-detect UAE stock by known list or .AE/.DFM/.ADX suffix."""
    t = ticker.upper().split(".")[0]  # strip any existing suffix
    if t in KNOWN_UAE_TICKERS:
        return True
    tu = ticker.upper()
    return tu.endswith(".AE") or tu.endswith(".DFM") or tu.endswith(".ADX")


def resolve_yf_ticker(ticker: str, exchange: str = "") -> str:
    """Return correct Yahoo Finance symbol.
    Auto-appends .AE for known UAE stocks when exchange not provided.
    """
    t = ticker.upper()
    # Already has a suffix → normalise to .AE
    if t.endswith(".DFM") or t.endswith(".ADX"):
        return t.split(".")[0] + ".AE"
    if t.endswith(".AE"):
        return t
    # Exchange known to be UAE
    if exchange.upper() in UAE_EXCHANGES:
        return f"{t}.AE"
    # Auto-detect from known list
    if is_uae_ticker(t):
        return f"{t}.AE"
    return t  # US / other


def is_uae(exchange: str) -> bool:
    return exchange.upper() in UAE_EXCHANGES


def yf_ticker(ticker: str, exchange: str) -> str:
    """Convert ticker + exchange to the correct Yahoo Finance symbol.
    DFM/ADX stocks use the .AE suffix on Yahoo Finance.
    """
    return resolve_yf_ticker(ticker, exchange)


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
