"""Insider trading tools — OpenInsider scraping."""
import logging
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StockResearchBot/1.0)"}


def openinsider_scrape(ticker: str) -> list:
    """Scrape OpenInsider for recent insider transactions."""
    try:
        url = f"https://openinsider.com/screener?s={ticker}&fd=30&o=-filing_date"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table", {"class": "tinytable"})
        if not table:
            return []
        rows = table.find_all("tr")[1:]  # skip header
        results = []
        for row in rows[:15]:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) >= 10:
                results.append({
                    "filing_date": cols[1],
                    "trade_date": cols[2],
                    "ticker": cols[3],
                    "insider": cols[5],
                    "title": cols[6],
                    "trade_type": cols[7],
                    "price": cols[8],
                    "qty": cols[9],
                    "value": cols[11] if len(cols) > 11 else "",
                })
        return results
    except Exception as exc:
        log.error("openinsider_scrape(%s): %s", ticker, exc)
        return []


def summarise_insider_activity(transactions: list) -> dict:
    """Summarise buy/sell ratio from insider transactions."""
    buys = [t for t in transactions if "P" in t.get("trade_type", "").upper()]
    sells = [t for t in transactions if "S" in t.get("trade_type", "").upper()]
    net_signal = "NEUTRAL"
    if len(buys) > len(sells) * 2:
        net_signal = "BULLISH"
    elif len(sells) > len(buys) * 2:
        net_signal = "BEARISH"
    return {
        "buy_count": len(buys),
        "sell_count": len(sells),
        "net_signal": net_signal,
        "latest": transactions[:3],
    }
