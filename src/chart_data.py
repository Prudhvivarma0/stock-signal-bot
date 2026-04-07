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
    from src.tools.uae_data import is_uae, yf_ticker as uae_yf_ticker, get_uae_history
    period_map = {"1D": "1d", "1W": "5d", "1M": "1mo", "3M": "3mo", "6M": "6mo", "ALL": "5y"}
    interval = TIMEFRAME_INTERVAL.get(timeframe, "1d")
    period = period_map.get(timeframe, "1mo")

    # UAE stocks — use .AE suffix via yfinance
    if is_uae(exchange):
        try:
            df = get_uae_history(ticker, exchange, period=period, interval=interval)
            if not df.empty:
                df.columns = [str(c).split("_")[0] if isinstance(c, tuple) else str(c) for c in df.columns]
                df.rename(columns={"Datetime": "date", "Date": "date"}, inplace=True)
                return df
        except Exception as exc:
            log.warning("UAE candles failed for %s: %s", ticker, exc)

    # US stocks — standard yfinance
    try:
        sym = ticker
        df = yf.download(sym, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        df.rename(columns={"Datetime": "date", "Date": "date"}, inplace=True)
        return df
    except Exception as exc:
        log.error("get_stock_candles(%s %s): %s", ticker, timeframe, exc)
        return pd.DataFrame()


def get_latest_price(ticker: str, exchange: str = "US") -> float | None:
    """Get latest price — first from DB cache, then live."""
    from src.tools.uae_data import is_uae, get_uae_price
    try:
        rows = get_price_history(ticker, days=1)
        if rows:
            latest = sorted(rows, key=lambda x: x[0], reverse=True)[0]
            return latest[1]
    except Exception:
        pass
    try:
        if is_uae(exchange):
            return get_uae_price(ticker, exchange)
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
