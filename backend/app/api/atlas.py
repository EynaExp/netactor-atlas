"""ATLAS external API.

Lets the ATLAS app drive NetActor with a single admin-managed API key
(``X-API-Key``): launch a scan for one target, poll its status, read the
findings, and fetch the per-target JSON report (identifier + title/profile
items, CVE data enriched from the NVD API).

Mounted under ``/api/atlas``:

    GET    /ping                 API key check
    POST   /scan                 launch a scan -> 202 {identifier, engagement_id, ...}
    GET    /scan/{id}            status / summary / score / error
    GET    /scan/{id}/findings   findings, optional ?severity=
    GET    /scan/{id}/report     per-target JSON report (NVD-enriched profiles)
    GET    /key                  admin JWT: current ATLAS key
    POST   /key                  admin JWT: generate / rotate the ATLAS key
    DELETE /key                  admin JWT: revoke the ATLAS key
    GET    /nvd-key              admin JWT: current NVD API key (optional)
    POST   /nvd-key              admin JWT: set the NVD API key
    DELETE /nvd-key              admin JWT: clear the NVD API key

``{id}`` accepts either the ATLAS ``identifier`` returned at launch or the
NetActor ``engagement_id``.

The scan request accepts (and ignores) the extra fields ATLAS already sends
for the Hardino contract (``os_type``, ``username``, ``password``, ...);
NetActor drives its agents from the target alone, so no credentials are
accepted or stored here.
"""
from __future__ import annotations

import json
import hashlib
import logging
import os
import re
import secrets
import uuid
from collections import Counter
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import broadcast_event, llm_settings, require_admin
from app.core.agent import STOP_REQUESTS
from app.core.cli_executor import toolbox_manager
from app.core.kv import delete_setting, get_setting, set_setting
from app.core.nvd import CVENotFound, NVDBackendError, fetch_cve
from app.core.orchestrator import AgentOrchestrator
from app.core.taxonomy import FALLBACK, RULES, TAXONOMY, classify
from app.db.database import async_session, get_db
from app.models.models import AtlasScan, Engagement, Finding, PhaseLog
from app.tools.tool_registry import tool_registry

router = APIRouter()
logger = logging.getLogger(__name__)

ATLAS_KEY_SETTING = "atlas_api_key"
NVD_KEY_SETTING = "nvd_api_key"

SCAN_MODES = ("quick", "full", "stealth")
REPORT_LEVELS = ("minimal", "medium", "detailed")
PHASES = ("recon", "scanner", "vuln_analyzer", "report")
PHASES_WITH_EXPLOIT = ("recon", "scanner", "vuln_analyzer", "exploit", "report")

# Same weighting as the assessment score: critical 15, high 8, medium 3, low 1.
SEVERITY_WEIGHTS = {"critical": 15, "high": 8, "medium": 3, "low": 1}

HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
)
CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)

# Report format version — bump when the generated shape changes so cached
# reports from older deployments are regenerated instead of served stale.
REPORT_FORMAT = 4

# Fingerprint of the classification rules: editing them invalidates cached
# reports automatically instead of serving stale categories.
CLASSIFIER_VERSION = hashlib.sha256(repr(RULES).encode()).hexdigest()[:8]

# Words that never identify a product in a finding title.
_MAPPING_STOPWORDS = {
    "arbitrary", "remote", "local", "code", "execution", "command", "injection",
    "vulnerability", "vulnerable", "exploit", "exploitable", "disclosure",
    "bypass", "overflow", "elevation", "privilege", "escalation", "traversal",
    "directory", "path", "file", "read", "write", "auth", "authentication",
    "denial", "service", "buffer", "memory", "corruption", "pointer", "race",
    "condition", "the", "and", "for", "with", "via", "from", "older", "before",
    "after", "version", "versions", "upgrade", "patch", "security", "advisory",
    "issue", "software", "component", "server", "client", "port", "scan",
    "detected", "found", "known", "public", "multiple", "various", "allows",
    "user", "users", "request", "requests", "response", "application", "app",
}


