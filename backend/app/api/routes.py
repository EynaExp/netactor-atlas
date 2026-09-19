from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.database import get_db, async_session
from app.models.models import Engagement, Target, Finding, AgentSession, AgentAction, AgentConfig, PhaseLog, Report
from app.schemas.schemas import (
    EngagementCreate, EngagementResponse,
    TargetCreate, TargetResponse,
    FindingResponse,
    AgentConfigUpdate, AgentConfigResponse,
    AgentSessionResponse, AgentActionResponse,
    LLMSettingsUpdate, LLMSettingsResponse,
    ToolboxConfigCreate, ToolboxConfigResponse, ToolboxTestRequest,
    CLICommandRequest, PhaseApprovalRequest, ReportResponse,
    AssetResponse, AssetUpdateRequest
)
import os
from app.core.orchestrator import AgentOrchestrator
from app.core.agent import STOP_REQUESTS
from app.core.auth import (
    hash_password, verify_password, create_access_token, decode_token, oauth2_scheme
)
from fastapi import Header
from app.models.models import User, ToolState, AuditLog
from app.schemas.schemas import (
    LoginRequest, TokenResponse, UserResponse, UserCreateRequest, UserUpdateRequest,
    ToolStateResponse, ToolStateUpdate
)
from app.core.config import settings, DEFAULT_TOOLBOXES
from app.core.cli_executor import ToolboxManager, ToolboxConfig, ExecutorType, toolbox_manager
from app.tools.tool_registry import tool_registry
from typing import List, Optional, Dict
from datetime import datetime
import uuid
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

llm_settings = {
    "base_url": settings.LLM_BASE_URL,
    "api_key": settings.LLM_API_KEY,
    "model": settings.LLM_MODEL
}

ws_connections: Dict[str, List[WebSocket]] = {}


async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


async def require_admin(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# --- Auth endpoints ---
@router.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(user.username, user.role, user.id)
    await audit(db, user.username, "login", {})
    return TokenResponse(access_token=token, username=user.username, role=user.role)


@router.get("/auth/me", response_model=UserResponse)
async def me(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user["sub"]))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return u


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


