from typing import Dict, Any, List
from app.core.agent import BaseAgent
from app.core.llm import LLMClient


class ReconAgent(BaseAgent):
    def __init__(self, llm_client: LLMClient, **kwargs):
        super().__init__(agent_type="recon", llm_client=llm_client, **kwargs)

    def default_system_prompt(self) -> str:
        return """You are a network reconnaissance agent in a penetration testing framework.

Your goal is to discover all network services and their versions on the target. This is ASSET DISCOVERY, not web application testing.

RECONNAISSANCE METHODOLOGY:
1. Run nmap port scan to discover open ports and services
2. Run nmap service version detection (-sV) on discovered ports
3. Run nmap OS detection (-O) when possible
4. Identify software names and exact versions for every service
5. Use searchsploit to look up known CVEs and exploits for each discovered service version

IMPORTANT RULES:
- Focus ONLY on network services (SSH, HTTP, databases, management interfaces, etc.)
- Do NOT test web application endpoints (no LFI, SQLi, XSS, directory traversal)
- Do NOT use curl to test web vulnerabilities
- DO use curl ONLY to identify web server software and version from headers
- Extract the software name and version from nmap output for every service
- Search ExploitDB/searchsploit for each discovered software+version pair

OUTPUT FORMAT - When complete, provide:
{
  "analysis_complete": true,
  "summary": "Overview of discovered network services and versions",
  "findings": [
    {
      "title": "Service discovered: [software] [version] on port [port]",
      "severity": "info",
      "description": "Discovered [software] [version] running on port [port]/[protocol]",
      "evidence": "Raw nmap output showing the service"
    }
  ]
}

Be thorough with version detection — accurate version info is critical for CVE matching."""

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        targets = input_data.get("targets", [])
        scan_mode = input_data.get("scan_mode", "quick")
        tools = input_data.get("tools", [])

        target_list = ", ".join([
            t.get("value", str(t)) if isinstance(t, dict) else str(t)
            for t in targets
        ])

        task = f"""Perform network reconnaissance on the following targets:

Targets: {target_list}
Scan Mode: {scan_mode}

Your task:
1. Run nmap port scan (-sV -sC) on each target to discover open ports and services with versions
2. Identify the exact software name and version for every open service
3. Use curl -I ONLY to confirm web server version from HTTP headers (do NOT test web app vulnerabilities)
4. Use searchsploit to look up known CVEs for each discovered service/version
5. Compile all findings into a structured report

Start by scanning the first target with nmap to discover open ports and service versions."""

        result = await self.run_agent_loop(
            task=task,
            context={"targets": targets, "scan_mode": scan_mode, "tools": tools},
            max_iterations=15
        )

        return {
            "hosts": targets,
            "scan_mode": scan_mode,
            "tool_calls": result.get("tool_calls", []),
            "findings": result.get("findings", []),
            "summary": result.get("summary", ""),
            "analysis": result.get("summary", "")
        }
