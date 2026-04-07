"""StockTwits sentiment stream."""
import logging
import requests

log = logging.getLogger(__name__)


def stocktwits_stream(ticker: str) -> dict:
    try:
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        messages = data.get("messages", [])
        bull = sum(1 for m in messages if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bullish")
        bear = sum(1 for m in messages if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bearish")
        total = bull + bear
        bullish_pct = round(bull / total * 100, 1) if total else 50.0
        return {
            "bullish_count": bull,
            "bearish_count": bear,
            "bullish_pct": bullish_pct,
            "total_messages": len(messages),
        }
    except Exception as exc:
        log.error("stocktwits_stream(%s): %s", ticker, exc)
        return {"bullish_pct": 50.0, "error": str(exc)}
