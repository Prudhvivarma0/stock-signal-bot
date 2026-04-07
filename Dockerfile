FROM python:3.11-slim

WORKDIR /app

# System deps for pandas-ta, pytesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt litellm

COPY . .

# Remove any accidentally copied secrets
RUN rm -f .env signals.db portfolio.json

EXPOSE 8501

# Health check
HEALTHCHECK --interval=60s --timeout=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["python", "main.py"]
