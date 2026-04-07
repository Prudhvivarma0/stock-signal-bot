"""Chart data provider for the Streamlit dashboard."""
import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from src.database import get_portfolio_history_rows, get_price_history

log = logging.getLogger(__name__)

TIMEFRAME_DAYS = {
    "1D": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "ALL": 1825,
}

TIMEFRAME_INTERVAL = {
    "1D": "15m", "1W": "1h", "1M": "1d", "3M": "1d", "6M": "1d", "ALL": "1d",
}


def get_portfolio_history(timeframe: str = "ALL") -> pd.DataFrame:
    """Returns dataframe with date, total_value, total_invested."""
    days = TIMEFRAME_DAYS.get(timeframe, 1825)
    rows = get_portfolio_history_rows(days=days)
    if not rows:
        return pd.DataFrame(columns=["date", "total_value", "total_invested"])
    df = pd.DataFrame(rows, columns=["date", "total_value", "total_invested"])
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values("date", inplace=True)
    return df


def get_stock_candles(ticker: str, timeframe: str = "1M", exchange: str = "US") -> pd.DataFrame:
    """Returns OHLCV dataframe for candlestick chart."""
    import os
    days = TIMEFRAME_DAYS.get(timeframe, 30)
    interval = TIMEFRAME_INTERVAL.get(timeframe, "1d")

    # UAE stocks via EODHD if available
    eodhd_key = os.getenv("EODHD_API_KEY", "")
    if exchange in ("DFM", "ADX") and eodhd_key:
        try:
            import requests
            from_dt = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            to_dt = datetime.now().strftime("%Y-%m-%d")
            r = requests.get(
                f"https://eodhd.com/api/eod/{ticker}.{exchange}",
                params={"api_token": eodhd_key, "from": from_dt, "to": to_dt, "fmt": "json"},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            df = pd.DataFrame(data)
            if not df.empty:
                df["date"] = pd.to_datetime(df["date"])
                df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                                   "close": "Close", "volume": "Volume"}, inplace=True)
                return df
        except Exception as exc:
            log.warning("EODHD failed for %s: %s — falling back to yfinance", ticker, exc)

    # Fallback: yfinance
    try:
        period_map = {"1D": "1d", "1W": "5d", "1M": "1mo", "3M": "3mo", "6M": "6mo", "ALL": "5y"}
        period = period_map.get(timeframe, "1mo")
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df.rename(columns={"Datetime": "date", "Date": "date"}, inplace=True)
        return df
    except Exception as exc:
        log.error("get_stock_candles(%s %s): %s", ticker, timeframe, exc)
        return pd.DataFrame()


def get_latest_price(ticker: str) -> float | None:
    """Get latest price — first from DB cache, then live."""
    try:
        rows = get_price_history(ticker, days=1)
        if rows:
            # most recent
            latest = sorted(rows, key=lambda x: x[0], reverse=True)[0]
            return latest[1]
    except Exception:
        pass
    try:
        from src.tools.yfinance_tools import get_latest_price as live_price
        return live_price(ticker)
    except Exception as exc:
        log.error("get_latest_price(%s): %s", ticker, exc)
        return None


def get_sparkline(ticker: str, days: int = 7) -> list:
    """7-day daily closing prices for sparkline."""
    try:
        df = yf.download(ticker, period="7d", interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return []
        col = "Close" if "Close" in df.columns else df.columns[-2]
        return df[col].dropna().tolist()
    except Exception as exc:
        log.error("get_sparkline(%s): %s", ticker, exc)
        return []
