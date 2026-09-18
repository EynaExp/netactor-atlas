from typing import Dict, Any, List
from app.core.agent import BaseAgent
from app.core.llm import LLMClient


class VulnAnalyzerAgent(BaseAgent):
    def __init__(self, llm_client: LLMClient, **kwargs):
        super().__init__(agent_type="vuln_analyzer", llm_client=llm_client, **kwargs)

    def default_system_prompt(self) -> str:
        return """You are a vulnerability analysis agent in a penetration testing framework.

Your goal is to analyze and verify discovered vulnerabilities, assess their severity, and identify attack chains.

ANALYSIS METHODOLOGY:
1. Review scan results and identified vulnerabilities
2. Use curl to verify web vulnerabilities (test requests, check responses)
3. Use nmap to confirm service versions and configurations
4. Search for additional exploits or attack vectors (searchsploit)
5. Assess each vulnerability for:
   - Exploitability (how easy to exploit)
   - Impact (what damage could occur)
   - Confidence level (confirmed vs suspected)

APPROACH:
- Verify vulnerabilities before marking as confirmed
- Calculate CVSS scores where possible
- Identify CWE/OWASP mappings
- Look for vulnerability chains (multiple vulns that combine)
- Be conservative with severity ratings

OUTPUT FORMAT - When complete, provide:
{
  "analysis_complete": true,
  "summary": "Overview of vulnerability analysis",
  "findings": [
    {
      "title": "Verified vulnerability",
      "severity": "info|low|medium|high|critical",
      "cvss_score": 7.5,
      "cwe_id": "CWE-89",
      "description": "Detailed description",
      "evidence": "Proof of vulnerability",
      "remediation": "How to fix"
    }
  ]
}

Focus on verified, actionable findings."""

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        scan_results = input_data.get("scan_results", {})
        recon_data = input_data.get("recon_data", {})

        task = """Analyze and verify the discovered vulnerabilities:

Review the scan results and recon data provided in context.

Your task:
1. Review each identified vulnerability from the scan
2. Use curl to verify web-based vulnerabilities where possible
3. Use nmap to confirm service versions
4. Search for additional exploit details (searchsploit)
5. Assess severity and exploitability of each finding
6. Identify any attack chains or vulnerability combinations

Start by reviewing the scan results to identify the most critical findings."""

        result = await self.run_agent_loop(
            task=task,
            context={"scan_results": scan_results, "recon_data": recon_data},
            max_iterations=12
        )

        # Ensure findings are in the correct format for saving
        verified_vulns = []
        for finding in result.get("findings", []):
            verified_vulns.append({
                "title": finding.get("title", "Unknown Vulnerability"),
                "severity": finding.get("severity", "info"),
                "cvss_score": finding.get("cvss_score"),
                "cwe_id": finding.get("cwe_id"),
                "description": finding.get("description", ""),
                "proof": finding.get("evidence", ""),
                "tool_source": "vuln_analyzer",
                "remediation": finding.get("remediation", "")
            })

        return {
            "verified_vulnerabilities": verified_vulns,
            "tool_calls": result.get("tool_calls", []),
            "findings": result.get("findings", []),
            "summary": result.get("summary", ""),
            "detailed_analysis": result.get("summary", "")
        }
