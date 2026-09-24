from typing import Dict, Any, List
from app.core.agent import BaseAgent
from app.core.llm import LLMClient


class VulnAnalyzerAgent(BaseAgent):
    def __init__(self, llm_client: LLMClient, **kwargs):
        super().__init__(agent_type="vuln_analyzer", llm_client=llm_client, **kwargs)

    def default_system_prompt(self) -> str:
        return """You are a network vulnerability analysis agent in a penetration testing framework.

Your goal is to analyze, verify, and assess the severity of discovered network vulnerabilities (CVEs). This is NETWORK VULNERABILITY ANALYSIS, not web application testing.

ANALYSIS METHODOLOGY:
1. Review scan results and CVE findings
2. Verify each CVE by checking if the affected software version matches what was discovered
3. Use searchsploit to get additional details on each CVE (exploit availability, CVSS)
4. Use nmap to confirm service versions and configurations
5. Assess each vulnerability for:
   - Exploitability (public exploits available? remote or local?)
   - Impact (data loss, privilege escalation, denial of service?)
   - Confidence level (version match confirmed vs suspected)

IMPORTANT RULES:
- Focus ONLY on network-level vulnerabilities and CVEs
- Do NOT test or verify web application vulnerabilities
- DO verify that the software version in recon matches the CVE's affected range
- Calculate risk severity based on CVSS scores and exploit availability
- Identify CWE mappings where applicable
- Look for vulnerability chains (e.g., CVE A gives access, CVE B escalates privileges)

OUTPUT FORMAT - When complete, provide:
{
  "analysis_complete": true,
  "summary": "Overview of verified network vulnerabilities",
  "findings": [
    {
      "title": "[Software] [Version] - [CVE ID]",
      "severity": "info|low|medium|high|critical",
      "cvss_score": 7.5,
      "cwe_id": "CWE-XXX",
      "description": "Detailed description of the verified vulnerability",
      "evidence": "Proof of vulnerability (searchsploit output, version match)",
      "remediation": "How to fix (upgrade version, apply patch, etc.)"
    }
  ]
}

Focus on verified, actionable findings with confirmed CVE matches."""

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        scan_results = input_data.get("scan_results", {})
        recon_data = input_data.get("recon_data", {})

        task = """Analyze and verify the discovered network vulnerabilities:

Review the scan results and recon data provided in context.

Your task:
1. Review each identified CVE/vulnerability from the scan
2. Verify that the discovered software version matches the CVE's affected range
3. Use searchsploit to get detailed information on each CVE
4. Use nmap to confirm service versions
5. Assess severity and exploitability of each finding
6. Identify any attack chains or vulnerability combinations
7. Assign CVSS scores and CWE IDs where possible

Start by reviewing the scan results to identify the most critical CVE findings."""

        result = await self.run_agent_loop(
            task=task,
            context={"scan_results": scan_results, "recon_data": recon_data},
            max_iterations=12
        )

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
            "detailed_analysis": result.get("summary", ""),
            "llm_failed": result.get("llm_failed", False),
            "llm_error": result.get("llm_error", "")
        }
