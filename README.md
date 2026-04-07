# Stock Signal Bot

An AI-powered stock research system: a local portfolio dashboard + a continuous multi-agent research engine that monitors your holdings 24/7 and alerts you via Telegram when something actually matters.

---

## What it does

**Part 1 — Portfolio Dashboard** (Streamlit, runs on localhost)
- Live P&L for each holding, with entry price and stop-loss lines on the chart
- Candlestick charts (1D to ALL timeframe) with SMA20/50 overlays
- USD / AED toggle — all values convert in real time (1 USD = 3.6725 AED fixed peg)
- UAE stocks (DFM/ADX) shown in AED natively; US stocks in USD
- Watchlist sparklines
- Alerts feed showing every research signal the engine sent
- AI chat assistant — add stocks, run scans, ask questions in plain language

**Part 2 — Research Engine** (CrewAI + APScheduler, runs in background)
- 9 specialist AI agents analyse your holdings from every angle
- Pulse scans every 90 minutes (lightweight: news + price anomaly)
- Deep scans twice daily at 7AM and 7PM Dubai time
- Emergency scan auto-triggers when a price anomaly or breaking news is detected
- Sunday weekly debrief sent to Telegram
- All results cached in SQLite — agents are not re-run if data is less than 6 hours old

---

## The 9 agents

| # | Agent | Model | What it covers |
|---|---|---|---|
| 1 | Fundamentals | llama-3.1-8b-instant | P/E, revenue, margins, FCF, insider trades, debt |
| 2 | News Intelligence | llama-3.1-8b-instant | RSS feeds, press releases, SEC 8-K alerts, breaking news |
| 3 | Social & Sentiment | llama-3.1-8b-instant | Reddit (18 subs), StockTwits, Twitter, Google Trends, Wikipedia, YouTube |
| 4 | Technical | llama-3.1-8b-instant | RSI, MACD, Bollinger, options flow, short interest, momentum |
| 5 | Analyst & Institutional | llama-3.1-8b-instant | Ratings, price targets, 13F filings, smart money flows |
| 6 | Alternative Data | llama-3.1-8b-instant | Job postings, GitHub, earnings call language, macro catalysts |
| 7 | Risk Manager | llama-3.1-8b-instant | Position sizing (half-Kelly), ATR stop, R:R ratio |
| 8 | Bull Advocate | llama-3.1-8b-instant | Strongest possible bull case, citing source agents |
| 9 | Bear Advocate | llama-3.1-8b-instant | Strongest possible bear case, citing source agents |
| — | Manager (decides) | llama-3.3-70b-versatile | Reads all 9 reports, decides: alert or silence |

The manager uses the large 70B model for final synthesis. Everyone else uses the fast 8B model to stay within free tier rate limits.

---

## How the model thinks

Each deep scan follows this pipeline:

```
Agents 1-6 (run sequentially, 3s gap each)
    ↓
Risk Manager (position sizing from agents 4+1)
    ↓
Bull Advocate (argues hardest bull case from all 6 reports)
    ↓
Bear Advocate (argues hardest bear case from all 6 reports)
    ↓
Manager reads everything → decides: ALERT or NO_ALERT
```

The manager's default is silence. It only sends an alert when something genuinely changes the picture. Most scans end in `NO_ALERT`.

If an alert is warranted, the message follows this structure:

```
SITUATION — what changed and why it matters
BULL CASE — why this could go well
BEAR CASE — why this could go wrong
RISK MANAGER SAYS — position size, stop price, R:R ratio
WHAT TO WATCH — next catalysts to monitor
```

---

## LLM routing and rate limit strategy

```
groq/llama-3.1-8b-instant  →  Agents 1-6, Risk Manager, Bull, Bear, Chat
groq/llama-3.3-70b-versatile  →  Manager only (once per stock per scan)
gemini/gemini-1.5-flash  →  Automatic fallback if Groq returns 429
```

**Why two Groq models?**
- `llama-3.1-8b-instant` has higher rate limits (~14,400 requests/day free) and low latency. Good enough for structured data extraction.
- `llama-3.3-70b-versatile` is the best reasoning model available free. Used sparingly (one call per stock per scan cycle).

**Rate limit handling:**
1. 3-second pause between agents within a scan
2. 10-minute pause between stocks in a deep scan cycle (e.g. NVDA scanned, 10 min wait, then SALIK)
3. If Groq still returns 429: exponential backoff (60s → 120s → 240s)
4. If Groq is exhausted after 3 retries: automatically switches all remaining agents in that scan to `gemini/gemini-1.5-flash` (different quota pool). Add your `GEMINI_API_KEY` to `.env` to enable this.

