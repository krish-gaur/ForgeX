"""ForgeX ORM models — mirror the architecture document §05 (extended where the
master specification requires: forensic-function scripts, findings, graph store,
local anchor ledger, jobs)."""
from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------- enums
class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    LEAD_INVESTIGATOR = "LEAD_INVESTIGATOR"
    INVESTIGATOR = "INVESTIGATOR"
    AUDITOR = "AUDITOR"


ROLE_RANK = {Role.AUDITOR: 0, Role.INVESTIGATOR: 1, Role.LEAD_INVESTIGATOR: 2, Role.ADMIN: 3}


class InvestigationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"
    SUSPENDED = "SUSPENDED"


class TargetOS(str, enum.Enum):
    WINDOWS = "WINDOWS"
    LINUX = "LINUX"
    UNKNOWN = "UNKNOWN"


class SourceMode(str, enum.Enum):
    LIVE_LOCAL = "LIVE_LOCAL"
    DATASET = "DATASET"


class Provenance(str, enum.Enum):
    LIVE = "LIVE"
    SYNTHETIC = "SYNTHETIC"


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    POLICY_DENIED = "POLICY_DENIED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class CollectorType(str, enum.Enum):
    PROCESS = "PROCESS"
    FILE = "FILE"
    NETWORK = "NETWORK"
    USER = "USER"
    EVENT = "EVENT"
    TIMELINE = "TIMELINE"


class CollectorStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    SKIPPED = "SKIPPED"


class EvidenceType(str, enum.Enum):
    PROCESS = "PROCESS"
    FILE = "FILE"
    NETWORK_CONNECTION = "NETWORK_CONNECTION"
    USER_ACCOUNT = "USER_ACCOUNT"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    TIMELINE_ENTRY = "TIMELINE_ENTRY"
    PCAP_FILE = "PCAP_FILE"
    LOG_ENTRY = "LOG_ENTRY"
    REGISTRY = "REGISTRY"
    BROWSER_ARTIFACT = "BROWSER_ARTIFACT"
    MEMORY_ARTIFACT = "MEMORY_ARTIFACT"