def _product_claim(title: str) -> List[str]:
    """Best-effort product words from a finding title (for CVE cross-checks).

    Hyphenated product names are kept whole ("node-serialize") so the warning
    names the product the agent actually claimed.
    """
    text = CVE_RE.sub(" ", title or "")
    text = re.sub(r"[<>=~^|]+", " ", text)
    text = re.sub(r"\bv?\d+(?:\.\d+)+[a-z0-9]*\b", " ", text, flags=re.IGNORECASE)
    words = re.findall(r"[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+|[A-Za-z][A-Za-z0-9]{2,}", text)
    out: List[str] = []
    for word in words:
        wl = word.lower()
        if wl in _MAPPING_STOPWORDS or wl in out:
            continue
        out.append(wl)
    return out[:6]


def _mapping_warning(title: str, profile: dict) -> Optional[str]:
    """Flag a CVE/product mismatch.

    The analysis agents are LLMs and sometimes pair a CVE with the wrong
    product. The NVD description is ground truth, so when none of the product
    words from the finding title appear in it, the mapping is suspect and the
    report says so instead of silently presenting a confident wrong claim.
    """
    cve_id = (profile.get("cve_id") or "").upper()
    if not cve_id or title.strip().upper() == cve_id:
        return None  # title is just the requested CVE id — no product claimed
    description = (profile.get("description") or "").lower()
    if not description:
        return None
    claim = _product_claim(title)
    if not claim or any(word in description for word in claim):
        return None
    return (
        f"NVD description for {cve_id} does not mention "
        f"{', '.join(claim[:3])} - the CVE may not match the product named in "
        "the finding; verify the mapping before acting on it"
    )


# --- auth -------------------------------------------------------------------

async def require_atlas_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> str:
    """Authenticate an ATLAS caller against the stored API key."""
    stored = await get_setting(ATLAS_KEY_SETTING)
    if not stored:
        raise HTTPException(
            status_code=503, detail="ATLAS API is not configured (no API key)"
        )
    if not x_api_key or not secrets.compare_digest(x_api_key, stored):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
    return x_api_key


# --- helpers ----------------------------------------------------------------

def _classify_target(host: str) -> str:
    """Validate a target and return its NetActor target type ('ip'/'cidr'/'domain')."""
    import ipaddress

    host = host.strip()
    if not host or len(host) > 255 or " " in host:
        raise HTTPException(status_code=400, detail="Invalid host")
    try:
        ipaddress.ip_address(host)
        return "ip"
    except ValueError:
        pass
    if "/" in host:
        try:
            ipaddress.ip_network(host, strict=False)
            return "cidr"
        except ValueError:
            pass
    if HOSTNAME_RE.match(host):
        return "domain"
    raise HTTPException(status_code=400, detail="Invalid host: not an IP, CIDR or hostname")


def _score(counts: Counter) -> int:
    penalty = sum(SEVERITY_WEIGHTS.get(sev, 0) * n for sev, n in counts.items())
    return max(0, min(100, 100 - penalty))


def _finding_text(finding: Finding) -> str:
    parts = [finding.title, finding.description, finding.endpoint, finding.remediation]
    if finding.proof:
        parts.append(json.dumps(finding.proof, default=str))
    return " ".join(p for p in parts if p)


def _extract_cves(finding: Finding) -> List[str]:
    """CVE ids referenced by a finding, uppercased, deduped, order preserved."""
    out: List[str] = []
    for cve in CVE_RE.findall(_finding_text(finding)):
        cve = cve.upper()
        if cve not in out:
            out.append(cve)
    return out


async def _resolve_scan(db: AsyncSession, scan_id: str) -> tuple[AtlasScan, Engagement]:
    row = (
        await db.execute(select(AtlasScan).where(AtlasScan.identifier == scan_id))
    ).scalar_one_or_none()
    if not row:
        row = (
            await db.execute(select(AtlasScan).where(AtlasScan.engagement_id == scan_id))
        ).scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=404, detail="Scan not found (unknown identifier or engagement id)"
        )
    engagement = (
        await db.execute(select(Engagement).where(Engagement.id == row.engagement_id))
    ).scalar_one_or_none()
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return row, engagement


