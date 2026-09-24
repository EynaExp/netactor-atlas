from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.core.llm import LLMClient
from app.core.cli_executor import ToolboxManager, toolbox_manager
from app.tools.tool_registry import tool_registry, ToolRegistry
from datetime import datetime
import uuid
import time
import json
import re
import logging
import ipaddress
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Engagement stop requests: engagement_id -> True. The agent loop checks this
# before every iteration so a stop takes effect within seconds.
STOP_REQUESTS: Dict[str, bool] = {}

# OpenAI function-calling format for MCP tools
MCP_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "nmap",
            "description": "Network exploration, port scanning and service detection. Use for discovering open ports, running services, OS detection, and service versions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Target IP, hostname, or CIDR range"},
                    "flags": {"type": "string", "description": "Nmap flags. Examples: '-sV' for version detection, '-sC' for default scripts, '-p 80,443' for specific ports, '-O' for OS detection, '-A' for aggressive scan, '-T4' for fast timing, '--script vuln' for vulnerability scripts"}
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "masscan",
            "description": "Fast port scanner for large networks. Much faster than nmap for full port scans but less accurate. Use for initial discovery of open ports on large targets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Target IP, hostname, or CIDR range"},
                    "flags": {"type": "string", "description": "Masscan flags. Examples: '-p1-65535 --rate=1000' for full ports, '-p80,443 --rate=500' for web ports"}
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "nxc",
            "description": "NetExec (nxc) - network enumeration and exploitation tool. Supports SMB, LDAP, WinRM, SSH, FTP, RDP, HTTP protocols. Use for credential testing, enumeration, and finding misconfigurations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Target IP or hostname"},
                    "protocol": {"type": "string", "enum": ["smb", "ldap", "winrm", "ssh", "ftp", "rdp", "http"], "description": "Protocol to use"},
                    "flags": {"type": "string", "description": "Additional flags. Examples: '-u admin -p password' for auth, '--shares' for SMB share listing, '--users' for user enum, '--pass-pol' for password policy"}
                },
                "required": ["target", "protocol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "searchsploit",
            "description": "Search ExploitDB for public exploits and shellcodes. Use to find known exploits for discovered software versions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query - software name, version, or CVE number. Examples: 'Apache 2.4.49', 'CVE-2021-44228', 'OpenSSH 8.2'"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "adscan",
            "description": "Active Directory pentesting and auditing tool. Use for AD enumeration, misconfiguration detection, and privilege escalation paths.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Target domain controller IP or domain name"},
                    "flags": {"type": "string", "description": "Flags for adscan. Examples: '-u user -p pass' for authentication"}
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "adpeas",
            "description": "adPEAS - winPEAS for Active Directory. Automated AD enumeration: BloodHound collection, Certipy ADCS misconfiguration detection, domain info, users, groups, shares, GPOs, delegation attacks. Requires credentials. Use after finding valid AD credentials.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Domain Controller IP or hostname"},
                    "username": {"type": "string", "description": "Domain username"},
                    "password": {"type": "string", "description": "Domain password"},
                    "domain": {"type": "string", "description": "Domain name (e.g. corp.local)"},
                    "flags": {"type": "string", "description": "Extra flags. Examples: '-nb' skip BloodHound, '-nc' skip Certipy"}
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "nuclei",
            "description": "Nuclei - template-based vulnerability scanner with 9000+ templates. Use AFTER nmap/masscan discover open ports. Checks for known CVEs, RCE, SSRF, default credentials, SSL/TLS misconfigs, DNS issues. Supports web (http), raw network services (tcp), and SSL targets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Target IP or hostname"},
                    "url": {"type": "string", "description": "Full URL for web scanning (e.g. http://target:8080)"},
                    "port": {"type": "string", "description": "Port for raw network/tcp scanning (used with protocol='network')"},
                    "protocol": {"type": "string", "enum": ["http", "network", "ssl", "dns"], "description": "Scan type: http for web, network for raw TCP services, ssl for TLS checks"},
                    "severity": {"type": "string", "description": "Filter by severity (e.g. 'critical,high')"},
                    "tags": {"type": "string", "description": "Filter by tags (e.g. 'cve,rce,ssl')"},
                    "flags": {"type": "string", "description": "Additional nuclei flags"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "curl",
            "description": "HTTP request tool. Use for testing web applications, checking endpoints, fetching headers, testing for vulnerabilities like LFI/SSRF, and verifying web server configurations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target URL to send request to"},
                    "flags": {"type": "string", "description": "Curl flags. Examples: '-I' for headers only, '-X POST' for POST request, '-d \"data\"' for request body, '-H \"Header: value\"' for custom headers, '-v' for verbose, '-k' to ignore SSL errors"}
                },
                "required": ["url"]
            }
        }
    }
]

