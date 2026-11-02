"""Database models for CloudCost Copilot using SQLAlchemy 2.0."""
import datetime
from typing import Optional, Any
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, Text,
    ForeignKey, Index, JSON
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    kind = Column(String(32), nullable=False)  # 'csv' or 'synthetic'
    seed = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    resources = relationship("Resource", back_populates="dataset", cascade="all, delete-orphan")
    cost_line_items = relationship("CostLineItem", back_populates="dataset", cascade="all, delete-orphan")
    daily_spends = relationship("DailySpend", back_populates="dataset", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="dataset", cascade="all, delete-orphan")
    anomalies = relationship("Anomaly", back_populates="dataset", cascade="all, delete-orphan")
    ground_truths = relationship("GroundTruth", back_populates="dataset", cascade="all, delete-orphan")
    data_warnings = relationship("DataWarning", back_populates="dataset", cascade="all, delete-orphan")


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(64), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id = Column(String(128), nullable=False, index=True)
    service_name = Column(String(128), nullable=False, index=True)
    service_class = Column(String(64), nullable=False)
    region_id = Column(String(64), nullable=False)
    machine_type = Column(String(64), nullable=True)
    tags = Column(JSON, default=dict, nullable=False)
    is_prod = Column(Boolean, default=False, nullable=False)

    dataset = relationship("Dataset", back_populates="resources")


class CostLineItem(Base):
    __tablename__ = "cost_line_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(64), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id = Column(String(128), nullable=False, index=True)
    service_name = Column(String(128), nullable=False, index=True)
    region_id = Column(String(64), nullable=False)
    consumed_quantity = Column(Float, nullable=False)
    consumed_unit = Column(String(32), nullable=False)
    unit_price = Column(Float, nullable=False)
    billed_cost = Column(Float, nullable=False)
    charge_period_start = Column(DateTime, nullable=False)
    charge_period_end = Column(DateTime, nullable=False)

    dataset = relationship("Dataset", back_populates="cost_line_items")


class DailySpend(Base):
    __tablename__ = "daily_spend"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(64), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    service_name = Column(String(128), nullable=False, index=True)
    region_id = Column(String(64), nullable=False)
    billed_cost = Column(Float, nullable=False)
    is_derived = Column(Boolean, default=False, nullable=False)

    dataset = relationship("Dataset", back_populates="daily_spends")

    __table_args__ = (
        Index("idx_daily_spend_dataset_date", "dataset_id", "date"),
    )


class UtilizationSeries(Base):
    __tablename__ = "utilization_series"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(64), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id = Column(String(128), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    cpu_avg = Column(Float, nullable=False)
    cpu_p95 = Column(Float, nullable=False)
    mem_avg = Column(Float, nullable=False)
    mem_p95 = Column(Float, nullable=False)
    net_in_bytes = Column(Float, nullable=True)
    net_out_bytes = Column(Float, nullable=True)

    __table_args__ = (
        Index("idx_util_series_res_date", "dataset_id", "resource_id", "date"),
    )


class UtilizationSummary(Base):
    __tablename__ = "utilization_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(64), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id = Column(String(128), nullable=False, index=True)
    data_quality = Column(String(32), nullable=False)  # 'snapshot' or 'series'
    cpu_latest = Column(Float, nullable=False)
    cpu_avg = Column(Float, nullable=False)
    cpu_p95 = Column(Float, nullable=True)
    mem_latest = Column(Float, nullable=False)
    mem_avg = Column(Float, nullable=False)
    mem_p95 = Column(Float, nullable=True)
    cpu_cv = Column(Float, nullable=True)
    window_days = Column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index("idx_util_summary_res", "dataset_id", "resource_id", unique=True),
    )


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(64), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id = Column(String(128), nullable=False, index=True)
    service_name = Column(String(128), nullable=False)
    type = Column(String(32), nullable=False)  # 'idle', 'underused', 'weak_signal'
    savings_low = Column(Float, nullable=False)
    savings_high = Column(Float, nullable=False)
    savings_mid = Column(Float, nullable=False)
    savings_basis = Column(String(32), nullable=False)  # 'price_table', 'assumption'
    savings_unit = Column(String(32), nullable=False)   # 'monthly', 'observed_window'
    confidence = Column(Float, nullable=False)
    effort = Column(Integer, nullable=False)
    priority = Column(Float, nullable=False, index=True)
    reason = Column(Text, nullable=False)
    status = Column(String(32), default="open", nullable=False)  # 'open', 'accepted', 'dismissed', 'dry_run_generated'
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    dataset = relationship("Dataset", back_populates="recommendations")


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(64), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    service_name = Column(String(128), nullable=False)
    expected = Column(Float, nullable=False)
    actual = Column(Float, nullable=False)
    peak_zscore = Column(Float, nullable=False)
    severity = Column(String(32), nullable=False)  # 'low', 'medium', 'high'
    explained_by = Column(JSON, nullable=True)

    dataset = relationship("Dataset", back_populates="anomalies")


class GroundTruth(Base):
    __tablename__ = "ground_truth"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(64), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(32), nullable=False)  # 'anomaly', 'idle', 'underused', 'hard_negative'
    subtype = Column(String(64), nullable=True)  # e.g., 'bursty', 'batch', 'dr', 'spike', 'step', 'drift'
    target = Column(String(128), nullable=False)  # resource_id or service_name
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_positive = Column(Boolean, nullable=False)
    note = Column(Text, nullable=True)

    dataset = relationship("Dataset", back_populates="ground_truths")


class DataWarning(Base):
    __tablename__ = "data_warnings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(64), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(64), nullable=False)  # 'quarantined_row', 'mixed_units', 'bad_range'
    resource_id = Column(String(128), nullable=True)
    detail = Column(JSON, nullable=False)

    dataset = relationship("Dataset", back_populates="data_warnings")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    actor = Column(String(64), default="user", nullable=False)
    action = Column(String(64), nullable=False)
    entity = Column(String(64), nullable=False)
    entity_id = Column(String(128), nullable=False)
    payload = Column(JSON, nullable=True)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    dataset_id = Column(String(64), nullable=True)
    seed = Column(Integer, nullable=True)
    results = Column(JSON, nullable=False)


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    dataset_id = Column(String(64), nullable=False, index=True)
    question = Column(Text, nullable=False)
    tool_calls = Column(JSON, nullable=True)
    answer = Column(Text, nullable=False)
    faithfulness = Column(JSON, nullable=True)

