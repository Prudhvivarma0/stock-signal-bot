"""
CrewAI agent definitions.

LLM STRATEGY
============
Agents 1-6 (data collectors): groq/llama-3.1-8b-instant
  → Fast, ~14,400 RPD free, low latency, good enough for structured extraction

Agent 7 (manager / decision): groq/llama-3.3-70b-versatile
  → Best reasoning, used only once per stock per scan

Bull/Bear/Risk agents: groq/llama-3.1-8b-instant
  → Structured output, doesn't need 70B quality

Fallback on Groq 429: gemini/gemini-1.5-flash
  → Free tier, different quota pool, activated automatically
"""
import logging
import os
import time

from crewai import Agent, LLM
from src.tools.crew_tools import (
    technical_analysis, yfinance_fundamentals, av_company_overview, av_earnings,
    fred_macro, insider_transactions, sec_8k_alerts, sec_edgar_facts,
    news_scan, press_releases,
    reddit_scan, stocktwits_sentiment, google_trends, wikipedia_views,
    analyst_ratings, institutional_ownership,
    job_postings, options_flow,
    uae_fundamentals, uae_price_data, uae_news, uae_insider_transactions,
)

log = logging.getLogger(__name__)

FAST_MODEL  = "anthropic/claude-haiku-4-5-20251001"   # agents 1-6, bull/bear/risk
SMART_MODEL = "anthropic/claude-sonnet-4-6"          # manager only
FALLBACK_MODEL = "groq/llama-3.1-8b-instant"         # fallback if Anthropic unavailable

# Module-level fallback flag — set to True when Groq is rate-limited
_FALLBACK_ACTIVE = False


def set_fallback(active: bool):
    """Activate or deactivate Gemini fallback for all new agents."""
    global _FALLBACK_ACTIVE
    _FALLBACK_ACTIVE = active
    if active:
        log.warning("Gemini fallback activated — all new agents will use %s", FALLBACK_MODEL)
    else:
        log.info("Gemini fallback deactivated — back to Groq")


def _llm(model: str = FAST_MODEL) -> LLM:
    """Build LLM — Anthropic primary, Groq fallback."""
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    groq_key = os.getenv("GROQ_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")

    _kw = {"temperature": 0.1, "max_tokens": 4096, "timeout": 60, "max_retries": 0}

    if model.startswith("anthropic") and anthropic_key and not _FALLBACK_ACTIVE:
        return LLM(model=model, api_key=anthropic_key, **_kw)

    if model.startswith("groq") and groq_key and not _FALLBACK_ACTIVE:
        return LLM(model=model, api_key=groq_key, **_kw)

    if model.startswith("gemini") and gemini_key:
        return LLM(model=model, api_key=gemini_key, **_kw)

    # Fallback chain: Groq → Gemini
    if groq_key:
        log.warning("Primary LLM unavailable, falling back to Groq")
        return LLM(model="groq/llama-3.1-8b-instant", api_key=groq_key, **_kw)
    if gemini_key:
        log.warning("Falling back to Gemini")
        return LLM(model="gemini/gemini-2.0-flash-lite", api_key=gemini_key, **_kw)

    raise ValueError("No LLM API key available. Set ANTHROPIC_API_KEY in .env")


def _fast_llm() -> LLM:
    return _llm(FAST_MODEL)


def _smart_llm() -> LLM:
    return _llm(SMART_MODEL)


# ── Specialist agents (fast model) ────────────────────────────────────────────

def fundamentals_agent() -> Agent:
    return Agent(
        role="Fundamentals Analyst",
        goal=(
            "Analyse the fundamental financial health of a stock: earnings, revenue, margins, "
            "valuation ratios, insider activity, and macro context. "
            "Return structured JSON with signal, confidence 0-100, and key metrics."
        ),
        backstory=(
            "CFA-level analyst, 15 years covering equities. "
            "You extract facts from data — P/E, FCF, debt, insider trades. "
            "You are blunt: if the numbers are bad, you say so. "
            "Every claim cites its source."
        ),
        llm=_fast_llm(),
        tools=[yfinance_fundamentals, av_company_overview, av_earnings,
               fred_macro, insider_transactions, sec_8k_alerts, sec_edgar_facts,
               uae_fundamentals, uae_insider_transactions],
        verbose=True,
        allow_delegation=False,
    )


def news_agent() -> Agent:
    return Agent(
        role="News Intelligence Analyst",
        goal=(
            "Scan all available news sources for the stock. "
            "Find breaking events, regulatory filings, sentiment shifts. "
            "Return structured JSON with signal, confidence 0-100, urgent flags."
        ),
        backstory=(
            "Former Reuters journalist turned buy-side researcher. "
            "50 headlines, 2 actually matter — you find those two. "
            "You never cry wolf. Only flag things that genuinely change the picture."
        ),
        llm=_fast_llm(),
        tools=[news_scan, press_releases, sec_8k_alerts, uae_news],
        verbose=True,
        allow_delegation=False,
    )


def social_agent() -> Agent:
    return Agent(
        role="Social & Sentiment Intelligence Analyst",
        goal=(
            "Monitor Reddit, StockTwits, Twitter, Google Trends, Wikipedia, YouTube. "
            "Detect early community interest before mainstream. "
            "Return structured JSON with signal, confidence 0-100, pre_hype_signal bool."
        ),
        backstory=(
            "Ran a quant fund alt-data desk for 5 years. "
            "Community momentum, measured right, precedes price by days or weeks. "
            "You distinguish organic interest from pump-and-dump."
        ),
        llm=_fast_llm(),
        tools=[reddit_scan, stocktwits_sentiment, google_trends, wikipedia_views],
        verbose=True,
        allow_delegation=False,
    )


