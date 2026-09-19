"""Professional penetration test report templates."""
from datetime import datetime
from typing import Dict, Any, List, Optional


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "informational": 4}
SEVERITY_COLORS = {"critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM", "low": "LOW", "info": "INFO"}


def _format_severity(sev: str) -> str:
    return SEVERITY_COLORS.get(sev.lower(), sev.upper())


def _sort_findings(findings: list) -> list:
    return sorted(findings, key=lambda f: SEVERITY_ORDER.get(f.get("severity", "info").lower(), 5))


def _count_by_severity(findings: list) -> Dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        sev = f.get("severity", "info").lower()
        if sev in counts:
            counts[sev] += 1
    return counts


def _risk_rating(counts: Dict[str, int]) -> str:
    if counts["critical"] > 0:
        return "CRITICAL"
    if counts["high"] > 0:
        return "HIGH"
    if counts["medium"] > 0:
        return "MEDIUM"
    if counts["low"] > 0:
        return "LOW"
    return "INFO"


def _extract_recon_data(phases: Dict) -> Dict:
    recon = phases.get("recon", {})
    services = recon.get("discovered_services", recon.get("services", []))
    hosts = recon.get("discovered_hosts", recon.get("hosts", []))
    return {
        "hosts": hosts,
        "services": services,
        "host_count": len(hosts) if isinstance(hosts, list) else 0,
        "service_count": len(services) if isinstance(services, list) else 0,
    }


def _extract_scanner_data(phases: Dict) -> Dict:
    scanner = phases.get("scanner", {})
    vulns = scanner.get("vulnerabilities", scanner.get("findings", []))
    return {
        "vulnerabilities": vulns,
        "vuln_count": len(vulns) if isinstance(vulns, list) else 0,
    }


def _extract_vuln_data(phases: Dict) -> Dict:
    vuln = phases.get("vuln_analyzer", {})
    verified = vuln.get("verified_vulnerabilities", vuln.get("findings", []))
    return {
        "verified": verified,
        "verified_count": len(verified) if isinstance(verified, list) else 0,
    }


def generate_report(phases: Dict, engagement: Dict, report_level: str = "medium") -> str:
    """Generate a professional penetration test report from phase data."""
    target = engagement.get("target", "Unknown")
    scope = engagement.get("target_scope", [])
    scope_str = ", ".join(
        t.get("host") or t.get("value") or t.get("target", "") for t in scope if isinstance(t, dict)
    ) if scope else target
    if not scope_str:
        scope_str = target

    recon = _extract_recon_data(phases)
    scanner = _extract_scanner_data(phases)
    vuln = _extract_vuln_data(phases)

    all_findings = []
    all_findings.extend(scanner.get("vulnerabilities", []))
    all_findings.extend(vuln.get("verified", []))

    all_findings = _sort_findings(all_findings)
    counts = _count_by_severity(all_findings)
    risk = _risk_rating(counts)

    now = datetime.utcnow().strftime("%B %d, %Y")
    duration = engagement.get("duration", "N/A")

    md = _cover_section(scope_str, now, risk, counts, duration)
    md += _executive_summary_section(all_findings, counts, risk, scope_str)
    md += _scope_methodology_section(scope_str, recon, scanner)
    md += _findings_overview_section(counts, all_findings)
    md += _detailed_findings_section(all_findings, report_level)
    md += _remediation_section(all_findings)
    md += _appendix_section(recon, scanner, vuln)

    return md


def _cover_section(target: str, date: str, risk: str, counts: Dict, duration: str) -> str:
    return f"""# PENETRATION TEST REPORT

---

**Target:** {target}

**Date:** {date}

**Overall Risk Rating:** {risk}

**Duration:** {duration}

---

| Severity | Count |
|----------|-------|
| Critical | {counts['critical']} |
| High | {counts['high']} |
| Medium | {counts['medium']} |
| Low | {counts['low']} |
| Informational | {counts['info']} |
| **Total** | **{sum(counts.values())}** |

---

"""


