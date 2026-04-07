"""EODHD API tools — UAE and global stock fundamentals + EOD price data."""
import logging
import os
from datetime import datetime, timedelta

import requests

log = logging.getLogger(__name__)
BASE = "https://eodhd.com/api"


def _key():
    k = os.getenv("EODHD_API_KEY", "")
    if not k:
        raise ValueError("EODHD_API_KEY not set")
    return k


def eodhd_fundamentals(ticker: str, exchange: str = "DFM") -> dict:
    """Full fundamental data for a stock. exchange = DFM, ADX, NASDAQ, NYSE etc."""
    try:
        r = requests.get(
            f"{BASE}/fundamentals/{ticker}.{exchange}",
            params={"api_token": _key(), "fmt": "json"},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            return {}

        highlights = data.get("Highlights", {}) or {}
        valuation = data.get("Valuation", {}) or {}
        tech = data.get("Technicals", {}) or {}
        shares = data.get("SharesStats", {}) or {}
        officers = data.get("outstandingShares", {}) or {}

        return {
            "market_cap": highlights.get("MarketCapitalization"),
            "pe_ratio": highlights.get("PERatio"),
            "eps": highlights.get("EarningsShare"),
            "eps_estimate_next_year": highlights.get("EPSEstimateNextYear"),
            "revenue_ttm": highlights.get("RevenueTTM"),
            "revenue_per_share": highlights.get("RevenuePerShareTTM"),
            "profit_margin": highlights.get("ProfitMargin"),
            "operating_margin": highlights.get("OperatingMarginTTM"),
            "roe": highlights.get("ReturnOnEquityTTM"),
            "roa": highlights.get("ReturnOnAssetsTTM"),
            "revenue_growth_qoq": highlights.get("QuarterlyRevenueGrowthYOY"),
            "earnings_growth_qoq": highlights.get("QuarterlyEarningsGrowthYOY"),
            "dividend_yield": highlights.get("DividendYield"),
            "book_value": highlights.get("BookValue"),
            "pb_ratio": valuation.get("PriceBookMRQ"),
            "ps_ratio": valuation.get("PriceSalesTTM"),
            "ev_ebitda": valuation.get("EnterpriseValueEbitda"),
            "beta": tech.get("Beta"),
            "52w_high": tech.get("52WeekHigh"),
            "52w_low": tech.get("52WeekLow"),
            "short_ratio": tech.get("ShortRatio"),
            "shares_short": shares.get("SharesShort"),
            "shares_float": shares.get("SharesFloat"),
            "insider_own_pct": shares.get("PercentInsiders"),
            "institution_own_pct": shares.get("PercentInstitutions"),
        }
    except Exception as exc:
        log.error("eodhd_fundamentals(%s.%s): %s", ticker, exchange, exc)
        return {}


def eodhd_eod_prices(ticker: str, exchange: str = "DFM", days: int = 365) -> list:
    """End-of-day price history."""
    try:
        from_dt = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        to_dt = datetime.now().strftime("%Y-%m-%d")
        r = requests.get(
            f"{BASE}/eod/{ticker}.{exchange}",
            params={"api_token": _key(), "from": from_dt, "to": to_dt, "fmt": "json"},
            timeout=20,
        )
        r.raise_for_status()
        return r.json() or []
    except Exception as exc:
        log.error("eodhd_eod_prices(%s.%s): %s", ticker, exchange, exc)
        return []


def eodhd_news(ticker: str, exchange: str = "DFM", limit: int = 20) -> list:
    """Latest news for a ticker from EODHD."""
    try:
        r = requests.get(
            f"{BASE}/news",
            params={
                "s": f"{ticker}.{exchange}",
                "api_token": _key(),
                "limit": limit,
                "fmt": "json",
            },
            timeout=15,
        )
        r.raise_for_status()
        items = r.json() or []
        return [
            {"title": i.get("title", ""), "date": i.get("date", ""),
             "source": "eodhd_news", "link": i.get("link", "")}
            for i in items
        ]
    except Exception as exc:
        log.error("eodhd_news(%s.%s): %s", ticker, exchange, exc)
        return []


def eodhd_insider_transactions(ticker: str, exchange: str = "DFM") -> list:
    """Insider transactions from EODHD."""
    try:
        r = requests.get(
            f"{BASE}/insider-transactions",
            params={"code": f"{ticker}.{exchange}", "api_token": _key(), "fmt": "json"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json() or {}
        return data.get("data", [])[:20]
    except Exception as exc:
        log.error("eodhd_insider_transactions(%s.%s): %s", ticker, exchange, exc)
        return []
