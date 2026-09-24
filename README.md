# NetActor

AI-Based Network Penetration Testing Framework with Toolbox Architecture

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend                           │
│  Dashboard │ New Scan │ Agents │ Settings (Toolboxes)       │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                  FastAPI Backend                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │            Agent Orchestrator                       │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │    │
│  │  │  Recon  │ │ Vuln    │ │Exploit  │ │Report   │    │    │
│  │  │  Agent  │ │ Agent   │ │ Agent   │ │ Agent   │    │    │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘    │    │
│  └───────┼───────────┼───────────┼───────────┼─────────┘    │
│          │           │           │           │              │
│  ┌───────▼───────────▼───────────▼───────────▼────────┐     │
│  │              CLI Executor / MCP Client             │     │
│  └───────────────────────┬────────────────────────────┘     │
└──────────────────────────┼──────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
┌─────────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐
│  Toolbox       │ │ Toolbox      │ │ SSH Remote   │
│  (Docker)      │ │ (Docker)     │ │ Machine      │
│  ┌──────────┐  │ │ ┌──────────┐ │ │ ┌──────────┐ │
│  │ nmap     │  │ │ │ sqlmap   │ │ │ │ custom   │ │
│  │ nuclei   │  │ │ │ ffuf     │ │ │ │ tools    │ │
│  │ subfinder│  │ │ │ curl     │ │ │ │          │ │
│  │ httpx    │  │ │ │          │ │ │ │          │ │
│  └──────────┘  │ │ └──────────┘ │ │ └──────────┘ │
│  MCP Server    │ │ MCP Server   │ │ CLI Execute  │
└────────────────┘ └──────────────┘ └──────────────┘
```

## Features

- **AI Agent Workflow**: Automated pentest pipeline with specialized agents
- **Toolbox Architecture**: Tools run in isolated Docker containers or remote SSH
- **MCP Protocol**: Agents communicate with toolboxes via Model Context Protocol
- **Customizable System Prompts**: Configure each agent's behavior
- **Full Traceability**: Every CLI command and tool call logged
- **Multiple Toolbox Support**: Docker, SSH, or local execution
- **OpenAI-Compatible**: Connect any compatible LLM

## Quick Start

### Docker (Recommended)

```bash
cd netactor

# Start all services (backend + toolbox + frontend)
docker-compose -f docker/docker-compose.yml up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Toolbox MCP: http://localhost:3001/mcp

### Manual Setup

#### Toolbox (Docker)

```bash
cd toolbox
docker build -t netactor-toolbox .
docker run -d --name netactor-toolbox -p 3001:3001 netactor-toolbox
```

#### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Configuration

### LLM Settings

Configure your AI model in Settings > LLM Configuration:

| Provider | Base URL | Model |
|----------|----------|-------|
| Ollama | http://localhost:11434/v1 | llama3.2, codellama |
| OpenAI | https://api.openai.com/v1 | gpt-4, gpt-4o |
| LM Studio | http://localhost:8080/v1 | Any loaded model |
| vLLM | http://localhost:1234/v1 | Any served model |

### Toolbox Configuration

Configure toolboxes in Settings > Toolboxes:

**Docker Toolbox:**
- Container Name: `netactor-toolbox`
- MCP URL: `http://localhost:3001/mcp`

**SSH Toolbox:**
- Host: `192.168.1.100`
- Port: `22`
- User: `root`
- Password or Key: Your credentials

### ATLAS External API