def _executive_summary_section(findings: list, counts: Dict, risk: str, target: str) -> str:
    total = sum(counts.values())

    if total == 0:
        summary_text = (
            "The penetration test of the target environment did not identify any "
            "critical security vulnerabilities. The target demonstrates a reasonable "
            "security posture, though continued monitoring and hardening are recommended."
        )
    elif risk == "CRITICAL":
        summary_text = (
            f"The penetration test identified {total} security findings, including "
            f"{counts['critical']} critical vulnerabilities that require immediate attention. "
            "These critical findings could allow unauthorized access, data exfiltration, "
            "or full compromise of the target environment. Immediate remediation is strongly "
            "recommended to reduce the risk of a real-world attack."
        )
    elif risk == "HIGH":
        summary_text = (
            f"The penetration test identified {total} security findings, including "
            f"{counts['high']} high-severity vulnerabilities that pose a significant risk "
            "to the target environment. These findings could be exploited by an attacker "
            "to gain elevated privileges, access sensitive data, or disrupt services. "
            "Prompt remediation is recommended."
        )
    elif risk == "MEDIUM":
        summary_text = (
            f"The penetration test identified {total} security findings, with the most "
            f"serious being {counts['medium']} medium-severity issues. While these do not "
            "represent an immediate critical risk, they could be combined with other "
            "vulnerabilities or exploited under specific conditions. Remediation is "
            "recommended within the normal patch cycle."
        )
    else:
        summary_text = (
            f"The penetration test identified {total} findings, all at low or informational "
            "severity. These findings represent minor security improvements that can be "
            "addressed as part of regular security maintenance."
        )

    return f"""# 1. Executive Summary

{summary_text}

## Key Findings

| Severity | Count | Impact |
|----------|-------|--------|
| Critical | {counts['critical']} | Immediate compromise risk |
| High | {counts['high']} | Significant data/service risk |
| Medium | {counts['medium']} | Conditional exploitation risk |
| Low | {counts['low']} | Minor security improvement |
| Informational | {counts['info']} | Best practice recommendations |

## Risk Assessment

The overall risk rating for this engagement is **{risk}**. {'Immediate action is required to address critical vulnerabilities.' if risk == 'CRITICAL' else 'Timely remediation is recommended to reduce the attack surface.' if risk in ('HIGH', 'MEDIUM') else 'The environment demonstrates good security practices.'}

---

"""


def _scope_methodology_section(target: str, recon: Dict, scanner: Dict) -> str:
    host_count = recon.get("host_count", 0)
    service_count = recon.get("service_count", 0)

    return f"""# 2. Scope and Methodology

## Engagement Scope

| Parameter | Value |
|-----------|-------|
| Target | {target} |
| Hosts Discovered | {host_count} |
| Services Identified | {service_count} |
| Testing Type | External Penetration Test |

## Methodology

The penetration test was conducted following industry-standard methodologies:

1. **Reconnaissance** — Network discovery and service enumeration using nmap and masscan
2. **Vulnerability Scanning** — Automated vulnerability detection using Nuclei templates and custom checks
3. **Vulnerability Analysis** — Manual verification and validation of discovered vulnerabilities
4. **Exploitation** (if enabled) — Controlled exploitation of verified vulnerabilities

## Tools Used

- **Network Discovery:** nmap, masscan
- **Vulnerability Scanning:** Nuclei, custom security checks
- **Active Directory:** adscan, adPEAS
- **Credential Testing:** NetExec (nxc)
- **Exploitation:** searchsploit, custom exploit modules

## Limitations

- Testing was performed within the authorized scope only
- Social engineering and physical attacks were not included
- Denial-of-service testing was not performed

---

"""


def _findings_overview_section(counts: Dict, findings: list) -> str:
    md = "# 3. Findings Overview\n\n"

    if not findings:
        md += "No vulnerabilities were identified during this engagement.\n\n---\n\n"
        return md

    md += "| # | Severity | Title | Affected Component |\n"
    md += "|---|----------|-------|--------------------|\n"

    for i, f in enumerate(findings, 1):
        sev = _format_severity(f.get("severity", "info"))
        title = f.get("title", "Untitled Finding")
        affected = f.get("affected_component", f.get("target", "N/A"))
        if isinstance(affected, list):
            affected = ", ".join(str(a) for a in affected[:3])
        md += f"| {i} | {sev} | {title} | {affected} |\n"

    md += "\n---\n\n"
    return md


def _detailed_findings_section(findings: list, report_level: str) -> str:
    md = "# 4. Detailed Findings\n\n"

    if not findings:
        md += "No detailed findings to report.\n\n---\n\n"
        return md

    for i, f in enumerate(findings, 1):
        sev = _format_severity(f.get("severity", "info"))
        title = f.get("title", "Untitled Finding")
        description = f.get("description", "No description provided.")
        remediation = f.get("remediation", "")
        evidence = f.get("evidence", "")
        cvss = f.get("cvss_score", "N/A")
        cwe = f.get("cwe_id", "N/A")
        affected = f.get("affected_component", f.get("target", "N/A"))
        if isinstance(affected, list):
            affected = ", ".join(str(a) for a in affected)

        md += f"## 4.{i} {title}\n\n"
        md += f"**Severity:** {sev}\n\n"

        if cvss != "N/A":
            md += f"**CVSS Score:** {cvss}\n\n"
        if cwe != "N/A":
            md += f"**CWE:** {cwe}\n\n"

        md += f"**Affected Component:** {affected}\n\n"
        md += f"### Description\n\n{description}\n\n"

        if evidence and report_level in ("medium", "detailed"):
            if isinstance(evidence, list):
                evidence = "\n".join(str(e) for e in evidence)
            md += f"### Evidence\n\n```\n{evidence}\n```\n\n"

        if remediation:
            md += f"### Remediation\n\n{remediation}\n\n"

        md += "---\n\n"

    return md


