"""CrewAI task definitions — concise prompts to minimise token usage."""
import json
from crewai import Task
from src import agents as ag


def _holding_ctx(holding: dict) -> str:
    if not holding or not holding.get("entry_price"):
        return ""
    return (
        f"Investor holds {holding.get('shares')} shares @ "
        f"${holding.get('entry_price')} avg entry."
    )


def _position_question(holding: dict, ticker: str) -> str:
    """Returns the right question depending on whether the stock is held."""
    if holding and holding.get("entry_price"):
        return (
            f"Investor holds {holding.get('shares')} shares of {ticker} "
            f"@ ${holding.get('entry_price')} avg entry. "
            f"Question: HOLD, SELL, or BUY MORE?"
        )
    return f"Investor does NOT hold {ticker}. Question: BUY or SKIP?"


def fundamentals_task(ticker: str, holding: dict = None) -> Task:
    exchange = holding.get("exchange", "US") if holding else "US"
    is_uae = exchange in ("DFM", "ADX")
    data_note = (
        f"UAE stock on {exchange} — use EODHD for fundamentals, skip SEC tools."
        if is_uae else
        "Use SEC EDGAR for revenue/income trends, 8-K filings, and insider transactions."
    )
    return Task(
        description=(
            f"Fundamental analysis of {ticker}. {_holding_ctx(holding)}\n"
            f"Get: P/E, forward P/E, PEG, EPS growth, revenue trend, margins, FCF, "
            f"debt/equity, ROE, institutional %, analyst targets, insider activity.\n"
            f"{data_note}\n"
            f"Return JSON: {{fundamental_score(-1 to 1), valuation, financial_health, "
            f"insider_signal, key_metrics, flags, reasoning, signal, confidence}}"
        ),
        expected_output="JSON with fundamental_score, valuation, financial_health, signal, confidence, reasoning.",
        agent=ag.fundamentals_agent(),
    )


def news_task(ticker: str, company_name: str = "") -> Task:
    return Task(
        description=(
            f"News intelligence for {ticker} ({company_name}).\n"
            f"Scan RSS feeds, press releases, SEC 8-K. Score each article -1 to +1. "
            f"Flag URGENT for: fraud, SEC investigation, lawsuit, bankruptcy, recall.\n"
            f"Return JSON: {{news_score, urgent_flags, top_positive, top_negative, "
            f"sentiment_shift, reasoning}}"
        ),
        expected_output="JSON with news_score, urgent_flags, top_positive, top_negative, reasoning.",
        agent=ag.news_agent(),
    )


def social_task(ticker: str, company_name: str = "") -> Task:
    return Task(
        description=(
            f"Social/community intelligence for {ticker} ({company_name}).\n"
            f"Check Reddit (mention velocity), StockTwits (bull/bear ratio), "
            f"Google Trends (acceleration from low base = pre-hype signal), "
            f"Wikipedia pageviews, Twitter.\n"
            f"Return JSON: {{social_score, reddit_mentions_24h, reddit_velocity, "
            f"stocktwits_bullish_pct, google_trends_direction, pre_hype_signal, reasoning}}"
        ),
        expected_output="JSON with social_score, pre_hype_signal, reddit_velocity, reasoning.",
        agent=ag.social_agent(),
    )


def technical_task(ticker: str, holding: dict = None) -> Task:
    entry_ctx = ""
    if holding:
        entry_ctx = f"Entry ${holding.get('entry_price')}, stop {holding.get('stop_loss_pct', 8)}%."
    return Task(
        description=(
            f"Technical analysis of {ticker}. {entry_ctx}\n"
            f"Calculate: SMA20/50/200, RSI, MACD, Bollinger Bands, ATR, OBV. "
            f"Identify trend, momentum, key support/resistance. "
            f"Check options flow (put/call ratio, unusual activity). "
            f"Compare relative strength vs SPY/QQQ.\n"
            f"Return JSON: {{technical_score(-1 to 1), signal(BUY/NEUTRAL/AVOID), "
            f"trend, rsi, macd_signal, support_level, resistance_level, "
            f"stop_loss_price, options_signal, reasoning}}"
        ),
        expected_output="JSON with technical_score, signal, trend, rsi, support_level, resistance_level, reasoning.",
        agent=ag.technical_agent(),
    )


