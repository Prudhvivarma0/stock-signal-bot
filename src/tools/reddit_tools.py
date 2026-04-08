"""Reddit scanning via PRAW."""
import logging
import os
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

SUBREDDITS = [
    "stocks", "investing", "wallstreetbets", "StockMarket",
    "options", "ValueInvesting",
]


def _get_reddit():
    import praw
    return praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID", ""),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET", ""),
        user_agent=os.getenv("REDDIT_USER_AGENT", "StockResearchBot/1.0"),
        timeout=10,
        ratelimit_seconds=5,
    )


def reddit_scan(ticker: str) -> dict:
    """Scan Reddit for ticker mentions."""
    if not os.getenv("REDDIT_CLIENT_ID", ""):
        log.info("reddit_scan: no credentials configured, skipping")
        return {"mentions_24h": 0, "velocity": 0, "error": "no_credentials"}
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    ex = ThreadPoolExecutor(max_workers=1)
    try:
        future = ex.submit(_reddit_scan_inner, ticker)
        result = future.result(timeout=30)
        ex.shutdown(wait=False)
        return result
    except FuturesTimeout:
        ex.shutdown(wait=False)
        log.warning("reddit_scan(%s): timed out after 30s", ticker)
        return {"mentions_24h": 0, "velocity": 0, "error": "timeout"}
    except Exception as exc:
        ex.shutdown(wait=False)
        log.error("reddit_scan(%s): %s", ticker, exc)
        return {"mentions_24h": 0, "velocity": 0, "error": str(exc)}


def _reddit_scan_inner(ticker: str) -> dict:
    try:
        reddit = _get_reddit()
        now = datetime.now(timezone.utc)
        cutoff_6h = (now - timedelta(hours=6)).timestamp()
        cutoff_prev = (now - timedelta(hours=12)).timestamp()

        mentions_24h = 0
        last_6h = 0
        prev_6h = 0
        urgent_dd = []

        for sub_name in SUBREDDITS:
            try:
                sub = reddit.subreddit(sub_name)
                for post in sub.search(ticker, sort="new", time_filter="day", limit=10):
                    title = (post.title or "").lower()
                    body = (post.selftext or "").lower()
                    if ticker.lower() not in title and ticker.lower() not in body:
                        continue
                    mentions_24h += 1
                    if post.created_utc >= cutoff_6h:
                        last_6h += 1
                    elif post.created_utc >= cutoff_prev:
                        prev_6h += 1
                    if post.score >= 100 and any(w in title for w in ["dd", "deep dive", "analysis", "thesis"]):
                        urgent_dd.append({
                            "title": post.title,
                            "score": post.score,
                            "subreddit": sub_name,
                        })
            except Exception as sub_exc:
                log.debug("reddit sub %s: %s", sub_name, sub_exc)

        velocity = (last_6h - prev_6h) / max(prev_6h, 1)

        return {
            "mentions_24h": mentions_24h,
            "mentions_last_6h": last_6h,
            "velocity": round(velocity, 2),
            "urgent_dd_posts": urgent_dd[:5],
            "trigger_emergency": bool(urgent_dd),
        }
    except Exception as exc:
        log.error("_reddit_scan_inner(%s): %s", ticker, exc)
        return {"mentions_24h": 0, "velocity": 0, "error": str(exc)}
