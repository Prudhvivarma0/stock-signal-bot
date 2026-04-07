"""Portfolio Intelligence Dashboard — Streamlit localhost."""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

from src.database import init_db, get_recent_alerts, get_latest_scan
from src.chart_data import get_portfolio_history, get_stock_candles, get_latest_price, get_sparkline

PORTFOLIO_PATH = BASE_DIR / "portfolio.json"

st.set_page_config(page_title="Portfolio Intelligence", page_icon="📈", layout="wide",
                   initial_sidebar_state="collapsed")

try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=5 * 60 * 1000, key="autorefresh")
except ImportError:
    pass

init_db()


def load_portfolio() -> dict:
    if PORTFOLIO_PATH.exists():
        with open(PORTFOLIO_PATH) as f:
            return json.load(f)
    return {"holdings": [], "watchlist": [], "user_name": "Investor"}


def save_portfolio(p: dict):
    with open(PORTFOLIO_PATH, "w") as f:
        json.dump(p, f, indent=2)


# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: #1e1e2e; border-radius: 12px; padding: 16px 20px;
    border: 1px solid #2a2a3e; margin-bottom: 8px;
}
.signal-pill {
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: 12px; font-weight: 600; margin-left: 8px;
}
.pill-green { background: #1a3a2a; color: #4ade80; border: 1px solid #4ade80; }
.pill-red   { background: #3a1a1a; color: #f87171; border: 1px solid #f87171; }
.pill-yellow{ background: #3a3a1a; color: #fbbf24; border: 1px solid #fbbf24; }
.section-header {
    font-size: 18px; font-weight: 700; color: #e2e8f0;
    border-bottom: 1px solid #2a2a3e; padding-bottom: 8px; margin: 20px 0 12px 0;
}
.chat-msg { padding: 10px 14px; border-radius: 8px; margin: 6px 0; font-size: 14px; }
.chat-user { background: #1e3a5f; text-align: right; }
.chat-bot  { background: #1e2e1e; }
</style>
""", unsafe_allow_html=True)

# ── Navigation ────────────────────────────────────────────────────────────────
portfolio = load_portfolio()
name = portfolio.get("user_name", "Investor")
holdings = portfolio.get("holdings", [])
watchlist = portfolio.get("watchlist", [])

tab_portfolio, tab_performance, tab_alerts, tab_chat = st.tabs([
    "📊 Portfolio", "📈 Performance", "🔔 Alerts", "💬 Assistant"
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — PORTFOLIO
# ═══════════════════════════════════════════════════════════════════════════════
with tab_portfolio:
    st.markdown(
        f"### {name}'s Portfolio &nbsp;&nbsp;"
        f"<small style='color:#64748b'>Updated: {datetime.now().strftime('%H:%M:%S')}</small>",
        unsafe_allow_html=True
    )

    # ── Summary bar ──────────────────────────────────────────────────────────
    total_invested = total_current = 0.0
    best_ticker, best_pct, worst_ticker, worst_pct = "", -999.0, "", 999.0
    holding_prices = {}

    for h in holdings:
        ticker = h["ticker"]
        shares = h.get("shares", 0)
        entry = h.get("entry_price", 0)
        price = get_latest_price(ticker) or entry
        holding_prices[ticker] = price
        invested = shares * entry
        current = shares * price
        total_invested += invested
        total_current += current
        if invested > 0:
            pct = (current - invested) / invested * 100
            if pct > best_pct: best_pct, best_ticker = pct, ticker
            if pct < worst_pct: worst_pct, worst_ticker = pct, ticker

    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💰 Invested", f"${total_invested:,.2f}")
    c2.metric("📦 Current Value", f"${total_current:,.2f}")
    c3.metric("📊 Total P&L", f"${total_pnl:+,.2f}",
              delta=f"{total_pnl_pct:+.2f}%", delta_color="normal")
    c4.metric("🚀 Best", best_ticker or "—",
              delta=f"{best_pct:+.1f}%" if best_ticker else None)
    c5.metric("📉 Worst", worst_ticker or "—",
              delta=f"{worst_pct:+.1f}%" if worst_ticker else None, delta_color="inverse")

    st.divider()

    # ── Add stock inline ──────────────────────────────────────────────────────
    with st.expander("➕ Add a Stock to Portfolio"):
        col_a, col_b, col_c, col_d, col_e = st.columns([2, 1.5, 1.5, 1.5, 1])
        new_ticker = col_a.text_input("Ticker", placeholder="e.g. TSLA").upper().strip()
        new_shares = col_b.number_input("Shares", min_value=0.0, step=0.001, format="%.3f")
        new_price = col_c.number_input("Avg Entry Price", min_value=0.0, step=0.01, format="%.4f")
        new_stop = col_d.number_input("Stop Loss %", min_value=1.0, max_value=99.0, value=8.0, step=0.5)
        if col_e.button("Add", use_container_width=True) and new_ticker and new_shares > 0 and new_price > 0:
            from src.tools.yfinance_tools import estimate_entry_date
            from src.setup import detect_exchange
            exchange = detect_exchange(new_ticker)
            entry_date = estimate_entry_date(new_ticker, new_price)
            holdings.append({
                "ticker": new_ticker, "exchange": exchange,
                "shares": float(new_shares), "entry_price": float(new_price),
                "entry_date_estimated": entry_date, "stop_loss_pct": float(new_stop),
                "thesis": "", "screenshot_path": "",
            })
            portfolio["holdings"] = holdings
            save_portfolio(portfolio)
            st.success(f"✓ {new_ticker} added ({exchange})")
            st.rerun()

    # ── Holdings ──────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Holdings</div>', unsafe_allow_html=True)

    if not holdings:
        st.info("No holdings yet. Add your first stock above.")

    for h in holdings:
        ticker = h["ticker"]
        shares = h.get("shares", 0)
        entry = h.get("entry_price", 0.0)
        stop_pct = h.get("stop_loss_pct", 8)
        stop_price = round(entry * (1 - stop_pct / 100), 4)
        entry_date = h.get("entry_date_estimated", "")
        exchange = h.get("exchange", "US")

        current_price = holding_prices.get(ticker, entry)
        pnl_usd = (current_price - entry) * shares
        pnl_pct = (current_price - entry) / entry * 100 if entry else 0
        pnl_color = "🟢" if pnl_usd >= 0 else "🔴"

        scan = get_latest_scan(ticker)
        signal_label = ""
        if scan:
            raw = scan.get("raw", {})
            sig = raw.get("signal", raw.get("technical_score", ""))
            if sig:
                signal_label = f" · {sig}"

        label = (f"{pnl_color} **{ticker}** — {shares} shares @ ${entry}"
                 f"  |  ${current_price:.4f}  |  {'+' if pnl_usd>=0 else ''}{pnl_pct:.2f}%{signal_label}")

        with st.expander(label, expanded=True):
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Entry", f"${entry:.4f}")
            m2.metric("Current", f"${current_price:.4f}")
            m3.metric("P&L", f"${pnl_usd:+,.2f}", delta=f"{pnl_pct:+.2f}%")
            m4.metric("Stop Loss", f"${stop_price:.4f}", delta=f"-{stop_pct}%", delta_color="inverse")
            m5.metric("Exchange", exchange)

            # Timeframe buttons
            tf_key = f"tf_{ticker}"
            tfs = ["1D", "1W", "1M", "3M", "6M", "ALL"]
            tf_cols = st.columns(6)
            current_tf = st.session_state.get(tf_key, "1M")
            for i, tf in enumerate(tfs):
                if tf_cols[i].button(tf, key=f"tfbtn_{ticker}_{tf}", use_container_width=True):
                    current_tf = tf
                    st.session_state[tf_key] = tf

            candle_df = get_stock_candles(ticker, current_tf, exchange)
            if not candle_df.empty:
                candle_df.columns = [str(c).lower() for c in candle_df.columns]
                date_col = next((c for c in candle_df.columns if "date" in c), candle_df.columns[0])

                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=candle_df[date_col],
                    open=candle_df.get("open", candle_df.iloc[:, 1]),
                    high=candle_df.get("high", candle_df.iloc[:, 2]),
                    low=candle_df.get("low", candle_df.iloc[:, 3]),
                    close=candle_df.get("close", candle_df.iloc[:, 4]),
                    name="Price", increasing_line_color="#4ade80", decreasing_line_color="#f87171",
                ))
                if "close" in candle_df.columns and len(candle_df) >= 20:
                    candle_df["sma20"] = candle_df["close"].rolling(20).mean()
                    fig.add_trace(go.Scatter(x=candle_df[date_col], y=candle_df["sma20"],
                                            name="SMA20", line=dict(color="#60a5fa", width=1)))
                    if len(candle_df) >= 50:
                        candle_df["sma50"] = candle_df["close"].rolling(50).mean()
                        fig.add_trace(go.Scatter(x=candle_df[date_col], y=candle_df["sma50"],
                                                name="SMA50", line=dict(color="#a78bfa", width=1)))

                fig.add_hline(y=entry, line=dict(color="#fb923c", dash="dash", width=1.5),
                              annotation_text=f"Entry ${entry:.2f}",
                              annotation_font=dict(color="#fb923c"))
                fig.add_hline(y=stop_price, line=dict(color="#f87171", dash="dash", width=1.5),
                              annotation_text=f"Stop ${stop_price:.2f}",
                              annotation_font=dict(color="#f87171"))
                if entry_date and len(str(entry_date)) >= 10:
                    fig.add_vline(x=str(entry_date)[:10], line=dict(color="#fb923c", dash="dot", width=1))

                fig.update_layout(
                    height=420, xaxis_rangeslider_visible=False,
                    margin=dict(l=0, r=0, t=10, b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(gridcolor="rgba(255,255,255,0.05)", color="#94a3b8"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.05)", tickprefix="$", color="#94a3b8"),
                    legend=dict(orientation="h", y=1.08, font=dict(size=11)),
                )
                st.plotly_chart(fig, use_container_width=True)

                if "volume" in candle_df.columns:
                    vol_fig = go.Figure(go.Bar(
                        x=candle_df[date_col], y=candle_df["volume"],
                        marker_color="rgba(100,150,250,0.4)",
                    ))
                    vol_fig.update_layout(height=100, margin=dict(l=0, r=0, t=0, b=0),
                                         paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                         showlegend=False, xaxis=dict(visible=False),
                                         yaxis=dict(gridcolor="rgba(255,255,255,0.05)", color="#64748b"))
                    st.plotly_chart(vol_fig, use_container_width=True)
            else:
                st.warning(f"No price data for {ticker} ({current_tf})")

            # Latest research signal
            if scan:
                st.markdown(
                    f"**🔍 Last scan** `{str(scan['scan_time'])[:16]}` — {scan['summary'][:200]}"
                )
            else:
                st.caption("No research scan yet — run `python main.py --deep` to start.")

            # Remove button
            if st.button(f"🗑 Remove {ticker}", key=f"rm_{ticker}"):
                portfolio["holdings"] = [x for x in portfolio["holdings"] if x["ticker"] != ticker]
                save_portfolio(portfolio)
                st.rerun()

    # ── Watchlist ─────────────────────────────────────────────────────────────
    if watchlist:
        st.markdown('<div class="section-header">Watchlist</div>', unsafe_allow_html=True)
        w_cols = st.columns(min(len(watchlist), 4))
        for i, wt in enumerate(watchlist):
            with w_cols[i % 4]:
                wp = get_latest_price(wt) or 0
                spark = get_sparkline(wt)
                st.metric(wt, f"${wp:.4f}" if wp else "N/A")
                if spark:
                    st.line_chart(pd.DataFrame({"price": spark}), height=70, use_container_width=True)
                ws = get_latest_scan(wt)
                if ws:
                    st.caption(ws["summary"][:80])
        st.divider()

        with st.expander("Manage Watchlist"):
            add_wt = st.text_input("Add ticker to watchlist").upper().strip()
            col_w1, col_w2 = st.columns(2)
            if col_w1.button("Add to Watchlist") and add_wt:
                if add_wt not in watchlist:
                    portfolio["watchlist"] = watchlist + [add_wt]
                    save_portfolio(portfolio)
                    st.rerun()
            remove_wt = st.selectbox("Remove from watchlist", [""] + watchlist)
            if col_w2.button("Remove") and remove_wt:
                portfolio["watchlist"] = [t for t in watchlist if t != remove_wt]
                save_portfolio(portfolio)
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PERFORMANCE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_performance:
    st.markdown("### Portfolio Performance")

    tf_cols = st.columns(6)
    tfs = ["1D", "1W", "1M", "3M", "6M", "ALL"]
    sel_tf = st.session_state.get("perf_tf", "1M")
    for i, tf in enumerate(tfs):
        if tf_cols[i].button(tf, key=f"perftf_{tf}", use_container_width=True):
            sel_tf = tf
            st.session_state["perf_tf"] = tf

    port_df = get_portfolio_history(sel_tf)
    if not port_df.empty:
        # P&L line chart
        port_df["pnl"] = port_df["total_value"] - port_df["total_invested"]
        port_df["pnl_pct"] = port_df["pnl"] / port_df["total_invested"] * 100

        fig_pf = go.Figure()
        fig_pf.add_trace(go.Scatter(
            x=port_df["date"], y=port_df["total_invested"],
            name="Invested", line=dict(color="#64748b", dash="dash"),
        ))
        above = port_df["total_value"].copy()
        below = port_df["total_value"].copy()
        above[above < port_df["total_invested"]] = None
        below[below > port_df["total_invested"]] = None

        fig_pf.add_trace(go.Scatter(
            x=port_df["date"], y=port_df["total_value"],
            name="Portfolio Value", line=dict(color="#e2e8f0", width=2),
            fill="tonexty", fillcolor="rgba(74,222,128,0.15)",
        ))
        fig_pf.update_layout(
            height=380, margin=dict(l=0, r=0, t=20, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)", color="#94a3b8"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)", tickprefix="$", color="#94a3b8"),
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig_pf, use_container_width=True)

        # P&L % chart
        fig_pnl = go.Figure(go.Scatter(
            x=port_df["date"], y=port_df["pnl_pct"],
            fill="tozeroy",
            fillcolor="rgba(74,222,128,0.1)",
            line=dict(color="#4ade80", width=2),
            name="P&L %",
        ))
        fig_pnl.add_hline(y=0, line=dict(color="#64748b", width=1))
        fig_pnl.update_layout(
            height=200, margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor="rgba(255,255,255,0.05)", color="#94a3b8"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)", ticksuffix="%", color="#94a3b8"),
        )
        st.plotly_chart(fig_pnl, use_container_width=True)

        # Per-holding performance
        st.markdown("#### Individual Performance")
        perf_data = []
        for h in holdings:
            t = h["ticker"]
            pr = get_latest_price(t) or h.get("entry_price", 0)
            cost = h["shares"] * h["entry_price"]
            val = h["shares"] * pr
            perf_data.append({
                "Ticker": t, "Shares": h["shares"],
                "Entry": f"${h['entry_price']:.4f}", "Current": f"${pr:.4f}",
                "Cost": f"${cost:,.2f}", "Value": f"${val:,.2f}",
                "P&L $": f"${val-cost:+,.2f}",
                "P&L %": f"{(val-cost)/cost*100:+.2f}%" if cost else "—",
            })
        if perf_data:
            st.dataframe(pd.DataFrame(perf_data), use_container_width=True, hide_index=True)
    else:
        st.info("Performance history builds up as the engine runs. Check back after the first price snapshot cycle (runs every 15 min).")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ALERTS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_alerts:
    st.markdown("### Research Alerts")

    alerts = get_recent_alerts(20)
    if alerts:
        for ts, tkr, atype, msg in alerts:
            icons = {"OPPORTUNITY": "🟢", "WARNING": "🟡", "URGENT": "🔴",
                     "HOLD_SIGNAL": "🔵", "WEEKLY_DEBRIEF": "📊", "SIGNAL": "⚪"}
            icon = icons.get(atype, "⚪")
            with st.expander(f"{icon} **{tkr}** — {atype} — {str(ts)[:16]}"):
                # Parse and display structured sections
                text = msg
                for section in ["SITUATION", "BULL CASE", "BEAR CASE",
                                 "PROBABILITY WEIGHTED VIEW", "WHAT TO WATCH"]:
                    if section in text:
                        text = text.replace(section, f"\n**{section}**")
                st.markdown(text)
    else:
        st.info("No alerts yet. Run a deep scan: `python main.py --deep --ticker NVDA`")

    st.divider()
    st.markdown("#### Engine Status")
    health_log = BASE_DIR / "logs" / "health.log"
    last_alive = "Not started"
    if health_log.exists():
        lines = health_log.read_text().strip().split("\n")
        if lines and lines[-1]:
            last_alive = lines[-1].replace("alive ", "")
    col1, col2 = st.columns(2)
    col1.info(f"Last health ping: {last_alive}")
    col2.info(f"DB: {BASE_DIR / 'signals.db'}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — CHAT ASSISTANT
# ═══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.markdown("### AI Portfolio Assistant")
    st.caption("Ask anything. Add stocks, run scans, check performance, or just ask a question.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content":
             f"Hey {name}! I'm monitoring your portfolio. You can tell me things like:\n"
             "• *'I bought 5 shares of TSLA at $220'*\n"
             "• *'Run a deep scan on NVDA'*\n"
             "• *'How is my portfolio doing?'*\n"
             "• *'Add AAPL to my watchlist'*\n"
             "• *'Remove SALIK from holdings'*"}
        ]

    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Message your assistant...")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    from src.crew import run_chat_command
                    action = run_chat_command(user_input, portfolio)
                    act = action.get("action", "unknown")
                    reply = ""

                    if act == "add_stock":
                        t = action.get("ticker", "").upper()
                        sh = float(action.get("shares", 0))
                        ep = float(action.get("entry_price", 0))
                        sl = float(action.get("stop_loss_pct", 8))
                        if t and sh > 0 and ep > 0:
                            from src.tools.yfinance_tools import estimate_entry_date
                            from setup import detect_exchange
                            exch = detect_exchange(t)
                            edate = estimate_entry_date(t, ep)
                            portfolio["holdings"] = [h for h in portfolio["holdings"] if h["ticker"] != t]
                            portfolio["holdings"].append({
                                "ticker": t, "exchange": exch, "shares": sh,
                                "entry_price": ep, "entry_date_estimated": edate,
                                "stop_loss_pct": sl, "thesis": "", "screenshot_path": "",
                            })
                            save_portfolio(portfolio)
                            reply = f"✅ Added **{t}** — {sh} shares @ ${ep} (exchange: {exch}, stop: {sl}%)"
                        else:
                            reply = f"I need ticker, shares, and entry price. Could you confirm those?"

                    elif act == "remove_stock":
                        t = action.get("ticker", "").upper()
                        before = len(portfolio["holdings"])
                        portfolio["holdings"] = [h for h in portfolio["holdings"] if h["ticker"] != t]
                        save_portfolio(portfolio)
                        reply = f"✅ Removed **{t}** from portfolio." if len(portfolio["holdings"]) < before else f"Couldn't find {t} in your holdings."

                    elif act == "add_watchlist":
                        t = action.get("ticker", "").upper()
                        if t and t not in portfolio.get("watchlist", []):
                            portfolio.setdefault("watchlist", []).append(t)
                            save_portfolio(portfolio)
                            reply = f"✅ Added **{t}** to your watchlist."
                        else:
                            reply = f"{t} is already on your watchlist."

                    elif act == "run_scan":
                        t = action.get("ticker", "").upper()
                        scan_type = action.get("type", "pulse")
                        reply = f"🔍 Kicking off a {scan_type} scan on **{t}**... check the Alerts tab in a few minutes."
                        import threading
                        def _bg_scan(tkr, stype, pf):
                            from src.crew import run_deep_scan, run_pulse_scan
                            h = next((x for x in pf["holdings"] if x["ticker"] == tkr), {})
                            if stype == "deep":
                                run_deep_scan(tkr, h, pf)
                            else:
                                run_pulse_scan(tkr, pf)
                        threading.Thread(target=_bg_scan, args=(t, scan_type, portfolio), daemon=True).start()

                    elif act == "show_performance":
                        lines = [f"**Portfolio Summary as of {datetime.now().strftime('%H:%M')}**\n"]
                        for h in portfolio["holdings"]:
                            pr = get_latest_price(h["ticker"]) or h["entry_price"]
                            val = h["shares"] * pr
                            cost = h["shares"] * h["entry_price"]
                            pnl_pct = (val - cost) / cost * 100 if cost else 0
                            lines.append(f"• **{h['ticker']}**: ${val:,.2f} ({pnl_pct:+.1f}%)")
                        lines.append(f"\n**Total**: ${total_current:,.2f} | P&L: ${total_pnl:+,.2f} ({total_pnl_pct:+.1f}%)")
                        reply = "\n".join(lines)

                    elif act == "answer_question":
                        reply = action.get("answer", "I'm not sure about that.")

                    else:
                        clarification = action.get("clarification", "")
                        reply = f"I'm not sure what you mean. {clarification}" if clarification else "Could you rephrase that? I can add/remove stocks, run scans, or answer questions about your portfolio."

                except Exception as e:
                    reply = f"Something went wrong: {str(e)[:100]}"

            st.markdown(reply)
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