async def _scan_findings(db: AsyncSession, engagement_id: str) -> List[Finding]:
    result = await db.execute(
        select(Finding)
        .where(Finding.engagement_id == engagement_id)
        .order_by(Finding.created_at.desc())
    )
    return list(result.scalars().all())


def _target_of(engagement: Engagement) -> str:
    scope = engagement.target_scope or []
    if scope and isinstance(scope[0], dict):
        return str(scope[0].get("value") or scope[0].get("host") or scope[0].get("target") or "")
    return str(scope[0]) if scope else ""


# --- background scan --------------------------------------------------------

async def _run_scan(
    identifier: str,
    engagement_id: str,
    target_scope: List[dict],
    scan_mode: str,
    enable_exploit: bool,
    tools: Optional[List[str]],
    auto_approve: bool,
    report_level: str,
) -> None:
    """Run the engagement in the background and record the final status."""
    error = None
    final_status = "completed"
    async with async_session() as session:
        try:
            orchestrator = AgentOrchestrator(
                db=session,
                llm_settings=llm_settings,
                toolbox_manager=toolbox_manager,
                tool_registry=tool_registry,
            )
            orchestrator.set_progress_callback(broadcast_event)
            result = await orchestrator.run_engagement(
                engagement_id=engagement_id,
                targets=target_scope,
                scan_mode=scan_mode,
                enable_exploit=enable_exploit,
                tools=tools,
                auto_approve=auto_approve,
                report_level=report_level,
            )
            final_status = result.get("status") or "completed"
            if final_status == "stopped" or STOP_REQUESTS.get(engagement_id):
                final_status = "stopped"
                STOP_REQUESTS.pop(engagement_id, None)
            elif final_status == "failed":
                error = result.get("error") or "scan failed"
        except Exception as e:  # noqa: BLE001 - surfaced to ATLAS via status
            final_status = "failed"
            error = f"{type(e).__name__}: {e}"
            logger.exception("ATLAS scan %s failed", engagement_id)
            try:
                await broadcast_event(engagement_id, "error", {"error": error})
            except Exception:
                pass

        # The orchestrator can hit a DB error (e.g. a bad value from the LLM)
        # that leaves the session rolled back. Clear it before the final write,
        # and never let a status write failure hide the engagement forever.
        try:
            await session.rollback()
            completed_at = datetime.utcnow() if final_status == "completed" else None
            await session.execute(
                update(Engagement)
                .where(Engagement.id == engagement_id)
                .values(status=final_status, completed_at=completed_at)
            )
            await session.execute(
                update(AtlasScan)
                .where(AtlasScan.identifier == identifier)
                .values(error=error, updated_at=datetime.utcnow())
            )
            await session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Could not persist final status for ATLAS scan %s", engagement_id)


# --- schemas ----------------------------------------------------------------

class AtlasScanRequest(BaseModel):
    host: str = Field(..., description="Target IP, CIDR or hostname")
    title: Optional[str] = Field(None, description="Scan title (defaults to host)")
    scan_mode: str = Field("quick", description="quick | full | stealth")
    report_level: str = Field("minimal", description="minimal | medium | detailed")
    enable_exploit: bool = False
    auto_approve: bool = True
    tools: Optional[List[str]] = None
    cve_ids: Optional[List[str]] = Field(
        None, description="Optional explicit CVE ids; otherwise taken from findings"
    )


class NvdKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=10, max_length=200)


# --- public API (X-API-Key) -------------------------------------------------

@router.get("/ping")
async def atlas_ping(_key: str = Depends(require_atlas_key)):
    return {
        "ok": True,
        "service": "netactor",
        "feature": "atlas",
        "authenticated": True,
        "time": datetime.utcnow().isoformat(),
    }


