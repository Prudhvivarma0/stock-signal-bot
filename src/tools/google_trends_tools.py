"""Google Trends analysis via pytrends."""
import logging
import time

log = logging.getLogger(__name__)


def google_trends_scan(ticker: str, company_name: str = "") -> dict:
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=240)  # UTC+4 Dubai
        kw = company_name or ticker
        pt.build_payload([kw], timeframe="today 3-m")
        df = pt.interest_over_time()
        if df.empty:
            return {"error": "no data"}
        series = df[kw].dropna()
        if len(series) < 4:
            return {"current": int(series.iloc[-1]) if len(series) else 0}

        # slope acceleration: compare recent 4 weeks to prior 4 weeks
        recent = series.iloc[-4:].mean()
        prior = series.iloc[-8:-4].mean() if len(series) >= 8 else series.iloc[:4].mean()
        absolute = float(series.iloc[-1])
        slope = float(recent - prior)

        pre_hype = absolute < 30 and slope > 5  # low absolute, rising

        return {
            "current_score": round(absolute, 1),
            "recent_avg": round(float(recent), 1),
            "prior_avg": round(float(prior), 1),
            "slope": round(slope, 2),
            "pre_hype_signal": pre_hype,
            "direction": "rising" if slope > 0 else "falling",
        }
    except Exception as exc:
        log.error("google_trends_scan(%s): %s", ticker, exc)
        return {"error": str(exc)}
