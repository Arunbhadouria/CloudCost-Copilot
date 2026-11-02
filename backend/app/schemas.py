"""Pydantic v2 schemas for CloudCost Copilot API."""
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from pydantic import BaseModel, Field


# Standard Error Response
class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# Health Check
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"


# Datasets
class DatasetItem(BaseModel):
    id: str
    name: str
    kind: str  # 'csv' | 'synthetic'
    seed: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime


class CsvUploadResponse(BaseModel):
    dataset_id: str
    rows_loaded: int
    rows_quarantined: int
    warnings: int
    date_range: Dict[str, Optional[str]]


class SyntheticGenerateRequest(BaseModel):
    seed: int = 1
    months: int = 3
    resources: int = 60
    anomaly_rate: float = 0.05
    start_date: str = "2025-01-01"


class DatasetSummaryResponse(BaseModel):
    id: str
    name: str
    kind: str
    total_cost: float
    resources: int
    date_range: Dict[str, Optional[str]]
    is_derived_daily: bool
    findings_count: int
    savings_range: Dict[str, float]
    anomalies_count: int


class DataWarningItem(BaseModel):
    id: int
    kind: str
    resource_id: Optional[str] = None
    detail: Dict[str, Any]


# Costs
class CostBreakdownItem(BaseModel):
    key: str
    billed_cost: float
    share_pct: float


class DailyCostItem(BaseModel):
    date: str
    billed_cost: float
    service_name: Optional[str] = None
    region_id: Optional[str] = None


class CostTopItem(BaseModel):
    service_name: str
    billed_cost: float
    share_pct: float


# Recommendations
class RecommendationItem(BaseModel):
    id: int
    dataset_id: str
    resource_id: str
    service_name: str
    type: str  # 'idle', 'underused', 'weak_signal'
    savings_low: float
    savings_high: float
    savings_mid: float
    savings_basis: str  # 'price_table', 'assumption'
    savings_unit: str   # 'monthly', 'observed_window'
    confidence: float
    effort: int
    priority: float
    reason: str
    status: str  # 'open', 'accepted', 'dismissed', 'dry_run_generated'
    created_at: datetime


class DetectRunRequest(BaseModel):
    dataset_id: str
    path: str = "auto"  # 'auto' | 'snapshot' | 'series'


class DetectRunResponse(BaseModel):
    dataset_id: str
    path_used: str
    counts: Dict[str, int]
    total_savings_mid: float


# Dry-run
class DryRunResponse(BaseModel):
    command: Optional[str] = None
    rollback: Optional[str] = None
    warnings: List[str] = []
    manual_review: bool = False


# Anomalies
class AnomalyItem(BaseModel):
    id: int
    dataset_id: str
    start_date: str
    end_date: str
    service_name: str
    expected: float
    actual: float
    peak_zscore: float
    severity: str
    explained_by: Optional[List[Dict[str, Any]]] = None


# Chat
class ChatRequest(BaseModel):
    dataset_id: str
    message: str


# Evaluation
class EvalRunRequest(BaseModel):
    seeds: List[int] = Field(default_factory=lambda: [100, 101, 102])


class EvalRunResponse(BaseModel):
    id: int
    created_at: datetime
    results: Dict[str, Any]


# Audit Log
class AuditLogItem(BaseModel):
    id: int
    ts: datetime
    actor: str
    action: str
    entity: str
    entity_id: str
    payload: Optional[Dict[str, Any]] = None

