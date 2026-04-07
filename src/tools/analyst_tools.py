"""Analyst ratings, price targets, institutional ownership."""
import logging
import requests
from bs4 import BeautifulSoup
import feedparser

log = logging.getLogger(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StockResearchBot/1.0)"}


def yfinance_analyst(ticker: str) -> dict:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        return {
            "recommendation_mean": info.get("recommendationMean"),
            "target_mean": info.get("targetMeanPrice"),
            "target_high": info.get("targetHighPrice"),
            "target_low": info.get("targetLowPrice"),
            "analyst_count": info.get("numberOfAnalystOpinions"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        }
    except Exception as exc:
        log.error("yfinance_analyst(%s): %s", ticker, exc)
        return {}


def finviz_analyst_scrape(ticker: str) -> dict:
    try:
        r = requests.get(f"https://finviz.com/quote.ashx?t={ticker}", headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        def snap(label):
            try:
                cell = soup.find("td", string=label)
                if cell:
                    return cell.find_next_sibling("td").get_text(strip=True)
            except Exception:
                pass
            return None

        return {
            "recommendation": snap("Recom"),
            "target_price": snap("Target Price"),
            "eps_next_year": snap("EPS next Y"),
            "short_float": snap("Short Float"),
            "insider_own": snap("Insider Own"),
            "inst_own": snap("Inst Own"),
        }
    except Exception as exc:
        log.error("finviz_analyst_scrape(%s): %s", ticker, exc)
        return {}


def benzinga_ratings_rss(ticker: str) -> list:
    try:
        feed = feedparser.parse("https://www.benzinga.com/rss/analyst-ratings")
        results = []
        for e in feed.entries[:30]:
            if ticker.upper() in (e.get("title", "") + e.get("summary", "")).upper():
                results.append({
                    "title": e.get("title", ""),
                    "summary": e.get("summary", "")[:200],
                })
        return results[:5]
    except Exception as exc:
        log.error("benzinga_ratings_rss(%s): %s", ticker, exc)
        return []


def build_analyst_report(ticker: str) -> dict:
    yf_data = yfinance_analyst(ticker)
    fv_data = finviz_analyst_scrape(ticker)
    ratings = benzinga_ratings_rss(ticker)

    current = yf_data.get("current_price") or 0
    target = yf_data.get("target_mean") or 0
    upside = round((target - current) / current * 100, 1) if current and target else None

    consensus_raw = yf_data.get("recommendation_mean") or 3
    if consensus_raw <= 1.5:
        consensus = "STRONG BUY"
    elif consensus_raw <= 2.5:
        consensus = "BUY"
    elif consensus_raw <= 3.5:
        consensus = "HOLD"
    elif consensus_raw <= 4.5:
        consensus = "SELL"
    else:
        consensus = "STRONG SELL"

    return {
        "analyst_score": round((3.0 - float(consensus_raw)) / 2, 2),
        "consensus": consensus,
        "avg_target": target,
        "upside_pct": upside,
        "analyst_count": yf_data.get("analyst_count"),
        "target_high": yf_data.get("target_high"),
        "target_low": yf_data.get("target_low"),
        "short_float": fv_data.get("short_float"),
        "recent_rating_changes": ratings,
        "reasoning": f"Consensus={consensus}, Target={target}, Upside={upside}%, "
                     f"Analysts={yf_data.get('analyst_count')}",
    }