# Text-based tool calling format for models without native tool support
TOOL_CALL_PROMPT = """You have access to the following tools:

{tool_descriptions}

To use a tool, respond with a JSON object in this exact format (no other text):
{{"tool_call": {{"name": "tool_name", "arguments": {{"param1": "value1", "param2": "value2"}}}}}}

When you have enough information and don't need to call more tools, respond with:
{{"analysis_complete": true, "summary": "your summary here", "findings": [{{"title": "...", "severity": "...", "description": "...", "evidence": "..."}}]}}

RULES:
- Call ONE tool at a time
- Always include the tool_call JSON object when calling a tool
- Parse tool output carefully for relevant information
- Be methodical - gather information step by step
- After gathering enough data, output your analysis_complete response
- Maximum {max_iterations} tool calls allowed"""


class BaseAgent(ABC):
    def __init__(
        self,
        agent_type: str,
        llm_client: LLMClient,
        system_prompt: str = None,
        engagement_id: str = None,
        session_id: str = None,
        toolbox_manager: ToolboxManager = None,
        tool_registry: ToolRegistry = None,
        enabled_tools: Optional[List[str]] = None,
        allowed_targets: Optional[List[str]] = None
    ):
        self.agent_type = agent_type
        self.llm = llm_client
        self.enabled_tools = set(enabled_tools) if enabled_tools is not None else None
        self.allowed_targets = [t.strip().lower() for t in (allowed_targets or []) if t and t.strip()]
        self.system_prompt = system_prompt or self.default_system_prompt()
        self.engagement_id = engagement_id
        self.session_id = session_id or str(uuid.uuid4())
        self.actions: List[Dict[str, Any]] = []
        self.context: Dict[str, Any] = {}
        self.toolbox_manager = toolbox_manager or toolbox_manager
        self.tool_registry = tool_registry or tool_registry
        self.max_iterations = 20
        self.iteration = 0

    @abstractmethod
    def default_system_prompt(self) -> str:
        pass

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    def _get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions for the LLM (filtered by enabled tools)"""
        descriptions = []
        for tool in MCP_TOOL_DEFINITIONS:
            if self.enabled_tools is not None and tool["function"]["name"] not in self.enabled_tools:
                continue
            fn = tool["function"]
            params = fn["parameters"]["properties"]
            required = fn["parameters"].get("required", [])
            param_str = ", ".join([f"{k}{'*' if k in required else ''}" for k in params.keys()])
            descriptions.append(f"- {fn['name']}: {fn['description']} (params: {param_str})")
        return "\n".join(descriptions)

    def _parse_tool_call(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse tool call from LLM response (supports both native and text-based formats)"""
        # Try to parse as JSON
        try:
            data = json.loads(response.strip())
            if "tool_call" in data:
                return data["tool_call"]
            if "function_call" in data:
                return data["function_call"]
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if "tool_call" in data:
                    return data["tool_call"]
            except json.JSONDecodeError:
                pass

        # Try to find tool_call pattern in text
        tool_match = re.search(r'\{"tool_call":\s*(\{.*?\})\}', response, re.DOTALL)
        if tool_match:
            try:
                return json.loads(tool_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try function_call pattern
        func_match = re.search(r'"name":\s*"(\w+)"\s*,\s*"arguments":\s*(\{.*?\})', response, re.DOTALL)
        if func_match:
            try:
                return {
                    "name": func_match.group(1),
                    "arguments": json.loads(func_match.group(2))
                }
            except json.JSONDecodeError:
                pass

        return None

    def _parse_analysis_complete(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse analysis_complete response"""
        try:
            data = json.loads(response.strip())
            if data.get("analysis_complete"):
                return data
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if data.get("analysis_complete"):
                    return data
            except json.JSONDecodeError:
                pass

        complete_match = re.search(r'\{"analysis_complete".*?\}', response, re.DOTALL)
        if complete_match:
            try:
                data = json.loads(complete_match.group(0))
                if data.get("analysis_complete"):
                    return data
            except json.JSONDecodeError:
                pass

        return None

    def _scope_violation(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
        """Return an error message if the tool targets something outside engagement scope.
        Non-targeted tools (e.g. searchsploit queries) are always allowed."""
        if not self.allowed_targets:
            return None  # no scope defined -> no enforcement

        candidates = []
        for key in ("target", "dc_ip"):
            v = arguments.get(key)
            if v and isinstance(v, str):
                v = v.strip().lower()
                # targets may accidentally include a scheme — parse it out
                if "://" in v:
                    try:
                        parsed = urlparse(v)
                        if parsed.hostname:
                            v = parsed.hostname.lower()
                    except Exception:
                        pass
                candidates.append(v)
        url = arguments.get("url")
        if url and isinstance(url, str):
            try:
                parsed = urlparse(url if "://" in url else f"http://{url}")
                if parsed.hostname:
                    candidates.append(parsed.hostname.lower())
            except Exception:
                pass

        if not candidates:
            return None  # tool call has no target argument

        networks = []
        hosts = set()
        for t in self.allowed_targets:
            try:
                networks.append(ipaddress.ip_network(t, strict=False))
            except ValueError:
                hosts.add(t)

        for cand in candidates:
            # strip scheme leftovers / port
            cand_host = cand.split("/")[0].split(":")[0]
            ok = False
            try:
                ip = ipaddress.ip_address(cand_host)
                for net in networks:
                    if ip in net:
                        ok = True
                        break
            except ValueError:
                # hostname: exact match or subdomain of a scoped domain
                for h in hosts:
                    if cand_host == h or cand_host.endswith("." + h):
                        ok = True
                        break
            if not ok:
                return (
                    f"SCOPE VIOLATION: '{cand_host}' is outside the authorized engagement scope "
                    f"({', '.join(self.allowed_targets)}). You must ONLY scan targets within scope. "
                    f"Re-run against an in-scope target or finish your analysis."
                )
        return None

    async def execute_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool via MCP protocol"""
        # Enforce engagement scope
        violation = self._scope_violation(tool_name, arguments)
        if violation:
            logger.warning(f"[{self.agent_type}] {violation[:120]}")
            self.actions.append({
                "id": str(uuid.uuid4()),
                "action_type": "scope_blocked",
                "tool_name": tool_name,
                "input": arguments,
                "output": {"error": violation},
                "duration_ms": 0,
                "success": False,
                "timestamp": datetime.utcnow().isoformat()
            })
            return {"error": violation}
        # Reject disabled tools
        if self.enabled_tools is not None and tool_name not in self.enabled_tools:
            logger.warning(f"[{self.agent_type}] Blocked call to disabled tool: {tool_name}")
            return {"error": f"Tool '{tool_name}' is disabled by the administrator. Choose another tool or finish your analysis."}
        start_time = time.time()
        action_id = str(uuid.uuid4())

        result = await self.toolbox_manager.mcp_call("pentest-tools", tool_name, arguments)
        duration = int((time.time() - start_time) * 1000)

        action = {
            "id": action_id,
            "action_type": "mcp_call",
            "tool_name": tool_name,
            "input": arguments,
            "output": result,
            "duration_ms": duration,
            "success": "error" not in result,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.actions.append(action)
        return result

    async def think(self, prompt: str, context: Dict[str, Any] = None) -> str:
        start_time = time.time()
        action_id = str(uuid.uuid4())

        messages = [{"role": "user", "content": prompt}]
        if context:
            messages[0]["content"] = f"Context: {json.dumps(context)}\n\n{prompt}"

        result = await self.llm.chat(
            messages=messages,
            system_prompt=self.system_prompt
        )

        duration = int((time.time() - start_time) * 1000)
        action = {
            "id": action_id,
            "action_type": "llm_call",
            "tool_name": "llm",
            "input": {"prompt": prompt[:200]},
            "output": result,
            "duration_ms": duration,
            "success": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.actions.append(action)
        return result["content"]

    async def run_agent_loop(
        self,
        task: str,
        context: Dict[str, Any] = None,
        max_iterations: int = None
    ) -> Dict[str, Any]:
        """
        Run the core agent loop: LLM thinks -> calls tool -> gets result -> repeats.
        This is the main intelligence loop that powers all agents.
        """
        self.max_iterations = max_iterations or self.max_iterations
        self.iteration = 0
        conversation: List[Dict[str, str]] = []

        # Build initial message with context (limit size)
        initial_msg = task
        if context:
            ctx_str = json.dumps(context, indent=2)
            if len(ctx_str) > 3000:
                ctx_str = ctx_str[:3000] + "\n... (truncated)"
            initial_msg = f"Context from previous stages:\n{ctx_str}\n\nTask: {task}"

        conversation.append({"role": "user", "content": initial_msg})

        # Add tool descriptions to system prompt
        tool_prompt = TOOL_CALL_PROMPT.format(
            tool_descriptions=self._get_tool_descriptions(),
            max_iterations=self.max_iterations
        )
        enhanced_system = f"{self.system_prompt}\n\n{tool_prompt}"

        results = {
            "tool_calls": [],
            "findings": [],
            "summary": "",
            "llm_failed": False
        }

        for i in range(self.max_iterations):
            if self.engagement_id and STOP_REQUESTS.get(self.engagement_id):
                logger.info(f"[{self.agent_type}] Stop requested — aborting agent loop")
                results["summary"] = results["summary"] or "Stopped by user"
                # Flag is left set — the orchestrator consumes it and halts the workflow
                break
            self.iteration = i + 1
            logger.info(f"[{self.agent_type}] Iteration {self.iteration}/{self.max_iterations}")

            # Call LLM
            start_time = time.time()
            try:
                llm_result = await self.llm.chat(
                    messages=conversation,
                    system_prompt=enhanced_system
                )
            except Exception as e:
                logger.error(f"[{self.agent_type}] LLM call failed: {e}")
                results["summary"] = f"LLM call failed: {str(e)}"
                # Surfaced so the orchestrator can mark the engagement failed
                # instead of reporting a clean run with zero findings.
                results["llm_failed"] = True
                results["llm_error"] = str(e)
                break
            duration = int((time.time() - start_time) * 1000)

            response = llm_result.get("content", "")
            if not response:
                response = llm_result.get("reasoning", "")
            
            logger.info(f"[{self.agent_type}] LLM response ({duration}ms, {len(response)} chars): {response[:200]}...")

            # Record LLM action
            self.actions.append({
                "id": str(uuid.uuid4()),
                "action_type": "llm_call",
                "tool_name": "llm",
                "input": {"iteration": self.iteration, "message_count": len(conversation)},
                "output": llm_result,
                "duration_ms": duration,
                "success": True,
                "timestamp": datetime.utcnow().isoformat()
            })

            # Check if analysis is complete
            complete = self._parse_analysis_complete(response)
            if complete:
                results["summary"] = complete.get("summary", "")
                results["findings"] = complete.get("findings", [])
                logger.info(f"[{self.agent_type}] Analysis complete after {self.iteration} iterations")
                break

            # Try to parse tool call
            tool_call = self._parse_tool_call(response)
            if tool_call:
                tool_name = tool_call.get("name", "")
                arguments = tool_call.get("arguments", {})

                logger.info(f"[{self.agent_type}] Calling tool: {tool_name}({json.dumps(arguments)[:200]})")

                # Execute the tool via MCP
                tool_result = await self.execute_mcp_tool(tool_name, arguments)

                # Extract text content from MCP result
                tool_output_text = self._extract_tool_output(tool_result)

                results["tool_calls"].append({
                    "tool": tool_name,
                    "arguments": arguments,
                    "output": tool_output_text[:2000],
                    "success": "error" not in tool_result
                })

                # Add tool result to conversation (truncate if too large)
                if len(tool_output_text) > 5000:
                    tool_output_text = tool_output_text[:5000] + "\n... (output truncated)"
                
                conversation.append({"role": "assistant", "content": response})
                conversation.append({
                    "role": "user",
                    "content": f"Tool '{tool_name}' executed successfully. Output:\n{tool_output_text}\n\nContinue your analysis. If you have enough data, output your analysis_complete response."
                })
            else:
                # No tool call and not complete - ask LLM to continue
                logger.info(f"[{self.agent_type}] No tool call detected, prompting continuation")
                conversation.append({"role": "assistant", "content": response})
                conversation.append({
                    "role": "user",
                    "content": "Your response did not contain a valid tool_call or analysis_complete JSON. Please respond with EXACTLY one of:\n1. {\"tool_call\": {\"name\": \"tool_name\", \"arguments\": {...}}}\n2. {\"analysis_complete\": true, \"summary\": \"...\", \"findings\": [...]}\n\nTry again with the correct format."
                })

        else:
            # Max iterations reached
            logger.warning(f"[{self.agent_type}] Max iterations ({self.max_iterations}) reached")
            # Ask for final summary
            conversation.append({
                "role": "user",
                "content": "Maximum iterations reached. Please provide your final analysis and findings now using the analysis_complete format."
            })
            final_result = await self.llm.chat(
                messages=conversation,
                system_prompt=enhanced_system
            )
            final_response = final_result.get("content", "")
            complete = self._parse_analysis_complete(final_response)
            if complete:
                results["summary"] = complete.get("summary", "")
                results["findings"] = complete.get("findings", [])

        return results

    def _extract_tool_output(self, tool_result: Dict[str, Any]) -> str:
        """Extract readable text from MCP tool result"""
        if isinstance(tool_result, dict):
            # MCP format: {content: [{type: "text", text: "..."}]}
            if "content" in tool_result:
                content = tool_result["content"]
                if isinstance(content, list) and len(content) > 0:
                    texts = []
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            texts.append(item["text"])
                    return "\n".join(texts)
                return str(content)
            # Error format
            if "error" in tool_result:
                return f"Error: {tool_result['error']}"
            return json.dumps(tool_result, indent=2)[:3000]
        return str(tool_result)[:3000]

    async def run_command(self, command: str, toolbox: str = "pentest-tools", timeout: int = 60) -> Dict[str, Any]:
        """Execute a CLI command on a toolbox"""
        start_time = time.time()
        action_id = str(uuid.uuid4())

        result = await self.toolbox_manager.execute_on_toolbox(toolbox, command, timeout)
        duration = int((time.time() - start_time) * 1000)

        action = {
            "id": action_id,
            "action_type": "cli_command",
            "tool_name": toolbox,
            "input": {"command": command},
            "output": result,
            "duration_ms": duration,
            "success": result.get("success", False),
            "timestamp": datetime.utcnow().isoformat()
        }
        self.actions.append(action)
        return result

    async def use_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Use a registered tool"""
        start_time = time.time()
        action_id = str(uuid.uuid4())

        result = await self.tool_registry.execute_tool(tool_name, args)
        duration = int((time.time() - start_time) * 1000)

        action = {
            "id": action_id,
            "action_type": "tool_call",
            "tool_name": tool_name,
            "input": args,
            "output": result,
            "duration_ms": duration,
            "success": result.get("success", False),
            "timestamp": datetime.utcnow().isoformat()
        }
        self.actions.append(action)
        return result

    async def mcp_call(self, toolbox: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool on a toolbox"""
        start_time = time.time()
        action_id = str(uuid.uuid4())

        result = await self.toolbox_manager.mcp_call(toolbox, tool_name, arguments)
        duration = int((time.time() - start_time) * 1000)

        action = {
            "id": action_id,
            "action_type": "mcp_call",
            "tool_name": f"{toolbox}/{tool_name}",
            "input": arguments,
            "output": result,
            "duration_ms": duration,
            "success": "error" not in result,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.actions.append(action)
        return result

    def get_trace(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_type": self.agent_type,
            "engagement_id": self.engagement_id,
            "actions": self.actions,
            "total_actions": len(self.actions),
            "total_duration_ms": sum(a.get("duration_ms", 0) for a in self.actions)
        }
