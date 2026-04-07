# Stock Signal Bot

A two-part AI-powered stock research system: an interactive portfolio dashboard plus a continuous multi-agent research engine that monitors your holdings 24/7 and alerts you via Telegram when something actually matters.

## What it does

**Part 1 — Portfolio Dashboard** (Streamlit)
- Combined portfolio value chart with green/red fill vs invested baseline
- Per-holding candlestick charts with SMA20/50, entry price, stop-loss lines, volume
- Watchlist sparklines
- Real-time P&L
- Recent alerts feed

**Part 2 — Research Engine** (CrewAI + APScheduler)
- **7 specialist agents** running on Groq's free LLaMA 3.3 70B
- **Pulse scans** every 90 minutes: news, social velocity, price anomalies
- **Deep scans** twice daily at 7AM and 7PM (Dubai time)
- **Emergency scans** auto-triggered when anomaly detected
- **Weekly debrief** every Sunday

### The 7 agents

| Agent | What it covers |
|---|---|
| Fundamentals | P/E, revenue, margins, insider trades, SEC filings |
| News Intelligence | 15+ RSS sources, press releases, SEC 8-K alerts |
| Social & Community | Reddit (18 subs), StockTwits, Twitter/X, Google Trends, Wikipedia, YouTube |
| Technical | RSI, MACD, Bollinger, options flow, short squeeze signals |
| Analyst & Institutional | Ratings, price targets, 13F filings, smart money activity |
| Alternative Data | Job postings, GitHub activity, earnings call sentiment, macro events |
| Manager (LLM) | Reads all 6 reports, decides if alert is worth sending |

The manager has **zero hardcoded rules** — it uses pure LLM reasoning to decide. Most of the time it stays silent. It only alerts when it would genuinely tell a smart friend "you need to look at this today."

## Tech stack

- **LLM**: `groq/llama-3.3-70b-versatile` (free tier)
- **OCR**: `groq/llama-3.2-11b-vision-preview` (screenshot price extraction)
- **Orchestration**: CrewAI hierarchical crews
- **Scheduler**: APScheduler
- **Dashboard**: Streamlit + Plotly
- **Alerts**: Telegram (python-telegram-bot)
- **Storage**: SQLite via SQLAlchemy
- **Data**: yfinance, EODHD (UAE), SEC EDGAR, RSS feeds, Reddit PRAW

## Quick start

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API keys

Edit `.env`:
```
GROQ_API_KEY=your_key_here
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Minimum required: `GROQ_API_KEY` + `TELEGRAM_BOT_TOKEN`

Optional (adds more data sources):
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` — for Reddit scanning
- `EODHD_API_KEY` — for UAE (DFM/ADX) stock data
- `FRED_API_KEY` — for macro data (Fed rate, CPI, yield curve)

### 3. First-time setup

```bash
python main.py
```

If `portfolio.json` has no holdings, the interactive setup wizard runs automatically. It will:
- Ask for your name, budget, and holdings
- Accept a brokerage screenshot to extract your average price via Groq Vision OCR
- Estimate your entry date from price history
- Send a test Telegram message

### 4. Normal launch

```bash
python main.py
```

This starts the Streamlit dashboard (port 8501) and the research engine simultaneously.

## Test commands

```bash
# Scan one ticker without sending Telegram
python main.py --test --ticker AAPL

# Scan and send Telegram
python main.py --test --ticker AAPL --send

# Test UAE stock
python main.py --test --ticker EMAAR.DFM

# Run one pulse scan
python main.py --pulse

# Run one deep scan now
python main.py --deep --ticker AAPL

# Dashboard only
streamlit run dashboard.py
```

## Alert types

| Type | When |
|---|---|
| `OPPORTUNITY` | Pre-hype signal confirmed by multiple independent sources |
| `WARNING` | Holding showing meaningful thesis deterioration |
| `URGENT` | Breaking 8-K, stop-loss hit, sudden breakdown |
| `WEEKLY DEBRIEF` | Sunday narrative summary |

Anti-spam: same ticker won't alert twice within 72 hours.

## File structure

```
stock-signal-bot/
├── main.py              # Entry point
├── setup.py             # First-time onboarding wizard
├── dashboard.py         # Streamlit dashboard
├── portfolio.json       # Your holdings (auto-created by setup)
├── .env                 # API keys (never commit this)
├── requirements.txt
├── src/
│   ├── agents.py        # CrewAI agent definitions
│   ├── tasks.py         # CrewAI task definitions
│   ├── crew.py          # Scan orchestration
│   ├── scheduler.py     # APScheduler loops
│   ├── database.py      # SQLite layer
│   ├── chart_data.py    # Dashboard data provider
│   └── tools/           # 20+ data source tools
└── logs/
    ├── signals.log      # Rotating research log
    └── health.log       # Hourly alive pings
```

## Notes

- All tools are wrapped in `try/except` — one failing data source never crashes the agent
- Groq 429 errors trigger exponential backoff (60s, 120s, 240s)
- Failed Telegram messages go to a dead-letter queue and retry every 30 minutes
- UAE stocks (DFM/ADX) use EODHD if key is set, otherwise fall back to yfinance
