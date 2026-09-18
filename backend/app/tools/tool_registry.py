from typing import Dict, Any, Optional, List
from app.core.cli_executor import CLIExecutor, ToolboxManager, toolbox_manager
from dataclasses import dataclass


@dataclass
class ToolDefinition:
    name: str
    description: str
    command_template: str
    toolbox: str  # Which toolbox has this tool
    category: str = "general"


class ToolRegistry:
    def __init__(self, toolbox_manager: ToolboxManager):
        self.toolbox_manager = toolbox_manager
        self.tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition):
        self.tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self.tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "toolbox": t.toolbox
            }
            for t in self.tools.values()
        ]

    def list_toolboxes(self) -> List[Dict[str, Any]]:
        toolboxes = []
        for name, config in self.toolbox_manager.toolboxes.items():
            tool_count = len([t for t in self.tools.values() if t.toolbox == name])
            toolboxes.append({
                "name": name,
                "executor_type": config.executor_type.value,
                "tool_count": tool_count,
                "container_name": config.container_name,
                "image": config.image,
                "ssh_host": config.ssh_host,
                "ssh_port": config.ssh_port or 22,
                "ssh_user": config.ssh_user,
                "mcp_url": config.mcp_url,
                "working_dir": config.working_dir or "/workspace"
            })
        return toolboxes

    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found", "success": False}

        command = self._build_command(tool, args)
        return await self.toolbox_manager.execute_on_toolbox(
            tool.toolbox, command
        )

    async def execute_raw(self, toolbox_name: str, command: str) -> Dict[str, Any]:
        return await self.toolbox_manager.execute_on_toolbox(toolbox_name, command)

    def _build_command(self, tool: ToolDefinition, args: Dict[str, Any]) -> str:
        cmd = tool.command_template
        for key, value in args.items():
            cmd = cmd.replace(f"{{{key}}}", str(value))
        return cmd


def create_default_registry() -> ToolRegistry:
    registry = ToolRegistry(toolbox_manager)

    # Nmap tools
    registry.register(ToolDefinition(
        name="nmap_scan",
        description="Scan ports and services with nmap",
        command_template="nmap -sV -p {ports} {target}",
        toolbox="pentest-tools",
        category="recon"
    ))
    registry.register(ToolDefinition(
        name="nmap_quick",
        description="Quick nmap scan",
        command_template="nmap -F -T4 {target}",
        toolbox="pentest-tools",
        category="recon"
    ))
    registry.register(ToolDefinition(
        name="nmap_full",
        description="Full port scan with version detection",
        command_template="nmap -p- -sV -sC -T4 {target}",
        toolbox="pentest-tools",
        category="recon"
    ))

    # Nuclei tools
    registry.register(ToolDefinition(
        name="nuclei_scan",
        description="Vulnerability scan with nuclei templates",
        command_template="nuclei -u {target} -severity {severity} -jsonl",
        toolbox="pentest-tools",
        category="vuln"
    ))
    registry.register(ToolDefinition(
        name="nuclei_tags",
        description="Nuclei scan with specific tags",
        command_template="nuclei -u {target} -tags {tags} -jsonl",
        toolbox="pentest-tools",
        category="vuln"
    ))

    # SQLMap
    registry.register(ToolDefinition(
        name="sqlmap_test",
        description="Test for SQL injection",
        command_template="sqlmap -u {url} --batch --level {level} --risk {risk}",
        toolbox="pentest-tools",
        category="exploit"
    ))

    # ffuf
    registry.register(ToolDefinition(
        name="ffuf_dirscan",
        description="Directory/file fuzzing with ffuf",
        command_template="ffuf -u {url}/FUZZ -w {wordlist} -mc 200,301,302,403 -o /dev/stdout -of json",
        toolbox="pentest-tools",
        category="recon"
    ))

    # Subfinder
    registry.register(ToolDefinition(
        name="subfinder",
        description="Subdomain enumeration",
        command_template="subfinder -d {domain} -silent",
        toolbox="pentest-tools",
        category="recon"
    ))

    # httpx
    registry.register(ToolDefinition(
        name="httpx_probe",
        description="HTTP probing and technology detection",
        command_template="httpx -l {input_file} -silent -json",
        toolbox="pentest-tools",
        category="recon"
    ))

    # WhatWeb
    registry.register(ToolDefinition(
        name="whatweb",
        description="Web technology fingerprinting",
        command_template="whatweb {target} --color=never",
        toolbox="pentest-tools",
        category="recon"
    ))

    return registry


# Global tool registry
tool_registry = create_default_registry()
