"""Technical analysis tools using pandas-ta."""
import logging
import pandas as pd
import numpy as np

log = logging.getLogger(__name__)


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators to OHLCV dataframe."""
    try:
        import pandas_ta as ta
        if df.empty or len(df) < 20:
            return df
        df = df.copy()
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ["_".join(c).strip("_") for c in df.columns]
        # Normalize column names
        df.columns = [c.split("_")[0] if "_" in c else c for c in df.columns]
        df.columns = [c.lower() for c in df.columns]

        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.sma(length=200, append=True)
        df.ta.ema(length=9, append=True)
        df.ta.ema(length=21, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.stoch(k=14, d=3, smooth_k=3, append=True)
        df.ta.willr(length=14, append=True)
        df.ta.cci(length=20, append=True)
        df.ta.mfi(length=14, append=True)
        df.ta.atr(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.kc(length=20, scalar=1.5, append=True)
        df.ta.obv(append=True)
        df.ta.ad(append=True)
        df.ta.cmf(length=20, append=True)
        return df
    except Exception as exc:
        log.error("calculate_indicators: %s", exc)
        return df


def detect_patterns(df: pd.DataFrame) -> dict:
    """Detect key chart patterns."""
    patterns = {}
    try:
        if df.empty or len(df) < 55:
            return patterns
        close = df["close"] if "close" in df.columns else df.iloc[:, 3]
        sma20_col = [c for c in df.columns if "sma_20" in c.lower() or "SMA_20" in c]
        sma50_col = [c for c in df.columns if "sma_50" in c.lower() or "SMA_50" in c]
        sma200_col = [c for c in df.columns if "sma_200" in c.lower() or "SMA_200" in c]

        if sma20_col and sma50_col:
            sma20 = df[sma20_col[0]]
            sma50 = df[sma50_col[0]]
            patterns["golden_cross"] = bool(
                sma20.iloc[-2] <= sma50.iloc[-2] and sma20.iloc[-1] > sma50.iloc[-1]
            )
            patterns["death_cross"] = bool(
                sma20.iloc[-2] >= sma50.iloc[-2] and sma20.iloc[-1] < sma50.iloc[-1]
            )

        # Higher highs / lower lows (last 20 candles)
        recent = close.tail(20)
        highs = recent.rolling(5).max()
        lows = recent.rolling(5).min()
        patterns["higher_highs"] = bool(highs.iloc[-1] > highs.iloc[-6]) if len(highs) > 6 else False
        patterns["higher_lows"] = bool(lows.iloc[-1] > lows.iloc[-6]) if len(lows) > 6 else False
        patterns["lower_highs"] = bool(highs.iloc[-1] < highs.iloc[-6]) if len(highs) > 6 else False
        patterns["lower_lows"] = bool(lows.iloc[-1] < lows.iloc[-6]) if len(lows) > 6 else False

        # Bollinger squeeze (bandwidth < 5% of price)
        bb_upper_cols = [c for c in df.columns if "bbu" in c.lower()]
        bb_lower_cols = [c for c in df.columns if "bbl" in c.lower()]
        if bb_upper_cols and bb_lower_cols:
            bandwidth = (df[bb_upper_cols[0]] - df[bb_lower_cols[0]]) / close
            patterns["bb_squeeze"] = bool(bandwidth.iloc[-1] < 0.05)

        # Volume expansion/contraction
        vol = df["volume"] if "volume" in df.columns else None
        if vol is not None:
            avg_vol = vol.tail(20).mean()
            patterns["volume_expansion"] = bool(vol.iloc[-1] > avg_vol * 1.5)
            patterns["volume_contraction"] = bool(vol.iloc[-1] < avg_vol * 0.5)

    except Exception as exc:
        log.error("detect_patterns: %s", exc)

    return patterns


def relative_strength(ticker: str, df_ticker: pd.DataFrame) -> dict:
    """Compare ticker returns vs SPY, QQQ."""
    import yfinance as yf
    result = {}
    try:
        benchmarks = {"SPY": None, "QQQ": None}
        for b in benchmarks:
            bdf = yf.download(b, period="6mo", interval="1d", progress=False, auto_adjust=True)
            if not bdf.empty:
                benchmarks[b] = bdf

        close_col = "close" if "close" in df_ticker.columns else df_ticker.columns[-2]
        for period_days, label in [(21, "1m"), (63, "3m"), (126, "6m")]:
            try:
                ticker_ret = float(df_ticker[close_col].iloc[-1] / df_ticker[close_col].iloc[-period_days] - 1)
                result[f"return_{label}"] = round(ticker_ret * 100, 2)
                for b, bdf in benchmarks.items():
                    if bdf is not None:
                        bcol = "close" if "close" in bdf.columns else bdf.columns[-2]
                        b_ret = float(bdf[bcol].iloc[-1] / bdf[bcol].iloc[-period_days] - 1)
                        result[f"rs_vs_{b}_{label}"] = round((ticker_ret - b_ret) * 100, 2)
            except Exception:
                pass
    except Exception as exc:
        log.error("relative_strength(%s): %s", ticker, exc)
    return result


def support_resistance(df: pd.DataFrame) -> dict:
    """Identify key support and resistance from weekly closes."""
    try:
        close = df["close"] if "close" in df.columns else df.iloc[:, 3]
        highs = df["high"] if "high" in df.columns else df.iloc[:, 1]
        lows = df["low"] if "low" in df.columns else df.iloc[:, 2]
        recent_high = float(highs.tail(50).max())
        recent_low = float(lows.tail(50).min())
        current = float(close.iloc[-1])
        return {
            "current_price": round(current, 4),
            "resistance": round(recent_high, 4),
            "support": round(recent_low, 4),
        }
    except Exception as exc:
        log.error("support_resistance: %s", exc)
        return {}


def calculate_stop_loss(entry_price: float, atr: float, multiplier: float = 2.0) -> float:
    """ATR-based stop loss."""
    return round(entry_price - (atr * multiplier), 4)


def build_technical_report(ticker: str) -> dict:
    """Full technical report for a ticker."""
    from src.tools.yfinance_tools import price_data, options_flow, short_squeeze_score

    report = {"ticker": ticker}
    try:
        df_daily = price_data(ticker, period="2y", interval="1d")
        df_weekly = price_data(ticker, period="5y", interval="1wk")

        if df_daily.empty:
            return {"ticker": ticker, "error": "no price data"}

        df = calculate_indicators(df_daily)
        patterns = detect_patterns(df)
        sr = support_resistance(df)
        rs = relative_strength(ticker, df)

        # pull key values safely
        def safe(col_fragments, default=None):
            for frag in col_fragments:
                matches = [c for c in df.columns if frag.lower() in c.lower()]
                if matches:
                    val = df[matches[0]].iloc[-1]
                    if pd.notna(val):
                        return round(float(val), 4)
            return default

        rsi = safe(["rsi_14"])
        macd_hist = safe(["macdh"])
        cci = safe(["cci_20"])
        mfi = safe(["mfi_14"])
        atr = safe(["atrr_14", "atr_14"])

        close = df["close"].iloc[-1] if "close" in df.columns else df.iloc[-1, 3]

        # trend
        sma20 = safe(["sma_20"])
        sma50 = safe(["sma_50"])
        sma200 = safe(["sma_200"])
        trend = "NEUTRAL"
        if sma20 and sma50 and sma200:
            if close > sma20 > sma50 > sma200:
                trend = "STRONG_UPTREND"
            elif close > sma20 > sma50:
                trend = "UPTREND"
            elif close < sma20 < sma50 < sma200:
                trend = "STRONG_DOWNTREND"
            elif close < sma20 < sma50:
                trend = "DOWNTREND"

        # signal
        signal = "NEUTRAL"
        bull_count = sum([
            rsi is not None and rsi < 70,
            macd_hist is not None and macd_hist > 0,
            patterns.get("golden_cross", False),
            patterns.get("higher_highs", False),
            trend in ("UPTREND", "STRONG_UPTREND"),
        ])
        bear_count = sum([
            rsi is not None and rsi < 30,
            macd_hist is not None and macd_hist < 0,
            patterns.get("death_cross", False),
            patterns.get("lower_lows", False),
            trend in ("DOWNTREND", "STRONG_DOWNTREND"),
        ])
        if bull_count >= 3:
            signal = "BUY"
        elif bear_count >= 3:
            signal = "AVOID"

        opts = options_flow(ticker)
        squeeze = short_squeeze_score(ticker)

        stop_price = calculate_stop_loss(float(close), atr or 0) if atr else None

        report.update({
            "technical_score": round((bull_count - bear_count) / 5, 2),
            "signal": signal,
            "trend": trend,
            "rsi": rsi,
            "macd_signal": "bullish" if (macd_hist or 0) > 0 else "bearish",
            "cci": cci,
            "mfi": mfi,
            "atr": atr,
            "golden_cross": patterns.get("golden_cross"),
            "death_cross": patterns.get("death_cross"),
            "bb_squeeze": patterns.get("bb_squeeze"),
            "volume_expansion": patterns.get("volume_expansion"),
            "support_level": sr.get("support"),
            "resistance_level": sr.get("resistance"),
            "current_price": round(float(close), 4),
            "stop_loss_price": stop_price,
            "relative_strength": rs,
            "options_signal": opts,
            "unusual_options": opts.get("unusual_options", []),
            "short_data": squeeze,
            "reasoning": f"Trend={trend}, RSI={rsi}, MACD={'bullish' if (macd_hist or 0)>0 else 'bearish'}, "
                         f"GoldenCross={patterns.get('golden_cross')}, DeathCross={patterns.get('death_cross')}",
        })
    except Exception as exc:
        log.error("build_technical_report(%s): %s", ticker, exc)
        report["error"] = str(exc)

    return report