@router.post("/scan")
async def atlas_scan(
    body: AtlasScanRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(require_atlas_key),
    db: AsyncSession = Depends(get_db),
):
    """Launch a scan for one target. Returns 202 with the poll/report URLs."""
    target_type = _classify_target(body.host)
    if body.scan_mode not in SCAN_MODES:
        raise HTTPException(
            status_code=400, detail=f"scan_mode must be one of {', '.join(SCAN_MODES)}"
        )
    if body.report_level not in REPORT_LEVELS:
        raise HTTPException(
            status_code=400, detail=f"report_level must be one of {', '.join(REPORT_LEVELS)}"
        )

    cve_ids: List[str] = []
    for raw in body.cve_ids or []:
        cve = (raw or "").strip().upper()
        if not re.fullmatch(r"CVE-\d{4}-\d{4,7}", cve):
            raise HTTPException(status_code=400, detail=f"Invalid CVE id: {raw!r}")
        if cve not in cve_ids:
            cve_ids.append(cve)

    engagement_id = str(uuid.uuid4())
    identifier = "atlas_" + uuid.uuid4().hex[:24]
    title = (body.title or f"ATLAS scan - {body.host.strip()}").strip()[:255]

    engagement = Engagement(
        id=engagement_id,
        name=title,
        target_scope=[{"type": target_type, "value": body.host.strip()}],
        owner="atlas",
        scan_mode=body.scan_mode,
        enable_exploit=body.enable_exploit,
        report_level=body.report_level,
        status="running",
        current_phase="recon",
        phase_status="running",
    )
    db.add(engagement)
    db.add(
        AtlasScan(
            identifier=identifier,
            engagement_id=engagement_id,
            api_key_prefix=hashlib.sha256(api_key.encode()).hexdigest()[:8],
            request_info={
                "host": body.host.strip(),
                "target_type": target_type,
                "scan_mode": body.scan_mode,
                "report_level": body.report_level,
                "enable_exploit": body.enable_exploit,
                "cve_ids": cve_ids,
            },
        )
    )
    await db.commit()

    background_tasks.add_task(
        _run_scan,
        identifier,
        engagement_id,
        engagement.target_scope,
        body.scan_mode,
        body.enable_exploit,
        body.tools,
        body.auto_approve,
        body.report_level,
    )

    return JSONResponse(
        status_code=202,
        content={
            "status": "started",
            "identifier": identifier,
            "engagement_id": engagement_id,
            "title": title,
            "target": body.host.strip(),
            "scan_mode": body.scan_mode,
            "status_url": f"/api/atlas/scan/{engagement_id}",
            "report_url": f"/api/atlas/scan/{identifier}/report",
        },
    )


@router.get("/scan/{scan_id}")
async def atlas_scan_status(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    _key: str = Depends(require_atlas_key),
):
    """Scan status, finding counts, phase checks, score and last error."""
    row, engagement = await _resolve_scan(db, scan_id)
    findings = await _scan_findings(db, engagement.id)
    counts = Counter((f.severity or "info").lower() for f in findings)

    phases = PHASES_WITH_EXPLOIT if engagement.enable_exploit else PHASES
    logs = (
        await db.execute(select(PhaseLog).where(PhaseLog.engagement_id == engagement.id))
    ).scalars().all()
    # A degraded phase also has a "completed" log (the phase loop itself ran to
    # the end), so bad phases must be subtracted from the passed set.
    degraded = [log for log in logs if (log.status or "").lower() == "degraded"]
    failed_logs = [log for log in logs if (log.status or "").lower() == "failed"]
    failed_phases = {log.phase for log in failed_logs} & set(phases)
    degraded_phases = ({log.phase for log in degraded} & set(phases)) - failed_phases
    passed = (
        {log.phase for log in logs if (log.status or "").lower() == "completed"} & set(phases)
    ) - failed_phases - degraded_phases
    failed = len(failed_phases)
    degraded_count = len(degraded_phases)

    score = None
    if engagement.status == "completed":
        score = _score(counts)

    warnings = [log.message for log in degraded if log.message]
    warnings += [log.message for log in failed_logs if log.message]
    if row.error:
        warnings.append(row.error)

    severity_summary = {
        sev: counts.get(sev, 0)
        for sev in ("critical", "high", "medium", "low", "info")
    }
    return {
        "identifier": row.identifier,
        "engagement_id": engagement.id,
        "status": engagement.status,
        "title": engagement.name,
        "target": _target_of(engagement),
        "scan_mode": engagement.scan_mode,
        "current_phase": engagement.current_phase,
        "phase_status": engagement.phase_status,
        "score": score,
        "checks": {
            "total": len(phases),
            "passed": len(passed),
            "failed": failed,
            "degraded": degraded_count,
            "pending": max(0, len(phases) - len(passed) - failed - degraded_count),
        },
        "summary": {
            "findings_total": len(findings),
            "by_severity": severity_summary,
        },
        "error": row.error,
        "warnings": warnings,
        "created_at": engagement.created_at,
        "completed_at": engagement.completed_at,
    }


