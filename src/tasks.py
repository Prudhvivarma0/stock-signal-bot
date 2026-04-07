"""CrewAI task definitions."""
import json
from crewai import Task
from src import agents as ag


def fundamentals_task(ticker: str, holding: dict = None) -> Task:
    holding_context = ""
    if holding:
        holding_context = (
            f"The investor holds {holding.get('shares')} shares at "
            f"${holding.get('entry_price')} avg entry. "
            f"Original thesis: {holding.get('thesis', 'not provided')}."
        )

    return Task(
        description=(
            f"Run a complete fundamental analysis on {ticker}. {holding_context}\n\n"
            "Use yfinance_fundamentals to get P/E, forward P/E, PEG, EPS, revenue growth, "
            "margins, FCF, debt/equity, ROE, book value, short ratio, institutional ownership, "
            "analyst targets, and earnings history.\n"
            "Use sec_edgar_facts to get 3-year revenue/income/cash flow trends.\n"
            "Use sec_8k_alerts to check for any breaking events today.\n"
            "Use insider_transactions and openinsider_scrape for last 30 days of insider activity.\n"
            "Use fred_macro for current interest rate environment.\n\n"
            "Return a JSON with: fundamental_score (-1 to 1), valuation (cheap/fair/expensive), "
            "financial_health (strong/mixed/weak), insider_signal (bullish/neutral/bearish), "
            "key_metrics (dict), trend_direction, flags (list), reasoning (string)."
        ),
        expected_output=(
            "JSON object with fundamental_score, valuation, financial_health, insider_signal, "
            "key_metrics, trend_direction, flags, reasoning."
        ),
        agent=ag.fundamentals_agent(),
    )


def news_task(ticker: str, company_name: str = "") -> Task:
    return Task(
        description=(
            f"Run comprehensive news intelligence on {ticker} ({company_name}).\n\n"
            "Check: Google News RSS (multiple query angles), Yahoo Finance RSS, "
            "Reuters, CNBC, Seeking Alpha, Benzinga analyst ratings, "
            "Business Wire press releases, PR Newswire, NASDAQ press releases, UAE news sources.\n"
            "Also check SEC 8-K filings for today.\n\n"
            "Score each article -1 to +1. Weight: last 6h = 3x, last 24h = 2x, older = 1x.\n"
            "Flag URGENT for: recall, SEC investigation, fraud, lawsuit, class action, bankruptcy.\n\n"
            "Return JSON with: news_score, article_count, sources_checked, urgent_flags, "
            "top_positive (list), top_negative (list), press_releases_today, sentiment_shift, reasoning."
        ),
        expected_output=(
            "JSON with news_score, article_count, sources_checked, urgent_flags, "
            "top_positive, top_negative, press_releases_today, sentiment_shift, reasoning."
        ),
        agent=ag.news_agent(),
    )


def social_task(ticker: str, company_name: str = "") -> Task:
    return Task(
        description=(
            f"Run social and community intelligence on {ticker} ({company_name}).\n\n"
            "Scan Reddit across 18 subreddits for mention count and velocity (last 6h vs prev 6h). "
            "Flag any DD posts with >100 upvotes.\n"
            "Check StockTwits bull/bear ratio.\n"
            "Try Nitter RSS for Twitter mentions.\n"
            "Check TradingView ideas RSS for bullish/bearish count.\n"
            "Run Google Trends (90-day): calculate slope acceleration. "
            "Low absolute + rising slope = pre-hype signal.\n"
            "Check Wikipedia pageview 90-day trend and week-over-week change.\n"
            "Check YouTube finance channels for mentions in last 7 days.\n\n"
            "Return JSON with: social_score, reddit_mentions_24h, reddit_velocity, "
            "stocktwits_bullish_pct, google_trends_direction, google_trends_score, "
            "wikipedia_views_change, pre_hype_signal (bool), pre_hype_reasoning, "
            "urgent_flags, reasoning."
        ),
        expected_output=(
            "JSON with social_score, reddit_mentions_24h, reddit_velocity, "
            "stocktwits_bullish_pct, google_trends_direction, google_trends_score, "
            "wikipedia_views_change, pre_hype_signal, pre_hype_reasoning, urgent_flags, reasoning."
        ),
        agent=ag.social_agent(),
    )


def technical_task(ticker: str, holding: dict = None) -> Task:
    entry_context = ""
    if holding:
        entry_context = (
            f"Entry price: ${holding.get('entry_price')}, "
            f"Stop-loss: {holding.get('stop_loss_pct', 8)}%."
        )

    return Task(
        description=(
            f"Run full technical analysis on {ticker}. {entry_context}\n\n"
            "Fetch daily OHLCV (2 years) and weekly OHLCV (5 years).\n"
            "Calculate: SMA20/50/200, EMA9/21/50, RSI(14), MACD(12,26,9), "
            "Stochastic(14,3,3), Williams %R, CCI(20), MFI(14), ATR(14), "
            "Bollinger Bands(20,2), Keltner Channels, OBV, CMF.\n"
            "Detect patterns: golden/death cross, higher highs/lows, Bollinger squeeze, "
            "volume expansion/contraction.\n"
            "Compare vs SPY/QQQ for 1m/3m/6m relative strength.\n"
            "Analyse options chain: put/call ratio, unusual large call activity.\n"
            "Calculate ATR-based stop loss.\n\n"
            "Return JSON with: technical_score (-1 to 1), signal (BUY/NEUTRAL/AVOID), "
            "trend, rsi, macd_signal, golden_cross, death_cross, support_level, "
            "resistance_level, stop_loss_price, options_signal, unusual_options, "
            "momentum_vs_market, reasoning."
        ),
        expected_output=(
            "JSON with technical_score, signal, trend, rsi, macd_signal, golden_cross, "
            "death_cross, support_level, resistance_level, stop_loss_price, options_signal, "
            "unusual_options, momentum_vs_market, reasoning."
        ),
        agent=ag.technical_agent(),
    )