@router.put("/auth/password")
async def change_own_password(body: PasswordChangeRequest, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user["sub"]))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(body.old_password, u.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    u.password_hash = hash_password(body.new_password)
    await audit(db, user["sub"], "password_change", {})
    return {"status": "changed"}


@router.get("/auth/users", response_model=List[UserResponse])
async def list_users(admin: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    return result.scalars().all()


@router.post("/auth/users", response_model=UserResponse)
async def create_user(body: UserCreateRequest, admin: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
    if body.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Role must be admin or user")
    u = User(id=str(uuid.uuid4()), username=body.username,
             password_hash=hash_password(body.password), role=body.role)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    await audit(db, admin.get("sub", "?"), "user_create", {"target": body.username, "role": body.role})
    return u


@router.put("/auth/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, body: UserUpdateRequest, admin: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if body.password:
        u.password_hash = hash_password(body.password)
    if body.role:
        if body.role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="Role must be admin or user")
        if u.username == "admin" and body.role != "admin":
            raise HTTPException(status_code=400, detail="Cannot demote default admin")
        u.role = body.role
    await db.commit()
    await db.refresh(u)
    await audit(db, admin.get("sub", "?"), "user_update", {"target": u.username, "role": u.role})
    return u


@router.delete("/auth/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if u.username == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete default admin")
    await db.delete(u)
    await db.commit()
    await audit(db, admin.get("sub", "?"), "user_delete", {"target": u.username})
    return {"status": "deleted"}


@router.websocket("/ws/{engagement_id}")
async def websocket_endpoint(websocket: WebSocket, engagement_id: str):
    await websocket.accept()
    if engagement_id not in ws_connections:
        ws_connections[engagement_id] = []
    ws_connections[engagement_id].append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_connections[engagement_id].remove(websocket)
        if not ws_connections[engagement_id]:
            del ws_connections[engagement_id]


async def audit(db: AsyncSession, username: str, action: str, details: dict = None):
    db.add(AuditLog(id=str(uuid.uuid4()), username=username, action=action, details=details or {}))
    await db.commit()


async def require_engagement_access(engagement_id: str, user: dict, db: AsyncSession) -> Engagement:
    result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    eng = result.scalar_one_or_none()
    if not eng:
        raise HTTPException(status_code=404, detail="Engagement not found")
    if user.get("role") != "admin" and eng.owner and eng.owner != user["sub"]:
        raise HTTPException(status_code=403, detail="Not your engagement")
    return eng


async def broadcast_global(event_type: str, data: dict):
    """Broadcast to all connected websockets."""
    message = json.dumps({"type": event_type, "data": data})
    for eid in list(ws_connections.keys()):
        await broadcast_event(eid, event_type, data)


async def broadcast_event(engagement_id: str, event_type: str, data: dict):
    if engagement_id in ws_connections:
        message = json.dumps({"type": event_type, "data": data})
        dead = []
        for ws in ws_connections[engagement_id]:
            try:
                await ws.send_text(message)
            except:
                dead.append(ws)
        for ws in dead:
            ws_connections[engagement_id].remove(ws)


# LLM Settings
@router.get("/settings/llm", response_model=LLMSettingsResponse)
async def get_llm_settings(admin: dict = Depends(require_admin)):
    return llm_settings


@router.put("/settings/llm", response_model=LLMSettingsResponse)
async def update_llm_settings(update: LLMSettingsUpdate, admin: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if update.base_url is not None:
        llm_settings["base_url"] = update.base_url
    if update.api_key is not None:
        llm_settings["api_key"] = update.api_key
    if update.model is not None:
        llm_settings["model"] = update.model
    await audit(db, admin.get("sub", "?"), "llm_settings_update",
                {k: (v[:6] + "..." if k == "api_key" and v else v) for k, v in update.model_dump(exclude_none=True).items()})
    return llm_settings


@router.post("/settings/llm/test")
async def test_llm_connection(admin: dict = Depends(require_admin)):
    import httpx
    base_url = llm_settings.get("base_url", "").rstrip("/")
    api_key = llm_settings.get("api_key", "")
    model = llm_settings.get("model", "")
    if not base_url or not api_key or not model:
        return {"success": False, "error": "Missing base_url, api_key, or model"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Reply only with: OK"},
                        {"role": "user", "content": "Reply with exactly: OK"}
                    ],
                    "max_tokens": 10,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                usage = data.get("usage", {})
                return {
                    "success": True,
                    "model": data.get("model", model),
                    "tokens_used": usage.get("total_tokens", 0),
                }
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Toolbox endpoints
@router.get("/toolboxes", response_model=List[ToolboxConfigResponse])
async def list_toolboxes(admin: dict = Depends(require_admin)):
    return tool_registry.list_toolboxes()


@router.post("/toolboxes", response_model=ToolboxConfigResponse)
async def add_toolbox(config: ToolboxConfigCreate, admin: dict = Depends(require_admin)):
    executor_type = ExecutorType(config.executor_type)
    toolbox_config = ToolboxConfig(
        name=config.name,
        executor_type=executor_type,
        container_name=config.container_name,
        image=config.image,
        ssh_host=config.ssh_host,
        ssh_port=config.ssh_port,
        ssh_user=config.ssh_user,
        ssh_password=config.ssh_password,
        ssh_key_path=config.ssh_key_path,
        mcp_url=config.mcp_url,
        working_dir=config.working_dir
    )
    toolbox_manager.register_toolbox(toolbox_config)
    tool_count = len([t for t in tool_registry.tools.values() if t.toolbox == config.name])
    return ToolboxConfigResponse(
        name=config.name,
        executor_type=config.executor_type,
        container_name=config.container_name,
        image=config.image,
        ssh_host=config.ssh_host,
        ssh_port=config.ssh_port,
        ssh_user=config.ssh_user,
        mcp_url=config.mcp_url,
        working_dir=config.working_dir,
        tool_count=tool_count
    )


@router.delete("/toolboxes/{name}")
async def delete_toolbox(name: str, admin: dict = Depends(require_admin)):
    if name in toolbox_manager.toolboxes:
        del toolbox_manager.toolboxes[name]
        if name in toolbox_manager.executors:
            await toolbox_manager.executors[name].close()
            del toolbox_manager.executors[name]
        if name in toolbox_manager.mcp_clients:
            del toolbox_manager.mcp_clients[name]
    return {"status": "deleted"}


@router.post("/toolboxes/test")
async def test_toolbox(request: ToolboxTestRequest, admin: dict = Depends(require_admin)):
    result = await toolbox_manager.execute_on_toolbox(request.name, request.command)
    return result


@router.get("/toolboxes/{name}/tools")
async def list_toolbox_tools(name: str, admin: dict = Depends(require_admin)):
    tools = [t for t in tool_registry.tools.values() if t.toolbox == name]
    return [{"name": t.name, "description": t.description, "category": t.category} for t in tools]


@router.post("/toolboxes/{name}/execute")
async def execute_on_toolbox(name: str, command: str, timeout: int = 60, admin: dict = Depends(require_admin)):
    result = await toolbox_manager.execute_on_toolbox(name, command, timeout)
    return result


# CLI
@router.post("/cli/execute")
async def execute_cli(request: CLICommandRequest, admin: dict = Depends(require_admin)):
    result = await toolbox_manager.execute_on_toolbox(request.toolbox, request.command, request.timeout)
    return result


# Tools
@router.get("/tools")
async def list_tools():
    return tool_registry.list_tools()


@router.get("/tools/states", response_model=List[ToolStateResponse])
async def get_tool_states(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ToolState).order_by(ToolState.tool_name))
    return result.scalars().all()


@router.put("/tools/states/{tool_name}", response_model=ToolStateResponse)
async def set_tool_state(tool_name: str, body: ToolStateUpdate, admin: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ToolState).where(ToolState.tool_name == tool_name))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    tool.enabled = body.enabled
    await db.commit()
    await db.refresh(tool)
    await audit(db, admin.get("sub", "?"), "tool_toggle", {"tool": tool_name, "enabled": body.enabled})
    await broadcast_global("tool_state_changed", {"tool": tool_name, "enabled": body.enabled})
    return tool


@router.post("/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, args: dict):
    result = await tool_registry.execute_tool(tool_name, args)
    return result


# Engagements
@router.post("/engagements", response_model=EngagementResponse)
async def create_engagement(data: EngagementCreate, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    engagement = Engagement(
        id=str(uuid.uuid4()),
        name=data.name,
        target_scope=data.target_scope,
        owner=user["sub"],
        scan_mode=data.scan_mode,
        enable_exploit=data.enable_exploit,
        report_level=data.report_level,
        status="created",
        current_phase="recon",
        phase_status="pending"
    )
    db.add(engagement)
    await db.commit()
    await db.refresh(engagement)
    return engagement


@router.get("/engagements", response_model=List[EngagementResponse])
async def list_engagements(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    query = select(Engagement).order_by(Engagement.created_at.desc())
    if user.get("role") != "admin":
        query = query.where(Engagement.owner == user["sub"])
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/engagements/{engagement_id}", response_model=EngagementResponse)
async def get_engagement(engagement_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await require_engagement_access(engagement_id, user, db)


@router.delete("/engagements/{engagement_id}")
async def delete_engagement(engagement_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    engagement = await require_engagement_access(engagement_id, user, db)
    await audit(db, user["sub"], "engagement_delete", {"id": engagement_id, "name": engagement.name})
    await db.delete(engagement)
    await db.commit()
    return {"status": "deleted"}


@router.post("/engagements/{engagement_id}/run")
async def run_engagement(
    engagement_id: str,
    background_tasks: BackgroundTasks,
    enable_exploit: Optional[bool] = None,
    auto_approve: bool = True,
    tools: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    engagement = result.scalar_one_or_none()
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")

    engagement.status = "running"
    if enable_exploit is not None:
        engagement.enable_exploit = enable_exploit
    effective_exploit = engagement.enable_exploit
    await db.commit()
    await audit(db, user["sub"], "scan_start", {"id": engagement_id, "name": engagement.name, "targets": engagement.target_scope})

    async def run_task():
        import sys
        print(f"[run_task] Starting engagement {engagement_id}", file=sys.stderr, flush=True)
        # Fresh DB session: the request-scoped session is closed when the response
        # returns, so background work must use its own session.
        from app.core.orchestrator import AgentOrchestrator
        async with async_session() as session:
            print(f"[run_task] DB session created", file=sys.stderr, flush=True)
            orchestrator = AgentOrchestrator(
                db=session,
                llm_settings=llm_settings,
                toolbox_manager=toolbox_manager,
                tool_registry=tool_registry
            )
            print(f"[run_task] Orchestrator created, llm={llm_settings}", file=sys.stderr, flush=True)
            orchestrator.set_progress_callback(broadcast_event)
            try:
                result = await orchestrator.run_engagement(
                    engagement_id=engagement_id,
                    targets=engagement.target_scope,
                    scan_mode=engagement.scan_mode,
                    enable_exploit=enable_exploit,
                    tools=tools,
                    auto_approve=auto_approve,
                    report_level=engagement.report_level
                )
                print(f"[run_task] Engagement completed: {result.get('status')}", file=sys.stderr, flush=True)
                final_status = "completed"
                completed_at = datetime.utcnow()
                if result.get("status") == "stopped":
                    final_status = "stopped"
                    completed_at = None
                elif STOP_REQUESTS.get(engagement_id):
                    final_status = "stopped"
                    completed_at = None
                    STOP_REQUESTS.pop(engagement_id, None)
                stmt = update(Engagement).where(Engagement.id == engagement_id).values(
                    status=final_status, completed_at=completed_at
                )
                await session.execute(stmt)
                await session.commit()
            except Exception as e:
                import sys
                print(f"[run_task] FAILED: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
                import traceback
                traceback.print_exc(file=sys.stderr)
                logger.exception(f"Engagement {engagement_id} failed")
                stmt = update(Engagement).where(Engagement.id == engagement_id).values(status="failed")
                await session.execute(stmt)
                await session.commit()
                await broadcast_event(engagement_id, "error", {"error": str(e)})

    background_tasks.add_task(run_task)
    return {"status": "started", "engagement_id": engagement_id}


class StopResponse(BaseModel):
    status: str


@router.post("/engagements/{engagement_id}/stop", response_model=StopResponse)
async def stop_engagement(engagement_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    eng = await require_engagement_access(engagement_id, user, db)
    if eng.status not in ("running",):
        raise HTTPException(status_code=400, detail="Engagement is not running")
    STOP_REQUESTS[engagement_id] = True
    eng.status = "stopping"
    await db.commit()
    await audit(db, user["sub"], "scan_stop", {"id": engagement_id})
    return {"status": "stopping"}


@router.post("/engagements/{engagement_id}/retry", response_model=StopResponse)
async def retry_engagement(
    engagement_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Reset a failed/stopped/completed engagement and run it again from the first phase."""
    eng = await require_engagement_access(engagement_id, user, db)
    if eng.status == "running":
        raise HTTPException(status_code=400, detail="Engagement is already running")
    STOP_REQUESTS.pop(engagement_id, None)
    eng.status = "running"
    eng.current_phase = "recon"
    eng.phase_status = "pending"
    await db.commit()
    await audit(db, user["sub"], "scan_retry", {"id": engagement_id})

    async def run_task():
        from app.core.orchestrator import AgentOrchestrator
        async with async_session() as session:
            orchestrator = AgentOrchestrator(
                db=session,
                llm_settings=llm_settings,
                toolbox_manager=toolbox_manager,
                tool_registry=tool_registry
            )
            orchestrator.set_progress_callback(broadcast_event)
            try:
                result = await orchestrator.run_engagement(
                    engagement_id=engagement_id,
                    targets=eng.target_scope,
                    scan_mode=eng.scan_mode,
                    enable_exploit=eng.enable_exploit,
                    auto_approve=True,
                    report_level=eng.report_level
                )
                final_status = "completed"
                completed_at = datetime.utcnow()
                if result.get("status") == "stopped":
                    final_status = "stopped"
                    completed_at = None
                elif STOP_REQUESTS.get(engagement_id):
                    final_status = "stopped"
                    completed_at = None
                    STOP_REQUESTS.pop(engagement_id, None)
                await session.execute(update(Engagement).where(Engagement.id == engagement_id).values(
                    status=final_status, completed_at=completed_at
                ))
                await session.commit()
            except Exception as e:
                logger.exception(f"Engagement {engagement_id} retry failed")
                await session.execute(update(Engagement).where(Engagement.id == engagement_id).values(status="failed"))
                await session.commit()
                await broadcast_event(engagement_id, "error", {"error": str(e)})

    background_tasks.add_task(run_task)
    return {"status": "started"}


@router.get("/engagements/{engagement_id}/reports/{report_id}/export")
async def export_report(engagement_id: str, report_id: str, format: str = "markdown", user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Download a report as Markdown, Word (.docx), or PDF."""
    eng = await require_engagement_access(engagement_id, user, db)
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.engagement_id == engagement_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if format == "docx":
        if not report.docx_path or not os.path.exists(report.docx_path):
            raise HTTPException(status_code=404, detail="Word document not available. Report may need to be regenerated.")
        from fastapi.responses import FileResponse
        filename = f"netactor-report-{eng.name.replace(' ', '-').lower()}.docx"
        return FileResponse(report.docx_path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=filename)

    if format == "pdf":
        if not report.pdf_path or not os.path.exists(report.pdf_path):
            raise HTTPException(status_code=404, detail="PDF not available. Report may need to be regenerated.")
        from fastapi.responses import FileResponse
        filename = f"netactor-report-{eng.name.replace(' ', '-').lower()}.pdf"
        return FileResponse(report.pdf_path, media_type="application/pdf", filename=filename)

    findings_result = await db.execute(
        select(Finding).where(Finding.engagement_id == engagement_id).order_by(Finding.created_at)
    )
    findings = findings_result.scalars().all()

    md = f"# {eng.name} — Penetration Test Report\n\n"
    md += f"**Target:** {', '.join(t.get('host') or t.get('value') or '' for t in (eng.target_scope or []))}\n\n"
    md += f"**Date:** {report.created_at}\n**Level:** {report.level}\n\n---\n\n"
    md += "## Executive Summary\n\n"
    md += (report.summary or "") + "\n\n---\n\n"
    md += "## Findings\n\n"
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "informational": 4}
    ordered = sorted(findings, key=lambda f: sev_order.get(f.severity.lower(), 5))
    for i, f in enumerate(ordered, 1):
        md += f"### {i}. [{f.severity.upper()}] {f.title}\n\n"
        if f.description:
            md += f"{f.description}\n\n"
        if f.remediation:
            md += f"**Remediation:** {f.remediation}\n\n"
        md += "\n"
    md += "---\n\n"
    md += (report.content or "") + "\n"
    filename = f"netactor-report-{eng.name.replace(' ', '-').lower()}.md"
    from fastapi import Response
    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/audit-logs")
async def get_audit_logs(limit: int = 50, admin: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 200))
    )
    return result.scalars().all()


@router.post("/engagements/{engagement_id}/approve/{phase}")
async def approve_phase(
    engagement_id: str,
    phase: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Engagement).where(Engagement.id == engagement_id))
    engagement = result.scalar_one_or_none()
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")

    orchestrator = AgentOrchestrator(
        db=db,
        llm_settings=llm_settings,
        toolbox_manager=toolbox_manager,
        tool_registry=tool_registry
    )
    orchestrator.approve_phase(engagement_id, phase)
    await broadcast_event(engagement_id, "phase_approved", {"phase": phase})
    return {"status": "approved", "phase": phase}


@router.get("/engagements/{engagement_id}/sessions", response_model=List[AgentSessionResponse])
async def get_engagement_sessions(engagement_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentSession)
        .where(AgentSession.engagement_id == engagement_id)
        .order_by(AgentSession.started_at)
    )
    return result.scalars().all()


OUTPUT_PREVIEW_LIMIT = 1500  # chars of tool/LLM output sent in list views


@router.get("/engagements/{engagement_id}/actions", response_model=List[AgentActionResponse])
async def get_engagement_actions(engagement_id: str, full: bool = False, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sessions = await db.execute(
        select(AgentSession).where(AgentSession.engagement_id == engagement_id)
    )
    session_ids = [s.id for s in sessions.scalars().all()]
    if not session_ids:
        return []
    result = await db.execute(
        select(AgentAction)
        .where(AgentAction.session_id.in_(session_ids))
        .order_by(AgentAction.created_at)
    )
    actions = result.scalars().all()
    if full:
        return actions
    # List mode: truncate bulky output payloads so polling doesn't flood the UI
    out = []
    for a in actions:
        if a.output_data and isinstance(a.output_data, dict):
            data = a.output_data
            content = data.get("content")
            if content and isinstance(content, str) and len(content) > OUTPUT_PREVIEW_LIMIT:
                data = dict(data)
                data["content"] = content[:OUTPUT_PREVIEW_LIMIT] + f"... [truncated, {len(content)} chars total]"
                data["_truncated"] = True
            a = AgentAction(
                id=a.id, session_id=a.session_id, action_type=a.action_type,
                tool_name=a.tool_name, input_data=a.input_data, output_data=data,
                duration_ms=a.duration_ms, success=a.success, created_at=a.created_at
            )
        out.append(a)
    return out


@router.get("/engagements/{engagement_id}/actions/{action_id}", response_model=AgentActionResponse)
async def get_action_detail(engagement_id: str, action_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentAction)
        .join(AgentSession, AgentAction.session_id == AgentSession.id)
        .where(AgentAction.id == action_id, AgentSession.engagement_id == engagement_id)
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@router.get("/engagements/{engagement_id}/findings", response_model=List[FindingResponse])
async def get_engagement_findings(engagement_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Finding)
        .where(Finding.engagement_id == engagement_id)
        .order_by(Finding.created_at.desc())
    )
    return result.scalars().all()


@router.get("/engagements/{engagement_id}/logs")
async def get_engagement_logs(engagement_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PhaseLog)
        .where(PhaseLog.engagement_id == engagement_id)
        .order_by(PhaseLog.created_at)
    )
    return result.scalars().all()


@router.get("/engagements/{engagement_id}/reports", response_model=List[ReportResponse])
async def get_engagement_reports(engagement_id: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Report)
        .where(Report.engagement_id == engagement_id)
        .order_by(Report.created_at.desc())
    )
    return result.scalars().all()


# Agent Configs
@router.get("/agents/configs", response_model=List[AgentConfigResponse])
async def get_agent_configs(admin: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentConfig))
    return result.scalars().all()


@router.get("/agents/configs/{agent_type}", response_model=AgentConfigResponse)
async def get_agent_config(agent_type: str, admin: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentConfig).where(AgentConfig.agent_type == agent_type))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Agent config not found")
    return config


@router.put("/agents/configs/{agent_type}", response_model=AgentConfigResponse)
async def update_agent_config(agent_type: str, update: AgentConfigUpdate, admin: dict = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Update agent config. allowed_tools=null resets to 'all tools allowed'."""
    result = await db.execute(select(AgentConfig).where(AgentConfig.agent_type == agent_type))
    config = result.scalar_one_or_none()

    if not config:
        config = AgentConfig(
            id=str(uuid.uuid4()),
            agent_type=agent_type,
            system_prompt=update.system_prompt or "",
            max_tokens=update.max_tokens or 4096,
            temperature=update.temperature or 0.7,
            enabled=update.enabled if update.enabled is not None else True,
            allowed_tools=update.allowed_tools
        )
        db.add(config)
    else:
        if update.system_prompt is not None:
            config.system_prompt = update.system_prompt
        if update.max_tokens is not None:
            config.max_tokens = update.max_tokens
        if update.temperature is not None:
            config.temperature = update.temperature
        if update.enabled is not None:
            config.enabled = update.enabled
        if "allowed_tools" in update.model_fields_set:
            config.allowed_tools = update.allowed_tools

    await db.commit()
    await db.refresh(config)
    return config


# ============ Asset Inventory ============

@router.get("/assets")
async def list_assets(
    host: Optional[str] = None,
    asset_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.models.models import Asset, AssetSnapshot
    query = select(Asset)
    if host:
        query = query.where(Asset.host.contains(host))
    if asset_type:
        query = query.where(Asset.asset_type == asset_type)
    query = query.order_by(Asset.last_seen.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    assets = result.scalars().all()

    asset_list = []
    for asset in assets:
        snap_result = await db.execute(
            select(AssetSnapshot)
            .where(AssetSnapshot.asset_id == asset.id)
            .order_by(AssetSnapshot.created_at.desc())
            .limit(10)
        )
        snapshots = snap_result.scalars().all()
        asset_list.append({
            "id": asset.id,
            "host": asset.host,
            "asset_type": asset.asset_type,
            "first_seen": asset.first_seen,
            "last_seen": asset.last_seen,
            "owner": asset.owner,
            "notes": asset.notes,
            "snapshots": [{
                "id": s.id,
                "asset_id": s.asset_id,
                "engagement_id": s.engagement_id,
                "port": s.port,
                "protocol": s.protocol,
                "service": s.service,
                "version": s.version,
                "product": s.product,
                "extra_info": s.extra_info,
                "state": s.state,
                "created_at": s.created_at
            } for s in snapshots]
        })
    return asset_list


@router.get("/assets/{asset_id}")
async def get_asset(
    asset_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.models.models import Asset, AssetSnapshot
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    snap_result = await db.execute(
        select(AssetSnapshot)
        .where(AssetSnapshot.asset_id == asset_id)
        .order_by(AssetSnapshot.created_at.desc())
    )
    snapshots = snap_result.scalars().all()

    return {
        "id": asset.id,
        "host": asset.host,
        "asset_type": asset.asset_type,
        "first_seen": asset.first_seen,
        "last_seen": asset.last_seen,
        "owner": asset.owner,
        "notes": asset.notes,
        "snapshots": [{
            "id": s.id,
            "asset_id": s.asset_id,
            "engagement_id": s.engagement_id,
            "port": s.port,
            "protocol": s.protocol,
            "service": s.service,
            "version": s.version,
            "product": s.product,
            "extra_info": s.extra_info,
            "state": s.state,
            "created_at": s.created_at
        } for s in snapshots]
    }


@router.put("/assets/{asset_id}")
async def update_asset(
    asset_id: str,
    update: AssetUpdateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.models.models import Asset
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if update.notes is not None:
        asset.notes = update.notes
    if update.owner is not None:
        asset.owner = update.owner

    await db.commit()
    await db.refresh(asset)
    return {"id": asset.id, "host": asset.host, "notes": asset.notes, "owner": asset.owner}


@router.get("/assets/changes/{engagement_id}")
async def get_asset_changes(
    engagement_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.models.models import Asset, AssetSnapshot
    from sqlalchemy import and_

    snap_result = await db.execute(
        select(AssetSnapshot)
        .where(AssetSnapshot.engagement_id == engagement_id)
        .order_by(AssetSnapshot.created_at.desc())
    )
    current_snaps = snap_result.scalars().all()

    changes = []
    for snap in current_snaps:
        asset_result = await db.execute(select(Asset).where(Asset.id == snap.asset_id))
        asset = asset_result.scalar_one_or_none()
        if not asset:
            continue

        prev_result = await db.execute(
            select(AssetSnapshot)
            .where(
                and_(
                    AssetSnapshot.asset_id == snap.asset_id,
                    AssetSnapshot.engagement_id != engagement_id
                )
            )
            .order_by(AssetSnapshot.created_at.desc())
            .limit(1)
        )
        prev_snap = prev_result.scalar_one_or_none()

        if not prev_snap:
            changes.append({
                "host": asset.host,
                "port": snap.port or 0,
                "service": snap.service or "unknown",
                "change_type": "new",
                "details": f"New service discovered: {snap.service or 'unknown'} on port {snap.port}",
                "engagement_id": engagement_id
            })
        else:
            fields_changed = []
            if snap.port != prev_snap.port:
                fields_changed.append(f"port: {prev_snap.port} -> {snap.port}")
            if snap.service != prev_snap.service:
                fields_changed.append(f"service: {prev_snap.service} -> {snap.service}")
            if snap.version != prev_snap.version:
                fields_changed.append(f"version: {prev_snap.version} -> {snap.version}")
            if snap.product != prev_snap.product:
                fields_changed.append(f"product: {prev_snap.product} -> {snap.product}")

            if fields_changed:
                changes.append({
                    "host": asset.host,
                    "port": snap.port or 0,
                    "service": snap.service or "unknown",
                    "change_type": "modified",
                    "details": "; ".join(fields_changed),
                    "engagement_id": engagement_id
                })

    prev_result = await db.execute(
        select(AssetSnapshot)
        .where(
            and_(
                AssetSnapshot.engagement_id != engagement_id,
                AssetSnapshot.asset_id.in_([s.asset_id for s in current_snaps]) if current_snaps else False
            )
        )
    )
    prev_snaps = prev_result.scalars().all()
    prev_asset_ids = set(s.asset_id for s in prev_snaps)
    current_asset_ids = set(s.asset_id for s in current_snaps)

    for asset_id in prev_asset_ids - current_asset_ids:
        asset_result = await db.execute(select(Asset).where(Asset.id == asset_id))
        asset = asset_result.scalar_one_or_none()
        if asset:
            changes.append({
                "host": asset.host,
                "port": 0,
                "service": "unknown",
                "change_type": "removed",
                "details": "Asset no longer discovered",
                "engagement_id": engagement_id
            })

    return changes


@router.post("/assets/save")
async def save_discovered_assets(
    engagement_id: str,
    assets_data: List[Dict],
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.models.models import Asset, AssetSnapshot

    saved = 0
    for item in assets_data:
        host = item.get("host", "")
        port = item.get("port")
        protocol = item.get("protocol", "tcp")
        service = item.get("service", "unknown")
        version = item.get("version", "")
        product = item.get("product", "")

        result = await db.execute(
            select(Asset).where(Asset.host == host)
        )
        asset = result.scalar_one_or_none()

        if not asset:
            asset = Asset(
                id=str(uuid.uuid4()),
                host=host,
                asset_type=item.get("asset_type", "host"),
                owner=user.get("sub")
            )
            db.add(asset)
            await db.flush()

        asset.last_seen = datetime.utcnow()

        snapshot = AssetSnapshot(
            id=str(uuid.uuid4()),
            asset_id=asset.id,
            engagement_id=engagement_id,
            port=port,
            protocol=protocol,
            service=service,
            version=version,
            product=product,
            extra_info=item.get("extra_info"),
            state=item.get("state", "open")
        )
        db.add(snapshot)
        saved += 1

    await db.commit()
    return {"saved": saved}