@router.get("/scan/{scan_id}/findings")
async def atlas_scan_findings(
    scan_id: str,
    severity: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _key: str = Depends(require_atlas_key),
):
    """Findings for a scan, optionally filtered by severity.

    Every finding carries its taxonomy pair: ``category`` (parent) and
    ``subcategory`` (child).
    """
    row, engagement = await _resolve_scan(db, scan_id)
    findings = await _scan_findings(db, engagement.id)
    if severity:
        wanted = severity.strip().lower()
        findings = [f for f in findings if (f.severity or "").lower() == wanted]

    classified = []
    by_category: dict[str, int] = {}
    for f in findings:
        cls = classify(f.title, f.description, f.remediation)
        by_category[cls["parent"]] = by_category.get(cls["parent"], 0) + 1
        classified.append((f, _extract_cves(f), cls))

    return {
        "identifier": row.identifier,
        "engagement_id": engagement.id,
        "status": engagement.status,
        "total": len(findings),
        "by_category": by_category,
        "findings": [
            {
                "id": f.id,
                "title": f.title,
                "severity": f.severity,
                "cvss_score": f.cvss_score,
                "cwe_id": f.cwe_id,
                "status": f.status,
                "description": f.description,
                "endpoint": f.endpoint,
                "tool_source": f.tool_source,
                "remediation": f.remediation,
                "cve_ids": cve_list,
                # taxonomy: parent = title, child = profile
                "category": cls["parent"],
                "subcategory": cls["child"],
                "classification": {"method": cls["method"], "score": cls["score"]},
                "created_at": f.created_at,
            }
            for f, cve_list, cls in classified
        ],
    }