---

## Caching

Agent results are cached in SQLite for **6 hours**.

Before running any agent, the system checks: "Do I have a result for this ticker + agent that is less than 6 hours old?" If yes, it skips the LLM call entirely and reuses the cached result.

This means:
- A deep scan at 7AM uses fresh data
- A deep scan at 7PM re-runs all agents (7AM cache has expired)
- An emergency scan triggered at 9AM would reuse 7AM cache for most agents (only 2 hours old)
- You can force a fresh run: `python main.py --deep --ticker NVDA --no-cache` (not yet implemented — delete `signals.db` to clear all cache)

---

## Scan timing

| Loop | Trigger | What it does |
|---|---|---|
| A — Pulse | Every 90 minutes | News scan + price anomaly check. No LLM calls. Fast. |
| B — Deep | 7AM and 7PM Dubai time | Full 9-agent pipeline. One stock every 10 minutes. |
| C — Emergency | When pulse detects anomaly | Full deep scan, immediately, for that one ticker |
| D — Weekly | Sunday 8AM Dubai time | Summary of the week, sent to Telegram |
| Price snapshots | Every 15 minutes | Saves price to SQLite, updates portfolio value history |
| Health ping | Every hour | Writes timestamp to `logs/health.log` |

A deep scan with 2 stocks takes approximately 30-40 minutes total (two 10-15 minute scans with a 10-minute wait between them).

---

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/YOUR_USERNAME/stock-signal-bot
cd stock-signal-bot
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# Edit .env and fill in your keys (see API keys section below)

# 3. Set up your portfolio
python setup.py

# 4. Run the system
python main.py
# Dashboard opens at http://localhost:8501
# Research engine runs in background
```

---

## API keys

| Key | Required | Free tier | Get it at |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | Yes — very generous | console.groq.com |
| `TELEGRAM_BOT_TOKEN` | Yes | Free | @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | Yes | Free | Send a message to your bot, run setup.py to auto-detect |
| `NEWSAPI_KEY` | Recommended | 100 req/day free | newsapi.org |
| `EODHD_API_KEY` | Optional | Limited on free plan | eodhd.com |
| `ALPHA_VANTAGE_KEY` | Optional | 25 req/day free | alphavantage.co |
| `FRED_API_KEY` | Optional | Free | fred.stlouisfed.org/docs/api |
| `GEMINI_API_KEY` | Optional | Yes | aistudio.google.com | 
| `REDDIT_CLIENT_ID` | Optional | Free | reddit.com/prefs/apps |

Copy `.env.example` to `.env` — never commit `.env` to git (it's in `.gitignore`).

---

## UAE stocks (DFM / ADX)

UAE stocks use the DFM (Dubai Financial Market) or ADX (Abu Dhabi Securities Exchange).

- Price data comes from Yahoo Finance using the `.AE` suffix (e.g. `SALIK.AE`)
- Prices are in AED (UAE dirham). The fixed peg is 1 USD = 3.6725 AED.
- In the dashboard, toggle the USD/AED button to switch display currency
- EODHD free plan does not support DFM/ADX data — the system falls back to yfinance automatically

Example tickers: `SALIK` (DFM), `EMAAR` (DFM), `ADNOC` (ADX)

---

## Running on an old machine (always-on server)

You can run this on any always-on machine (old Mac, Linux box, Raspberry Pi).

**Step 1: Install on the machine**
```bash
git clone https://github.com/YOUR_USERNAME/stock-signal-bot
cd stock-signal-bot
pip install -r requirements.txt
cp .env.example .env
# fill in .env, run setup.py
```

**Step 2: Keep it running in the background**
```bash
# Option A: nohup (simplest)
nohup python main.py > logs/main.log 2>&1 &

# Option B: use the provided script
chmod +x run_background.sh
./run_background.sh

# Option C: macOS launchd (auto-starts on login/reboot)
# See docs/launchd_setup.md (coming soon)
```

**Step 3: Access the dashboard from anywhere with Cloudflare Tunnel**

Cloudflare Tunnel is free and lets you expose localhost to the internet securely — no port forwarding, no dynamic DNS.

```bash
# Install cloudflared
brew install cloudflare/cloudflare/cloudflared   # macOS
# or: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

# One-time login
cloudflared tunnel login

# Create a tunnel (one-time)
cloudflared tunnel create stock-bot

# Start the tunnel (run this alongside main.py)
cloudflared tunnel --url http://localhost:8501

