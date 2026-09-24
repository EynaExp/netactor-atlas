from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from app.db.database import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


class ToolState(Base):
    __tablename__ = "tool_states"

    id = Column(String, primary_key=True, default=generate_uuid)
    tool_name = Column(String(100), unique=True, nullable=False)
    enabled = Column(Boolean, default=True)
    description = Column(String(500), nullable=True)
    category = Column(String(50), default="general")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), default="user")  # admin | user
    created_at = Column(DateTime, server_default=func.now())


class Engagement(Base):
    __tablename__ = "engagements"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    target_scope = Column(JSON, nullable=False)
    status = Column(String(50), default="created")
    owner = Column(String(100), nullable=True)  # username of creator
    scan_mode = Column(String(50), default="quick")
    enable_exploit = Column(Boolean, default=False)
    report_level = Column(String(50), default="minimal")
    current_phase = Column(String(50), default="recon")
    phase_status = Column(String(50), default="pending")
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)


class Target(Base):
    __tablename__ = "targets"

    id = Column(String, primary_key=True, default=generate_uuid)
    engagement_id = Column(String, nullable=False)
    type = Column(String(50), nullable=False)
    value = Column(Text, nullable=False)
    meta_info = Column(JSON, nullable=True)


class Finding(Base):
    __tablename__ = "findings"

    id = Column(String, primary_key=True, default=generate_uuid)
    engagement_id = Column(String, nullable=False)
    title = Column(String(500), nullable=False)
    severity = Column(String(50), nullable=False)
    cvss_score = Column(Float, nullable=True)
    cwe_id = Column(String(20), nullable=True)
    status = Column(String(50), default="candidate")
    description = Column(Text, nullable=True)
    proof = Column(JSON, nullable=True)
    tool_source = Column(String(100), nullable=True)
    endpoint = Column(Text, nullable=True)
    remediation = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    engagement_id = Column(String, nullable=False)
    agent_type = Column(String(100), nullable=False)
    model_url = Column(String(500), nullable=True)
    model_name = Column(String(100), nullable=True)
    status = Column(String(50), default="pending")
    tokens_used = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, nullable=False)
    action_type = Column(String(100), nullable=False)
    tool_name = Column(String(100), nullable=True)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class AgentConfig(Base):
    __tablename__ = "agent_configs"

    id = Column(String, primary_key=True, default=generate_uuid)
    agent_type = Column(String(100), unique=True, nullable=False)
    system_prompt = Column(Text, nullable=False)
    max_tokens = Column(Integer, default=4096)
    temperature = Column(Float, default=0.7)
    enabled = Column(Boolean, default=True)
    allowed_tools = Column(JSON, nullable=True)  # null = all tools allowed


class PhaseLog(Base):
    __tablename__ = "phase_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    engagement_id = Column(String, nullable=False)
    phase = Column(String(50), nullable=False)
    status = Column(String(50), default="running")
    message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=generate_uuid)
    engagement_id = Column(String, nullable=False)
    level = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    docx_path = Column(String, nullable=True)
    pdf_path = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Asset(Base):
    __tablename__ = "assets"

    id = Column(String, primary_key=True, default=generate_uuid)
    host = Column(String(255), nullable=False)
    asset_type = Column(String(50), nullable=False)  # host, service, web
    first_seen = Column(DateTime, server_default=func.now())
    last_seen = Column(DateTime, server_default=func.now())
    owner = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)


class AssetSnapshot(Base):
    __tablename__ = "asset_snapshots"

    id = Column(String, primary_key=True, default=generate_uuid)
    asset_id = Column(String, nullable=False)
    engagement_id = Column(String, nullable=False)
    port = Column(Integer, nullable=True)
    protocol = Column(String(20), nullable=True)
    service = Column(String(100), nullable=True)
    version = Column(String(200), nullable=True)
    product = Column(String(200), nullable=True)
    extra_info = Column(Text, nullable=True)
    state = Column(String(20), default="open")  # open, filtered, closed
    created_at = Column(DateTime, server_default=func.now())


class Setting(Base):
    """Generic key/value settings persisted in the DB (survives restarts)."""
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AtlasScan(Base):
    """ATLAS external API request linked to its NetActor engagement."""
    __tablename__ = "atlas_scans"

    identifier = Column(String(64), primary_key=True)           # ATLAS-facing id
    engagement_id = Column(String, nullable=False, index=True)   # NetActor scan id
    api_key_prefix = Column(String(16), nullable=True)
    request_info = Column(JSON, nullable=True)   # scan parameters (never secrets)
    report = Column(JSON, nullable=True)         # cached NVD-enriched report
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
