"""CrewAI tool wrappers — connects real data sources to agents."""
import json
import logging

from crewai.tools import tool

log = logging.getLogger(__name__)


def _j(obj) -> str:
    """Safe JSON serialise."""
    try:
        return json.dumps(obj, default=str)
    except Exception:
        return str(obj)


# ── Technical ─────────────────────────────────────────────────────────────────

@tool("technical_analysis")
def technical_analysis(ticker: str) -> str:
    """Full technical analysis: RSI, MACD, SMA20/50/200, Bollinger Bands, ATR,
    support/resistance, volume, options flow, relative strength vs SPY/QQQ.
    Input: ticker symbol (e.g. NVDA, AAPL)"""
    try:
        from src.tools.technical_tools import build_technical_report
        return _j(build_technical_report(ticker))
    except Exception as exc:
        return f"technical_analysis error: {exc}"


# ── Fundamentals ──────────────────────────────────────────────────────────────

@tool("yfinance_fundamentals")
def yfinance_fundamentals(ticker: str) -> str:
    """P/E, forward P/E, PEG, EPS, revenue growth, margins, FCF, debt/equity,
    ROE, book value, analyst targets, institutional ownership, earnings history.
    Input: ticker symbol"""
    try:
        from src.tools.yfinance_tools import yfinance_fundamentals as _fn
        return _j(_fn(ticker))
    except Exception as exc:
        return f"yfinance_fundamentals error: {exc}"


@tool("av_company_overview")
def av_company_overview(ticker: str) -> str:
    """Alpha Vantage company overview: sector, industry, P/E, EPS, revenue,
    profit margin, analyst target, description.
    Input: ticker symbol"""
    try:
        from src.tools.alpha_vantage_tools import av_company_overview as _fn
        return _j(_fn(ticker))
    except Exception as exc:
        return f"av_company_overview error: {exc}"


@tool("av_earnings")
def av_earnings(ticker: str) -> str:
    """Alpha Vantage earnings history: quarterly EPS actual vs estimate,
    surprise %, revenue trend.
    Input: ticker symbol"""
    try:
        from src.tools.alpha_vantage_tools import av_earnings as _fn
        return _j(_fn(ticker))
    except Exception as exc:
        return f"av_earnings error: {exc}"


@tool("fred_macro")
def fred_macro(_: str = "") -> str:
    """Current macro environment: Fed funds rate, CPI, 10Y/2Y treasury yields,
    unemployment rate. Input: ignored, pass empty string."""
    try:
        from src.tools.macro_tools import fred_macro as _fn
        return _j(_fn())
    except Exception as exc:
        return f"fred_macro error: {exc}"


@tool("insider_transactions")
def insider_transactions(ticker: str) -> str:
    """Recent insider buying/selling from OpenInsider (last 30 days).
    Input: ticker symbol"""
    try:
        from src.tools.insider_tools import openinsider_scrape
        return _j(openinsider_scrape(ticker))
    except Exception as exc:
        return f"insider_transactions error: {exc}"


@tool("sec_8k_alerts")
def sec_8k_alerts(ticker: str) -> str:
    """Recent SEC 8-K filings (material events, earnings, M&A, leadership changes).
    Input: ticker symbol"""
    try:
        from src.tools.sec_edgar_tools import sec_8k_recent
        return _j(sec_8k_recent(ticker))
    except Exception as exc:
        return f"sec_8k_alerts error: {exc}"


@tool("sec_edgar_facts")
def sec_edgar_facts(ticker: str) -> str:
    """3-year revenue, net income, and free cash flow trend from SEC EDGAR.
    Input: ticker symbol"""
    try:
        from src.tools.sec_edgar_tools import sec_edgar_facts as _fn
        return _j(_fn(ticker))
    except Exception as exc:
        return f"sec_edgar_facts error: {exc}"


# ── News ──────────────────────────────────────────────────────────────────────

@tool("news_scan")
def news_scan(ticker: str) -> str:
    """Scan 10+ news sources (Google News, Yahoo Finance, Reuters, CNBC,
    NewsAPI, Seeking Alpha, Benzinga) for recent articles. Returns scored
    sentiment and urgent flags.
    Input: ticker symbol"""
    try:
        from src.tools.news_rss_tools import build_news_report
        return _j(build_news_report(ticker))
    except Exception as exc:
        return f"news_scan error: {exc}"


@tool("press_releases")
def press_releases(ticker: str) -> str:
    """Recent press releases from Business Wire and PR Newswire.
    Input: ticker symbol or company name"""
    try:
        from src.tools.press_release_tools import nasdaq_press_releases
        return _j(nasdaq_press_releases(ticker))
    except Exception as exc:
        return f"press_releases error: {exc}"


# ── Social ────────────────────────────────────────────────────────────────────

@tool("reddit_scan")
def reddit_scan(ticker: str) -> str:
    """Scan 18 subreddits for mention count, velocity, sentiment, and notable posts.
    Input: ticker symbol"""
    try:
        from src.tools.reddit_tools import scan_reddit
        return _j(scan_reddit(ticker))
    except Exception as exc:
        return f"reddit_scan error: {exc}"


@tool("stocktwits_sentiment")
def stocktwits_sentiment(ticker: str) -> str:
    """StockTwits bull/bear ratio and recent message volume.
    Input: ticker symbol"""
    try:
        from src.tools.stocktwits_tools import stocktwits_stream as _fn
        return _j(_fn(ticker))
    except Exception as exc:
        return f"stocktwits_sentiment error: {exc}"


