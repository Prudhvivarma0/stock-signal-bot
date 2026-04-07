"""CrewAI crew orchestration for stock research."""
import json
import logging
import time
from datetime import datetime

from crewai import Crew, Process

from src import agents as ag, tasks as tk
from src.database import (
    save_scan, save_alert, was_alert_sent_recently,
    save_sentiment, get_sentiment_baseline,
)
from src.tools.telegram_tool import send_alert

log = logging.getLogger(__name__)


def _safe_json(text: str) -> dict:
    """Try to extract JSON from agent output."""
    try:
        # strip markdown code fences
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(cleaned)
    except Exception:
        return {"raw_text": text[:500]}


def _groq_with_backoff(crew_run_fn, max_retries: int = 3):
    """Run a crew function with exponential backoff on 429s."""
    for attempt in range(max_retries):
        try:
            return crew_run_fn()
        except Exception as exc:
            if "429" in str(exc) or "rate_limit" in str(exc).lower():
                wait = 60 * (2 ** attempt)
                log.warning("Groq rate limit, waiting %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Max retries exceeded for Groq API")


def run_deep_scan(ticker: str, holding: dict, portfolio: dict) -> dict:
    """Run full 6-agent + manager scan on a single ticker."""
    company_name = holding.get("company_name", "") if holding else ""
    log.info("Starting deep scan: %s", ticker)

    results = {}

    # --- Agent 1: Fundamentals ---
    try:
        crew1 = Crew(
            agents=[ag.fundamentals_agent()],
            tasks=[tk.fundamentals_task(ticker, holding)],
            process=Process.sequential,
            verbose=False,
        )
        out = _groq_with_backoff(crew1.kickoff)
        results["fundamentals"] = str(out)
        data = _safe_json(str(out))
        save_scan(ticker, "fundamentals", data.get("reasoning", "")[:500],
                  data.get("flags", []), data)
    except Exception as exc:
        log.error("Fundamentals agent failed for %s: %s", ticker, exc)
        results["fundamentals"] = f"ERROR: {exc}"

    time.sleep(3)  # respect rate limits between agents

    # --- Agent 2: News ---
    try:
        crew2 = Crew(
            agents=[ag.news_agent()],
            tasks=[tk.news_task(ticker, company_name)],
            process=Process.sequential,
            verbose=False,
        )
        out = _groq_with_backoff(crew2.kickoff)
        results["news"] = str(out)
        data = _safe_json(str(out))
        save_scan(ticker, "news", data.get("reasoning", "")[:500],
                  data.get("urgent_flags", []), data)
        if data.get("news_score") is not None:
            save_sentiment(ticker, float(data["news_score"]), 0)
    except Exception as exc:
        log.error("News agent failed for %s: %s", ticker, exc)
        results["news"] = f"ERROR: {exc}"

    time.sleep(3)

    # --- Agent 3: Social ---
    try:
        crew3 = Crew(
            agents=[ag.social_agent()],
            tasks=[tk.social_task(ticker, company_name)],
            process=Process.sequential,
            verbose=False,
        )
        out = _groq_with_backoff(crew3.kickoff)
        results["social"] = str(out)
        data = _safe_json(str(out))
        save_scan(ticker, "social", data.get("reasoning", "")[:500],
                  data.get("urgent_flags", []), data)
        if data.get("social_score") is not None:
            save_sentiment(ticker, 0, float(data["social_score"]))
    except Exception as exc:
        log.error("Social agent failed for %s: %s", ticker, exc)
        results["social"] = f"ERROR: {exc}"

    time.sleep(3)

    # --- Agent 4: Technical ---
    try:
        crew4 = Crew(
            agents=[ag.technical_agent()],
            tasks=[tk.technical_task(ticker, holding)],
            process=Process.sequential,
            verbose=False,
        )
        out = _groq_with_backoff(crew4.kickoff)
        results["technical"] = str(out)
        data = _safe_json(str(out))
        save_scan(ticker, "technical", data.get("reasoning", "")[:500], [], data)
    except Exception as exc:
        log.error("Technical agent failed for %s: %s", ticker, exc)
        results["technical"] = f"ERROR: {exc}"

    time.sleep(3)

    # --- Agent 5: Analyst/Institutional ---
    try:
        crew5 = Crew(
            agents=[ag.analyst_institutional_agent()],
            tasks=[tk.analyst_institutional_task(ticker)],
            process=Process.sequential,
            verbose=False,
        )
        out = _groq_with_backoff(crew5.kickoff)
        results["analyst"] = str(out)
        data = _safe_json(str(out))
        save_scan(ticker, "analyst", data.get("reasoning", "")[:500], [], data)
    except Exception as exc:
        log.error("Analyst agent failed for %s: %s", ticker, exc)
        results["analyst"] = f"ERROR: {exc}"

    time.sleep(3)

    # --- Agent 6: Alternative Data ---
    try:
        crew6 = Crew(
            agents=[ag.alternative_data_agent()],
            tasks=[tk.alternative_data_task(ticker, company_name)],
            process=Process.sequential,
            verbose=False,
        )
        out = _groq_with_backoff(crew6.kickoff)
        results["alt_data"] = str(out)
        data = _safe_json(str(out))
        save_scan(ticker, "alt_data", data.get("reasoning", "")[:500],
                  data.get("pre_hype_signals", []), data)
    except Exception as exc:
        log.error("Alt data agent failed for %s: %s", ticker, exc)
        results["alt_data"] = f"ERROR: {exc}"

    time.sleep(3)

    # --- Risk Manager ---
    risk_assessment = ""
    try:
        risk_task = tk.risk_manager_task(
            ticker=ticker,
            holding=holding or {},
            portfolio=portfolio,
            technical_result=results.get("technical", "not available"),
            fundamentals_result=results.get("fundamentals", "not available"),
            bull_case="pending",
            bear_case="pending",
        )
        crew_risk = Crew(agents=[ag.risk_manager_agent()], tasks=[risk_task],
                         process=Process.sequential, verbose=False)
        risk_out = _groq_with_backoff(crew_risk.kickoff)
        risk_assessment = str(risk_out)
        results["risk_assessment"] = risk_assessment
        risk_data = _safe_json(risk_assessment)
        save_scan(ticker, "risk_manager", risk_data.get("reasoning", "")[:300], [], risk_data)
        time.sleep(3)
    except Exception as exc:
        log.error("Risk manager failed for %s: %s", ticker, exc)

    # --- Bull / Bear Debate ---
    bull_case, bear_case = "", ""
    try:
        bull_task, bear_task = tk.debate_task(
            ticker=ticker,
            holding=holding or {},
            fundamentals_result=results.get("fundamentals", "not available"),
            news_result=results.get("news", "not available"),
            social_result=results.get("social", "not available"),
            technical_result=results.get("technical", "not available"),
            analyst_result=results.get("analyst", "not available"),
            alt_data_result=results.get("alt_data", "not available"),
        )
        # Run bull and bear sequentially (rate limit friendly)
        crew_bull = Crew(agents=[ag.bull_advocate_agent()], tasks=[bull_task],
                         process=Process.sequential, verbose=False)
        bull_out = _groq_with_backoff(crew_bull.kickoff)
        bull_case = str(bull_out)
        results["bull_case"] = bull_case
        save_scan(ticker, "bull_advocate", bull_case[:500], [], {"bull_case": bull_case})

        time.sleep(3)

        crew_bear = Crew(agents=[ag.bear_advocate_agent()], tasks=[bear_task],
                         process=Process.sequential, verbose=False)
        bear_out = _groq_with_backoff(crew_bear.kickoff)
        bear_case = str(bear_out)
        results["bear_case"] = bear_case
        save_scan(ticker, "bear_advocate", bear_case[:500], [], {"bear_case": bear_case})

        time.sleep(3)
    except Exception as exc:
        log.error("Debate agents failed for %s: %s", ticker, exc)

    # --- Manager Decision (reads debate + all research) ---
    try:
        manager_task = tk.manager_decision_task(
            ticker=ticker,
            holding=holding or {},
            portfolio=portfolio,
            fundamentals_result=results.get("fundamentals", "not available"),
            news_result=results.get("news", "not available"),
            social_result=results.get("social", "not available"),
            technical_result=results.get("technical", "not available"),
            analyst_result=results.get("analyst", "not available"),
            alt_data_result=results.get("alt_data", "not available"),
            bull_case=bull_case,
            bear_case=bear_case,
            risk_assessment=results.get("risk_assessment", ""),
        )
        crew_mgr = Crew(agents=[ag.manager_agent()], tasks=[manager_task],
                        process=Process.sequential, verbose=False)
        decision_raw = _groq_with_backoff(crew_mgr.kickoff)
        decision = str(decision_raw).strip()
        results["manager_decision"] = decision

        if "NO_ALERT" not in decision.upper() and len(decision) > 20:
            upper = decision.upper()
            if "SELL" in upper or "URGENT_EXIT" in upper:
                alert_type = "URGENT"
            elif "HOLD_SIGNAL" in upper:
                alert_type = "HOLD_SIGNAL"
            elif "OPPORTUNITY" in upper:
                alert_type = "OPPORTUNITY"
            elif "WARNING" in upper or "SELL_WARNING" in upper:
                alert_type = "WARNING"
            else:
                alert_type = "SIGNAL"

            if not was_alert_sent_recently(ticker, hours=72):
                chat_id = portfolio.get("telegram_chat_id", "")
                delivered = send_alert(decision, chat_id=chat_id or None)
                save_alert(ticker, alert_type, decision, delivered=delivered)
                log.info("Alert sent for %s (%s)", ticker, alert_type)
            else:
                log.info("Alert suppressed for %s — sent within 72h", ticker)
        else:
            log.info("Manager: NO_ALERT for %s", ticker)

    except Exception as exc:
        log.error("Manager agent failed for %s: %s", ticker, exc)
        results["manager_decision"] = f"ERROR: {exc}"

    return results


