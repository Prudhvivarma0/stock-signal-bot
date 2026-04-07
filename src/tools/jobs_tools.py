"""Job posting signals via public APIs."""
import logging
import requests

log = logging.getLogger(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StockResearchBot/1.0)"}


def job_postings_scan(company_name: str) -> dict:
    """Use LinkedIn jobs API (public JSON) to count open roles by department."""
    try:
        query = company_name.replace(" ", "%20")
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={query}&start=0"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = soup.find_all("li")
        titles = [j.find("h3").get_text(strip=True).lower() if j.find("h3") else "" for j in jobs]

        dept_counts = {}
        buckets = {
            "engineering": ["engineer", "developer", "software", "data", "ml", "ai", "machine learning"],
            "finance": ["finance", "accounting", "treasury", "m&a", "mergers", "acquisitions"],
            "legal": ["legal", "compliance", "counsel", "attorney", "regulatory"],
            "sales": ["sales", "account executive", "business development"],
            "marketing": ["marketing", "brand", "content", "growth"],
            "hr": ["hr", "human resources", "recruiting", "talent"],
            "operations": ["operations", "supply chain", "logistics"],
        }
        for title in titles:
            for dept, keywords in buckets.items():
                if any(k in title for k in keywords):
                    dept_counts[dept] = dept_counts.get(dept, 0) + 1

        # flags
        flags = []
        if dept_counts.get("finance", 0) > 5:
            flags.append("high_finance_hiring — possible M&A or restructuring")
        if dept_counts.get("legal", 0) > 3:
            flags.append("elevated_legal_hiring — potential regulatory issues")
        if dept_counts.get("engineering", 0) > 10:
            flags.append("heavy_engineering_hiring — product expansion")

        return {
            "total_postings": len(titles),
            "by_department": dept_counts,
            "flags": flags,
        }
    except Exception as exc:
        log.error("job_postings_scan(%s): %s", company_name, exc)
        return {}
