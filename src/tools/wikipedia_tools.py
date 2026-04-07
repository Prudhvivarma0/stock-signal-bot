"""Wikipedia pageview trends."""
import logging
import requests
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


def wikipedia_views(article_title: str) -> dict:
    try:
        end = datetime.now()
        start = end - timedelta(days=90)
        url = (
            f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
            f"en.wikipedia/all-access/all-agents/{article_title}/daily/"
            f"{start.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}"
        )
        r = requests.get(url, timeout=15, headers={"User-Agent": "StockResearchBot/1.0"})
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            return {}
        views = [i["views"] for i in items]
        recent_7 = sum(views[-7:])
        prior_7 = sum(views[-14:-7])
        wow_change = round((recent_7 - prior_7) / max(prior_7, 1) * 100, 1)
        return {
            "recent_7d_views": recent_7,
            "prior_7d_views": prior_7,
            "wow_change_pct": wow_change,
            "total_90d_views": sum(views),
        }
    except Exception as exc:
        log.error("wikipedia_views(%s): %s", article_title, exc)
        return {}
