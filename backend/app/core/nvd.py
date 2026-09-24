"""NVD CVE 2.0 client + profile parser used by the ATLAS report.

Fetches ``https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=...`` and
normalizes each CVE into the ATLAS profile schema:

    cve_id, is_exploit, cvss_v3_0 (+ vector/severity), attack_vector,
    attack_complexity, privileges_required, user_interaction, description,
    impact {confidentiality, integrity, availability}

``is_exploit`` is true when the CVE is present in the CISA Known Exploited
Vulnerabilities catalog (NVD field ``cisaExploitAdd``).  CVSS preference order
is v3.0, then v3.1, then v2.0; the version actually used is reported in
``cvss_version`` and ``cvss_v3_0`` is only filled for v3.x metrics.

Anonymous NVD callers are throttled to the published 2 requests / 30 s budget
and cached in memory for 24 h.  A free NVD API key (sent as the ``apiKey``
header) raises the budget to 50 requests / 30 s.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx

NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

_ANON_INTERVAL = 15.0
_KEYED_INTERVAL = 0.7
_CACHE_TTL = 24 * 3600

_cache: dict[str, tuple[float, dict]] = {}
_lock = asyncio.Lock()
_last_call = 0.0


class CVENotFound(Exception):
    """Unknown CVE id (NVD answered without a match)."""


class NVDBackendError(Exception):
    """NVD unreachable, rate limited, or returned something unusable."""


def parse_cve(cve: dict) -> dict[str, Any]:
    """Normalize one NVD ``cve`` object into the ATLAS profile schema."""
    cve_id = cve.get("id", "")

    description = next(
        (d.get("value", "") for d in cve.get("descriptions", []) if d.get("lang") == "en"),
        "",
    )

    metrics = cve.get("metrics") or {}
    version: Optional[str] = None
    chosen: Optional[dict] = None
    for key, ver in (
        ("cvssMetricV30", "3.0"),
        ("cvssMetricV31", "3.1"),
        ("cvssMetricV2", "2.0"),
    ):
        entries = metrics.get(key) or []
        if entries:
            # prefer the NVD "Primary" score over secondary/vendor duplicates
            chosen = next((e for e in entries if e.get("type") == "Primary"), entries[0])
            version = ver
            break

    score = vector = severity = None
    attack_vector = attack_complexity = None
    privileges_required = user_interaction = None
    impact = {"confidentiality": None, "integrity": None, "availability": None}
    if chosen:
        data = chosen.get("cvssData") or {}
        score = data.get("baseScore", chosen.get("baseScore"))
        vector = data.get("vectorString")
        severity = chosen.get("baseSeverity") or data.get("baseSeverity")
        attack_vector = data.get("attackVector")
        attack_complexity = data.get("attackComplexity")
        # CVSS v2 has no privilegesRequired / userInteraction concepts
        privileges_required = data.get("privilegesRequired")
        user_interaction = data.get("userInteraction")
        impact = {
            "confidentiality": data.get("confidentialityImpact"),
            "integrity": data.get("integrityImpact"),
            "availability": data.get("availabilityImpact"),
        }

    kev_added = cve.get("cisaExploitAdd")  # only present for CISA KEV entries
    return {
        "cve_id": cve_id,
        "is_exploit": bool(kev_added),
        "exploit_added": kev_added,
        "cvss_v3_0": score if version in ("3.0", "3.1") else None,
        "cvss_score": score,
        "cvss_version": version,
        "cvss_vector": vector,
        "cvss_severity": severity,
        "attack_vector": attack_vector,
        "attack_complexity": attack_complexity,
        "privileges_required": privileges_required,
        "user_interaction": user_interaction,
        "description": description,
        "impact": impact,
        "published": cve.get("published"),
        "last_modified": cve.get("lastModified"),
        "vuln_status": cve.get("vulnStatus"),
        "source": "nvd",
    }


async def fetch_cve(cve_id: str, api_key: str = "", timeout: float = 30.0) -> dict[str, Any]:
    """Fetch and normalize a single CVE, throttled and cached (24 h TTL)."""
    global _last_call

    cve_id = (cve_id or "").strip().upper()
    if not cve_id.startswith("CVE-") or len(cve_id) < 11:
        raise CVENotFound(f"not a CVE id: {cve_id!r}")

    hit = _cache.get(cve_id)
    if hit and time.monotonic() - hit[0] < _CACHE_TTL:
        return hit[1]

    async with _lock:
        interval = _KEYED_INTERVAL if api_key else _ANON_INTERVAL
        wait = interval - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = time.monotonic()

        headers = {"apiKey": api_key} if api_key else {}
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(NVD_URL, params={"cveId": cve_id}, headers=headers)
        except httpx.HTTPError as e:
            raise NVDBackendError(f"NVD unreachable: {e}") from e

        if resp.status_code == 404:
            raise CVENotFound(cve_id)
        if resp.status_code in (403, 429):
            raise NVDBackendError(
                f"NVD rate limited (HTTP {resp.status_code}); set an NVD API key or retry later"
            )
        if resp.status_code != 200:
            raise NVDBackendError(f"NVD returned HTTP {resp.status_code}")
        try:
            payload = resp.json()
        except ValueError as e:
            raise NVDBackendError("NVD returned invalid JSON") from e

    vulns = payload.get("vulnerabilities") or []
    if not vulns:
        raise CVENotFound(cve_id)

    profile = parse_cve(vulns[0].get("cve") or {})
    _cache[cve_id] = (time.monotonic(), profile)
    return profile
