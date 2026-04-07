"""News RSS aggregation and sentiment scoring."""
import logging
import os
import statistics
import time
from datetime import datetime, timedelta, timezone

import feedparser
import requests

log = logging.getLogger(__name__)


def newsapi_search(ticker: str, company_name: str = "") -> list:
    """NewsAPI everything endpoint — 100 req/day on free tier."""
    try:
        api_key = os.getenv("NEWSAPI_KEY", "")
        if not api_key:
            return []
        query = company_name or ticker
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "sortBy": "publishedAt",
                "pageSize": 20,
                "language": "en",
                "apiKey": api_key,
            },
            timeout=15,
        )
        r.raise_for_status()
        articles = r.json().get("articles", [])
        from datetime import timezone as tz
        results = []
        for a in articles:
            pub = a.get("publishedAt", "")
            age = 48.0
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                age = (datetime.now(tz.utc) - dt).total_seconds() / 3600
            except Exception:
                pass
            results.append({
                "title": a.get("title", ""),
                "source": f"newsapi:{a.get('source', {}).get('name', 'unknown')}",
                "age_hours": age,
                "link": a.get("url", ""),
            })
        return results
    except Exception as exc:
        log.error("newsapi_search(%s): %s", ticker, exc)
        return []


def _parse_feed(url: str, timeout: int = 10) -> list:
    try:
        feed = feedparser.parse(url)
        return feed.entries or []
    except Exception as exc:
        log.error("_parse_feed(%s): %s", url, exc)
        return []


