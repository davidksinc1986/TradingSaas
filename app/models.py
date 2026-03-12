from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    connectors = relationship("Connector", back_populates="user", cascade="all, delete-orphan")
    trade_runs = relationship("TradeRun", back_populates="user", cascade="all, delete-orphan")
    trade_logs = relationship("TradeLog", back_populates="user", cascade="all, delete-orphan")
    platform_grants = relationship("UserPlatformGrant", back_populates="user", cascade="all, delete-orphan")


class PlatformPolicy(Base):
    __tablename__ = "platform_policies"
    __table_args__ = (UniqueConstraint("platform", name="uq_platform_policy_platform"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(50), index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50), default="market")
    is_enabled_global: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_manual_symbols: Mapped[bool] = mapped_column(Boolean, default=True)
    top_symbols_json: Mapped[dict] = mapped_column(JSON, default=dict)
    allowed_symbols_json: Mapped[dict] = mapped_column(JSON, default=dict)
    guide_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user_grants = relationship("UserPlatformGrant", back_populates="platform_policy", cascade="all, delete-orphan")


class UserPlatformGrant(Base):
    __tablename__ = "user_platform_grants"
    __table_args__ = (UniqueConstraint("user_id", "platform", name="uq_user_platform_grant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform: Mapped[str] = mapped_column(ForeignKey("platform_policies.platform"), index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    max_symbols: Mapped[int] = mapped_column(Integer, default=5)
    max_daily_movements: Mapped[int] = mapped_column(Integer, default=20)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="platform_grants")
    platform_policy = relationship("PlatformPolicy", back_populates="user_grants")


class Connector(Base):
    __tablename__ = "connectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    platform: Mapped[str] = mapped_column(String(50), index=True)
    label: Mapped[str] = mapped_column(String(100), default="Default")
    mode: Mapped[str] = mapped_column(String(20), default="paper")
    market_type: Mapped[str] = mapped_column(String(20), default="spot")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    symbols_json: Mapped[dict] = mapped_column(JSON, default=dict)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    encrypted_secret_blob: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="connectors")
    trade_runs = relationship("TradeRun", back_populates="connector", cascade="all, delete-orphan")
    trade_logs = relationship("TradeLog", back_populates="connector", cascade="all, delete-orphan")


class StrategyProfile(Base):
    __tablename__ = "strategy_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)


class TradeRun(Base):
    __tablename__ = "trade_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id"), index=True)
    strategy_slug: Mapped[str] = mapped_column(String(100))
    symbol: Mapped[str] = mapped_column(String(100))
    timeframe: Mapped[str] = mapped_column(String(20), default="1h")
    signal: Mapped[str] = mapped_column(String(20))
    ml_probability: Mapped[float] = mapped_column(Float, default=0.5)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="trade_runs")
    connector = relationship("Connector", back_populates="trade_runs")


class TradeLog(Base):
    __tablename__ = "trade_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id"), index=True)
    platform: Mapped[str] = mapped_column(String(50))
    symbol: Mapped[str] = mapped_column(String(100))
    side: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    order_type: Mapped[str] = mapped_column(String(20), default="market")
    status: Mapped[str] = mapped_column(String(30), default="filled")
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="trade_logs")
    connector = relationship("Connector", back_populates="trade_logs")