def analyst_institutional_task(ticker: str) -> Task:
    return Task(
        description=(
            f"Analyst and institutional intelligence for {ticker}.\n"
            f"Get analyst consensus, price targets, recent upgrades/downgrades. "
            f"Check 13F filings for institutional buying/selling. "
            f"Get short interest % and squeeze potential.\n"
            f"Return JSON: {{analyst_score(-1 to 1), consensus, avg_target, upside_pct, "
            f"recent_changes, institutional_trend, short_interest_pct, "
            f"short_squeeze_potential, smart_money_signal, reasoning}}"
        ),
        expected_output="JSON with analyst_score, consensus, avg_target, upside_pct, smart_money_signal, reasoning.",
        agent=ag.analyst_institutional_agent(),
    )


def alternative_data_task(ticker: str, company_name: str = "") -> Task:
    return Task(
        description=(
            f"Alternative data intelligence for {ticker} ({company_name}).\n"
            f"Google Trends 12-month acceleration, job posting trends, "
            f"GitHub activity (if tech), earnings call sentiment, "
            f"upcoming earnings/macro catalysts in next 7 days.\n"
            f"Return JSON: {{alternative_score(-1 to 1), pre_hype_detected, "
            f"pre_hype_signals, early_warning_signals, hiring_signal, "
            f"upcoming_catalysts, macro_risks, reasoning}}"
        ),
        expected_output="JSON with alternative_score, pre_hype_detected, upcoming_catalysts, macro_risks, reasoning.",
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
    n_holdings = len(portfolio.get("holdings", []))
    is_holding = bool(holding and holding.get("entry_price"))
    shares = holding.get("shares", 0) if holding else 0
    entry = holding.get("entry_price", 0) if holding else 0
    stop_pct = holding.get("stop_loss_pct", 8) if holding else 8
    exposure = shares * entry

    return Task(
        description=(
            f"Risk assessment for {ticker}.\n"
            f"Budget: ${budget:,} | Holdings: {n_holdings} | "
            f"{'Current exposure: $' + f'{exposure:,.0f}' if is_holding else 'Not held'}. "
            f"Stop: {stop_pct}%.\n\n"
            f"Technical: {technical_result[:300]}\n"
            f"Fundamentals: {fundamentals_result[:300]}\n\n"
            f"Use half-Kelly criterion. Max 20% in one position. "
            f"{'Decide: ADD, HOLD, or REDUCE.' if is_holding else 'Decide: BUY or NO_POSITION.'}\n\n"
            f"Return JSON: {{action, confidence, position_size_usd, max_loss_usd, "
            f"stop_loss_price, risk_reward_ratio, portfolio_heat, reasoning}}"
        ),
        expected_output="JSON with action, confidence, position_size_usd, stop_loss_price, risk_reward_ratio, reasoning.",
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
    """Returns (bull_task, bear_task)."""
    # Trim research summaries to save tokens
    context = (
        f"Research for {ticker}:\n"
        f"Fundamentals: {fundamentals_result[:400]}\n"
        f"News: {news_result[:300]}\n"
        f"Social: {social_result[:300]}\n"
        f"Technical: {technical_result[:300]}\n"
        f"Analyst: {analyst_result[:300]}\n"
        f"Alt data: {alt_data_result[:300]}\n"
    )

    position_q = _position_question(holding, ticker)

    bull_task = Task(
        description=(
            f"Build the strongest BULL case for {ticker}.\n"
            f"{position_q}\n\n"
            f"{context}\n"
            f"Use ONLY evidence from the research above.\n"
            f"Format:\n"
            f"BULL CASE:\n1. [argument + source]\n2. [argument + source]\n3. [argument + source]\n"
            f"KEY CATALYST: [specific trigger]\n"
            f"BULL PROBABILITY: X%\n"
            f"INVALIDATED IF: [honest condition]"
        ),
        expected_output="Structured bull case with probability and invalidation condition.",
        agent=ag.bull_advocate_agent(),
    )

    bear_task = Task(
        description=(
            f"Build the strongest BEAR case for {ticker}.\n"
            f"{position_q}\n\n"
            f"{context}\n"
            f"Use ONLY evidence from the research above.\n"
            f"Format:\n"
            f"BEAR CASE:\n1. [argument + source]\n2. [argument + source]\n3. [argument + source]\n"
            f"KEY RISK: [specific trigger]\n"
            f"BEAR PROBABILITY: X%\n"
            f"INVALIDATED IF: [honest condition]"
        ),
        expected_output="Structured bear case with probability and invalidation condition.",
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
    name = portfolio.get("user_name", "the investor")
    is_holding = bool(holding and holding.get("entry_price"))
    position_q = _position_question(holding, ticker)
    alert_types = "HOLD_SIGNAL / SELL_WARNING / BUY_MORE / URGENT_EXIT / NO_ALERT" if is_holding else "OPPORTUNITY / WARNING / NO_ALERT"

    return Task(
        description=(
            f"Final decision for {ticker}.\n"
            f"{position_q}\n\n"
            f"FUNDAMENTALS: {fundamentals_result[:400]}\n"
            f"NEWS: {news_result[:400]}\n"
            f"SOCIAL: {social_result[:300]}\n"
            f"TECHNICAL: {technical_result[:400]}\n"
            f"ANALYST: {analyst_result[:300]}\n"
            f"ALT DATA: {alt_data_result[:300]}\n"
            f"RISK: {risk_assessment[:300]}\n"
            f"BULL: {bull_case[:400]}\n"
            f"BEAR: {bear_case[:400]}\n\n"
            f"CRITICAL: Default is NO_ALERT. Only alert if something genuinely changed today.\n"
            f"Ask: would I message a smart friend about this right now?\n\n"
            f"If alerting, format EXACTLY:\n"
            f"📊 {ticker} — [TYPE]\n\n"
            f"SITUATION\n[2-3 sentences, what changed and why it matters NOW]\n\n"
            f"BULL CASE  [X%]\n[2 arguments with source]\n\n"
            f"BEAR CASE  [X%]\n[2 arguments with source]\n\n"
            f"RISK MANAGER SAYS\n[HOLD/SELL/BUY MORE/ADD — size $X — stop $Y — R:R]\n\n"
            f"WHAT TO WATCH\n[1-2 specific triggers]\n\n"
            f"Under 350 words. No jargon.\n"
            f"If NO alert: output exactly NO_ALERT\n"
            f"alert_type must be one of: {alert_types}"
        ),
        expected_output="NO_ALERT or structured alert with SITUATION/BULL CASE/BEAR CASE/RISK MANAGER SAYS/WHAT TO WATCH.",
        agent=ag.manager_agent(),
    )


def chat_command_task(user_message: str, portfolio: dict) -> Task:
    holdings_str = ", ".join(h["ticker"] for h in portfolio.get("holdings", []))
    watchlist_str = ", ".join(portfolio.get("watchlist", []))
    return Task(
        description=(
            f"User said: \"{user_message}\"\n"
            f"Holdings: {holdings_str or 'none'} | Watchlist: {watchlist_str or 'none'}\n\n"
            "Return a JSON ARRAY of all actions to execute in sequence.\n"
            "Action types:\n"
            '{"action":"add_stock","ticker":"X","shares":N,"entry_price":N,"stop_loss_pct":8}\n'
            '{"action":"remove_stock","ticker":"X"}\n'
            '{"action":"add_watchlist","ticker":"X"}\n'
            '{"action":"run_scan","ticker":"X","type":"deep|pulse"} — omit ticker to scan all\n'
            '{"action":"show_performance"}\n'
            '{"action":"answer_question","answer":"..."}\n'
            '{"action":"unknown","clarification":"..."}\n\n'
            "Micron=MU, Google=GOOGL, Meta=META.\n"
            "Return ONLY valid JSON array. No markdown, no explanation."
        ),
        expected_output="Valid JSON array of action objects.",
        agent=ag.chat_agent(),
    )