def technical_agent() -> Agent:
    return Agent(
        role="Technical Analysis Specialist",
        goal=(
            "Analyse price action, momentum indicators, patterns, relative strength, "
            "options flow, short interest. "
            "Return structured JSON with signal (BUY/NEUTRAL/AVOID), confidence 0-100."
        ),
        backstory=(
            "10 years trading equity momentum. "
            "Trend, momentum, volume, options — your four pillars. "
            "You spot setups and breakdowns quickly."
        ),
        llm=_fast_llm(),
        tools=[technical_analysis, options_flow, uae_price_data],
        verbose=True,
        allow_delegation=False,
    )


def analyst_institutional_agent() -> Agent:
    return Agent(
        role="Analyst & Institutional Research Analyst",
        goal=(
            "Track analyst ratings, price targets, 13F filings, short interest. "
            "Return structured JSON with signal, confidence 0-100, smart_money_signal."
        ),
        backstory=(
            "Prime brokerage background. "
            "You know how institutional flows move markets. "
            "You read between the lines of upgrades, downgrades, and target changes."
        ),
        llm=_fast_llm(),
        tools=[analyst_ratings, institutional_ownership, yfinance_fundamentals],
        verbose=True,
        allow_delegation=False,
    )


def alternative_data_agent() -> Agent:
    return Agent(
        role="Alternative Data Intelligence Analyst",
        goal=(
            "Find early-warning signals not yet in price or news: "
            "Google Trends acceleration, job postings, app store sentiment, "
            "GitHub activity, earnings call language, macro risks, upcoming catalysts. "
            "Return structured JSON with signal, confidence 0-100, pre_hype_detected."
        ),
        backstory=(
            "Specialist in finding signals before they become obvious. "
            "Hiring surges, trend acceleration from low base, management hedging language — "
            "these are your bread and butter."
        ),
        llm=_fast_llm(),
        tools=[google_trends, job_postings, fred_macro, wikipedia_views],
        verbose=True,
        allow_delegation=False,
    )


# ── Debate & risk agents (fast model) ─────────────────────────────────────────

def risk_manager_agent() -> Agent:
    return Agent(
        role="Risk Manager",
        goal=(
            "Assess trade risk: entry price, stop loss level, R:R ratio. "
            "Ignore portfolio allocation — focus only on the trade itself. "
            "Return structured JSON with action, stop_loss_price, risk_reward_ratio, reasoning."
        ),
        backstory=(
            "Trader with 10 years experience. You focus on the individual trade: "
            "where to enter, where to cut losses, what the reward potential is. "
            "You do NOT flag portfolio allocation concerns — that's not your job. "
            "You size stops using ATR or key support levels, never arbitrary percentages."
        ),
        llm=_fast_llm(),
        verbose=True,
        allow_delegation=False,
    )


def bull_advocate_agent() -> Agent:
    return Agent(
        role="Bull Advocate",
        goal=(
            "Build the strongest possible bull case from the research provided. "
            "Every argument must cite its source agent. "
            "Assign BULL PROBABILITY 0-100% with honest confidence."
        ),
        backstory=(
            "Growth investor who made fortunes finding stocks before they ran. "
            "You find asymmetric upside and underappreciated catalysts. "
            "You argue hard but never fabricate — every claim has a source."
        ),
        llm=_fast_llm(),
        verbose=True,
        allow_delegation=False,
    )


def bear_advocate_agent() -> Agent:
    return Agent(
        role="Bear Advocate",
        goal=(
            "Build the strongest possible bear case from the research provided. "
            "Every argument must cite its source agent. "
            "Assign BEAR PROBABILITY 0-100% with honest confidence."
        ),
        backstory=(
            "Short-seller and risk manager who avoided countless landmines. "
            "You find deteriorating fundamentals, crowded trades, narrative risk. "
            "You argue hard but never fabricate — every claim has a source."
        ),
        llm=_fast_llm(),
        verbose=True,
        allow_delegation=False,
    )


# ── Manager agent (smart model — used once per scan) ──────────────────────────

def manager_agent() -> Agent:
    return Agent(
        role="Portfolio Intelligence Manager",
        goal=(
            "Read all research reports and make a clear, decisive call. "
            "Be a medium-risk active trader: catch momentum early, ride it, exit before it turns. "
            "If there is a good reason to BUY, BUY MORE, or SELL — say it clearly. "
            "HOLD is only the right answer when there is genuinely no edge right now."
        ),
        backstory=(
            "Active trader and portfolio manager. You trade momentum — "
            "you buy stocks that are moving up with a reason, and cut quickly when momentum fades. "
            "You are decisive: when the data points one way, you act on it. "
            "You never say HOLD just to be safe — that's a cop-out. "
            "If fundamentals + news + technicals all align bullish, you say BUY MORE or OPPORTUNITY. "
            "If they're deteriorating, you say SELL. "
            "You write like a smart trading friend giving a direct answer, not a cautious analyst."
        ),
        llm=_smart_llm(),
        verbose=True,
        allow_delegation=True,
    )


# ── Chat agent (fast model) ───────────────────────────────────────────────────

def chat_agent() -> Agent:
    return Agent(
        role="Portfolio Assistant",
        goal=(
            "Parse natural language commands into structured JSON actions: "
            "add_stock, remove_stock, add_watchlist, run_scan, show_performance, "
            "answer_question, or unknown."
        ),
        backstory=(
            "Intelligent portfolio assistant. "
            "You translate what the user says into precise structured actions. "
            "When unsure, ask for clarification."
        ),
        llm=_fast_llm(),
        verbose=True,
        allow_delegation=False,
    )
