from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Boolean, JSON, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import DATABASE_URL
_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
def _now(): return datetime.now(timezone.utc)
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(100))
    email: Mapped[str]=mapped_column(String(150), unique=True, index=True)
    password_hash: Mapped[str]=mapped_column(String(300))
    role: Mapped[str]=mapped_column(String(20), default="USER")
    is_active: Mapped[bool]=mapped_column(Boolean, default=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=_now)
    last_login: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
class UserInterest(Base):
    __tablename__="user_interests"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    interest: Mapped[str]=mapped_column(String(100))
    weight: Mapped[float]=mapped_column(Float, default=1.0)
class Content(Base):
    __tablename__="contents"
    id: Mapped[int]=mapped_column(primary_key=True)
    title: Mapped[str]=mapped_column(String(300))
    body: Mapped[str]=mapped_column(Text)
    category: Mapped[str]=mapped_column(String(80), index=True)
    content_type: Mapped[str]=mapped_column(String(20), default="article")
    author: Mapped[str]=mapped_column(String(120), default="IntelliRec")
    source_url: Mapped[str|None]=mapped_column(String(800), nullable=True)
    image_url: Mapped[str|None]=mapped_column(String(800), nullable=True)
    views: Mapped[int]=mapped_column(Integer, default=0)
    likes: Mapped[int]=mapped_column(Integer, default=0)
    comments_count: Mapped[int]=mapped_column(Integer, default=0)
    shares: Mapped[int]=mapped_column(Integer, default=0)
    saves: Mapped[int]=mapped_column(Integer, default=0)
    avg_watch_seconds: Mapped[float]=mapped_column(Float, default=0)
    completion_rate: Mapped[float]=mapped_column(Float, default=0)
    scroll_depth: Mapped[float]=mapped_column(Float, default=0)
    sentiment: Mapped[float]=mapped_column(Float, default=0)
    topic: Mapped[int]=mapped_column(Integer, default=-1)
    keywords: Mapped[str]=mapped_column(String(500), default="")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=_now)
class Interaction(Base):
    __tablename__="interactions"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content_id: Mapped[int]=mapped_column(ForeignKey("contents.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str]=mapped_column(String(20), index=True)
    duration_seconds: Mapped[int]=mapped_column(Integer, default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=_now)
class Comment(Base):
    __tablename__="comments"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content_id: Mapped[int]=mapped_column(ForeignKey("contents.id", ondelete="CASCADE"))
    text: Mapped[str]=mapped_column(Text)
    sentiment: Mapped[float]=mapped_column(Float, default=0)
    sentiment_label: Mapped[str]=mapped_column(String(20), default="neutral")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=_now)
class AnalyticsEvent(Base):
    __tablename__="analytics_events"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int|None]=mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content_id: Mapped[int|None]=mapped_column(ForeignKey("contents.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str]=mapped_column(String(80), index=True)
    event_value: Mapped[str|None]=mapped_column(String(255), nullable=True)
    event_metadata: Mapped[dict|None]=mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=_now)
class RecommendationFeedback(Base):
    __tablename__="recommendation_feedback"
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content_id: Mapped[int]=mapped_column(ForeignKey("contents.id", ondelete="CASCADE"))
    feedback: Mapped[str]=mapped_column(String(20))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=_now)
class TrendingTopic(Base):
    __tablename__="trending_topics"
    id: Mapped[int]=mapped_column(primary_key=True)
    topic: Mapped[str]=mapped_column(String(200), index=True)
    mention_count: Mapped[int]=mapped_column(Integer, default=0)
    engagement_score: Mapped[float]=mapped_column(Float, default=0)
    growth_percentage: Mapped[float]=mapped_column(Float, default=0)
    calculated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=_now)
