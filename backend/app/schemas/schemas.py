from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


# Auth schemas
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class UserUpdateRequest(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None


# Tool state schemas
class ToolStateResponse(BaseModel):
    tool_name: str
    enabled: bool
    description: Optional[str]
    category: Optional[str]

    class Config:
        from_attributes = True


class ToolStateUpdate(BaseModel):
    enabled: bool


# Engagement schemas
class EngagementCreate(BaseModel):
    name: str
    target_scope: List[dict]
    scan_mode: str = "quick"
    enable_exploit: bool = False
    report_level: str = "minimal"  # minimal, medium, detailed


class EngagementResponse(BaseModel):
    id: str
    name: str
    target_scope: List[dict]
    status: str
    scan_mode: str
    enable_exploit: bool
    report_level: str
    current_phase: Optional[str]
    phase_status: Optional[str]
    created_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# Target schemas
class TargetCreate(BaseModel):
    type: str
    value: str
    meta_info: Optional[dict] = None


class TargetResponse(BaseModel):
    id: str
    engagement_id: str
    type: str
    value: str
    meta_info: Optional[dict]

    class Config:
        from_attributes = True


# Finding schemas
class FindingResponse(BaseModel):
    id: str
    engagement_id: str
    title: str
    severity: str
    cvss_score: Optional[float]
    cwe_id: Optional[str]
    status: str
    description: Optional[str]
    proof: Optional[Any]
    tool_source: Optional[str]
    endpoint: Optional[str]
    remediation: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# Agent schemas
class AgentConfigUpdate(BaseModel):
    system_prompt: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    enabled: Optional[bool] = None
    allowed_tools: Optional[List[str]] = None


class AgentConfigResponse(BaseModel):
    id: str
    agent_type: str
    system_prompt: str
    max_tokens: int
    temperature: float
    enabled: bool
    allowed_tools: Optional[List[str]] = None

    class Config:
        from_attributes = True


class AgentSessionResponse(BaseModel):
    id: str
    engagement_id: str
    agent_type: str
    model_url: Optional[str]
    model_name: Optional[str]
    status: str
    tokens_used: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class AgentActionResponse(BaseModel):
    id: str
    session_id: str
    action_type: str
    tool_name: Optional[str]
    input_data: Optional[dict]
    output_data: Optional[dict]
    duration_ms: Optional[int]
    success: bool
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# LLM settings
class LLMSettingsUpdate(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


class LLMSettingsResponse(BaseModel):
    base_url: str
    api_key: str
    model: str


# Toolbox schemas
class ToolboxConfigCreate(BaseModel):
    name: str
    executor_type: str
    container_name: Optional[str] = None
    image: Optional[str] = None
    ssh_host: Optional[str] = None
    ssh_port: int = 22
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_key_path: Optional[str] = None
    mcp_url: Optional[str] = None
    working_dir: str = "/workspace"


class ToolboxConfigResponse(BaseModel):
    name: str
    executor_type: str
    container_name: Optional[str]
    image: Optional[str]
    ssh_host: Optional[str]
    ssh_port: int
    ssh_user: Optional[str]
    mcp_url: Optional[str]
    working_dir: str
    tool_count: int


class ToolboxTestRequest(BaseModel):
    name: str
    command: str = "echo 'Connection successful'"


class CLICommandRequest(BaseModel):
    toolbox: str
    command: str
    timeout: int = 60


# Phase control schemas
class PhaseApprovalRequest(BaseModel):
    approved: bool
    notes: Optional[str] = None


class ReportResponse(BaseModel):
    id: str
    engagement_id: str
    level: str
    content: str
    summary: Optional[str]
    docx_path: Optional[str]
    pdf_path: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReportRequest(BaseModel):
    level: str = "minimal"  # minimal, medium, detailed


# Asset inventory schemas
class AssetSnapshotResponse(BaseModel):
    id: str
    asset_id: str
    engagement_id: str
    port: Optional[int]
    protocol: Optional[str]
    service: Optional[str]
    version: Optional[str]
    product: Optional[str]
    extra_info: Optional[str]
    state: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class AssetResponse(BaseModel):
    id: str
    host: str
    asset_type: str
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]
    owner: Optional[str]
    notes: Optional[str]
    snapshots: List[AssetSnapshotResponse] = []

    class Config:
        from_attributes = True


class AssetUpdateRequest(BaseModel):
    notes: Optional[str] = None
    owner: Optional[str] = None


class AssetChangeResponse(BaseModel):
    host: str
    port: int
    service: str
    change_type: str  # new, removed, modified
    details: str
    engagement_id: str