@tool("google_trends")
def google_trends(ticker: str) -> str:
    """Google Trends 90-day interest score, slope acceleration,
    and pre-hype signal detection (low absolute + rising = early signal).
    Input: ticker symbol"""
    try:
        from src.tools.google_trends_tools import google_trends_scan
        return _j(google_trends_scan(ticker))
    except Exception as exc:
        return f"google_trends error: {exc}"


@tool("wikipedia_views")
def wikipedia_views(ticker: str) -> str:
    """Wikipedia page view trend (90 days). Rising views = growing retail interest.
    Input: company name or ticker"""
    try:
        from src.tools.wikipedia_tools import wikipedia_pageviews
        return _j(wikipedia_pageviews(ticker))
    except Exception as exc:
        return f"wikipedia_views error: {exc}"


# ── Analyst & Institutional ───────────────────────────────────────────────────

@tool("analyst_ratings")
def analyst_ratings(ticker: str) -> str:
    """Analyst consensus, mean/high/low price targets, number of analysts,
    recent upgrades/downgrades from Finviz and Benzinga.
    Input: ticker symbol"""
    try:
        from src.tools.analyst_tools import yfinance_analyst, finviz_analyst_scrape
        yf_data = yfinance_analyst(ticker)
        fv_data = finviz_analyst_scrape(ticker)
        return _j({"yfinance": yf_data, "finviz": fv_data})
    except Exception as exc:
        return f"analyst_ratings error: {exc}"


@tool("institutional_ownership")
def institutional_ownership(ticker: str) -> str:
    """Recent 13F filings, institutional buying/selling, major fund activity.
    Input: ticker symbol"""
    try:
        from src.tools.institutional_tools import sec_13f_institutional
        return _j(sec_13f_institutional(ticker))
    except Exception as exc:
        return f"institutional_ownership error: {exc}"


# ── Alternative Data ──────────────────────────────────────────────────────────

@tool("job_postings")
def job_postings(ticker: str) -> str:
    """Job posting trends from LinkedIn/Indeed. Hiring surge = growth signal.
    Input: company name or ticker"""
    try:
        from src.tools.jobs_tools import job_postings_scan
        return _j(job_postings_scan(ticker))
    except Exception as exc:
        return f"job_postings error: {exc}"


@tool("options_flow")
def options_flow(ticker: str) -> str:
    """Put/call ratio, total option volume, unusual large options activity.
    Input: ticker symbol"""
    try:
        from src.tools.yfinance_tools import options_flow as _fn
        return _j(_fn(ticker))
    except Exception as exc:
        return f"options_flow error: {exc}"


# ── UAE / DFM / ADX ───────────────────────────────────────────────────────────

@tool("uae_fundamentals")
def uae_fundamentals(ticker: str) -> str:
    """Fundamentals for UAE stocks listed on DFM or ADX (EODHD source).
    Returns P/E, EPS, revenue, margins, ROE, book value, dividend yield.
    Input: ticker symbol (e.g. EMAAR, SALIK, DIB, FAB)"""
    try:
        from src.tools.eodhd_tools import eodhd_fundamentals
        # Detect exchange: try DFM first, fall back to ADX
        result = eodhd_fundamentals(ticker, exchange="DFM")
        if not result:
            result = eodhd_fundamentals(ticker, exchange="ADX")
        # Also get yfinance data with .AE suffix
        from src.tools.yfinance_tools import yfinance_fundamentals
        yf_data = yfinance_fundamentals(ticker)
        return _j({"eodhd": result, "yfinance": yf_data})
    except Exception as exc:
        return f"uae_fundamentals error: {exc}"


@tool("uae_price_data")
def uae_price_data(ticker: str) -> str:
    """Price history and technical data for UAE stocks (DFM/ADX).
    Returns OHLCV data, 52-week high/low, recent price trend.
    Input: ticker symbol (e.g. EMAAR, SALIK)"""
    try:
        from src.tools.uae_data import get_uae_history, get_uae_price
        price = get_uae_price(ticker)
        hist = get_uae_history(ticker, period="6mo", interval="1d")
        rows = []
        if not hist.empty:
            rows = hist.tail(30).to_dict(orient="records")
        return _j({"current_price_aed": price, "history_30d": rows})
    except Exception as exc:
        return f"uae_price_data error: {exc}"


@tool("uae_news")
def uae_news(ticker: str) -> str:
    """News for UAE-listed stocks from Gulf News, Arabian Business, The National,
    Khaleej Times, and UAE-specific Google News.
    Input: ticker symbol (e.g. EMAAR, SALIK) or company name"""
    try:
        from src.tools.news_rss_tools import uae_company_news_rss, uae_news_rss
        from src.tools.eodhd_tools import eodhd_news
        articles = uae_company_news_rss(ticker)
        eodhd_items = eodhd_news(ticker, exchange="DFM")
        general = uae_news_rss()
        # Filter general news for mentions of the ticker
        t_lower = ticker.lower()
        relevant_general = [a for a in general if t_lower in a.get("title", "").lower()]
        all_items = articles + eodhd_items + relevant_general
        return _j({"article_count": len(all_items), "articles": all_items[:20]})
    except Exception as exc:
        return f"uae_news error: {exc}"


@tool("uae_insider_transactions")
def uae_insider_transactions(ticker: str) -> str:
    """Insider transactions for UAE stocks from EODHD (DFM/ADX filings).
    Input: ticker symbol"""
    try:
        from src.tools.eodhd_tools import eodhd_insider_transactions
        result = eodhd_insider_transactions(ticker, exchange="DFM")
        if not result:
            from src.tools.eodhd_tools import eodhd_insider_transactions as _fn
            result = _fn(ticker, exchange="ADX")
        return _j(result)
    except Exception as exc:
        return f"uae_insider_transactions error: {exc}"