class BlockchainStatus(str, enum.Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class AnalysisType(str, enum.Enum):
    CORRELATION = "CORRELATION"
    EXPLANATION = "EXPLANATION"
    QUERY_RESPONSE = "QUERY_RESPONSE"
    MITRE_MAPPING = "MITRE_MAPPING"


class ReportType(str, enum.Enum):
    FULL = "FULL"
    SUMMARY = "SUMMARY"
    CHAIN_OF_CUSTODY = "CHAIN_OF_CUSTODY"


class ReportStatus(str, enum.Enum):
    GENERATING = "GENERATING"
    READY = "READY"
    FAILED = "FAILED"


class AuditResult(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    DENIED = "DENIED"


class ScriptLanguage(str, enum.Enum):
    PYFUNC = "PYFUNC"  # ForgeX forensic function (sandboxed Python + forgex SDK)
    FQL = "FQL"        # Forensic Query Language (collection intent)


class ScriptExecStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    STOPPED = "STOPPED"
    SANDBOX_VIOLATION = "SANDBOX_VIOLATION"


class FindingSeverity(str, enum.Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingStatus(str, enum.Enum):
    OPEN = "OPEN"
    VERIFIED = "VERIFIED"
    DISMISSED = "DISMISSED"


class FindingSource(str, enum.Enum):
    SCRIPT = "SCRIPT"
    AI = "AI"
    MANUAL = "MANUAL"


class AnchorChain(str, enum.Enum):
    LOCAL_HASH_CHAIN = "LOCAL_HASH_CHAIN"
    SEPOLIA = "SEPOLIA"


# --------------------------------------------------------------------------- tables
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=Role.INVESTIGATOR.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (CheckConstraint("role IN ('ADMIN','LEAD_INVESTIGATOR','INVESTIGATOR','AUDITOR')", name="ck_users_role"),)


class Investigation(Base):
    __tablename__ = "investigations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target_host: Mapped[str] = mapped_column(String(255), nullable=False)
    target_os: Mapped[str] = mapped_column(String(20), default=TargetOS.UNKNOWN.value)
    source_mode: Mapped[str] = mapped_column(String(20), default=SourceMode.LIVE_LOCAL.value)
    source_path: Mapped[str | None] = mapped_column(String(500))
    provenance: Mapped[str] = mapped_column(String(20), default=Provenance.LIVE.value)
    status: Mapped[str] = mapped_column(String(20), default=InvestigationStatus.ACTIVE.value, index=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    lead_investigator: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','COMPLETED','ARCHIVED','SUSPENDED')", name="ck_inv_status"),
        CheckConstraint("target_os IN ('WINDOWS','LINUX','UNKNOWN')", name="ck_inv_os"),
        CheckConstraint("source_mode IN ('LIVE_LOCAL','DATASET')", name="ck_inv_source"),
    )


class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    rules: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FqlQuery(Base):
    __tablename__ = "fql_queries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_fql: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_ast: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.PENDING.value)
    policy_decision: Mapped[dict | None] = mapped_column(JSON)
    submitted_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class CollectorExecution(Base):
    __tablename__ = "collector_executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    fql_query_id: Mapped[str] = mapped_column(String(36), ForeignKey("fql_queries.id", ondelete="CASCADE"), nullable=False, index=True)
    collector_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=CollectorStatus.RUNNING.value)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items_collected: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    raw_params: Mapped[dict | None] = mapped_column(JSON)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("collector_executions.id", ondelete="SET NULL"))
    evidence_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    target_host: Mapped[str] = mapped_column(String(255), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    data_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_file_path: Mapped[str | None] = mapped_column(String(500))
    provenance: Mapped[str] = mapped_column(String(20), default=Provenance.LIVE.value)
    blockchain_tx: Mapped[str | None] = mapped_column(String(100))
    blockchain_status: Mapped[str] = mapped_column(String(20), default=BlockchainStatus.NOT_SUBMITTED.value)
    collected_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    __table_args__ = (UniqueConstraint("investigation_id", "data_hash", name="unique_evidence_hash"),)


class EvidenceEmbedding(Base):
    __tablename__ = "evidence_embeddings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(String(36), ForeignKey("evidence_items.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding: Mapped[list] = mapped_column(JSON, nullable=False)
    text_content: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GraphNode(Base):
    __tablename__ = "graph_nodes"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)  # e.g. proc:4567@host
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # user|process|file|network|event
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    props: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("evidence_items.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GraphEdge(Base):
    __tablename__ = "graph_edges"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    src_node: Mapped[str] = mapped_column(String(80), ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False)
    dst_node: Mapped[str] = mapped_column(String(80), ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False)
    rel_type: Mapped[str] = mapped_column(String(40), nullable=False)  # LAUNCHED|SPAWNED|ACCESSED_FILE|MADE_CONNECTION|TRIGGERED_EVENT|LOADED_BY|RESOLVED_FROM
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("evidence_items.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("src_node", "dst_node", "rel_type", name="unique_edge"),)


class AiAnalysis(Base):
    __tablename__ = "ai_analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_type: Mapped[str] = mapped_column(String(30), nullable=False)
    engine: Mapped[str] = mapped_column(String(30), default="HEURISTIC")  # HEURISTIC | LLM_ANTHROPIC | LLM_OPENAI
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    model_used: Mapped[str | None] = mapped_column(String(50))
    input_evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InvestigationReport(Base):
    __tablename__ = "investigation_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    report_type: Mapped[str] = mapped_column(String(20), default=ReportType.FULL.value)
    status: Mapped[str] = mapped_column(String(20), default=ReportStatus.GENERATING.value)
    file_path: Mapped[str | None] = mapped_column(String(500))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    actor_email: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(20), default=AuditResult.SUCCESS.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class ForensicScript(Base):
    """Script Lab artefact: a versioned forensic function (PYFUNC) or FQL script."""

    __tablename__ = "forensic_scripts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    investigation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(10), default=ScriptLanguage.PYFUNC.value)
    template_id: Mapped[str | None] = mapped_column(String(60))
    code: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ScriptVersion(Base):
    __tablename__ = "script_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    script_id: Mapped[str] = mapped_column(String(36), ForeignKey("forensic_scripts.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("script_id", "version", name="unique_script_version"),)


class ScriptExecution(Base):
    __tablename__ = "script_executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    script_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("forensic_scripts.id", ondelete="SET NULL"), index=True)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), default=ScriptExecStatus.PENDING.value)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    console_log: Mapped[str | None] = mapped_column(Text)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    resource_usage: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("script_executions.id", ondelete="SET NULL"))
    analysis_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_analyses.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(10), default=FindingSource.SCRIPT.value)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    mitre_techniques: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(10), default=FindingStatus.OPEN.value)
    verified_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    __table_args__ = (
        CheckConstraint("severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')", name="ck_finding_severity"),
        CheckConstraint("status IN ('OPEN','VERIFIED','DISMISSED')", name="ck_finding_status"),
    )


class AnchorRecord(Base):
    """Append-only tamper-evident hash chain anchoring evidence hashes."""

    __tablename__ = "anchor_records"
    id: Mapped[int] = mapped_column(Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(String(36), ForeignKey("evidence_items.id", ondelete="CASCADE"), nullable=False, index=True)
    data_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    chain: Mapped[str] = mapped_column(String(20), default=AnchorChain.LOCAL_HASH_CHAIN.value)
    tx_hash: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    """Persistent async-job record (inline asyncio executor and Celery both write here)."""

    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # COLLECT | AI | REPORT
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    ref_id: Mapped[str | None] = mapped_column(String(36))  # fql_query_id / analysis_id / report_id
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.PENDING.value, index=True)
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    payload: Mapped[dict | None] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = [n for n in dir() if not n.startswith("_")]
