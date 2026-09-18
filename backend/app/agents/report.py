from typing import Dict, Any, List
from app.core.agent import BaseAgent
from app.core.llm import LLMClient
from app.report_templates import generate_report
import logging

logger = logging.getLogger(__name__)


class ReportAgent(BaseAgent):
    def __init__(self, llm_client: LLMClient, **kwargs):
        super().__init__(agent_type="report", llm_client=llm_client, **kwargs)

    def default_system_prompt(self) -> str:
        return "You are a report generation agent in a penetration testing framework."

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        findings = input_data.get("findings", {})
        engagement = input_data.get("engagement", {})
        report_level = input_data.get("report_level", "medium")

        generated_content = generate_report(findings, engagement, report_level)

        all_findings = []
        vuln_data = findings.get("vuln_analyzer", {})
        scanner_data = findings.get("scanner", {})

        for source in [vuln_data.get("verified_vulnerabilities", []),
                       vuln_data.get("findings", []),
                       scanner_data.get("vulnerabilities", []),
                       scanner_data.get("findings", [])]:
            if isinstance(source, list):
                all_findings.extend(source)

        seen_titles = set()
        unique_findings = []
        for f in all_findings:
            title = f.get("title", "").strip().lower()
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_findings.append(f)

        summary = self._generate_executive_summary(unique_findings)

        return {
            "executive_summary": summary,
            "findings": [],
            "remediation": [f.get("remediation", "") for f in unique_findings if f.get("remediation")],
            "methodology": "Automated penetration testing using NetActor framework",
            "tool_calls": [],
            "generated_content": generated_content
        }

    def _generate_executive_summary(self, findings: list) -> str:
        if not findings:
            return "No vulnerabilities were identified during this engagement."

        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in findings:
            sev = f.get("severity", "info").lower()
            if sev in counts:
                counts[sev] += 1

        total = len(findings)
        if counts["critical"] > 0:
            return f"Critical: {total} findings including {counts['critical']} critical vulnerabilities requiring immediate remediation."
        elif counts["high"] > 0:
            return f"HIGH RISK: {total} findings including {counts['high']} high-severity vulnerabilities requiring prompt attention."
        elif counts["medium"] > 0:
            return f"{total} findings identified, with {counts['medium']} medium-severity issues requiring remediation within the patch cycle."
        else:
            return f"{total} findings identified at low/informational severity. Security posture is reasonable."
