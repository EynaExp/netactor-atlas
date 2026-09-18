from typing import Dict, Any, List
from app.core.agent import BaseAgent
from app.core.llm import LLMClient


class ReconAgent(BaseAgent):
    def __init__(self, llm_client: LLMClient, **kwargs):
        super().__init__(agent_type="recon", llm_client=llm_client, **kwargs)

    def default_system_prompt(self) -> str:
        return """You are a reconnaissance agent in a penetration testing framework.

Your goal is to gather comprehensive information about the target scope using the available tools.

RECONNAISSANCE METHODOLOGY:
1. Start with a port scan (nmap) to discover open services
2. Run service version detection on discovered ports
3. For web services, use curl to check HTTP headers and technology stack
4. Search for known exploits (searchsploit) for discovered software
5. If a domain target, enumerate further

APPROACH:
- Be methodical - scan ports first, then investigate services
- Use appropriate flags for the situation
- Document all findings as you go
- When you have enough data, output your analysis_complete response

OUTPUT FORMAT - When complete, provide:
{
  "analysis_complete": true,
  "summary": "Overview of reconnaissance findings",
  "findings": [
    {
      "title": "Finding title",
      "severity": "info|low|medium|high|critical",
      "description": "What was discovered",
      "evidence": "Raw tool output or observation"
    }
  ]
}

Always be thorough and document your methodology."""

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        targets = input_data.get("targets", [])
        scan_mode = input_data.get("scan_mode", "quick")
        tools = input_data.get("tools", [])

        target_list = ", ".join([
            t.get("value", str(t)) if isinstance(t, dict) else str(t)
            for t in targets
        ])

        task = f"""Perform reconnaissance on the following targets:

Targets: {target_list}
Scan Mode: {scan_mode}

Your task:
1. Run port scanning (nmap) on each target to discover open ports and services
2. Identify service versions and software
3. For any web services, check HTTP headers and technology stack using curl
4. Search for known exploits for discovered software versions using searchsploit
5. Compile all findings into a structured report

Start by scanning the first target with nmap to discover open ports."""

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
