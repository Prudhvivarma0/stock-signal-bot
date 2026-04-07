"""Press release and NASDAQ announcement tools."""
import logging
import requests

log = logging.getLogger(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StockResearchBot/1.0)"}


def nasdaq_press_releases(ticker: str) -> list:
    try:
        url = f"https://api.nasdaq.com/api/company/{ticker}/pressreleases?limit=10"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        items = data.get("data", {}).get("rows", []) or []
        return [{"title": i.get("headline"), "date": i.get("lastModified")} for i in items[:10]]
    except Exception as exc:
        log.error("nasdaq_press_releases(%s): %s", ticker, exc)
        return []


def dfm_adx_announcements() -> list:
    """Scrape DFM announcement headlines."""
    try:
        from bs4 import BeautifulSoup
        r = requests.get("https://www.dfm.ae/en/listed-companies/market-information/announcements",
                         headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        headlines = soup.select("h3.announcement-title, .announcement-item h4")
        return [{"title": h.get_text(strip=True), "source": "DFM"} for h in headlines[:10]]
    except Exception as exc:
        log.error("dfm_adx_announcements: %s", exc)
        return []
