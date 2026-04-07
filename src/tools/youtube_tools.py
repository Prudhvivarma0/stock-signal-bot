"""YouTube finance channel mention tracking via RSS."""
import logging
import feedparser
from datetime import datetime, timedelta, timezone
import email.utils

log = logging.getLogger(__name__)

FINANCE_CHANNELS = [
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCbmNph6atAoGfqLoCL_duAg",  # Ticker Symbol: YOU
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCV6KDgJskWaEckne5aPA0aQ",  # Graham Stephan
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCL_v4tC8QQ4oCPPBTLWbNGg",  # Andrei Jikh
    "https://www.youtube.com/feeds/videos.xml?channel_id=UC3mjMoJuFaABeR-ORypFxoA",  # Meet Kevin
]


def youtube_mentions(ticker: str) -> dict:
    mentions = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    try:
        for feed_url in FINANCE_CHANNELS:
            try:
                feed = feedparser.parse(feed_url)
                for e in feed.entries:
                    title = e.get("title", "")
                    if ticker.upper() in title.upper():
                        pub = e.get("published", "")
                        try:
                            ts = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                            if ts < cutoff:
                                continue
                        except Exception:
                            pass
                        mentions.append({
                            "title": title,
                            "channel": feed.feed.get("title", "unknown"),
                            "link": e.get("link", ""),
                        })
            except Exception as exc:
                log.debug("youtube feed %s: %s", feed_url, exc)
        return {"mention_count": len(mentions), "mentions": mentions[:10]}
    except Exception as exc:
        log.error("youtube_mentions(%s): %s", ticker, exc)
        return {"mention_count": 0}