def run_pulse_scan(ticker: str, portfolio: dict) -> dict:
    """Lightweight pulse scan: news + social + price anomaly check."""
    from src.tools.news_rss_tools import build_news_report
    from src.tools.yfinance_tools import get_latest_price, price_data
    import pandas as pd

    log.info("Pulse scan: %s", ticker)
    result = {"ticker": ticker, "timestamp": datetime.utcnow().isoformat()}

    # News
    try:
        news = build_news_report(ticker)
        result["news_score"] = news.get("news_score", 0)
        result["news_urgent"] = news.get("urgent_flags", [])
        save_scan(ticker, "pulse_news", news.get("reasoning", "")[:300],
                  news.get("urgent_flags", []), news)
    except Exception as exc:
        log.error("Pulse news %s: %s", ticker, exc)

    # Price anomaly
    try:
        df = price_data(ticker, period="5d", interval="15m")
        if not df.empty:
            closes = df["Close"].dropna() if "Close" in df.columns else df.iloc[:, 3].dropna()
            pct_change = float((closes.iloc[-1] - closes.iloc[-5]) / closes.iloc[-5] * 100)
            result["price_change_pct"] = round(pct_change, 2)
            result["price_anomaly"] = abs(pct_change) > 3.0
    except Exception as exc:
        log.error("Pulse price %s: %s", ticker, exc)

    # Trigger emergency scan if warranted
    trigger = (
        result.get("price_anomaly", False) or
        bool(result.get("news_urgent")) or
        result.get("news_score", 0) < -0.5
    )
    result["trigger_emergency"] = trigger

    return result