@router.get("/scan/{scan_id}/report")
async def atlas_scan_report(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    _key: str = Depends(require_atlas_key),
):
    """Per-target JSON report for ATLAS.

    Each item is a parent ``title`` — a risk category from the taxonomy — with
    a child ``profile`` carrying the matching taxonomy child and the NVD data:
    cve_id, is_exploit, CVSS v3.0 + vector, attack vector / complexity /
    privileges / user interaction, description and CIA impact.  Cached on the
    scan record once the engagement completes.
    """
    row, engagement = await _resolve_scan(db, scan_id)
    cached = row.report or {}
    if (cached.get("format") or 0) >= REPORT_FORMAT and cached.get("classifier") == CLASSIFIER_VERSION:
        return cached

    findings = await _scan_findings(db, engagement.id)

    # CVE ids: explicitly requested ones first, then any found in finding text
    cve_titles: dict[str, str] = {}
    for cve in (row.request_info or {}).get("cve_ids") or []:
        cve_titles.setdefault(cve, cve)
    for finding in findings:
        for cve in _extract_cves(finding):
            cve_titles.setdefault(cve, finding.title)

    # The finding each CVE came from, so the report keeps the original wording
    # next to the taxonomy classification.
    finding_by_title = {f.title: f for f in findings}

    nvd_key = await get_setting(NVD_KEY_SETTING) or os.environ.get("NVD_API_KEY", "")
    items = []
    warnings = []
    by_category: dict[str, int] = {}
    for cve, finding_title in cve_titles.items():
        try:
            profile = await fetch_cve(cve, api_key=nvd_key)
        except (CVENotFound, NVDBackendError) as e:
            profile = {"cve_id": cve, "source": "nvd", "error": str(e)}
        warning = _mapping_warning(finding_title, profile)
        profile["mapping_warning"] = warning
        if warning:
            warnings.append({"cve_id": cve, "warning": warning})

        finding = finding_by_title.get(finding_title)
        classification = classify(
            finding.title if finding else None,
            finding.description if finding else None,
            finding.remediation if finding else None,
            profile.get("description"),
        )
        by_category[classification["parent"]] = by_category.get(classification["parent"], 0) + 1

        profile["category"] = classification["child"]
        profile["finding_title"] = finding_title
        profile["classification"] = {
            "method": classification["method"],
            "score": classification["score"],
        }
        # title = taxonomy parent, profile = taxonomy child (+ CVE detail)
        items.append({"title": classification["parent"], "profile": profile})

    report = {
        "format": REPORT_FORMAT,
        "classifier": CLASSIFIER_VERSION,
        "identifier": row.identifier,
        "engagement_id": engagement.id,
        "title": engagement.name,
        "target": _target_of(engagement),
        "status": engagement.status,
        "generated_at": datetime.utcnow().isoformat(),
        "source": "NVD CVE 2.0",
        "findings_total": len(findings),
        "by_category": by_category,
        "warnings": warnings,
        "items": items,
    }
    if engagement.status == "completed":
        row.report = report
        await db.commit()
    return report


@router.get("/taxonomy")
async def atlas_taxonomy(_key: str = Depends(require_atlas_key)):
    """The risk taxonomy every vulnerability is classified into.

    Lets a client render the category tree (or validate the ``title`` /
    ``profile.category`` pair it receives) without hardcoding it.
    """
    return {
        "classifier": CLASSIFIER_VERSION,
        "fallback": {"parent": FALLBACK[0], "child": FALLBACK[1]},
        "parents": [
            {"parent": parent, "children": children}
            for parent, children in TAXONOMY.items()
        ],
    }


# --- admin key management (JWT, admin only) ---------------------------------

def _key_payload(key: Optional[str]) -> dict:
    return {
        "configured": bool(key),
        "key": key,
        "prefix": f"{key[:10]}..." if key else None,
        "header": "X-API-Key",
    }


@router.get("/key")
async def atlas_key_info(admin: dict = Depends(require_admin)):
    return _key_payload(await get_setting(ATLAS_KEY_SETTING))


@router.post("/key")
async def atlas_key_rotate(admin: dict = Depends(require_admin)):
    """Generate (or rotate) the ATLAS API key. The full key is returned once."""
    key = "atlas_" + secrets.token_urlsafe(32)
    await set_setting(ATLAS_KEY_SETTING, key)
    return _key_payload(key)


@router.delete("/key")
async def atlas_key_revoke(admin: dict = Depends(require_admin)):
    await delete_setting(ATLAS_KEY_SETTING)
    return {"status": "revoked", "configured": False}


@router.get("/nvd-key")
async def nvd_key_info(admin: dict = Depends(require_admin)):
    return _key_payload(await get_setting(NVD_KEY_SETTING))


@router.post("/nvd-key")
async def nvd_key_set(body: NvdKeyRequest, admin: dict = Depends(require_admin)):
    """Optional NVD API key - raises the NVD rate limit for report enrichment."""
    await set_setting(NVD_KEY_SETTING, body.api_key.strip())
    return {"status": "saved", "configured": True}


@router.delete("/nvd-key")
async def nvd_key_revoke(admin: dict = Depends(require_admin)):
    await delete_setting(NVD_KEY_SETTING)
    return {"status": "revoked", "configured": False}
