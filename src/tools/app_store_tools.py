"""App Store review sentiment via iOS RSS API."""
import logging
import feedparser

log = logging.getLogger(__name__)


def app_store_reviews(app_id: str, country: str = "us") -> dict:
    """Fetch iOS App Store reviews via RSS."""
    try:
        url = f"https://itunes.apple.com/{country}/rss/customerreviews/page=1/id={app_id}/sortby=mostrecent/json"
        import requests
        r = requests.get(url, timeout=15, headers={"User-Agent": "StockResearchBot/1.0"})
        r.raise_for_status()
        data = r.json()
        entries = data.get("feed", {}).get("entry", [])
        if not entries:
            return {}

        ratings = []
        recent_titles = []
        for e in entries[:30]:
            if isinstance(e, dict):
                rating_obj = e.get("im:rating", {})
                rating = rating_obj.get("label") if isinstance(rating_obj, dict) else None
                if rating:
                    try:
                        ratings.append(int(rating))
                    except ValueError:
                        pass
                title_obj = e.get("title", {})
                title = title_obj.get("label", "") if isinstance(title_obj, dict) else ""
                recent_titles.append(title)

        avg_rating = sum(ratings) / len(ratings) if ratings else None
        return {
            "avg_rating": round(avg_rating, 2) if avg_rating else None,
            "review_count": len(ratings),
            "sample_titles": recent_titles[:5],
        }
    except Exception as exc:
        log.error("app_store_reviews(%s): %s", app_id, exc)
        return {}
