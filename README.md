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
