"""Institutional ownership via SEC 13F filings."""
import logging
import requests
from datetime import datetime, timedelta

log = logging.getLogger(__name__)
HEADERS = {"User-Agent": "StockResearchBot research@example.com"}


def sec_13f_institutional(ticker: str) -> list:
    """Search SEC for recent 13F filings mentioning the ticker."""
    try:
        start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        url = (
            f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22"
            f"&forms=13F-HR&dateRange=custom&startdt={start}"
        )
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        hits = r.json().get("hits", {}).get("hits", [])
        return [
            {
                "filer": h["_source"].get("display_names"),
                "date": h["_source"].get("file_date"),
                "form": h["_source"].get("form_type"),
            }
            for h in hits[:10]
        ]
    except Exception as exc:
        log.error("sec_13f_institutional(%s): %s", ticker, exc)
        return []


def whalewisdom_scrape(ticker: str) -> dict:
    """Scrape WhaleWisdom institutional ownership summary."""
    try:
        from bs4 import BeautifulSoup
        r = requests.get(
            f"https://whalewisdom.com/stock/{ticker}",
            headers={"User-Agent": "Mozilla/5.0 (compatible; StockResearchBot/1.0)"},
            timeout=15,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        data = {}
        # Try to extract key metrics from the page
        for item in soup.select(".stats-item, .metric-item"):
            label = item.select_one(".label, .metric-label")
            value = item.select_one(".value, .metric-value")
            if label and value:
                data[label.get_text(strip=True)] = value.get_text(strip=True)
        return data or {"note": "page structure may have changed"}
    except Exception as exc:
        log.error("whalewisdom_scrape(%s): %s", ticker, exc)
        return {}
