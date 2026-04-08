"""Alpha Vantage tools — earnings, income statement, balance sheet, overview."""
import logging
import os
import time

import requests

log = logging.getLogger(__name__)
BASE = "https://www.alphavantage.co/query"


def _key():
    k = os.getenv("ALPHA_VANTAGE_KEY", "")
    if not k:
        raise ValueError("ALPHA_VANTAGE_KEY not set")
    return k


def _get(params: dict, retries: int = 2) -> dict:
    params["apikey"] = _key()
    for attempt in range(retries):
        try:
            r = requests.get(BASE, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            if "Note" in data or "Information" in data:
                # rate limit hit — return empty rather than blocking threads
                log.warning("Alpha Vantage rate limit — skipping (free tier daily limit reached)")
                return {}
            return data
        except Exception as exc:
            log.error("alpha_vantage _get(%s): %s", params.get("function"), exc)
    return {}


def av_company_overview(ticker: str) -> dict:
    """Full company overview: P/E, EPS, margins, dividend, 52w range, etc."""
    try:
        data = _get({"function": "OVERVIEW", "symbol": ticker})
        if not data:
            return {}
        return {
            "name": data.get("Name"),
            "sector": data.get("Sector"),
            "industry": data.get("Industry"),
            "market_cap": data.get("MarketCapitalization"),
            "pe_ratio": data.get("PERatio"),
            "forward_pe": data.get("ForwardPE"),
            "peg_ratio": data.get("PEGRatio"),
            "eps": data.get("EPS"),
            "book_value": data.get("BookValue"),
            "dividend_yield": data.get("DividendYield"),
            "profit_margin": data.get("ProfitMargin"),
            "operating_margin": data.get("OperatingMarginTTM"),
            "roe": data.get("ReturnOnEquityTTM"),
            "roa": data.get("ReturnOnAssetsTTM"),
            "revenue_ttm": data.get("RevenueTTM"),
            "gross_profit_ttm": data.get("GrossProfitTTM"),
            "diluted_eps_ttm": data.get("DilutedEPSTTM"),
            "quarterly_earnings_growth": data.get("QuarterlyEarningsGrowthYOY"),
            "quarterly_revenue_growth": data.get("QuarterlyRevenueGrowthYOY"),
            "analyst_target": data.get("AnalystTargetPrice"),
            "52w_high": data.get("52WeekHigh"),
            "52w_low": data.get("52WeekLow"),
            "50d_ma": data.get("50DayMovingAverage"),
            "200d_ma": data.get("200DayMovingAverage"),
            "shares_outstanding": data.get("SharesOutstanding"),
            "shares_float": data.get("SharesFloat"),
            "short_ratio": data.get("ShortRatio"),
            "short_pct_float": data.get("ShortPercentOutstanding"),
            "beta": data.get("Beta"),
            "description": (data.get("Description") or "")[:300],
        }
    except Exception as exc:
        log.error("av_company_overview(%s): %s", ticker, exc)
        return {}


def av_earnings(ticker: str) -> dict:
    """Quarterly and annual EPS history."""
    try:
        data = _get({"function": "EARNINGS", "symbol": ticker})
        quarterly = data.get("quarterlyEarnings", [])[:8]
        annual = data.get("annualEarnings", [])[:4]
        return {
            "quarterly_eps": [
                {"date": q.get("fiscalDateEnding"), "reported": q.get("reportedEPS"),
                 "estimated": q.get("estimatedEPS"), "surprise_pct": q.get("surprisePercentage")}
                for q in quarterly
            ],
            "annual_eps": [
                {"year": a.get("fiscalDateEnding"), "eps": a.get("reportedEPS")}
                for a in annual
            ],
        }
    except Exception as exc:
        log.error("av_earnings(%s): %s", ticker, exc)
        return {}


def av_income_statement(ticker: str) -> dict:
    """Last 4 quarters of revenue, gross profit, net income."""
    try:
        data = _get({"function": "INCOME_STATEMENT", "symbol": ticker})
        reports = data.get("quarterlyReports", [])[:4]
        return {
            "quarterly_income": [
                {
                    "date": r.get("fiscalDateEnding"),
                    "revenue": r.get("totalRevenue"),
                    "gross_profit": r.get("grossProfit"),
                    "net_income": r.get("netIncome"),
                    "ebitda": r.get("ebitda"),
                    "operating_income": r.get("operatingIncome"),
                }
                for r in reports
            ]
        }
    except Exception as exc:
        log.error("av_income_statement(%s): %s", ticker, exc)
        return {}