def analyst_institutional_task(ticker: str) -> Task:
    return Task(
        description=(
            f"Run analyst and institutional intelligence on {ticker}.\n\n"
            "Get analyst consensus, mean/high/low price targets, and analyst count from yfinance.\n"
            "Scrape Finviz for recommendation, price target, short float, insider/institutional %.\n"
            "Check Benzinga ratings RSS for recent upgrades/downgrades.\n"
            "Search SEC EDGAR 13F filings last 90 days for institutional activity.\n"
            "Check short interest trend.\n\n"
            "Return JSON with: analyst_score (-1 to 1), consensus, avg_target, upside_pct, "
            "recent_changes, institutional_trend, major_fund_activity, "
            "short_interest_pct, short_squeeze_potential, smart_money_signal, reasoning."
        ),
        expected_output=(
            "JSON with analyst_score, consensus, avg_target, upside_pct, recent_changes, "
            "institutional_trend, major_fund_activity, short_interest_pct, "
            "short_squeeze_potential, smart_money_signal, reasoning."
        ),
        agent=ag.analyst_institutional_agent(),
    )


def alternative_data_task(ticker: str, company_name: str = "") -> Task:
    return Task(
        description=(
            f"Run alternative data intelligence on {ticker} ({company_name}).\n\n"
            "Google Trends deep (12-month): identify exact acceleration points.\n"
            "Job postings scan: count by department, flag unusual patterns.\n"
            "GitHub activity (if tech company): stars, commits, contributors.\n"
            "Earnings call sentiment: scrape latest transcript, flag confident vs hedging language.\n"
            "Crypto fear & greed index for market context.\n"
            "Commodity prices: oil, gold, copper (relevant for UAE energy stocks).\n"
            "Earnings calendar: is earnings within 7 days? Heightened monitoring.\n"
            "Economic calendar: any high-impact macro events in next 48h?\n"
            "Newsletter mentions: Substack mentions signal retail attention wave.\n\n"
            "Return JSON with: alternative_score (-1 to 1), pre_hype_detected, "
            "pre_hype_signals (list), early_warning_signals (list), "
            "google_trend_direction, github_health, hiring_signal, "
            "app_sentiment_trend, macro_risks, upcoming_catalysts, reasoning."
        ),
        expected_output=(
            "JSON with alternative_score, pre_hype_detected, pre_hype_signals, "
            "early_warning_signals, google_trend_direction, github_health, hiring_signal, "
            "app_sentiment_trend, macro_risks, upcoming_catalysts, reasoning."
        ),
        agent=ag.alternative_data_agent(),
    )


def manager_decision_task(
    ticker: str,
    holding: dict,
    portfolio: dict,
    fundamentals_result: str,
    news_result: str,
    social_result: str,
    technical_result: str,
    analyst_result: str,
    alt_data_result: str,
) -> Task:
    budget = portfolio.get("budget_usd", 0)
    name = portfolio.get("user_name", "the investor")

    return Task(
        description=(
            f"You have received deep research on {ticker} from 6 specialist agents.\n\n"
            f"=== FUNDAMENTALS ===\n{fundamentals_result}\n\n"
            f"=== NEWS ===\n{news_result}\n\n"
            f"=== SOCIAL/SENTIMENT ===\n{social_result}\n\n"
            f"=== TECHNICAL ===\n{technical_result}\n\n"
            f"=== ANALYST/INSTITUTIONAL ===\n{analyst_result}\n\n"
            f"=== ALTERNATIVE DATA ===\n{alt_data_result}\n\n"
            "---\n"
            f"This research is for {name}, who:\n"
            f"- Has ${budget:,} available\n"
            "- Holds positions for days to weeks to months (NOT day trading)\n"
            "- Strategy: find signals before mainstream knows, buy early, sell into hype\n"
            "- Also needs protection: alert if something they hold is heading for trouble\n\n"
            "READ EVERYTHING. Then decide:\n"
            "1. Is there a genuine pre-hype signal confirmed by MULTIPLE INDEPENDENT sources?\n"
            "2. For this holding: is the original thesis deteriorating in a meaningful way?\n"
            "3. How confident are you really? What contradicts your view?\n"
            "4. What timeframe? What would change your view?\n\n"
            "CRITICAL: Most of the time, the right answer is silence.\n"
            "Only output an alert if you would genuinely call a smart friend and say "
            "'you need to look at this today.'\n\n"
            "If alerting, write like a smart friend sending a message.\n"
            "No tables, no scores, no bullet lists.\n"
            "Clear honest thinking in plain English. Under 350 words.\n"
            "Start with: {ticker} — OPPORTUNITY / WARNING / URGENT\n"
            "End with what they might consider (don't tell them what to do).\n\n"
            "If NOT alerting, output exactly: NO_ALERT\n\n"
            "Also output the alert_type field: OPPORTUNITY / WARNING / URGENT / NO_ALERT"
        ),
        expected_output=(
            "Either 'NO_ALERT' or a plain-English alert message under 350 words starting with "
            "'{ticker} — OPPORTUNITY/WARNING/URGENT', plus alert_type field."
        ),
        agent=ag.manager_agent(),
    )
