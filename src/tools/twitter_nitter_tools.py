"""Twitter/X via Nitter RSS fallback instances."""
import logging
import feedparser

log = logging.getLogger(__name__)

NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.net",
    "https://nitter.unixfox.eu",
]


def nitter_rss(ticker: str) -> dict:
    """Try nitter instances to get tweets mentioning the ticker."""
    for base in NITTER_INSTANCES:
        try:
            url = f"{base}/search/rss?q=%24{ticker}&f=tweets"
            feed = feedparser.parse(url)
            if feed.entries:
                positive_words = ["bullish", "buy", "long", "calls", "moon", "breakout", "beat"]
                negative_words = ["bearish", "sell", "short", "puts", "dump", "miss", "down"]
                scores = []
                for e in feed.entries[:30]:
                    title = (e.get("title", "") + " " + e.get("summary", "")).lower()
                    pos = sum(1 for w in positive_words if w in title)
                    neg = sum(1 for w in negative_words if w in title)
                    scores.append((pos - neg) / max(pos + neg, 1) if pos + neg else 0)
                avg = sum(scores) / len(scores) if scores else 0
                return {
                    "mention_count": len(feed.entries),
                    "avg_sentiment": round(avg, 3),
                    "instance_used": base,
                }
        except Exception as exc:
            log.debug("nitter %s: %s", base, exc)
    return {"mention_count": 0, "avg_sentiment": 0, "error": "all instances failed"}


def tradingview_ideas_rss(ticker: str) -> dict:
    """Count bullish vs bearish TradingView ideas."""
    try:
        url = f"https://www.tradingview.com/feed/?sort=recent&symbol=NASDAQ:{ticker}"
        feed = feedparser.parse(url)
        bull = sum(1 for e in feed.entries if "bullish" in (e.get("title", "") + e.get("summary", "")).lower())
        bear = sum(1 for e in feed.entries if "bearish" in (e.get("title", "") + e.get("summary", "")).lower())
        return {"total": len(feed.entries), "bullish": bull, "bearish": bear}
    except Exception as exc:
        log.error("tradingview_ideas_rss(%s): %s", ticker, exc)
        return {}