def run_chat_command(user_message: str, portfolio: dict) -> dict:
    """Parse a natural language command and return a structured action dict."""
    try:
        task = tk.chat_command_task(user_message, portfolio)
        crew = Crew(agents=[ag.chat_agent()], tasks=[task],
                    process=Process.sequential, verbose=False)
        out = _groq_with_backoff(crew.kickoff)
        return _safe_json(str(out))
    except Exception as exc:
        log.error("chat_command: %s", exc)
        return {"action": "unknown", "clarification": str(exc)}


def run_weekly_debrief(portfolio: dict) -> None:
    """Sunday weekly debrief — review week from SQLite and send narrative."""
    from src.database import get_recent_alerts, get_latest_scan
    from src.tools.telegram_tool import send_alert as tg_send

    name = portfolio.get("user_name", "Investor")
    tickers = [h["ticker"] for h in portfolio.get("holdings", [])]

    summary_parts = [f"📊 Weekly Debrief — {name}\n"]
    for ticker in tickers:
        scan = get_latest_scan(ticker)
        if scan:
            summary_parts.append(f"\n{ticker}: {scan['summary'][:200]}")

    recent_alerts = get_recent_alerts(limit=5)
    if recent_alerts:
        summary_parts.append("\n\nAlerts sent this week:")
        for ts, tkr, atype, msg in recent_alerts:
            summary_parts.append(f"• {tkr} ({atype}) — {str(ts)[:10]}")

    message = "\n".join(summary_parts)[:3000]
    chat_id = portfolio.get("telegram_chat_id", "")
    delivered = tg_send(message, chat_id=chat_id or None)
    save_alert("PORTFOLIO", "WEEKLY_DEBRIEF", message, delivered=delivered)
    log.info("Weekly debrief sent")