def _remediation_section(findings: list) -> str:
    md = "# 5. Remediation Plan\n\n"

    if not findings:
        md += "No specific remediation actions required.\n\n---\n\n"
        return md

    critical_high = [f for f in findings if f.get("severity", "").lower() in ("critical", "high")]
    medium = [f for f in findings if f.get("severity", "").lower() == "medium"]
    low_info = [f for f in findings if f.get("severity", "").lower() in ("low", "info")]

    if critical_high:
        md += "## Immediate Actions (0-7 days)\n\n"
        for f in critical_high:
            title = f.get("title", "Untitled")
            rem = f.get("remediation", "Review and remediate the identified vulnerability.")
            md += f"1. **{title}** — {rem}\n\n"

    if medium:
        md += "## Short-term Actions (7-30 days)\n\n"
        for f in medium:
            title = f.get("title", "Untitled")
            rem = f.get("remediation", "Review and remediate the identified vulnerability.")
            md += f"1. **{title}** — {rem}\n\n"

    if low_info:
        md += "## Long-term Actions (30-90 days)\n\n"
        for f in low_info:
            title = f.get("title", "Untitled")
            rem = f.get("remediation", "Address as part of regular security maintenance.")
            md += f"1. **{title}** — {rem}\n\n"

    md += "---\n\n"
    return md


def _appendix_section(recon: Dict, scanner: Dict, vuln: Dict) -> str:
    md = "# 6. Appendix\n\n"

    services = recon.get("services", [])
    if services and isinstance(services, list):
        md += "## Discovered Services\n\n"
        md += "| Host | Port | Protocol | Service |\n"
        md += "|------|------|----------|----------|\n"
        for s in services[:50]:
            if isinstance(s, dict):
                host = s.get("host", s.get("ip", "N/A"))
                port = s.get("port", s.get("portid", "N/A"))
                proto = s.get("protocol", "tcp")
                svc = s.get("service", s.get("name", "unknown"))
                md += f"| {host} | {port} | {proto} | {svc} |\n"
            elif isinstance(s, str):
                md += f"| {s} | - | - | - |\n"
        md += "\n"

    md += "---\n\n"
    md += "*Report generated by NetActor Penetration Testing Framework*\n"
    return md


def generate_section_report(section: str, phase_data: Dict, engagement: Dict) -> str:
    """Generate a report for a single phase/section."""
    target = engagement.get("target", "Unknown")
    now = datetime.utcnow().strftime("%B %d, %Y")

    md = f"# {section.upper().replace('_', ' ')} REPORT\n\n"
    md += f"**Target:** {target}\n**Date:** {now}\n\n---\n\n"

    if section == "recon":
        recon = _extract_recon_data({"recon": phase_data})
        md += _scope_methodology_section(target, recon, {})
        md += f"## Discovered Hosts\n\n"
        hosts = recon.get("hosts", [])
        if isinstance(hosts, list):
            for h in hosts:
                md += f"- {h}\n" if isinstance(h, str) else f"- {h.get('ip', h.get('host', 'N/A'))}\n"
        md += "\n## Discovered Services\n\n"
        services = recon.get("services", [])
        if isinstance(services, list):
            md += "| Host | Port | Service |\n|------|------|----------|\n"
            for s in services[:30]:
                if isinstance(s, dict):
                    md += f"| {s.get('host', 'N/A')} | {s.get('port', 'N/A')} | {s.get('service', 'N/A')} |\n"

    elif section == "scanner":
        scanner_data = _extract_scanner_data({"scanner": phase_data})
        vulns = scanner_data.get("vulnerabilities", [])
        md += f"## Discovered Vulnerabilities ({len(vulns)})\n\n"
        md += _detailed_findings_section(vulns, "medium")

    elif section == "vuln_analyzer":
        vuln_data = _extract_vuln_data({"vuln_analyzer": phase_data})
        verified = vuln_data.get("verified", [])
        md += f"## Verified Vulnerabilities ({len(verified)})\n\n"
        md += _detailed_findings_section(verified, "detailed")

    else:
        md += f"```\n{phase_data}\n```\n"

    return md
