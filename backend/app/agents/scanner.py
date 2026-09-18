from typing import Dict, Any, List
from app.core.agent import BaseAgent
from app.core.llm import LLMClient


class ScannerAgent(BaseAgent):
    def __init__(self, llm_client: LLMClient, **kwargs):
        super().__init__(agent_type="scanner", llm_client=llm_client, **kwargs)

    def default_system_prompt(self) -> str:
        return """You are a vulnerability scanning agent in a penetration testing framework.

Your goal is to scan discovered assets for vulnerabilities using the available tools.

SCANNING METHODOLOGY:
1. Review the recon data to identify services and versions
2. Use searchsploit to find known exploits for discovered software
3. For web services, use curl to test for common web vulnerabilities
4. Use nmap with vulnerability scripts (--script vuln) on specific services
5. Document all potential vulnerabilities found

APPROACH:
- Focus on high-risk services first (web servers, databases, management interfaces)
- Look for outdated software versions with known CVEs
- Check for default credentials or misconfigurations
- Test web endpoints for common vulnerabilities (LFI, directory traversal, etc.)
- Document evidence for each finding

OUTPUT FORMAT - When complete, provide:
{
  "analysis_complete": true,
  "summary": "Overview of vulnerability scan findings",
  "findings": [
    {
      "title": "Vulnerability title",
      "severity": "info|low|medium|high|critical",
      "description": "Description of the vulnerability",
      "evidence": "Proof or observation of the vulnerability"
    }
  ]
}

Be thorough but focus on confirmed or likely vulnerabilities."""

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        recon_data = input_data.get("recon_data", {})
        targets = input_data.get("targets", [])
        tools = input_data.get("tools", [])

        target_list = ", ".join([
            t.get("value", str(t)) if isinstance(t, dict) else str(t)
            for t in targets
        ])

        task = f"""Scan the following targets for vulnerabilities:

Targets: {target_list}
Recon Data: {self._format_recon_data(recon_data)}

Your task:
1. Review the recon data to identify services and versions
2. Search for known exploits (searchsploit) for each discovered software version
3. For web services, test HTTP endpoints using curl for common issues
4. Use nmap vulnerability scripts on interesting services
5. Compile all vulnerabilities found with evidence

Start by searching for exploits for the discovered software versions."""

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
        """Format recon data for the scanning task"""
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
