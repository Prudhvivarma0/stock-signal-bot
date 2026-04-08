"""Google Trends analysis via pytrends."""
import logging

log = logging.getLogger(__name__)


def google_trends_scan(ticker: str, company_name: str = "") -> dict:
    """Fetch Google Trends interest. 45s hard timeout via subprocess-safe thread."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    ex = ThreadPoolExecutor(max_workers=1)
    try:
        future = ex.submit(_trends_inner, ticker, company_name)
        result = future.result(timeout=45)
        ex.shutdown(wait=False)
        return result
    except FuturesTimeout:
        ex.shutdown(wait=False)
        log.warning("google_trends_scan(%s): timed out after 45s", ticker)
        return {"error": "timeout"}
    except Exception as exc:
        ex.shutdown(wait=False)
        log.error("google_trends_scan(%s): %s", ticker, exc)
        return {"error": str(exc)}


def _trends_inner(ticker: str, company_name: str = "") -> dict:
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=240, timeout=(10, 30))  # connect 10s, read 30s
        kw = company_name or ticker
        pt.build_payload([kw], timeframe="today 3-m")
        df = pt.interest_over_time()
        if df.empty:
            return {"error": "no data"}
        series = df[kw].dropna()
        if len(series) < 4:
            return {"current": int(series.iloc[-1]) if len(series) else 0}

        recent = series.iloc[-4:].mean()
        prior = series.iloc[-8:-4].mean() if len(series) >= 8 else series.iloc[:4].mean()
        absolute = float(series.iloc[-1])
        slope = float(recent - prior)
        pre_hype = absolute < 30 and slope > 5

        return {
            "current_score": round(absolute, 1),
            "recent_avg": round(float(recent), 1),
            "prior_avg": round(float(prior), 1),
            "slope": round(slope, 2),
            "pre_hype_signal": pre_hype,
            "direction": "rising" if slope > 0 else "falling",
        }
    except Exception as exc:
        log.error("_trends_inner(%s): %s", ticker, exc)
        return {"error": str(exc)}
