"""Database models for Telegram Gift Buyer"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, JSON, 
    ForeignKey, Float, Text, UniqueConstraint, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class RunMode(str, Enum):
    DRY = "dry"
    LIVE = "live"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PurchaseStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    VERIFICATION_NEEDED = "verification_needed"
    REFUNDED = "refunded"


class GiftSource(str, Enum):
    PRIMARY = "primary"
    RESALE = "resale"


class EventType(str, Enum):
    DISCOVERY = "discovery"
    EVALUATION = "evaluation"
    PURCHASE_ATTEMPT = "purchase_attempt"
    PURCHASE_SUCCESS = "purchase_success"
    PURCHASE_FAIL = "purchase_fail"
    RULE_MATCH = "rule_match"
    RULE_REJECT = "rule_reject"
    SAFETY_BLOCK = "safety_block"


class Ruleset(Base):
    __tablename__ = "rulesets"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    active = Column(Boolean, default=False)
    rules = Column(JSON, nullable=False)  # JSON rule configuration
    created_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    runs = relationship("Run", back_populates="ruleset")


class Run(Base):
    __tablename__ = "runs"
    
    id = Column(Integer, primary_key=True)
    ruleset_id = Column(Integer, ForeignKey("rulesets.id"), nullable=False)
    mode = Column(String(10), nullable=False)  # dry or live
    status = Column(String(20), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True))
    total_evaluated = Column(Integer, default=0)
    total_matched = Column(Integer, default=0)
    total_purchased = Column(Integer, default=0)
    total_spent_stars = Column(Integer, default=0)
    
    # Relationships
    ruleset = relationship("Ruleset", back_populates="runs")
    events = relationship("OperationEvent", back_populates="run")
    purchases = relationship("Purchase", back_populates="run")
    
    __table_args__ = (
        Index("idx_runs_status", "status"),
        Index("idx_runs_started", "started_at"),
    )


class OperationEvent(Base):
    __tablename__ = "op_events"
    
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSON)  # Event-specific data
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    run = relationship("Run", back_populates="events")
    
    __table_args__ = (
        Index("idx_events_run", "run_id"),
        Index("idx_events_type", "event_type"),
        Index("idx_events_timestamp", "timestamp"),
    )


class Purchase(Base):
    __tablename__ = "purchases"
    
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id"))
    gift_id = Column(String(100), nullable=False)
    gift_slug = Column(String(200))
    gift_title = Column(String(200))
    source = Column(String(20), nullable=False)  # primary or resale
    price_stars = Column(Integer, nullable=False)
    seller_id = Column(String(100))  # For resale
    transaction_id = Column(String(200), unique=True)
    status = Column(String(30), nullable=False)
    error_message = Column(Text)
    purchased_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Gift attributes for audit
    rarity_attributes = Column(JSON)  # backdrop, symbol, number, etc.
    
    # Relationships
    run = relationship("Run", back_populates="purchases")
    
    __table_args__ = (
        Index("idx_purchases_status", "status"),
        Index("idx_purchases_gift", "gift_id"),
        Index("idx_purchases_date", "purchased_at"),
    )


class GiftInventory(Base):
    __tablename__ = "inventory"
    
    id = Column(Integer, primary_key=True)
    gift_id = Column(String(100), unique=True, nullable=False)
    gift_slug = Column(String(200))
    title = Column(String(200))
    model = Column(String(100))
    series = Column(String(100))
    owned_count = Column(Integer, default=1)
    purchase_price = Column(Integer)  # Original price in Stars
    current_value = Column(Integer)  # Current market value
    can_resell_at = Column(DateTime(timezone=True))
    attributes = Column(JSON)  # Full gift attributes
    acquired_at = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index("idx_inventory_model", "model"),
        Index("idx_inventory_resell", "can_resell_at"),
    )


class Settings(Base):
    __tablename__ = "settings"
    
    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100))  # Telegram user ID
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50))  # ruleset, run, purchase, etc.
    entity_id = Column(String(100))
    details = Column(JSON)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_timestamp", "timestamp"),
    )


class SpendTracking(Base):
    """Track spending for rate limiting"""
    __tablename__ = "spend_tracking"
    
    id = Column(Integer, primary_key=True)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    total_spent_stars = Column(Integer, default=0)
    purchase_count = Column(Integer, default=0)
    
    __table_args__ = (
        UniqueConstraint("period_start", "period_end"),
        Index("idx_spend_period", "period_start", "period_end"),
    )