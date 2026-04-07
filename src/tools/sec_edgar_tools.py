"""SEC EDGAR tools — facts, filings, 8-K alerts."""
import logging
import time
from datetime import datetime, timedelta

import requests

log = logging.getLogger(__name__)
HEADERS = {"User-Agent": "StockResearchBot research@example.com"}


def _get(url: str, timeout: int = 15) -> dict | list | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.error("_get(%s): %s", url, exc)
        return None


def _ticker_to_cik(ticker: str) -> str | None:
    try:
        data = _get("https://www.sec.gov/files/company_tickers.json")
        if not data:
            return None
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker.upper():
                return str(entry["cik_str"]).zfill(10)
    except Exception as exc:
        log.error("_ticker_to_cik(%s): %s", ticker, exc)
    return None


def sec_edgar_facts(ticker: str) -> dict:
    """Fetch 3-year trend of revenue, net income, cash from XBRL company facts."""
    try:
        cik = _ticker_to_cik(ticker)
        if not cik:
            return {"error": f"CIK not found for {ticker}"}
        data = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
        if not data:
            return {}
        us_gaap = data.get("facts", {}).get("us-gaap", {})
        result = {}
        for concept in ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                         "NetIncomeLoss", "NetCashProvidedByUsedInOperatingActivities"]:
            units = us_gaap.get(concept, {}).get("units", {})
            usd = units.get("USD", [])
            annual = [x for x in usd if x.get("form") in ("10-K", "10-K/A") and x.get("fp") == "FY"]
            annual_sorted = sorted(annual, key=lambda x: x.get("end", ""), reverse=True)[:5]
            result[concept] = [{"end": x.get("end"), "val": x.get("val")} for x in annual_sorted]
        return result
    except Exception as exc:
        log.error("sec_edgar_facts(%s): %s", ticker, exc)
        return {}


def sec_10k_10q(ticker: str) -> list:
    """Latest 10-K and 10-Q filings."""
    try:
        url = (
            f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22"
            f"&forms=10-K,10-Q&dateRange=custom&startdt={(datetime.now()-timedelta(days=365)).strftime('%Y-%m-%d')}"
        )
        data = _get(url)
        if not data:
            return []
        hits = data.get("hits", {}).get("hits", [])
        return [
            {
                "form": h["_source"].get("form_type"),
                "date": h["_source"].get("file_date"),
                "url": h["_source"].get("file_date"),
                "title": h["_source"].get("display_names"),
            }
            for h in hits[:5]
        ]
    except Exception as exc:
        log.error("sec_10k_10q(%s): %s", ticker, exc)
        return []


def sec_8k_alerts(ticker: str) -> list:
    """Today's 8-K filings — breaking events."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        url = (
            f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22"
            f"&forms=8-K&dateRange=custom&startdt={today}"
        )
        data = _get(url)
        if not data:
            return []
        hits = data.get("hits", {}).get("hits", [])
        return [
            {
                "form": h["_source"].get("form_type"),
                "date": h["_source"].get("file_date"),
                "description": h["_source"].get("period_of_report"),
                "entities": h["_source"].get("display_names"),
            }
            for h in hits[:10]
        ]
    except Exception as exc:
        log.error("sec_8k_alerts(%s): %s", ticker, exc)
        return []


def insider_transactions(ticker: str) -> list:
    """Form 4 insider transactions last 30 days."""
    try:
        start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        url = (
            f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22"
            f"&forms=4&dateRange=custom&startdt={start}"
        )
        data = _get(url)
        if not data:
            return []
        hits = data.get("hits", {}).get("hits", [])
        return [
            {
                "date": h["_source"].get("file_date"),
                "filer": h["_source"].get("display_names"),
                "period": h["_source"].get("period_of_report"),
            }
            for h in hits[:20]
        ]
    except Exception as exc:
        log.error("insider_transactions(%s): %s", ticker, exc)
        return []
