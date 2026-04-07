"""USPTO patent filing signals."""
import logging
import requests
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


def patent_filings(company_name: str) -> dict:
    """Search USPTO full-text search for recent patent applications."""
    try:
        # USPTO PatentsView API
        r = requests.post(
            "https://api.patentsview.org/patents/query",
            json={
                "q": {"_contains": {"assignee_organization": company_name}},
                "f": ["patent_number", "patent_title", "patent_date", "patent_type",
                      "assignee_organization"],
                "o": {"sort": [{"patent_date": "desc"}]},
                "s": [{"patent_date": "desc"}],
            },
            headers={"Content-Type": "application/json"},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        patents = data.get("patents", []) or []

        # group by year
        current_year = datetime.now().year
        recent = [p for p in patents if str(current_year) in (p.get("patent_date") or "")]
        prev_year = [p for p in patents if str(current_year - 1) in (p.get("patent_date") or "")]

        return {
            "total_found": data.get("total_patent_count", len(patents)),
            "recent_year_count": len(recent),
            "prev_year_count": len(prev_year),
            "trend": "increasing" if len(recent) > len(prev_year) else "decreasing",
            "latest_titles": [p.get("patent_title") for p in recent[:5]],
        }
    except Exception as exc:
        log.error("patent_filings(%s): %s", company_name, exc)
        return {}
