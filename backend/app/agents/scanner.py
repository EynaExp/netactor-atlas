from typing import Dict, Any, List
from app.core.agent import BaseAgent
from app.core.llm import LLMClient


class ScannerAgent(BaseAgent):
    def __init__(self, llm_client: LLMClient, **kwargs):
        super().__init__(agent_type="scanner", llm_client=llm_client, **kwargs)

    def default_system_prompt(self) -> str:
        return """You are a network vulnerability scanning agent in a penetration testing framework.

Your goal is to find known vulnerabilities (CVEs) for discovered network services. This is NETWORK VULNERABILITY ASSESSMENT, not web application testing.

SCANNING METHODOLOGY:
1. Review the recon data to identify all services, software names, and versions
2. Use searchsploit to find known exploits/CVEs for each discovered software version
3. Use nmap with vulnerability scripts (--script vuln) on specific services to detect known CVEs
4. Check for outdated software versions with publicly known vulnerabilities
5. Document all CVEs found with their CVE IDs

IMPORTANT RULES:
- Focus ONLY on network-level vulnerabilities and known CVEs
- Do NOT test web application endpoints (no LFI, SQLi, XSS, directory traversal, etc.)
- DO use searchsploit extensively to match service versions to known CVEs
- DO use nmap --script vuln to detect network-level vulnerabilities
- Match exact software versions from recon to CVE databases
- Report each finding with its CVE ID if available

OUTPUT FORMAT - When complete, provide:
{
  "analysis_complete": true,
  "summary": "Overview of network vulnerability scan findings",
  "findings": [
    {
      "title": "[Software] [Version] - [CVE ID or vulnerability name]",
      "severity": "info|low|medium|high|critical",
      "description": "Description of the vulnerability and affected service",
      "evidence": "searchsploit output, nmap script output, or other proof"
    }
  ]
}

Be thorough but only report vulnerabilities backed by CVE data or ExploitDB entries."""

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        recon_data = input_data.get("recon_data", {})
        targets = input_data.get("targets", [])
        tools = input_data.get("tools", [])

        target_list = ", ".join([
            t.get("value", str(t)) if isinstance(t, dict) else str(t)
            for t in targets
        ])

        task = f"""Scan the following targets for network vulnerabilities and known CVEs:

Targets: {target_list}
Recon Data: {self._format_recon_data(recon_data)}

Your task:
1. Review the recon data to identify all services, software names, and versions
2. Use searchsploit to find known CVEs for each discovered software+version pair
3. Use nmap --script vuln on discovered services to detect known vulnerabilities
4. Focus on network-level vulnerabilities only (not web app issues)
5. Compile all CVEs found with evidence

Start by searching for exploits/CVEs for the discovered software versions."""

        result = await self.run_agent_loop(
            task=task,
            context={"recon_data": recon_data, "targets": targets},
            max_iterations=15
        )

        return {
            "vulnerabilities": result.get("findings", []),
            "tool_calls": result.get("tool_calls", []),
            "findings": result.get("findings", []),
            "summary": result.get("summary", ""),
            "analysis": result.get("summary", "")
        }

    def _format_recon_data(self, recon_data: Dict) -> str:
        if not recon_data:
            return "No recon data available"
        parts = []
        if recon_data.get("hosts"):
            parts.append(f"Hosts: {recon_data['hosts']}")
        if recon_data.get("tool_calls"):
            parts.append(f"Previous tool calls: {len(recon_data['tool_calls'])} tools executed")
        if recon_data.get("findings"):
            parts.append(f"Recon findings: {len(recon_data['findings'])} items")
        return "\n".join(parts) if parts else str(recon_data)[:500]
