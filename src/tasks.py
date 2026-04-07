"""CrewAI task definitions."""
import json
from crewai import Task
from src import agents as ag


SIGNAL_FORMAT = (
    "\n\nReturn your output as JSON with these fields at minimum:\n"
    '{"signal": "BULLISH|BEARISH|NEUTRAL", "confidence": 0-100, '
    '"score": -1.0 to 1.0, "flags": [], "reasoning": "..."}\n'
    "Every claim must cite its data source."
)


def fundamentals_task(ticker: str, holding: dict = None) -> Task:
    holding_context = ""
    exchange = "US"
    if holding:
        holding_context = (
            f"The investor holds {holding.get('shares')} shares at "
            f"${holding.get('entry_price')} avg entry. "
            f"Original thesis: {holding.get('thesis', 'not provided')}."
        )
        exchange = holding.get("exchange", "US")

    is_uae = exchange in ("DFM", "ADX")
    uae_note = (
        f"\nThis is a UAE stock on {exchange}. Use eodhd_fundamentals('{ticker}', '{exchange}') "
        f"for fundamentals and eodhd_insider_transactions for insider data. "
        f"SEC tools are not applicable — skip them."
    ) if is_uae else (
        "\nUse sec_edgar_facts to get 3-year revenue/income/cash flow trends.\n"
        "Use sec_8k_alerts to check for any breaking events today.\n"
        "Use insider_transactions and openinsider_scrape for last 30 days of insider activity."
    )

    return Task(
        description=(
            f"Run a complete fundamental analysis on {ticker}. {holding_context}\n\n"
            "Use yfinance_fundamentals to get P/E, forward P/E, PEG, EPS, revenue growth, "
            "margins, FCF, debt/equity, ROE, book value, short ratio, institutional ownership, "
            "analyst targets, and earnings history.\n"
            "Use av_company_overview and av_earnings for additional fundamental confirmation "
            "(EPS surprise history, quarterly revenue trend, analyst target).\n"
            f"{uae_note}\n"
            "Use fred_macro for current interest rate environment.\n\n"
            "Return a JSON with: fundamental_score (-1 to 1), valuation (cheap/fair/expensive), "
            "financial_health (strong/mixed/weak), insider_signal (bullish/neutral/bearish), "
            "key_metrics (dict), trend_direction, flags (list), reasoning (string), "
            "signal (BULLISH/BEARISH/NEUTRAL), confidence (0-100)."
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


def risk_manager_task(
    ticker: str,
    holding: dict,
    portfolio: dict,
    technical_result: str,
    fundamentals_result: str,
    bull_case: str,
    bear_case: str,
) -> Task:
    budget = portfolio.get("budget_usd", 0)
    total_holdings = len(portfolio.get("holdings", []))
    is_holding = bool(holding and holding.get("entry_price"))
    shares = holding.get("shares", 0) if holding else 0
    entry = holding.get("entry_price", 0) if holding else 0
    stop_pct = holding.get("stop_loss_pct", 8) if holding else 8
    current_exposure = shares * entry if is_holding else 0

    return Task(
        description=(
            f"Perform risk analysis for {ticker}.\n\n"
            f"Portfolio context:\n"
            f"- Total budget: ${budget:,}\n"
            f"- Number of holdings: {total_holdings}\n"
            f"- Current {ticker} exposure: ${current_exposure:,.2f}\n"
            f"- Stop loss set at: {stop_pct}%\n\n"
            f"Technical data:\n{technical_result[:500]}\n\n"
            f"Fundamentals:\n{fundamentals_result[:400]}\n\n"
            f"Bull case:\n{bull_case[:400]}\n\n"
            f"Bear case:\n{bear_case[:400]}\n\n"
            "Calculate and return a JSON risk assessment:\n"
            "{\n"
            '  "action": "BUY|SELL|HOLD|ADD|REDUCE",\n'
            '  "confidence": 0-100,\n'
            '  "position_size_pct": percentage of budget (0-20),\n'
            '  "position_size_usd": dollar amount,\n'
            '  "max_loss_usd": maximum acceptable loss,\n'
            '  "stop_loss_price": calculated stop price,\n'
            '  "risk_reward_ratio": estimated R:R,\n'
            '  "portfolio_heat": current total risk exposure as % of budget,\n'
            '  "kelly_fraction": kelly criterion position size (be conservative, use half-kelly),\n'
            '  "reasoning": "one clear sentence"\n'
            "}\n\n"
            "Position sizing rules:\n"
            "- High conviction (>75%): up to 15% of budget\n"
            "- Medium conviction (50-75%): 5-10% of budget\n"
            "- Low conviction (<50%): 2-5% or NO position\n"
            "- Never recommend >20% in a single position\n"
            "- If already holding: calculate whether to ADD, HOLD, or REDUCE"
        ),
        expected_output="JSON risk assessment with action, confidence, position_size_usd, stop_loss_price, risk_reward_ratio, reasoning.",
        agent=ag.risk_manager_agent(),
    )


def debate_task(
    ticker: str,
    holding: dict,
    fundamentals_result: str,
    news_result: str,
    social_result: str,
    technical_result: str,
    analyst_result: str,
    alt_data_result: str,
) -> tuple:
    """Returns (bull_task, bear_task) for parallel execution."""
    context = (
        f"RESEARCH SUMMARY FOR {ticker}\n\n"
        f"FUNDAMENTALS:\n{fundamentals_result[:800]}\n\n"
        f"NEWS:\n{news_result[:600]}\n\n"
        f"SOCIAL:\n{social_result[:600]}\n\n"
        f"TECHNICAL:\n{technical_result[:600]}\n\n"
        f"ANALYST:\n{analyst_result[:600]}\n\n"
        f"ALT DATA:\n{alt_data_result[:600]}\n"
    )
    is_holding = bool(holding and holding.get("entry_price"))
    position_context = (
        f"The investor ALREADY HOLDS {holding.get('shares')} shares at "
        f"${holding.get('entry_price')} avg entry. "
        f"Current question is: HOLD or SELL? Not whether to buy."
    ) if is_holding else f"The investor does NOT hold {ticker}. Question is: BUY or SKIP?"

    bull_task = Task(
        description=(
            f"Argue the strongest possible BULL case for {ticker}.\n"
            f"{position_context}\n\n"
            f"{context}\n"
            "Using ONLY evidence from the research above, build the bull argument.\n"
            "Structure your response as:\n"
            "BULL CASE:\n"
            "1. [strongest argument + data source]\n"
            "2. [second argument + data source]\n"
            "3. [third argument + data source]\n\n"
            "KEY CATALYST: [what specific event/signal could drive this higher]\n"
            "TIMEFRAME: [when this plays out]\n"
            "BULL PROBABILITY: [0-100]%\n"
            "CONFIDENCE: [low/medium/high] because [reason]\n"
            "WHAT WOULD INVALIDATE THIS: [honest answer]"
        ),
        expected_output="Structured bull case with probability estimate and invalidation condition.",
        agent=ag.bull_advocate_agent(),
    )

    bear_task = Task(
        description=(
            f"Argue the strongest possible BEAR case for {ticker}.\n"
            f"{position_context}\n\n"
            f"{context}\n"
            "Using ONLY evidence from the research above, build the bear argument.\n"
            "Structure your response as:\n"
            "BEAR CASE:\n"
            "1. [strongest argument + data source]\n"
            "2. [second argument + data source]\n"
            "3. [third argument + data source]\n\n"
            "KEY RISK: [what specific event/signal could drive this lower]\n"
            "TIMEFRAME: [when this plays out]\n"
            "BEAR PROBABILITY: [0-100]%\n"
            "CONFIDENCE: [low/medium/high] because [reason]\n"
            "WHAT WOULD INVALIDATE THIS: [honest answer]"
        ),
        expected_output="Structured bear case with probability estimate and invalidation condition.",
        agent=ag.bear_advocate_agent(),
    )

    return bull_task, bear_task


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
    bull_case: str = "",
    bear_case: str = "",
    risk_assessment: str = "",
) -> Task:
    budget = portfolio.get("budget_usd", 0)
    name = portfolio.get("user_name", "the investor")

    is_holding = bool(holding and holding.get("entry_price"))
    shares = holding.get("shares", 0) if holding else 0
    entry = holding.get("entry_price", 0) if holding else 0
    stop_pct = holding.get("stop_loss_pct", 8) if holding else 8

    position_block = (
        f"⚠️ POSITION STATUS: The investor ALREADY HOLDS {shares} shares at ${entry} avg entry.\n"
        f"Stop-loss set at {stop_pct}% below entry (${round(entry*(1-stop_pct/100),2)}).\n"
        f"The question is NOT whether to buy. It is: HOLD, ADD, or SELL?\n"
    ) if is_holding else (
        f"📋 POSITION STATUS: Not currently held. Budget available: ${budget:,}.\n"
        f"The question is: Is there a genuine signal worth acting on?\n"
    )

    alert_types = "HOLD_SIGNAL / SELL_WARNING / URGENT_EXIT / OPPORTUNITY / NO_ALERT" if is_holding else "OPPORTUNITY / WARNING / URGENT / NO_ALERT"

    return Task(
        description=(
            f"You are the final decision-maker for {ticker}.\n\n"
            f"{position_block}\n"
            "━━━ RESEARCH FROM 6 SPECIALIST AGENTS ━━━\n"
            f"FUNDAMENTALS:\n{fundamentals_result[:600]}\n\n"
            f"NEWS:\n{news_result[:600]}\n\n"
            f"SOCIAL:\n{social_result[:600]}\n\n"
            f"TECHNICAL:\n{technical_result[:600]}\n\n"
            f"ANALYST:\n{analyst_result[:600]}\n\n"
            f"ALT DATA:\n{alt_data_result[:600]}\n\n"
            "━━━ RISK MANAGER ━━━\n"
            f"{risk_assessment[:600]}\n\n"
            "━━━ BULL vs BEAR DEBATE ━━━\n"
            f"BULL ADVOCATE:\n{bull_case}\n\n"
            f"BEAR ADVOCATE:\n{bear_case}\n\n"
            "━━━ YOUR DECISION ━━━\n"
            "Weigh ALL inputs. Each agent stated a confidence (0-100). Weight higher-confidence agents more.\n"
            "The risk manager calculated a position size — include this in your recommendation.\n"
            "Ask yourself: would I genuinely message a smart friend about this today?\n\n"
            "CRITICAL: Most of the time, the right answer is NO_ALERT.\n"
            "Only alert if something has genuinely changed or a real signal is confirmed.\n\n"
            "If alerting, structure your message EXACTLY like this:\n\n"
            f"📊 {ticker} — [SIGNAL TYPE]\n\n"
            "SITUATION\n"
            "[2-3 sentences on what's happening and why it matters NOW]\n\n"
            "BULL CASE  [X% probability]\n"
            "[Top 2 bull arguments — each citing the agent that found it]\n\n"
            "BEAR CASE  [X% probability]\n"
            "[Top 2 bear arguments — each citing the agent that found it]\n\n"
            "RISK MANAGER SAYS\n"
            "[action: BUY/HOLD/SELL/REDUCE — position size $X — stop at $Y — R:R ratio]\n\n"
            "WHAT TO WATCH\n"
            "[1-2 specific triggers that would change your view]\n\n"
            "Under 400 words. No jargon. Write like a smart friend.\n\n"
            f"If NOT alerting: output exactly NO_ALERT\n"
            f"Also output alert_type: {alert_types}"
        ),
        expected_output=(
            "Either NO_ALERT or a structured alert message with SITUATION/BULL CASE/"
            "BEAR CASE/PROBABILITY WEIGHTED VIEW/WHAT TO WATCH sections."
        ),
        agent=ag.manager_agent(),
    )


def chat_command_task(user_message: str, portfolio: dict) -> Task:
    holdings_str = ", ".join(h["ticker"] for h in portfolio.get("holdings", []))
    watchlist_str = ", ".join(portfolio.get("watchlist", []))
    return Task(
        description=(
            f"The user said: \"{user_message}\"\n\n"
            f"Current holdings: {holdings_str or 'none'}\n"
            f"Current watchlist: {watchlist_str or 'none'}\n\n"
            "Parse this message into a JSON ARRAY of actions to execute in sequence.\n"
            "The user may ask for multiple things in one message — extract ALL of them.\n\n"
            "Possible action types:\n"
            "- {\"action\": \"add_stock\", \"ticker\": \"X\", \"shares\": N, \"entry_price\": N, \"stop_loss_pct\": 8}\n"
            "- {\"action\": \"remove_stock\", \"ticker\": \"X\"}\n"
            "- {\"action\": \"add_watchlist\", \"ticker\": \"X\"}\n"
            "- {\"action\": \"run_scan\", \"ticker\": \"X\", \"type\": \"deep|pulse\"} — omit ticker to scan all\n"
            "- {\"action\": \"show_performance\"}\n"
            "- {\"action\": \"answer_question\", \"answer\": \"...\"}\n"
            "- {\"action\": \"unknown\", \"clarification\": \"...\"}\n\n"
            "Examples:\n"
            "  'Add TSLA 5 shares at $220 and AAPL 2 shares at $150' → "
            "[{add_stock TSLA}, {add_stock AAPL}]\n"
            "  'I bought NVDA at $200 then scan it' → [{add_stock NVDA}, {run_scan NVDA deep}]\n"
            "  'scan all my stocks' → [{run_scan type:deep}] with no ticker\n\n"
            "Micron's ticker is MU. Google is GOOGL. Do not guess tickers you are unsure of.\n\n"
            "Return ONLY a valid JSON array. No markdown, no explanation, no code fences."
        ),
        expected_output="Valid JSON array of action objects.",
        agent=ag.chat_agent(),
    )