The ATLAS app can drive NetActor over HTTP with a single admin-managed API key
(Settings > ATLAS External API > Generate API Key). Every request authenticates
with the `X-API-Key` header. The key is stored in the database and survives
restarts; rotate or revoke it from the same card.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/atlas/ping` | Check the key (`200` / `401`) |
| `POST` | `/api/atlas/scan` | Launch a scan for one target -> `202` |
| `GET` | `/api/atlas/scan/{id}` | Status, finding counts, phase checks, score, error |
| `GET` | `/api/atlas/scan/{id}/findings?severity=high` | Findings (optional severity filter) |
| `GET` | `/api/atlas/scan/{id}/report` | Per-target JSON report with NVD-enriched CVE profiles |

`{id}` is either the `identifier` returned at launch or the `engagement_id`.

#### Launch a scan

```bash
curl -X POST http://localhost/api/atlas/scan \
  -H "X-API-Key: $ATLAS_KEY" \
  -H "Content-Type: application/json" \
  -d '{"host": "192.168.1.10", "title": "ATLAS weekly", "scan_mode": "quick", "report_level": "minimal", "cve_ids": ["CVE-2021-44228"]}'
```

```json
{
  "status": "started",
  "identifier": "atlas_2f9c...",
  "engagement_id": "c1b2...",
  "title": "ATLAS weekly",
  "target": "192.168.1.10",
  "scan_mode": "quick",
  "status_url": "/api/atlas/scan/c1b2...",
  "report_url": "/api/atlas/scan/atlas_2f9c.../report"
}
```

Body: `host` (IP, CIDR or hostname, required), `title`, `scan_mode`
(`quick` | `full` | `stealth`), `report_level` (`minimal` | `medium` |
`detailed`), `enable_exploit` (default `false`), `auto_approve` (default
`true`), `tools`, and optional `cve_ids` (when omitted, CVE ids are extracted
from the scan findings).

#### Per-target report

`GET /api/atlas/scan/{id}/report` returns the identifier generated when the scan
was launched, the scan title, and one item per CVE - a parent `title` (the
finding the CVE came from) with a child `profile` enriched from the NVD 2.0
API (`https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=`):

```json
{
  "identifier": "atlas_2f9c...",
  "engagement_id": "c1b2...",
  "title": "ATLAS weekly",
  "target": "192.168.1.10",
  "status": "completed",
  "generated_at": "2026-09-24T18:22:41.512000",
  "source": "NVD CVE 2.0",
  "findings_total": 12,
  "items": [
    {
      "title": "Apache Log4j2 remote code execution",
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
        "description": "...",
        "impact": {"confidentiality": "HIGH", "integrity": "HIGH", "availability": "HIGH"},
        "published": "2021-12-10T10:15:09.143",
        "vuln_status": "Analyzed",
        "source": "nvd"
      }
    }
  ]
}
```

`is_exploit` is true when the CVE is in the CISA Known Exploited Vulnerabilities
catalog. Anonymous NVD lookups are throttled (2 requests / 30 s) and cached
for 24 h; set an NVD API key in the same Settings card to raise the limit
(50 requests / 30 s). The report is cached per scan once the scan completes.

## Agent Types

1. **Recon Agent**: OSINT, DNS, port scanning, subdomain enumeration
2. **Scanner Agent**: Vulnerability scanning with nuclei, SQLi, XSS
3. **Vuln Analyzer**: Analyzes and verifies findings
4. **Exploit Agent**: Validates exploitability (optional)
5. **Report Agent**: Generates professional reports

## Built-in Tools

| Tool | Category | Description |
|------|----------|-------------|
| nmap | recon | Port scanning and service detection |
| nuclei | vuln | Template-based vulnerability scanning |
| sqlmap | exploit | SQL injection testing |
| ffuf | recon | Directory and file fuzzing |
| subfinder | recon | Subdomain enumeration |
| httpx | recon | HTTP probing |
| whatweb | recon | Technology fingerprinting |
| curl | general | HTTP requests |

## CLI Access

Agents can execute CLI commands via:

```python
# Run raw CLI command
result = await self.run_command("nmap -sV target.com")

# Use registered tool
result = await self.use_tool("nuclei_scan", {"target": "target.com", "severity": "high"})

# Call MCP tool
result = await self.mcp_call("pentest-tools", "nmap", {"target": "target.com"})
```

## License

MIT
