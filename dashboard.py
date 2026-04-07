"""Streamlit portfolio intelligence dashboard."""
import json
import os
import sys
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
from src.chart_data import (
    get_portfolio_history, get_stock_candles, get_latest_price, get_sparkline,
)

PORTFOLIO_PATH = BASE_DIR / "portfolio.json"


def load_portfolio() -> dict:
    if PORTFOLIO_PATH.exists():
        with open(PORTFOLIO_PATH) as f:
            return json.load(f)
    return {}


def format_pnl(pnl: float, pct: float) -> str:
    sign = "+" if pnl >= 0 else ""
    color = "green" if pnl >= 0 else "red"
    return f'<span style="color:{color}">{sign}${pnl:,.2f} ({sign}{pct:.1f}%)</span>'


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Portfolio Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Auto-refresh every 5 minutes ─────────────────────────────────────────────
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=5 * 60 * 1000, key="autorefresh")
except ImportError:
    pass

# ── Load data ────────────────────────────────────────────────────────────────
init_db()
portfolio = load_portfolio()
name = portfolio.get("user_name", "Investor")
holdings = portfolio.get("holdings", [])
watchlist = portfolio.get("watchlist", [])
now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    f"## 📈 {name}'s Portfolio Intelligence &nbsp;&nbsp;"
    f"<small style='color:grey'>Last updated: {now_str}</small>",
    unsafe_allow_html=True,
)

# ── Portfolio Summary Bar ────────────────────────────────────────────────────
total_invested = 0.0
total_current = 0.0
best_ticker, best_pct = "", -999.0
worst_ticker, worst_pct = "", 999.0

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
        if pct > best_pct:
            best_pct, best_ticker = pct, ticker
        if pct < worst_pct:
            worst_pct, worst_ticker = pct, ticker

total_pnl = total_current - total_invested
total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Invested", f"${total_invested:,.0f}")
col2.metric("Current Value", f"${total_current:,.0f}")
pnl_delta = f"{'+' if total_pnl >= 0 else ''}{total_pnl_pct:.1f}%"
col3.metric("Total P&L", f"${total_pnl:+,.0f}", delta=pnl_delta)
col4.metric("Best Performer", f"{best_ticker}", delta=f"{best_pct:+.1f}%" if best_ticker else None)
col5.metric("Worst Performer", f"{worst_ticker}", delta=f"{worst_pct:+.1f}%" if worst_ticker else None)

st.divider()

# ── Combined Portfolio Chart ──────────────────────────────────────────────────
st.subheader("Portfolio Value Over Time")

tf_cols = st.columns(6)
timeframes = ["1D", "1W", "1M", "3M", "6M", "ALL"]
selected_tf = st.session_state.get("portfolio_tf", "1M")
for i, tf in enumerate(timeframes):
    if tf_cols[i].button(tf, key=f"ptf_{tf}", use_container_width=True):
        selected_tf = tf
        st.session_state["portfolio_tf"] = tf

port_df = get_portfolio_history(selected_tf)

