from typing import Dict, Any, List, Optional
from app.core.llm import LLMClient
from app.core.agent import BaseAgent
from app.core.cli_executor import ToolboxManager, toolbox_manager
from app.core.config import settings
from app.tools.tool_registry import ToolRegistry, tool_registry
from app.agents.recon import ReconAgent
from app.agents.scanner import ScannerAgent
from app.agents.vuln_analyzer import VulnAnalyzerAgent
from app.agents.exploit import ExploitAgent
from app.agents.report import ReportAgent
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import AgentSession, AgentAction, Finding, PhaseLog, Report, ToolState
from datetime import datetime
import uuid
import json
import asyncio
import logging
import os
import subprocess

logger = logging.getLogger(__name__)

from app.core.agent import STOP_REQUESTS

PHASES = ["recon", "scanner", "vuln_analyzer", "report"]
PHASES_WITH_EXPLOIT = ["recon", "scanner", "vuln_analyzer", "exploit", "report"]


class AgentOrchestrator:
    def __init__(
        self,
        db: AsyncSession,
        llm_settings: Dict[str, str] = None,
        toolbox_manager: ToolboxManager = None,
        tool_registry: ToolRegistry = None
    ):
        self.db = db
        self.llm_settings = llm_settings or {}
        self.toolbox_manager = toolbox_manager or toolbox_manager
        self.tool_registry = tool_registry or tool_registry
        self.running_agents: Dict[str, BaseAgent] = {}
        self._progress_callback = None
        self._phase_events: Dict[str, asyncio.Event] = {}

    def set_progress_callback(self, callback):
        self._progress_callback = callback

    async def _emit_event(self, engagement_id: str, event_type: str, data: Dict):
        if self._progress_callback:
            await self._progress_callback(engagement_id, event_type, data)
        logger.info(f"[{engagement_id}] {event_type}: {json.dumps(data)[:200]}")

    async def _wait_for_approval(self, engagement_id: str, phase: str) -> bool:
        event = asyncio.Event()
        self._phase_events[f"{engagement_id}:{phase}"] = event
        await event.wait()
        return True

    def approve_phase(self, engagement_id: str, phase: str):
        key = f"{engagement_id}:{phase}"
        if key in self._phase_events:
            self._phase_events[key].set()
            del self._phase_events[key]

    def get_llm_client(self) -> LLMClient:
        return LLMClient(**self.llm_settings)

    async def get_enabled_tools(self) -> Optional[List[str]]:
        """Load enabled tools from DB. None means no restriction (all tools)."""
        from sqlalchemy import select
        result = await self.db.execute(select(ToolState))
        states = result.scalars().all()
        if not states:
            return None
        return [ts.tool_name for ts in states if ts.enabled]

    @staticmethod
    def _target_strings(targets: List[Dict]) -> List[str]:
        out = []
        for t in targets or []:
            if isinstance(t, dict):
                v = t.get("host") or t.get("value") or t.get("target")
                if v:
                    out.append(str(v))
            elif isinstance(t, str):
                out.append(t)
        return out

    def _effective_tools(self, config, enabled_tools: Optional[List[str]]) -> Optional[List[str]]:
        """Intersect global enabled tools with this agent's allowed_tools.
        Per-agent list applies only if the tool is also globally enabled."""
        agent_allowed = getattr(config, "allowed_tools", None) if config else None
        if agent_allowed is None:
            return enabled_tools
        eff = [t for t in agent_allowed if enabled_tools is None or t in enabled_tools]
        return eff

    async def get_agent_configs(self) -> Dict[str, Dict]:
        from sqlalchemy import select
        from app.models.models import AgentConfig
        result = await self.db.execute(select(AgentConfig))
        configs = {row.agent_type: row for row in result.scalars().all()}
        return configs

    async def run_engagement(
        self,
        engagement_id: str,
        targets: List[Dict],
        scan_mode: str = "quick",
        enable_exploit: bool = False,
        tools: List[str] = None,
        auto_approve: bool = False,
        report_level: str = None
    ) -> Dict[str, Any]:
        self.report_level = report_level or "medium"
        self._start_time = datetime.utcnow()
        llm = self.get_llm_client()
        configs = await self.get_agent_configs()
        enabled_tools = await self.get_enabled_tools()
        phases = PHASES_WITH_EXPLOIT if enable_exploit else PHASES

        workflow_results = {
            "engagement_id": engagement_id,
            "status": "running",
            "phases": {}
        }

        try:
            for phase in phases:
                if STOP_REQUESTS.get(engagement_id):
                    logger.info(f"Engagement {engagement_id}: stop requested before phase {phase}")
                    workflow_results["status"] = "stopped"
                    await self._update_engagement_phase(engagement_id, phase, "pending")
                    STOP_REQUESTS.pop(engagement_id, None)
                    break
                await self._update_engagement_phase(engagement_id, phase, "running")
                await self._emit_event(engagement_id, "phase_start", {
                    "phase": phase,
                    "message": f"Starting {phase} phase"
                })
                await self._log_phase(engagement_id, phase, "running", f"Starting {phase}")

                if phase == "recon":
                    result = await self._run_recon(llm, configs, engagement_id, targets, scan_mode, tools, enabled_tools)
                elif phase == "scanner":
                    result = await self._run_scanner(llm, configs, engagement_id, targets, workflow_results["phases"].get("recon", {}), tools, enabled_tools)
                elif phase == "vuln_analyzer":
                    result = await self._run_vuln_analyzer(llm, configs, engagement_id, workflow_results["phases"], enabled_tools, targets)
                elif phase == "exploit":
                    result = await self._run_exploit(llm, configs, engagement_id, targets, workflow_results["phases"], enabled_tools)
                elif phase == "report":
                    result = await self._run_report(llm, configs, engagement_id, workflow_results["phases"], enable_exploit, enabled_tools, targets, getattr(self, 'report_level', 'medium'))
                else:
                    result = {}

                workflow_results["phases"][phase] = result
                await self._update_engagement_phase(engagement_id, phase, "completed")
                await self._emit_event(engagement_id, "phase_complete", {
                    "phase": phase,
                    "result_summary": str(result)[:500]
                })
                await self._log_phase(engagement_id, phase, "completed", f"Completed {phase}")

                if phase in ("recon", "scanner"):
                    await self._save_assets(engagement_id, result)

                if not auto_approve and phase != "report":
                    await self._emit_event(engagement_id, "phase_approval_needed", {
                        "phase": phase,
                        "message": f"Phase {phase} complete. Awaiting approval to continue."
                    })
                    await self._wait_for_approval(engagement_id, phase)

            if workflow_results.get("status") != "stopped":
                await self._save_findings(engagement_id, workflow_results["phases"])
                await self._save_report(engagement_id, workflow_results["phases"])
                workflow_results["status"] = "completed"
                await self._update_engagement_phase(engagement_id, "report", "completed")

        except Exception as e:
            logger.exception(f"Engagement {engagement_id} failed")
            workflow_results["status"] = "failed"
            workflow_results["error"] = str(e)
            await self._emit_event(engagement_id, "error", {"error": str(e)})

        return workflow_results

    async def _run_recon(self, llm, configs, engagement_id, targets, scan_mode, tools, enabled_tools):
        session = await self._create_session(engagement_id, "recon")
        config = configs.get("recon")
        agent = ReconAgent(
            llm_client=llm,
            system_prompt=config.system_prompt if config else None,
            engagement_id=engagement_id,
            session_id=session.id,
            toolbox_manager=self.toolbox_manager,
            tool_registry=self.tool_registry,
            enabled_tools=self._effective_tools(config, enabled_tools),
            allowed_targets=self._target_strings(targets)
        )
        self.running_agents[session.id] = agent
        agent._progress_callback = lambda data: asyncio.create_task(
            self._emit_event(engagement_id, "agent_action", data)
        )

        result = await agent.execute({
            "targets": targets,
            "scan_mode": scan_mode,
            "tools": tools or []
        })
        await self._save_session(session, agent)
        del self.running_agents[session.id]
        return result

    async def _run_scanner(self, llm, configs, engagement_id, targets, recon_data, tools, enabled_tools):
        session = await self._create_session(engagement_id, "scanner")
        config = configs.get("scanner")
        agent = ScannerAgent(
            llm_client=llm,
            system_prompt=config.system_prompt if config else None,
            engagement_id=engagement_id,
            session_id=session.id,
            toolbox_manager=self.toolbox_manager,
            tool_registry=self.tool_registry,
            enabled_tools=self._effective_tools(config, enabled_tools),
            allowed_targets=self._target_strings(targets)
        )
        self.running_agents[session.id] = agent
        agent._progress_callback = lambda data: asyncio.create_task(
            self._emit_event(engagement_id, "agent_action", data)
        )

        result = await agent.execute({
            "recon_data": recon_data,
            "targets": targets,
            "tools": tools or []
        })
        await self._save_session(session, agent)
        del self.running_agents[session.id]
        return result

    async def _run_vuln_analyzer(self, llm, configs, engagement_id, phases, enabled_tools, targets):
        session = await self._create_session(engagement_id, "vuln_analyzer")
        config = configs.get("vuln_analyzer")
        agent = VulnAnalyzerAgent(
            llm_client=llm,
            system_prompt=config.system_prompt if config else None,
            engagement_id=engagement_id,
            session_id=session.id,
            toolbox_manager=self.toolbox_manager,
            tool_registry=self.tool_registry,
            enabled_tools=self._effective_tools(config, enabled_tools),
            allowed_targets=self._target_strings(targets)
        )
        self.running_agents[session.id] = agent
        agent._progress_callback = lambda data: asyncio.create_task(
            self._emit_event(engagement_id, "agent_action", data)
        )

        result = await agent.execute({
            "scan_results": phases.get("scanner", {}),
            "recon_data": phases.get("recon", {})
        })
        await self._save_session(session, agent)
        del self.running_agents[session.id]
        return result

    async def _run_exploit(self, llm, configs, engagement_id, targets, phases, enabled_tools):
        session = await self._create_session(engagement_id, "exploit")
        config = configs.get("exploit")
        agent = ExploitAgent(
            llm_client=llm,
            system_prompt=config.system_prompt if config else None,
            engagement_id=engagement_id,
            session_id=session.id,
            toolbox_manager=self.toolbox_manager,
            tool_registry=self.tool_registry,
            enabled_tools=self._effective_tools(config, enabled_tools),
            allowed_targets=self._target_strings(targets)
        )
        self.running_agents[session.id] = agent
        agent._progress_callback = lambda data: asyncio.create_task(
            self._emit_event(engagement_id, "agent_action", data)
        )

        vuln_data = phases.get("vuln_analyzer", {})
        result = await agent.execute({
            "vulnerabilities": vuln_data.get("verified_vulnerabilities", []),
            "targets": targets,
            "authorized": True
        })
        await self._save_session(session, agent)
        del self.running_agents[session.id]
        return result

    async def _run_report(self, llm, configs, engagement_id, phases, enable_exploit, enabled_tools, targets, report_level='medium'):
        session = await self._create_session(engagement_id, "report")
        config = configs.get("report")
        agent = ReportAgent(
            llm_client=llm,
            system_prompt=config.system_prompt if config else None,
            engagement_id=engagement_id,
            session_id=session.id,
            toolbox_manager=self.toolbox_manager,
            tool_registry=self.tool_registry,
            enabled_tools=self._effective_tools(config, enabled_tools),
            allowed_targets=self._target_strings(targets)
        )
        self.running_agents[session.id] = agent
        agent._progress_callback = lambda data: asyncio.create_task(
            self._emit_event(engagement_id, "agent_action", data)
        )

        elapsed = datetime.utcnow() - self._start_time
        minutes = int(elapsed.total_seconds() // 60)
        seconds = int(elapsed.total_seconds() % 60)
        duration_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

        result = await agent.execute({
            "findings": phases,
            "scan_data": phases,
            "engagement": {
                "id": engagement_id,
                "enable_exploit": enable_exploit,
                "target_scope": targets,
                "duration": duration_str,
            },
            "report_level": report_level
        })
        await self._save_session(session, agent)
        del self.running_agents[session.id]
        return result

    async def _create_session(self, engagement_id: str, agent_type: str) -> AgentSession:
        session = AgentSession(
            id=str(uuid.uuid4()),
            engagement_id=engagement_id,
            agent_type=agent_type,
            model_url=self.llm_settings.get("base_url"),
            model_name=self.llm_settings.get("model"),
            status="running",
            started_at=datetime.utcnow()
        )
        self.db.add(session)
        await self.db.commit()
        return session

    async def _save_session(self, session: AgentSession, agent: BaseAgent):
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        session.tokens_used = sum(
            a.get("output", {}).get("tokens_used", 0)
            for a in agent.actions
            if isinstance(a.get("output"), dict)
        )

        for action_data in agent.actions:
            action = AgentAction(
                id=action_data["id"],
                session_id=session.id,
                action_type=action_data["action_type"],
                tool_name=action_data.get("tool_name"),
                input_data=action_data.get("input"),
                output_data=action_data.get("output"),
                duration_ms=action_data.get("duration_ms"),
                success=action_data.get("success", True)
            )
            self.db.add(action)

        await self.db.commit()

    async def _update_engagement_phase(self, engagement_id: str, phase: str, status: str):
        from sqlalchemy import update
        from app.models.models import Engagement
        await self.db.execute(
            update(Engagement)
            .where(Engagement.id == engagement_id)
            .values(current_phase=phase, phase_status=status)
        )
        await self.db.commit()

    async def _log_phase(self, engagement_id: str, phase: str, status: str, message: str):
        log = PhaseLog(
            id=str(uuid.uuid4()),
            engagement_id=engagement_id,
            phase=phase,
            status=status,
            message=message
        )
        self.db.add(log)
        await self.db.commit()

    async def _save_assets(self, engagement_id: str, phase_result: Dict):
        from app.models.models import Asset, AssetSnapshot, AgentAction, AgentSession
        from sqlalchemy import select
        import re

        services = phase_result.get("discovered_services", [])
        if not services:
            services = phase_result.get("services", [])

        hosts = phase_result.get("discovered_hosts", [])
        if not hosts:
            hosts = phase_result.get("hosts", [])

        session_result = await self.db.execute(
            select(AgentSession).where(
                AgentSession.engagement_id == engagement_id,
                AgentSession.agent_type.in_(["recon", "scanner"])
            )
        )
        sessions = session_result.scalars().all()

        for session in sessions:
            action_result = await self.db.execute(
                select(AgentAction).where(
                    AgentAction.session_id == session.id,
                    AgentAction.tool_name.in_(["nmap", "masscan"])
                )
            )
            actions = action_result.scalars().all()

            for action in actions:
                output = action.output_data or {}
                nmap_text = ""

                if isinstance(output, dict):
                    content = output.get("content", [])
                    if content and isinstance(content, list):
                        text_part = content[0].get("text", "") if isinstance(content[0], dict) else ""
                        try:
                            inner = json.loads(text_part)
                            nmap_text = inner.get("stdout", text_part)
                        except:
                            nmap_text = text_part
                elif isinstance(output, str):
                    nmap_text = output

                if not nmap_text:
                    continue

                for line in nmap_text.split('\n'):
                    match = re.match(r'(\d+)/(tcp|udp)\s+(open|filtered)\s+(\S+)\s*(.*)', line)
                    if match:
                        port = int(match.group(1))
                        protocol = match.group(2)
                        state = match.group(3)
                        service = match.group(4)
                        version_info = match.group(5).strip()

                        host_addr = ""
                        for h in (hosts if isinstance(hosts, list) else []):
                            if isinstance(h, str):
                                host_addr = h
                                break
                            elif isinstance(h, dict):
                                host_addr = h.get("ip") or h.get("host") or h.get("address", "")
                                if host_addr:
                                    break

                        if not host_addr:
                            host_addr = "unknown"

                        services.append({
                            "host": host_addr,
                            "port": port,
                            "protocol": protocol,
                            "service": service,
                            "product": version_info,
                            "state": state
                        })

        saved = 0

        for host in hosts:
            if isinstance(host, str):
                host_addr = host
            elif isinstance(host, dict):
                host_addr = host.get("ip") or host.get("host") or host.get("address", "")
            else:
                continue

            if not host_addr:
                continue

            result = await self.db.execute(
                select(Asset).where(Asset.host == host_addr)
            )
            asset = result.scalar_one_or_none()

            if not asset:
                asset = Asset(
                    id=str(uuid.uuid4()),
                    host=host_addr,
                    asset_type="host"
                )
                self.db.add(asset)
                await self.db.flush()

            asset.last_seen = datetime.utcnow()
            saved += 1

        for svc in services:
            if isinstance(svc, str):
                continue
            if not isinstance(svc, dict):
                continue

            host_addr = svc.get("host") or svc.get("ip") or svc.get("address", "")
            port = svc.get("port") or svc.get("portid")
            if not host_addr or not port:
                continue

            try:
                port = int(port)
            except (ValueError, TypeError):
                continue

            result = await self.db.execute(
                select(Asset).where(Asset.host == host_addr)
            )
            asset = result.scalar_one_or_none()

            if not asset:
                asset = Asset(
                    id=str(uuid.uuid4()),
                    host=host_addr,
                    asset_type="service"
                )
                self.db.add(asset)
                await self.db.flush()

            asset.last_seen = datetime.utcnow()

            snapshot = AssetSnapshot(
                id=str(uuid.uuid4()),
                asset_id=asset.id,
                engagement_id=engagement_id,
                port=port,
                protocol=svc.get("protocol", "tcp"),
                service=svc.get("service") or svc.get("name", "unknown"),
                version=svc.get("version", ""),
                product=svc.get("product", ""),
                extra_info=svc.get("extra_info") or svc.get("extrainfo", ""),
                state=svc.get("state", "open")
            )
            self.db.add(snapshot)
            saved += 1

        if saved > 0:
            await self.db.commit()
            logger.info(f"Saved {saved} assets for engagement {engagement_id}")

    async def _save_findings(self, engagement_id: str, phases: Dict):
        vuln_data = phases.get("vuln_analyzer", {})
        findings = vuln_data.get("verified_vulnerabilities", [])
        if isinstance(findings, str):
            try:
                findings = json.loads(findings)
            except:
                findings = []

        seen_titles = set()

        def _norm_title(t):
            import re as _re
            return _re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()

        all_new = []

        def _queue(finding, title):
            key = _norm_title(title)
            if key and key in seen_titles:
                return
            seen_titles.add(key)
            all_new.append(finding)

        for vuln in findings:
            if isinstance(vuln, dict):
                finding = Finding(
                    id=str(uuid.uuid4()),
                    engagement_id=engagement_id,
                    title=vuln.get("title", "Unknown Vulnerability"),
                    severity=vuln.get("severity", "info"),
                    cvss_score=vuln.get("cvss_score"),
                    cwe_id=vuln.get("cwe_id"),
                    description=vuln.get("description"),
                    proof=vuln.get("proof") or vuln.get("evidence"),
                    tool_source=vuln.get("tool_source", "vuln_analyzer"),
                    endpoint=vuln.get("endpoint"),
                    remediation=vuln.get("remediation")
                )
                _queue(finding, vuln.get("title"))

        report_data = phases.get("report", {})
        report_findings = report_data.get("findings", [])
        for rf in report_findings:
            if isinstance(rf, dict) and rf.get("title"):
                finding = Finding(
                    id=str(uuid.uuid4()),
                    engagement_id=engagement_id,
                    title=rf.get("title", "Report Finding"),
                    severity=rf.get("severity", "info"),
                    description=rf.get("description"),
                    remediation=rf.get("remediation"),
                    tool_source="report_agent"
                )
                _queue(finding, rf.get("title"))

        for f in all_new:
            self.db.add(f)
        await self.db.commit()

    async def _save_report(self, engagement_id: str, phases: Dict):
        report_data = phases.get("report", {})
        if not report_data:
            return
        content = report_data.get("generated_content") or report_data.get("content") or report_data.get("summary", "")
        summary = report_data.get("executive_summary") or report_data.get("summary", "")
        if not content:
            return

        report_dir = settings.REPORT_DIR
        os.makedirs(report_dir, exist_ok=True)

        base_name = f"report_{engagement_id}"
        md_path = os.path.join(report_dir, f"{base_name}.md")
        docx_path = None
        pdf_path = None

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)

        container = settings.TOOLBOX_CONTAINER

        def _local_convert_docx():
            """Fallback: markdown -> docx via python (no docker needed)."""
            try:
                import markdown as mdlib
                from docx import Document
                from htmldocx import HtmlToDocx
                md_text = open(md_path, encoding="utf-8").read()
                html = mdlib.markdown(md_text, extensions=["tables", "fenced_code"])
                doc = Document()
                HtmlToDocx().add_html_to_document(html, doc)
                out = md_path.replace(".md", ".docx")
                doc.save(out)
                return out
            except Exception as e:
                logger.warning(f"Local DOCX conversion failed: {e}")
                return None

        def _local_convert_pdf():
            """Fallback: markdown -> pdf via weasyprint, then xhtml2pdf (no docker needed)."""
            import markdown as mdlib
            md_text = open(md_path, encoding="utf-8").read()
            html = mdlib.markdown(md_text, extensions=["tables", "fenced_code"])
            styled = (
                '<html><head><meta charset="utf-8"><style>'
                'body{font-family:Arial,sans-serif;margin:40px;font-size:11pt}'
                'h1,h2,h3{color:#1a3a5c}table{border-collapse:collapse;width:100%}'
                'td,th{border:1px solid #999;padding:6px}code{background:#f4f4f4;padding:2px}'
                'pre{background:#f4f4f4;padding:10px;overflow-x:auto}'
                '</style></head><body>' + html + '</body></html>'
            )
            out = md_path.replace(".md", ".pdf")
            try:
                from weasyprint import HTML
                HTML(string=styled).write_pdf(out)
                return out
            except Exception as e:
                logger.warning(f"WeasyPrint failed, trying xhtml2pdf: {e}")
            try:
                from xhtml2pdf import pisa
                with open(out, "wb") as pdf_file:
                    pisa.CreatePDF(styled, dest=pdf_file, encoding="utf-8")
                return out
            except Exception as e:
                logger.warning(f"Local PDF conversion failed: {e}")
                return None

        try:
            result = subprocess.run(
                ["docker", "exec", container,
                 "genoffice", "create", "--type", "docx",
                 "--from", f"/reports/{base_name}.md",
                 "--out", f"/reports/{base_name}.docx"],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                docx_path = md_path.replace(".md", ".docx")
                logger.info(f"Generated DOCX via genoffice: {docx_path}")
            else:
                logger.warning(f"DOCX generation failed ({result.stderr}), trying local conversion")
                docx_path = _local_convert_docx()
        except Exception as e:
            logger.warning(f"DOCX generation error ({e}), trying local conversion")
            docx_path = _local_convert_docx()

        try:
            env = os.environ.copy()
            env["ELECTRON_DISABLE_SANDBOX"] = "1"
            result = subprocess.run(
                ["docker", "exec", "-e", "ELECTRON_DISABLE_SANDBOX=1", container,
                 "xvfb-run", "genoffice", "convert",
                 f"/reports/{base_name}.md", "--to", "pdf",
                 "--out", f"/reports/{base_name}.pdf"],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                pdf_path = md_path.replace(".md", ".pdf")
                logger.info(f"Generated PDF via genoffice: {pdf_path}")
            else:
                logger.warning(f"PDF generation failed ({result.stderr}), trying local conversion")
                pdf_path = _local_convert_pdf()
        except Exception as e:
            logger.warning(f"PDF generation error ({e}), trying local conversion")
            pdf_path = _local_convert_pdf()

        report = Report(
            id=str(uuid.uuid4()),
            engagement_id=engagement_id,
            level=getattr(self, "report_level", "medium"),
            content=content if isinstance(content, str) else json.dumps(content),
            summary=summary if isinstance(summary, str) else json.dumps(summary),
            docx_path=docx_path,
            pdf_path=pdf_path
        )
        self.db.add(report)
        await self.db.commit()

    def stop_agent(self, session_id: str) -> bool:
        if session_id in self.running_agents:
            del self.running_agents[session_id]
            return True
        return False