# OR: run with a permanent subdomain (requires free Cloudflare account + domain)
# cloudflared tunnel route dns stock-bot your-subdomain.yourdomain.com
# cloudflared tunnel run stock-bot
```

After running the tunnel command, you get a URL like `https://abc123.trycloudflare.com` — open that from any device, anywhere.

**Step 4: Auto-start everything on reboot (macOS)**
```bash
# Add to ~/.zprofile or create a launchd plist
# Simplest approach:
echo "cd ~/stock-signal-bot && nohup python main.py > logs/main.log 2>&1 &" >> ~/.zprofile
echo "cloudflared tunnel --url http://localhost:8501 > logs/tunnel.log 2>&1 &" >> ~/.zprofile
```

**Alternative: ngrok** (simpler, but free tier has random URL each restart)
```bash
brew install ngrok
ngrok http 8501
# Opens a tunnel, gives you a public URL
```

---

## Project structure

```
stock-signal-bot/
├── main.py              # Entry point — starts dashboard + research engine
├── setup.py             # First-time setup wizard
├── dashboard.py         # Streamlit dashboard (4 tabs)
├── portfolio.json        # Your holdings + watchlist (gitignored)
├── signals.db           # SQLite database (gitignored)
├── .env                 # API keys (gitignored — never commit this)
├── .env.example         # Template for .env
├── src/
│   ├── agents.py        # CrewAI agent definitions + LLM routing
│   ├── crew.py          # Agent orchestration, caching, backoff
│   ├── tasks.py         # Task prompts for each agent
│   ├── scheduler.py     # APScheduler loops (A/B/C/D)
│   ├── database.py      # SQLite layer (7 tables)
│   ├── chart_data.py    # Price data for dashboard charts
│   └── tools/
│       ├── yfinance_tools.py       # Price, history, entry date estimation
│       ├── uae_data.py             # DFM/ADX via yfinance .AE suffix, AED/USD conversion
│       ├── news_rss_tools.py       # RSS feeds + NewsAPI
│       ├── telegram_tool.py        # Send alerts, dead letter queue
│       ├── alpha_vantage_tools.py  # Fundamentals data
│       ├── fred_tools.py           # Macro indicators
│       └── screenshot_ocr_tool.py  # Read entry price from screenshot
└── logs/                # Runtime logs (gitignored)
```

---

## Database tables

| Table | What it stores |
|---|---|
| `scans` | Every agent output, indexed by ticker + agent name + time |
| `alerts_sent` | Every Telegram alert, with delivered flag |
| `price_snapshots` | Price every 15 minutes for each ticker |
| `sentiment_history` | News and social scores over time |
| `trends_history` | Google Trends scores |
| `portfolio_history` | Daily portfolio value vs invested |
| `dead_letter_queue` | Failed Telegram messages, retried every 30 min |

---

## Command line

```bash
python main.py                          # Start dashboard + full engine
python main.py --deep                   # Run one deep scan cycle now (all tickers)
python main.py --deep --ticker NVDA     # Deep scan one ticker only
python main.py --pulse                  # Run one pulse scan cycle
python main.py --dashboard-only         # Start dashboard without research engine
```

---

## How this is different from other AI trading bots

Most AI trading bots either:
- Give you a buy/sell signal based on a single model's opinion
- Run one LLM prompt and show you the output directly

This system is different in a few ways:

**Adversarial by design.** The bull and bear agents are forced to argue opposing sides before the manager decides. The manager has read both cases. This reduces confirmation bias — the system has to confront the bear case before it can send a buy alert.

**The default answer is silence.** The manager's goal is explicitly `NO_ALERT` unless something genuinely warrants attention. This means when you do get a Telegram message, it's because something actually changed.

**Caching prevents overtrading.** Agent results are reused for 6 hours. The system won't spam you with the same analysis repackaged.

**Holdings vs watchlist are treated differently.** A stock you own gets `HOLD / SELL` analysis. A stock on your watchlist gets `BUY / SKIP` analysis. The prompts are different.

**UAE stocks are first-class.** DFM and ADX stocks work the same as US stocks. AED prices, AED charts, AED P&L. No manual currency conversion needed.

---

## Limitations and disclaimers

- **This is not financial advice.** It's a research tool that surfaces information and patterns. Make your own decisions.
- The LLMs can hallucinate. Always verify any factual claim before acting on it.
- Free API tiers limit how often the system can run and how much data it can pull.
- Past performance of any signal does not predict future results.
- UAE/DFM fundamentals data is limited (EODHD free plan doesn't cover DFM). The system uses whatever yfinance provides.
