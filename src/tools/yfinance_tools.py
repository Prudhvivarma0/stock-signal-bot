"""yfinance wrappers — fundamentals, price data, options."""
import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)


def yfinance_fundamentals(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        fields = [
            "shortName", "longName", "sector", "industry",
            "trailingPE", "forwardPE", "pegRatio", "trailingEps", "forwardEps",
            "revenueGrowth", "earningsGrowth", "profitMargins", "operatingMargins",
            "freeCashflow", "debtToEquity", "returnOnEquity", "returnOnAssets",
            "bookValue", "priceToBook", "shortRatio", "shortPercentOfFloat",
            "heldPercentInstitutions", "heldPercentInsiders",
            "targetMeanPrice", "targetHighPrice", "targetLowPrice",
            "recommendationMean", "numberOfAnalystOpinions",
            "marketCap", "enterpriseValue", "totalRevenue", "grossProfits",
            "ebitda", "totalDebt", "totalCash", "currentRatio", "quickRatio",
            "beta", "52WeekChange", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
            "dividendYield", "payoutRatio", "exDividendDate",
            "earningsTimestamp", "earningsTimestampStart", "earningsTimestampEnd",
        ]
        result = {k: info.get(k) for k in fields}

        # earnings history
        try:
            earnings = t.earnings_history
            if earnings is not None and not earnings.empty:
                result["earnings_history"] = earnings.tail(8).to_dict(orient="records")
        except Exception:
            pass

        return result
    except Exception as exc:
        log.error("yfinance_fundamentals(%s): %s", ticker, exc)
        return {}


def price_data(ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        df.dropna(inplace=True)
        return df
    except Exception as exc:
        log.error("price_data(%s %s %s): %s", ticker, period, interval, exc)
        return pd.DataFrame()


def premarket_price(ticker: str) -> float | None:
    try:
        info = yf.Ticker(ticker).info or {}
        return info.get("preMarketPrice") or info.get("regularMarketPrice")
    except Exception as exc:
        log.error("premarket_price(%s): %s", ticker, exc)
        return None


def get_latest_price(ticker: str) -> float | None:
    try:
        info = yf.Ticker(ticker).info or {}
        return (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
    except Exception as exc:
        log.error("get_latest_price(%s): %s", ticker, exc)
        return None


def estimate_entry_date(ticker: str, entry_price: float) -> str:
    """Find the last date the stock traded near entry_price."""
    try:
        df = yf.download(ticker, period="5y", interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return ""
        df = df.reset_index()
        # Flatten MultiIndex columns (ticker, field) -> field
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] if col[1] == "" else col[0] for col in df.columns]
        # Normalize to simple strings
        df.columns = [str(c).strip() for c in df.columns]
        close_col = next((c for c in df.columns if c.lower() == "close"), None)
        date_col = next((c for c in df.columns if c.lower() in ("date", "datetime")), None)
        if not close_col or not date_col:
            return ""
        df["diff"] = (df[close_col] - entry_price).abs()
        idx = df["diff"].idxmin()
        return str(df.loc[idx, date_col])[:10]
    except Exception as exc:
        log.error("estimate_entry_date(%s %.2f): %s", ticker, entry_price, exc)
        return ""


def options_flow(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        exps = t.options
        if not exps:
            return {}
        all_calls_vol, all_puts_vol = 0, 0
        unusual = []
        for exp in exps[:6]:
            chain = t.option_chain(exp)
            calls = chain.calls
            puts = chain.puts
            all_calls_vol += int(calls["volume"].fillna(0).sum())
            all_puts_vol += int(puts["volume"].fillna(0).sum())
            # flag large OTM calls
            for _, row in calls.iterrows():
                notional = float(row.get("lastPrice", 0) or 0) * float(row.get("volume", 0) or 0) * 100
                if notional > 500_000:
                    unusual.append({
                        "type": "CALL", "strike": row.get("strike"),
                        "exp": exp, "volume": row.get("volume"),
                        "notional": round(notional),
                    })
        pc_ratio = round(all_puts_vol / all_calls_vol, 2) if all_calls_vol else None
        return {
            "put_call_ratio": pc_ratio,
            "total_call_volume": all_calls_vol,
            "total_put_volume": all_puts_vol,
            "unusual_options": unusual[:10],
        }
    except Exception as exc:
        log.error("options_flow(%s): %s", ticker, exc)
        return {}


def short_squeeze_score(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info or {}
        return {
            "short_float": info.get("shortPercentOfFloat"),
            "short_ratio": info.get("shortRatio"),
            "shares_short": info.get("sharesShort"),
            "short_prior_month": info.get("sharesShortPriorMonth"),
        }
    except Exception as exc:
        log.error("short_squeeze_score(%s): %s", ticker, exc)
        return {}