def _entry_age_hours(entry) -> float:
    try:
        import email.utils
        pub = entry.get("published", "") or entry.get("updated", "")
        if pub:
            ts = email.utils.parsedate_to_datetime(pub)
            ts = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
            return (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    except Exception:
        pass
    return 48.0  # default old


def google_news_rss(ticker: str, company_name: str = "") -> list:
    queries = [
        f"{ticker}+stock",
        f"{ticker}+earnings",
        f"{ticker}+acquisition",
        f"{ticker}+SEC+investigation",
        f"{ticker}+partnership",
        f"{ticker}+recall",
        f"{ticker}+lawsuit",
    ]
    if company_name:
        queries.append(company_name.replace(" ", "+"))
    articles = []
    for q in queries:
        entries = _parse_feed(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en")
        for e in entries[:5]:
            articles.append({
                "title": e.get("title", ""),
                "source": "google_news",
                "query": q,
                "age_hours": _entry_age_hours(e),
                "link": e.get("link", ""),
            })
    return articles


def yahoo_finance_rss(ticker: str) -> list:
    entries = _parse_feed(f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US")
    return [{"title": e.get("title", ""), "source": "yahoo_finance", "age_hours": _entry_age_hours(e)} for e in entries[:10]]


def reuters_rss() -> list:
    feeds = [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.reuters.com/reuters/technologyNews",
    ]
    articles = []
    for url in feeds:
        for e in _parse_feed(url)[:5]:
            articles.append({"title": e.get("title", ""), "source": "reuters", "age_hours": _entry_age_hours(e)})
    return articles


def cnbc_rss() -> list:
    feeds = [
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    ]
    articles = []
    for url in feeds:
        for e in _parse_feed(url)[:5]:
            articles.append({"title": e.get("title", ""), "source": "cnbc", "age_hours": _entry_age_hours(e)})
    return articles


def seeking_alpha_rss(ticker: str) -> list:
    entries = _parse_feed(f"https://seekingalpha.com/api/sa/combined/{ticker}.xml")
    return [{"title": e.get("title", ""), "source": "seeking_alpha", "age_hours": _entry_age_hours(e)} for e in entries[:8]]


def benzinga_rss() -> list:
    feeds = [
        "https://www.benzinga.com/feed",
        "https://www.benzinga.com/rss/analyst-ratings",
    ]
    articles = []
    for url in feeds:
        for e in _parse_feed(url)[:5]:
            articles.append({"title": e.get("title", ""), "source": "benzinga", "age_hours": _entry_age_hours(e)})
    return articles


def business_wire_rss() -> list:
    entries = _parse_feed("https://www.businesswire.com/rss/home/?rss=G1")
    return [{"title": e.get("title", ""), "source": "business_wire", "age_hours": _entry_age_hours(e)} for e in entries[:10]]


def pr_newswire_rss() -> list:
    entries = _parse_feed("https://www.prnewswire.com/rss/news-releases-list.rss")
    return [{"title": e.get("title", ""), "source": "pr_newswire", "age_hours": _entry_age_hours(e)} for e in entries[:10]]


def uae_news_rss() -> list:
    feeds = [
        ("https://gulfnews.com/rss/business", "gulf_news"),
        ("https://www.khaleejtimes.com/feeds/business", "khaleej_times"),
        ("https://www.thenationalnews.com/arc/outboundfeeds/rss/?outputType=xml", "the_national"),
        ("https://www.arabianbusiness.com/rss", "arabian_business"),
    ]
    articles = []
    for url, src in feeds:
        for e in _parse_feed(url)[:5]:
            articles.append({"title": e.get("title", ""), "source": src, "age_hours": _entry_age_hours(e)})
    return articles


def sentiment_score_articles(articles: list) -> dict:
    """Score articles -1 to +1. Weight recent more heavily."""
    positive_words = [
        "surge", "soar", "beat", "record", "growth", "profit", "gain", "buy",
        "upgrade", "bullish", "strong", "revenue", "raised", "breakout", "deal",
        "partnership", "acquisition", "innovation", "expansion", "dividend",
    ]
    negative_words = [
        "crash", "plunge", "miss", "loss", "decline", "sell", "downgrade",
        "bearish", "weak", "debt", "lawsuit", "recall", "investigation", "fraud",
        "cut", "layoff", "warning", "risk", "concern", "volatile", "drop",
    ]

    total_weight, total_score = 0.0, 0.0
    scored = []
    for art in articles:
        title = art.get("title", "").lower()
        age = art.get("age_hours", 48)
        weight = 3.0 if age <= 6 else (2.0 if age <= 24 else 1.0)
        pos = sum(1 for w in positive_words if w in title)
        neg = sum(1 for w in negative_words if w in title)
        score = (pos - neg) / max(pos + neg, 1) if (pos + neg) else 0
        total_score += score * weight
        total_weight += weight
        scored.append({**art, "score": round(score, 2), "weight": weight})

    avg_score = total_score / total_weight if total_weight else 0

    scored_sorted = sorted(scored, key=lambda x: x["score"], reverse=True)
    top_positive = [a for a in scored_sorted if a["score"] > 0][:3]
    top_negative = [a for a in reversed(scored_sorted) if a["score"] < 0][:3]

    return {
        "avg_score": round(avg_score, 3),
        "article_count": len(articles),
        "top_positive": top_positive,
        "top_negative": top_negative,
    }


def build_news_report(ticker: str, company_name: str = "") -> dict:
    """Aggregate all news sources and score sentiment."""
    all_articles = []
    sources_checked = []

    for fn, args, name in [
        (google_news_rss, (ticker, company_name), "google_news"),
        (yahoo_finance_rss, (ticker,), "yahoo_finance"),
        (newsapi_search, (ticker, company_name), "newsapi"),
        (seeking_alpha_rss, (ticker,), "seeking_alpha"),
        (benzinga_rss, (), "benzinga"),
        (business_wire_rss, (), "business_wire"),
        (pr_newswire_rss, (), "pr_newswire"),
        (uae_news_rss, (), "uae_news"),
        (reuters_rss, (), "reuters"),
        (cnbc_rss, (), "cnbc"),
    ]:
        try:
            items = fn(*args)
            if items:
                all_articles.extend(items)
                sources_checked.append(name)
        except Exception as exc:
            log.error("build_news_report source %s: %s", name, exc)

    # filter to articles mentioning ticker or company
    relevant = [
        a for a in all_articles
        if ticker.lower() in a.get("title", "").lower()
        or (company_name and company_name.split()[0].lower() in a.get("title", "").lower())
    ]
    # fallback: use all
    if len(relevant) < 3:
        relevant = all_articles

    sentiment = sentiment_score_articles(relevant)

    # urgency flags
    urgent = []
    for a in relevant:
        t = a.get("title", "").lower()
        if any(w in t for w in ["recall", "sec investigation", "fraud", "lawsuit", "bankruptcy",
                                  "class action", "doj", "indictment", "crash"]):
            urgent.append(a.get("title"))

    return {
        "news_score": sentiment["avg_score"],
        "article_count": len(relevant),
        "sources_checked": sources_checked,
        "urgent_flags": urgent,
        "top_positive": sentiment["top_positive"],
        "top_negative": sentiment["top_negative"],
        "reasoning": f"Scanned {len(relevant)} articles from {len(sources_checked)} sources. "
                     f"Avg sentiment: {sentiment['avg_score']:.3f}. "
                     f"Urgent flags: {len(urgent)}.",
    }