if not port_df.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=port_df["date"], y=port_df["total_invested"],
        name="Invested", line=dict(color="grey", dash="dash"), fill=None,
    ))
    fig.add_trace(go.Scatter(
        x=port_df["date"], y=port_df["total_value"],
        name="Portfolio Value",
        line=dict(color="white"),
        fill="tonexty",
        fillcolor="rgba(0,200,100,0.2)",
    ))
    fig.update_layout(
        height=350, margin=dict(l=0, r=0, t=20, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.1)", tickprefix="$"),
        legend=dict(orientation="h", y=1.1),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Portfolio history will populate after the first price snapshot cycle runs.")

st.divider()

# ── Individual Holdings ───────────────────────────────────────────────────────
st.subheader("Holdings")

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

    with st.expander(f"**{ticker}** — {shares} shares @ ${entry}  |  Current: ${current_price:.4f}  |  P&L: {'+' if pnl_usd>=0 else ''}{pnl_pct:.1f}%", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg Entry", f"${entry:.4f}")
        c2.metric("Current Price", f"${current_price:.4f}")
        c3.metric("P&L", f"${pnl_usd:+,.2f}", delta=f"{pnl_pct:+.1f}%")
        c4.metric("Stop Loss", f"${stop_price:.4f}", delta=f"-{stop_pct}%")

        # Timeframe toggle for this holding
        h_tf_key = f"htf_{ticker}"
        h_tfs = ["1D", "1W", "1M", "3M", "6M", "ALL"]
        h_tf_cols = st.columns(6)
        current_htf = st.session_state.get(h_tf_key, "1M")
        for i, htf in enumerate(h_tfs):
            if h_tf_cols[i].button(htf, key=f"htf_{ticker}_{htf}", use_container_width=True):
                current_htf = htf
                st.session_state[h_tf_key] = htf

        candle_df = get_stock_candles(ticker, current_htf, exchange)
        if not candle_df.empty:
            # Normalize columns
            candle_df.columns = [c.lower() if isinstance(c, str) else c for c in candle_df.columns]
            date_col = "date" if "date" in candle_df.columns else candle_df.columns[0]

            fig2 = go.Figure()

            # Candlestick
            fig2.add_trace(go.Candlestick(
                x=candle_df[date_col],
                open=candle_df.get("open", candle_df.iloc[:, 1]),
                high=candle_df.get("high", candle_df.iloc[:, 2]),
                low=candle_df.get("low", candle_df.iloc[:, 3]),
                close=candle_df.get("close", candle_df.iloc[:, 4]),
                name="Price",
            ))

            # SMA20 / SMA50
            if "close" in candle_df.columns and len(candle_df) >= 20:
                candle_df["sma20"] = candle_df["close"].rolling(20).mean()
                candle_df["sma50"] = candle_df["close"].rolling(50).mean()
                fig2.add_trace(go.Scatter(
                    x=candle_df[date_col], y=candle_df["sma20"],
                    name="SMA20", line=dict(color="blue", width=1),
                ))
                if len(candle_df) >= 50:
                    fig2.add_trace(go.Scatter(
                        x=candle_df[date_col], y=candle_df["sma50"],
                        name="SMA50", line=dict(color="purple", width=1),
                    ))

            # Entry price line
            fig2.add_hline(y=entry, line=dict(color="orange", dash="dash", width=1),
                           annotation_text=f"Entry ${entry:.2f}")

            # Stop loss line
            fig2.add_hline(y=stop_price, line=dict(color="red", dash="dash", width=1),
                           annotation_text=f"Stop ${stop_price:.2f}")

            # Entry date line
            if entry_date:
                fig2.add_vline(x=entry_date, line=dict(color="orange", dash="dot", width=1))

            fig2.update_layout(
                height=450, xaxis_rangeslider_visible=False,
                margin=dict(l=0, r=0, t=20, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(gridcolor="rgba(255,255,255,0.05)", tickprefix="$"),
            )
            st.plotly_chart(fig2, use_container_width=True)

            # Volume subplot
            if "volume" in candle_df.columns:
                vol_fig = go.Figure(go.Bar(
                    x=candle_df[date_col], y=candle_df["volume"],
                    marker_color="rgba(100,150,250,0.5)", name="Volume",
                ))
                vol_fig.update_layout(
                    height=120, margin=dict(l=0, r=0, t=0, b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                )
                st.plotly_chart(vol_fig, use_container_width=True)
        else:
            st.warning(f"No candle data available for {ticker} ({current_htf})")

        # Latest signal
        scan = get_latest_scan(ticker)
        if scan:
            st.markdown(f"**Latest Signal** ({str(scan['scan_time'])[:16]}): {scan['summary']}")
        else:
            st.caption("No research scans yet.")

st.divider()

# ── Watchlist ─────────────────────────────────────────────────────────────────
if watchlist:
    st.subheader("Watchlist")
    w_cols = st.columns(min(len(watchlist), 4))
    for i, wticker in enumerate(watchlist):
        with w_cols[i % 4]:
            wprice = get_latest_price(wticker) or 0
            spark = get_sparkline(wticker)
            st.metric(wticker, f"${wprice:.4f}" if wprice else "N/A")
            if spark:
                sdf = pd.DataFrame({"p": spark})
                st.line_chart(sdf, height=80, use_container_width=True)
            wscan = get_latest_scan(wticker)
            if wscan:
                st.caption(wscan["summary"][:100])

    st.divider()

# ── Recent Alerts ─────────────────────────────────────────────────────────────
st.subheader("Recent Alerts")
alerts = get_recent_alerts(10)
if alerts:
    for ts, tkr, atype, msg in alerts:
        color = {"OPPORTUNITY": "🟢", "WARNING": "🟡", "URGENT": "🔴",
                 "WEEKLY_DEBRIEF": "📊"}.get(atype, "⚪")
        with st.expander(f"{color} {tkr} — {atype} — {str(ts)[:16]}"):
            st.text(msg[:500])
else:
    st.caption("No alerts sent yet.")

st.divider()

# ── Engine Status ─────────────────────────────────────────────────────────────
st.subheader("Research Engine Status")

health_log = BASE_DIR / "logs" / "health.log"
last_alive = "Unknown"
if health_log.exists():
    lines = health_log.read_text().strip().split("\n")
    if lines:
        last_alive = lines[-1].replace("alive ", "")

c1, c2 = st.columns(2)
c1.info(f"Last health ping: {last_alive}")
c2.info(f"Database: {BASE_DIR / 'signals.db'}")
