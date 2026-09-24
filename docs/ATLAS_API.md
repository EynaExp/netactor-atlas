# ATLAS External API

The ATLAS app drives NetActor over HTTP: it launches a scan for one target,
polls its status, reads the findings, and pulls a per-target JSON report whose
CVE profiles are enriched from the NVD API.

- **Base URL:** `http(s)://<netactor-host>/api/atlas`
- **Auth:** a single admin-managed API key sent as the `X-API-Key` header
- **Interactive schema:** `http://<netactor-host>/docs` (Swagger UI, includes
  these endpoints) and `http://<netactor-host>/openapi.json`
- **JSON Schema for the report payload:** [`atlas-report.schema.json`](atlas-report.schema.json)
  (draft 2020-12 — use it to generate a parser/model or validate responses)
- **Manage the key:** NetActor UI -> Settings -> ATLAS External API
  (`GET/POST/DELETE /api/atlas/key`, JWT admin only)

> The key is stored server-side in the database and survives restarts. Rotate
> it with `POST /api/atlas/key` (the previous key stops working immediately) and
> disable the integration entirely with `DELETE /api/atlas/key`.

## Quick start

```bash
KEY=atlas_...

# 1. verify the key
curl -H "X-API-Key: $KEY" http://localhost/api/atlas/ping

# 2. launch a scan (returns 202 immediately)
curl -X POST http://localhost/api/atlas/scan \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"host":"192.168.1.10","title":"ATLAS weekly","scan_mode":"quick"}'
# -> {"status":"started","identifier":"atlas_2f9c...","engagement_id":"c1b2...",
#     "status_url":"/api/atlas/scan/c1b2...","report_url":"/api/atlas/scan/atlas_2f9c.../report", ...}

# 3. poll until status is completed | failed | stopped
curl -H "X-API-Key: $KEY" http://localhost/api/atlas/scan/atlas_2f9c...

# 4. fetch the per-target report
curl -H "X-API-Key: $KEY" http://localhost/api/atlas/scan/atlas_2f9c.../report
```

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/ping` | API key | Connectivity + key check |
| `POST` | `/scan` | API key | Launch a scan for one target (`202`) |
| `GET` | `/scan/{id}` | API key | Status, counts, phase checks, score, error, warnings |
| `GET` | `/scan/{id}/findings` | API key | Findings, optional `?severity=` filter |
| `GET` | `/scan/{id}/report` | API key | Per-target JSON report (NVD-enriched CVE profiles) |
| `GET` | `/key` | admin JWT | Current ATLAS key metadata |
| `POST` | `/key` | admin JWT | Generate/rotate the ATLAS key |
| `DELETE` | `/key` | admin JWT | Revoke the ATLAS key |
| `GET`/`POST`/`DELETE` | `/nvd-key` | admin JWT | Optional NVD API key (raises NVD rate limit) |

`{id}` accepts **either** the `identifier` returned at launch **or** the
NetActor `engagement_id` — they resolve to the same scan.

---

## `GET /ping`

Health/auth check. `200` when the key is valid.

```json
{ "ok": true, "service": "netactor", "feature": "atlas", "authenticated": true, "time": "2026-09-24T18:22:41.512000" }
```

## `POST /scan`

Launches one scan for one target and returns immediately (`202 Accepted`).
The scan runs in the background: poll `status_url` for progress.

### Request body

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `host` | string | **yes** | - | IP, CIDR or hostname. `127.0.0.1`, `10.0.0.0/24`, `scanme.example.com` |
| `title` | string | no | `ATLAS scan - <host>` | Scan title (max 255 chars) |
| `scan_mode` | string | no | `quick` | `quick` \| `full` \| `stealth` |
| `report_level` | string | no | `minimal` | `minimal` \| `medium` \| `detailed` |
| `enable_exploit` | bool | no | `false` | Exploitation phase (use only on authorized targets) |
| `auto_approve` | bool | no | `true` | Auto-approve phase transitions (no human in the loop) |
| `tools` | string[] | no | all enabled | Restrict the toolbox tools the agents may use |
| `cve_ids` | string[] | no | `[]` | Explicit CVE ids for the report; otherwise CVEs are extracted from the findings |

Unknown extra fields are ignored, so an existing ATLAS client built against an
older contract keeps working.

### `202` response

```json
{
  "status": "started",
  "identifier": "atlas_2f9c8d0a1b3e4f5a6b7c8d9e",
  "engagement_id": "c1b2a3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
  "title": "ATLAS weekly",
  "target": "192.168.1.10",
  "scan_mode": "quick",
  "status_url": "/api/atlas/scan/c1b2a3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
  "report_url": "/api/atlas/scan/atlas_2f9c8d0a1b3e4f5a6b7c8d9e/report"
}
```

`identifier` is generated at launch and never changes; use it as the ATLAS-side
handle for the scan. The scan is persisted like a UI-created scan (visible in
the NetActor UI, owner `atlas`).

### Validation errors (`400`)

| Message | Cause |
|---------|-------|
| `Invalid host` / `Invalid host: not an IP, CIDR or hostname` | malformed target |
| `scan_mode must be one of quick, full, stealth` | unknown mode |
| `report_level must be one of minimal, medium, detailed` | unknown level |
| `Invalid CVE id: '...'` | malformed entry in `cve_ids` |

A missing `host` is a standard `422` (schema validation).

## `GET /scan/{id}`

```json
{
  "identifier": "atlas_2f9c8d0a1b3e4f5a6b7c8d9e",
  "engagement_id": "c1b2a3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
  "status": "running",
  "title": "ATLAS weekly",
  "target": "192.168.1.10",
  "scan_mode": "quick",
  "current_phase": "scanner",
  "phase_status": "running",
  "score": null,
  "checks": { "total": 4, "passed": 1, "failed": 0, "degraded": 0, "pending": 3 },
  "summary": { "findings_total": 0, "by_severity": { "critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0 } },
  "error": null,
  "warnings": [],
  "created_at": "2026-09-24T18:22:41",
  "completed_at": null
}
```

### Fields

| Field | Notes |
|-------|-------|
| `status` | `created` \| `running` \| `stopping` \| `stopped` \| `completed` \| `failed` |
| `current_phase` / `phase_status` | `recon`, `scanner`, `vuln_analyzer`, `exploit` (if enabled), `report` |
| `score` | `100 - 15*critical - 8*high - 3*medium - 1*low`, clamped to `0..100`; **`null` unless `completed`** |
| `checks` | Phase-level view: `passed`, `degraded` (phase ran but the LLM was unreachable), `failed`, `pending` |
| `summary.by_severity` | Finding counts per severity |
| `error` | Failure reason (`null` while healthy) |
| `warnings` | Non-fatal problems, e.g. `LLM unavailable: <reason>` per degraded phase |

### Status semantics (honest reporting)

- `completed` means the pipeline ran. If the **LLM provider was unreachable in
  every agent phase**, the engagement is marked `failed` with `error` set and
  `score: null` — a scan never reports a clean 100 because nothing ran.
- A single degraded phase is reported through `checks.degraded` + `warnings`,
  and the run still completes.
- Phase tool calls that target anything outside the requested `host` are
  blocked by the scope guard.

## `GET /scan/{id}/findings`

Query: `severity` (optional, case-insensitive: `critical|high|medium|low|info`).

```json
{
  "identifier": "atlas_2f9c8d0a1b3e4f5a6b7c8d9e",
  "engagement_id": "c1b2a3d4-...",
  "status": "completed",
  "total": 2,
  "findings": [
    {
      "id": "d488b0ed-cbfd-4a44-8087-d56964351a4b",
      "title": "OpenSSH 9.6p1 (port 22)",
      "severity": "low",
      "cvss_score": null,
      "cwe_id": null,
      "status": "candidate",
      "description": "OpenSSH version 9.6p1 is the latest stable release ...",
      "endpoint": "172.18.0.1:22",
      "tool_source": "vuln_analyzer",
      "remediation": "Disable legacy ciphers ...",
      "cve_ids": [],
      "created_at": "2026-09-24T18:27:02.114"
    }
  ]
}
```

Findings are produced by the analysis agents, so `cvss_score` may be `null`
(when the model reports "not applicable") and `cve_ids` is a convenience field
listing CVE references found in the finding text.

## `GET /scan/{id}/report`

The per-target JSON report ATLAS consumes. Available at any time; while the
scan is still running it reports `"status": "running"` with zero items. Once
the scan completes, the generated report is **cached** on the scan record and
served from there (NVD is queried once per CVE per scan).

```json
{
  "format": 3,
  "identifier": "atlas_2f9c8d0a1b3e4f5a6b7c8d9e",
  "engagement_id": "c1b2a3d4-...",
  "title": "ATLAS weekly",
  "target": "192.168.1.10",
  "status": "completed",
  "generated_at": "2026-09-24T18:31:44.902",
  "source": "NVD CVE 2.0",
  "findings_total": 4,
  "warnings": [],
  "items": [
    {
      "title": "Apache Log4j 2.14.1 - CVE-2021-44228 (JNDI RCE)",
      "profile": {
        "cve_id": "CVE-2021-44228",
        "is_exploit": true,
        "exploit_added": "2021-12-10",
        "cvss_v3_0": 10.0,
        "cvss_score": 10.0,
        "cvss_version": "3.1",
        "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
        "cvss_severity": "CRITICAL",
        "attack_vector": "NETWORK",
        "attack_complexity": "LOW",
        "privileges_required": "NONE",
        "user_interaction": "NONE",
        "description": "Apache Log4j2 2.0-beta9 through 2.15.0 ...",
        "impact": { "confidentiality": "HIGH", "integrity": "HIGH", "availability": "HIGH" },
        "published": "2021-12-10T10:15:09.143",
        "last_modified": "2026-08-11T19:33:44.513",
        "vuln_status": "Analyzed",
        "source": "nvd"
      }
    }
  ]
}
```

### Structure

- `identifier` — generated when the scan was launched (the ATLAS handle).
- `items[].title` — **parent**: the finding (or the CVE id when the CVE was
  passed explicitly via `cve_ids`).
- `items[].profile` — **child**: the CVE profile.

### `profile` fields

| Field | Notes |
|-------|-------|
| `cve_id` | Normalized CVE id |
| `is_exploit` | `true` when the CVE is in the CISA Known Exploited Vulnerabilities catalog (`cisaExploitAdd`) |
| `exploit_added` | Date it was added to KEV |
| `cvss_v3_0` | Base score of the NVD CVSS v3.x metric (`null` if only a v2 score exists) |
| `cvss_score` / `cvss_version` / `cvss_vector` / `cvss_severity` | Selected metric (v3.0 -> v3.1 -> v2.0 preference) |
| `attack_vector` / `attack_complexity` | `NETWORK`/`ADJACENT`/`LOCAL`, `LOW`/`HIGH` |
| `privileges_required` / `user_interaction` | `NONE`/`LOW`/`HIGH` (NVD enum values) |
| `description` | English NVD description |
| `impact.confidentiality` / `.integrity` / `.availability` | `HIGH`/`MEDIUM`/`LOW`/`NONE` |
| `published` / `last_modified` / `vuln_status` | NVD metadata |
| `mapping_warning` | `null`, or a message when the CVE's NVD description does not mention the product named in the finding title (the agent paired the CVE with the wrong product) |
| `source` | `nvd` (or `error` + message if NVD could not be reached) |

### Where CVE ids come from

1. `cve_ids` passed to `POST /scan`, then
2. CVE references extracted from the scan findings (`CVE-YYYY-NNNN+`).

### CVE/product mismatches

Analysis agents are LLMs and sometimes attach a CVE to the wrong product. The
report cross-checks each finding title against the NVD description: if none of
the product words from the title appear in the advisory, the profile gets a
`mapping_warning` and the report collects it in the top-level `warnings`
array, e.g.

```json
"warnings": [
  { "cve_id": "CVE-2020-11652",
    "warning": "NVD description for CVE-2020-11652 does not mention nginx - the CVE may not match the product named in the finding; verify the mapping before acting on it" }
]
```

`format` is the report schema version; cached reports from older deployments
are regenerated when it changes.

### NVD rate limits

Profiles come from `https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=`.
Without an NVD API key, NVD allows 2 requests / 30 s, so a report covering many
CVEs is built ~15 s per additional CVE; responses are cached in memory for 24 h.
Set an NVD API key (`POST /api/atlas/nvd-key`, admin JWT) to raise the budget to
50 requests / 30 s.

## Admin endpoints (JWT, admin role)

```bash
# generate or rotate the ATLAS key (returns the full key once)
curl -X POST http://localhost/api/atlas/key -H "Authorization: Bearer $JWT"

# inspect
curl http://localhost/api/atlas/key -H "Authorization: Bearer $JWT"
# -> {"configured": true, "key": "atlas_...", "prefix": "atlas_abcde...", "header": "X-API-Key"}

# revoke
curl -X DELETE http://localhost/api/atlas/key -H "Authorization: Bearer $JWT"
# -> {"status": "revoked", "configured": false}
```

NVD key: `GET /api/atlas/nvd-key`, `POST /api/atlas/nvd-key` with
`{"api_key": "..."}`, `DELETE /api/atlas/nvd-key`.

## Errors

| Status | Meaning |
|--------|---------|
| `400` | Validation failed (host, `scan_mode`, `report_level`, `cve_ids`) |
| `401` | Missing or invalid `X-API-Key` (or missing/invalid JWT on admin routes) |
| `403` | JWT valid but not an admin (admin routes only) |
| `404` | Unknown `identifier` / `engagement_id` |
| `422` | Body failed schema validation (e.g. missing `host`) |
| `503` | ATLAS API not configured on the server (no key generated yet) |

## Client examples

### Python

```python
import time, requests

BASE = "http://localhost/api/atlas"
KEY = "atlas_..."
H = {"X-API-Key": KEY, "Content-Type": "application/json"}

r = requests.post(f"{BASE}/scan", headers=H,
                  json={"host": "192.168.1.10", "title": "ATLAS weekly",
                        "scan_mode": "quick", "cve_ids": ["CVE-2021-44228"]})
r.raise_for_status()
scan = r.json()
identifier = scan["identifier"]

while True:
    st = requests.get(f"{BASE}/scan/{identifier}", headers=H).json()
    if st["status"] in ("completed", "failed", "stopped"):
        break
    time.sleep(10)

if st["status"] != "completed":
    raise RuntimeError(f"scan {st['status']}: {st['error']} {st['warnings']}")

report = requests.get(f"{BASE}/scan/{identifier}/report", headers=H).json()
for item in report["items"]:
    p = item["profile"]
    print(p["cve_id"], p["cvss_v3_0"], "exploit" if p["is_exploit"] else "", item["title"])
```

### JavaScript

```js
const BASE = 'http://localhost/api/atlas';
const H = { 'X-API-Key': 'atlas_...', 'Content-Type': 'application/json' };

const { identifier } = await (await fetch(`${BASE}/scan`, {
  method: 'POST', headers: H,
  body: JSON.stringify({ host: '192.168.1.10', scan_mode: 'quick' }),
})).json();

let status;
for (;;) {
  status = await (await fetch(`${BASE}/scan/${identifier}`, { headers: H })).json();
  if (['completed', 'failed', 'stopped'].includes(status.status)) break;
  await new Promise(r => setTimeout(r, 10000));
}

const report = await (await fetch(`${BASE}/scan/${identifier}/report`, { headers: H })).json();
console.log(report.items.map(i => [i.profile.cve_id, i.profile.cvss_v3_0, i.profile.is_exploit]));
```

## Operational notes

- **Scans are asynchronous.** `POST /scan` never blocks; typical quick scans of
  a single host take a few minutes depending on the LLM provider.
- **No cancel endpoint for API keys.** Stopping a running scan requires a
  logged-in user (`POST /api/engagements/{id}/stop`); treat `stopped` as final.
- **One host per scan.** For a CIDR, launch one scan per target you want a
  per-target report for.
- **Persistence.** `identifier -> engagement` links, the cached report and any
  error text live in the `atlas_scans` table; the API key lives in `settings`.
- **Authorization.** Only scan hosts you are authorized to test. The agents
  enforce a scope guard, and `enable_exploit` is opt-in.
