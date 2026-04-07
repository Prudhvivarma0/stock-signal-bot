"""SQLite database layer for signals.db."""
import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime,
    create_engine, text
)
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "signals.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base = declarative_base()

log = logging.getLogger(__name__)


class Scan(Base):
    __tablename__ = "scans"
    id = Column(Integer, primary_key=True)
    ticker = Column(String, index=True)
    scan_time = Column(DateTime, default=datetime.utcnow)
    agent_name = Column(String)
    summary = Column(Text)
    flags = Column(Text)
    raw_json = Column(Text)


class AlertSent(Base):
    __tablename__ = "alerts_sent"
    id = Column(Integer, primary_key=True)
    ticker = Column(String, index=True)
    type = Column(String)
    message = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)
    delivered = Column(Integer, default=1)


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    id = Column(Integer, primary_key=True)
    ticker = Column(String, index=True)
    price = Column(Float)
    volume = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)


class SentimentHistory(Base):
    __tablename__ = "sentiment_history"
    id = Column(Integer, primary_key=True)
    ticker = Column(String, index=True)
    news_score = Column(Float)
    social_score = Column(Float)
    date = Column(DateTime, default=datetime.utcnow)


class TrendsHistory(Base):
    __tablename__ = "trends_history"
    id = Column(Integer, primary_key=True)
    ticker = Column(String, index=True)
    google_trend_score = Column(Float)
    wiki_views = Column(Integer)
    date = Column(DateTime, default=datetime.utcnow)


class PortfolioHistory(Base):
    __tablename__ = "portfolio_history"
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, default=datetime.utcnow)
    total_value = Column(Float)
    total_invested = Column(Float)


class DeadLetterQueue(Base):
    __tablename__ = "dead_letter_queue"
    id = Column(Integer, primary_key=True)
    message = Column(Text)
    chat_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    retries = Column(Integer, default=0)


def init_db():
    Base.metadata.create_all(engine)
    log.info("Database initialised at %s", DB_PATH)


def save_scan(ticker: str, agent_name: str, summary: str, flags: list, raw: dict):
    with Session() as s:
        s.add(Scan(
            ticker=ticker,
            agent_name=agent_name,
            summary=summary,
            flags=json.dumps(flags),
            raw_json=json.dumps(raw),
        ))
        s.commit()


def save_alert(ticker: str, alert_type: str, message: str, delivered: bool = True):
    with Session() as s:
        s.add(AlertSent(
            ticker=ticker,
            type=alert_type,
            message=message,
            delivered=int(delivered),
        ))
        s.commit()


def was_alert_sent_recently(ticker: str, hours: int = 72) -> bool:
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    with Session() as s:
        row = s.query(AlertSent).filter(
            AlertSent.ticker == ticker,
            AlertSent.sent_at >= cutoff,
        ).first()
        return row is not None


def upsert_price_snapshot(ticker: str, price: float, volume: float):
    with Session() as s:
        s.add(PriceSnapshot(ticker=ticker, price=price, volume=volume))
        s.commit()


def get_price_history(ticker: str, days: int = 30):
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    with Session() as s:
        rows = (
            s.query(PriceSnapshot)
            .filter(PriceSnapshot.ticker == ticker, PriceSnapshot.timestamp >= cutoff)
            .order_by(PriceSnapshot.timestamp)
            .all()
        )
        return [(r.timestamp, r.price, r.volume) for r in rows]


def save_sentiment(ticker: str, news_score: float, social_score: float):
    with Session() as s:
        s.add(SentimentHistory(ticker=ticker, news_score=news_score, social_score=social_score))
        s.commit()


def get_sentiment_baseline(ticker: str, days: int = 7):
    from datetime import timedelta
    import statistics
    cutoff = datetime.utcnow() - timedelta(days=days)
    with Session() as s:
        rows = s.query(SentimentHistory).filter(
            SentimentHistory.ticker == ticker,
            SentimentHistory.date >= cutoff,
        ).all()
        scores = [r.news_score for r in rows if r.news_score is not None]
        if len(scores) < 2:
            return None, None
        return statistics.mean(scores), statistics.stdev(scores)


def save_portfolio_snapshot(total_value: float, total_invested: float):
    with Session() as s:
        today = datetime.utcnow().date()
        existing = s.query(PortfolioHistory).filter(
            text("date(date) = :d")
        ).params(d=str(today)).first()
        if existing:
            existing.total_value = total_value
            existing.total_invested = total_invested
        else:
            s.add(PortfolioHistory(total_value=total_value, total_invested=total_invested))
        s.commit()


def get_portfolio_history_rows(days: int = 365):
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    with Session() as s:
        rows = (
            s.query(PortfolioHistory)
            .filter(PortfolioHistory.date >= cutoff)
            .order_by(PortfolioHistory.date)
            .all()
        )
        return [(r.date, r.total_value, r.total_invested) for r in rows]


def get_recent_alerts(limit: int = 10):
    with Session() as s:
        rows = (
            s.query(AlertSent)
            .order_by(AlertSent.sent_at.desc())
            .limit(limit)
            .all()
        )
        return [(r.sent_at, r.ticker, r.type, r.message) for r in rows]


def get_cached_scan(ticker: str, agent_name: str, max_age_hours: int = 6) -> dict | None:
    """Return cached agent result if it exists and is within max_age_hours."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    with Session() as s:
        row = (
            s.query(Scan)
            .filter(
                Scan.ticker == ticker,
                Scan.agent_name == agent_name,
                Scan.scan_time >= cutoff,
            )
            .order_by(Scan.scan_time.desc())
            .first()
        )
        if row:
            return json.loads(row.raw_json or "{}")
    return None


def get_latest_scan(ticker: str, agent_name: str = None):
    with Session() as s:
        q = s.query(Scan).filter(Scan.ticker == ticker)
        if agent_name:
            q = q.filter(Scan.agent_name == agent_name)
        row = q.order_by(Scan.scan_time.desc()).first()
        if row:
            return {"summary": row.summary, "flags": json.loads(row.flags or "[]"),
                    "raw": json.loads(row.raw_json or "{}"), "scan_time": row.scan_time}
        return None


def save_dead_letter(message: str, chat_id: str):
    with Session() as s:
        s.add(DeadLetterQueue(message=message, chat_id=chat_id))
        s.commit()


def get_dead_letters(limit: int = 20):
    with Session() as s:
        rows = s.query(DeadLetterQueue).filter(
            DeadLetterQueue.retries < 5
        ).limit(limit).all()
        return rows


def mark_dead_letter_retried(dlq_id: int):
    with Session() as s:
        row = s.query(DeadLetterQueue).get(dlq_id)
        if row:
            row.retries += 1
            s.commit()


def delete_dead_letter(dlq_id: int):
    with Session() as s:
        row = s.query(DeadLetterQueue).get(dlq_id)
        if row:
            s.delete(row)
            s.commit()
