"""Macro data: FRED, World Bank, commodities."""
import logging
import os
import requests

log = logging.getLogger(__name__)


def fred_macro() -> dict:
    try:
        api_key = os.getenv("FRED_API_KEY", "")
        if not api_key:
            return {"note": "FRED_API_KEY not configured"}
        base = "https://api.stlouisfed.org/fred/series/observations"
        series = {
            "fed_rate": "FEDFUNDS",
            "cpi": "CPIAUCSL",
            "10y_yield": "GS10",
            "2y_yield": "GS2",
            "unemployment": "UNRATE",
        }
        result = {}
        for name, sid in series.items():
            try:
                r = requests.get(base, params={
                    "series_id": sid, "api_key": api_key, "file_type": "json",
                    "sort_order": "desc", "limit": 2,
                }, timeout=10)
                obs = r.json().get("observations", [])
                if obs:
                    result[name] = float(obs[0]["value"])
                    if len(obs) > 1:
                        result[f"{name}_prev"] = float(obs[1]["value"])
            except Exception:
                pass
        # yield curve inversion
        if "10y_yield" in result and "2y_yield" in result:
            result["yield_curve_spread"] = round(result["10y_yield"] - result["2y_yield"], 2)
            result["yield_curve_inverted"] = result["yield_curve_spread"] < 0
        return result
    except Exception as exc:
        log.error("fred_macro: %s", exc)
        return {}


def commodity_prices() -> dict:
    try:
        import yfinance as yf
        tickers = {"oil_wti": "CL=F", "gold": "GC=F", "copper": "HG=F", "natural_gas": "NG=F"}
        result = {}
        for name, sym in tickers.items():
            try:
                info = yf.Ticker(sym).info or {}
                result[name] = info.get("regularMarketPrice") or info.get("previousClose")
            except Exception:
                pass
        return result
    except Exception as exc:
        log.error("commodity_prices: %s", exc)
        return {}


def worldbank_uae() -> dict:
    """UAE GDP and FDI from World Bank API."""
    try:
        result = {}
        indicators = {
            "gdp_growth": "NY.GDP.MKTP.KD.ZG",
            "fdi_inflows": "BX.KLT.DINV.CD.WD",
        }
        for name, ind in indicators.items():
            try:
                r = requests.get(
                    f"https://api.worldbank.org/v2/country/AE/indicator/{ind}?format=json&per_page=3",
                    timeout=15,
                )
                data = r.json()
                if len(data) > 1 and data[1]:
                    latest = next((x for x in data[1] if x.get("value") is not None), None)
                    if latest:
                        result[name] = {"value": latest["value"], "year": latest["date"]}
            except Exception:
                pass
        return result
    except Exception as exc:
        log.error("worldbank_uae: %s", exc)
        return {}
