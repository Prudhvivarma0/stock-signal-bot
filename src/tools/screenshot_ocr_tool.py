"""Groq Vision OCR for brokerage screenshot price extraction."""
import base64
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)


def extract_price_from_screenshot(image_path: str, ticker: str) -> float | None:
    """Use Groq llama-3.2-11b-vision to extract average price from a screenshot."""
    try:
        from groq import Groq
        path = Path(image_path)
        if not path.exists():
            log.error("Image not found: %s", image_path)
            return None

        with open(path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # detect mime type
        suffix = path.suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".webp": "image/webp"}
        mime = mime_map.get(suffix, "image/jpeg")

        client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model="llama-3.2-11b-vision-preview",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime};base64,{image_data}",
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": (
                                        f"This is a brokerage screenshot. Extract the average price "
                                        f"or average cost per share for {ticker}. "
                                        "Return ONLY the number. No currency symbol, no text, just the number."
                                    ),
                                },
                            ],
                        }
                    ],
                    max_tokens=50,
                )
                raw = response.choices[0].message.content.strip()
                # clean up
                cleaned = raw.replace("$", "").replace(",", "").strip()
                return float(cleaned)
            except Exception as exc:
                if "429" in str(exc) or "rate limit" in str(exc).lower():
                    wait = 60 * (attempt + 1)
                    log.warning("Groq 429, waiting %ds (attempt %d)", wait, attempt + 1)
                    time.sleep(wait)
                else:
                    raise
        return None
    except Exception as exc:
        log.error("extract_price_from_screenshot(%s): %s", image_path, exc)
        return None
