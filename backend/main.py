from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings, DEFAULT_TOOLBOXES
from app.db.database import init_db
from app.api.routes import router
from app.api.atlas import router as atlas_router
from app.models.models import AgentConfig
from app.db.database import async_session
from app.core.cli_executor import ToolboxManager, ToolboxConfig, ExecutorType, toolbox_manager
from app.tools.tool_registry import tool_registry
from app.models.models import AgentConfig, User, ToolState
from app.core.auth import hash_password
from sqlalchemy import select
import uuid
import os

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Based Network Penetration Testing Framework"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(atlas_router, prefix="/api/atlas")


@app.on_event("startup")
async def startup():
    await init_db()
    await seed_agent_configs()
    await seed_admin_user()
    await seed_tool_states()
    init_toolboxes()


TOOL_CATALOG = {
    "nmap": ("Network exploration, port scanning and service detection", "recon"),
    "masscan": ("Fast port scanner for large networks", "recon"),
    "nxc": ("NetExec - SMB/LDAP/WinRM/SSH enumeration and exploitation", "network"),
    "searchsploit": ("Search ExploitDB for public exploits", "exploit"),
    "adscan": ("Active Directory pentesting and auditing", "ad"),
    "adpeas": ("adPEAS - winPEAS for Active Directory (BloodHound + Certipy)", "ad"),
    "curl": ("HTTP request tool for web testing", "web"),
    "nuclei": ("Nuclei - template-based vulnerability scanner (9000+ templates)", "vuln"),
}


async def seed_tool_states():
    """Ensure every known tool has a state row (enabled by default)."""
    async with async_session() as db:
        for name, (desc, cat) in TOOL_CATALOG.items():
            result = await db.execute(select(ToolState).where(ToolState.tool_name == name))
            if not result.scalars().first():
                db.add(ToolState(
                    id=str(uuid.uuid4()),
                    tool_name=name,
                    enabled=True,
                    description=desc,
                    category=cat
                ))
        await db.commit()


async def seed_admin_user():
    """Create default admin account if no users exist."""
    async with async_session() as db:
        result = await db.execute(select(User))
        if result.scalars().first():
            return
        admin = User(
            id=str(uuid.uuid4()),
            username="admin",
            password_hash=hash_password("admin123"),
            role="admin"
        )
        db.add(admin)
        await db.commit()
        print("[startup] Seeded default admin: admin / admin123")


def init_toolboxes():
    """Initialize default toolbox configurations"""
    for tb_config in DEFAULT_TOOLBOXES:
        executor_type = ExecutorType(tb_config["executor_type"])
        config = ToolboxConfig(
            name=tb_config["name"],
            executor_type=executor_type,
            container_name=tb_config.get("container_name"),
            image=tb_config.get("image"),
            ssh_host=tb_config.get("ssh_host"),
            ssh_port=tb_config.get("ssh_port", 22),
            ssh_user=tb_config.get("ssh_user"),
            mcp_url=tb_config.get("mcp_url"),
            working_dir=tb_config.get("working_dir", "/workspace")
        )
        toolbox_manager.register_toolbox(config)


STATIC_DIR = os.environ.get("STATIC_FILES_DIR", "")

@app.get("/health")
async def health():
    return {"status": "healthy"}

if STATIC_DIR and os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="static-assets")

    @app.get("/")
    async def root():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api") or full_path == "health":
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        file_path = os.path.join(STATIC_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
else:
    @app.get("/")
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running"
        }


async def seed_agent_configs():
    async with async_session() as db:
        result = await db.execute(select(AgentConfig))
        if result.scalars().first():
            return

        default_configs = [
            {
                "agent_type": "recon",
                "system_prompt": """You are a reconnaissance agent in a penetration testing framework.

Your role is to gather information about the target scope using CLI tools.

You have access to the following tools via CLI:
- nmap: Port scanning and service detection
- subfinder: Subdomain enumeration
- httpx: HTTP probing
- whatweb: Technology fingerprinting

Available commands:
- Use self.run_command("command") to execute CLI commands
- Use self.use_tool("tool_name", {args}) to use registered tools
- Use self.scan_target(target, scan_type) for quick scans
- Use self.recon_target(target) for full reconnaissance

Example workflow:
1. First, enumerate subdomains: subfinder -d example.com
2. Probe for live hosts: httpx -l subdomains.txt
3. Scan for open ports: nmap -sV target.com
4. Fingerprint technologies: whatweb target.com

Output structured JSON with:
- Discovered hosts and IPs
- Open ports and services
- Technology stack information
- Subdomains found
- Potential attack surfaces"""
            },
            {
                "agent_type": "scanner",
                "system_prompt": """You are a vulnerability scanning agent in a penetration testing framework.

Your role is to scan discovered assets for vulnerabilities using CLI tools.

You have access to the following tools via CLI:
- nuclei: Template-based vulnerability scanning
- sqlmap: SQL injection testing
- ffuf: Directory and file fuzzing

Available commands:
- Use self.run_command("command") to execute CLI commands
- Use self.use_tool("tool_name", {args}) to use registered tools

Example workflow:
1. Run nuclei templates: nuclei -u target.com -severity high,critical
2. Test for SQLi: sqlmap -u "http://target.com/page?id=1" --batch
3. Fuzz directories: ffuf -u http://target.com/FUZZ -w wordlist.txt

Output structured JSON with:
- Vulnerabilities found (title, severity, CVSS)
- Affected endpoints
- Evidence collected
- Tool used for detection
- CWE/OWASP mappings"""
            },
            {
                "agent_type": "vuln_analyzer",
                "system_prompt": """You are a vulnerability analysis agent in a penetration testing framework.

Your role is to analyze and verify discovered vulnerabilities.

You can use CLI tools to verify findings:
- curl: Test HTTP requests
- nmap: Verify open services
- Custom scripts: Verify specific vulnerabilities

Available commands:
- Use self.run_command("command") to execute CLI commands
- Use self.use_tool("tool_name", {args}) to use registered tools

When analyzing vulnerabilities, output structured JSON with:
- Verified vulnerabilities with confidence levels
- CVSS scores and severity ratings
- CWE/OWASP mappings
- Attack chain possibilities
- Remediation recommendations"""
            },
            {
                "agent_type": "exploit",
                "system_prompt": """You are an exploitation agent in a penetration testing framework.

Your role is to safely exploit verified vulnerabilities. IMPORTANT: Only exploit with explicit authorization.

You have access to exploitation tools via CLI:
- sqlmap: SQL injection exploitation
- Custom exploit scripts
- Metasploit modules (if available)

Available commands:
- Use self.run_command("command") to execute CLI commands
- Use self.use_tool("tool_name", {args}) to use registered tools

SAFETY RULES:
- Never cause denial of service
- Never destroy data
- Stay within authorized scope
- Document everything for the report"""
            },
            {
                "agent_type": "report",
                "system_prompt": """You are a report generation agent in a penetration testing framework.

Your role is to generate professional penetration test reports.

You can use CLI tools to generate reports:
- pandoc: Convert markdown to PDF/HTML
- Custom templates

When generating reports, output structured JSON with:
- Executive summary
- Technical findings with severity levels
- Remediation recommendations
- Methodology description
- Scope and limitations
- Appendices with evidence"""
            }
        ]

        for config in default_configs:
            agent_config = AgentConfig(
                id=str(uuid.uuid4()),
                **config
            )
            db.add(agent_config)

        await db.commit()
