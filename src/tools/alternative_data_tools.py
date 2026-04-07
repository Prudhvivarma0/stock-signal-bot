"""Alternative data signals — job postings, app store, GitHub, patents, earnings calls."""
import logging
import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StockResearchBot/1.0)"}


def glassdoor_sentiment(company_name: str) -> dict:
    """Placeholder — Glassdoor blocks scraping. Returns empty with note."""
    return {"note": "Glassdoor scraping blocked; manual review required", "company": company_name}


def github_activity(org_name: str) -> dict:
    try:
        r = requests.get(
            f"https://api.github.com/orgs/{org_name}/repos?per_page=20&sort=updated",
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=15,
        )
        r.raise_for_status()
        repos = r.json()
        total_stars = sum(repo.get("stargazers_count", 0) for repo in repos)
        total_forks = sum(repo.get("forks_count", 0) for repo in repos)
        return {
            "repo_count": len(repos),
            "total_stars": total_stars,
            "total_forks": total_forks,
            "top_repos": [
                {"name": r["name"], "stars": r["stargazers_count"]}
                for r in sorted(repos, key=lambda x: x.get("stargazers_count", 0), reverse=True)[:3]
            ],
        }
    except Exception as exc:
        log.error("github_activity(%s): %s", org_name, exc)
        return {}


def earnings_call_sentiment(ticker: str) -> dict:
    """Scrape Motley Fool for latest earnings call transcript sentiment indicators."""
    try:
        url = f"https://www.fool.com/earnings-call-transcripts/?search={ticker}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # grab first transcript link
        links = soup.select("a[href*='earnings-call-transcript']")
        if not links:
            return {"note": "no transcript found"}
        transcript_url = "https://www.fool.com" + links[0]["href"]
        r2 = requests.get(transcript_url, headers=HEADERS, timeout=15)
        r2.raise_for_status()
        soup2 = BeautifulSoup(r2.text, "html.parser")
        body = soup2.get_text(separator=" ").lower()[:5000]

        bullish_phrases = ["guidance raised", "buyback", "accelerating", "record revenue",
                           "strong demand", "margin expansion", "outperformed"]
        warning_phrases = ["headwinds", "uncertain", "monitoring", "softness",
                           "challenging environment", "below expectations", "reduced guidance"]

        bull_hits = [p for p in bullish_phrases if p in body]
        warn_hits = [p for p in warning_phrases if p in body]

        return {
            "bullish_signals": bull_hits,
            "warning_signals": warn_hits,
            "net_signal": "BULLISH" if len(bull_hits) > len(warn_hits) else
                          ("WARNING" if warn_hits else "NEUTRAL"),
        }
    except Exception as exc:
        log.error("earnings_call_sentiment(%s): %s", ticker, exc)
        return {}


def crypto_fear_greed() -> dict:
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        r.raise_for_status()
        data = r.json()["data"][0]
        return {
            "value": int(data["value"]),
            "classification": data["value_classification"],
            "extreme_fear": int(data["value"]) < 25,
            "extreme_greed": int(data["value"]) > 75,
        }
    except Exception as exc:
        log.error("crypto_fear_greed: %s", exc)
        return {}


def earnings_calendar(ticker: str) -> dict:
    try:
        import yfinance as yf
        from datetime import datetime, timedelta
        t = yf.Ticker(ticker)
        info = t.info or {}
        ts = info.get("earningsTimestamp") or info.get("earningsTimestampStart")
        if ts:
            dt = datetime.fromtimestamp(ts)
            days_away = (dt - datetime.now()).days
            return {
                "next_earnings": str(dt.date()),
                "days_away": days_away,
                "imminent": days_away <= 7,
            }
        return {"next_earnings": None}
    except Exception as exc:
        log.error("earnings_calendar(%s): %s", ticker, exc)
        return {}


def economic_calendar() -> list:
    """Fetch ForexFactory economic calendar XML for this week."""
    try:
        import feedparser
        feed = feedparser.parse("https://nfs.faireconomy.media/ff_calendar_thisweek.xml")
        high_impact = []
        for e in feed.entries:
            impact = e.get("impact", "").lower()
            if "high" in impact:
                high_impact.append({
                    "title": e.get("title", ""),
                    "date": e.get("published", ""),
                    "country": e.get("country", ""),
                })
        return high_impact[:10]
    except Exception as exc:
        log.error("economic_calendar: %s", exc)
        return []


def newsletter_mentions(ticker: str) -> dict:
    """Google News search for ticker on Substack."""
    try:
        import feedparser
        url = f"https://news.google.com/rss/search?q={ticker}+site:substack.com&hl=en"
        feed = feedparser.parse(url)
        return {
            "substack_mention_count": len(feed.entries),
            "recent": [e.get("title", "") for e in feed.entries[:3]],
        }
    except Exception as exc:
        log.error("newsletter_mentions(%s): %s", ticker, exc)
        return {}
