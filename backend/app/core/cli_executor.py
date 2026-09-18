from typing import Dict, Any, Optional
from enum import Enum
import asyncio
import json
import httpx
import asyncssh
from dataclasses import dataclass


class ExecutorType(str, Enum):
    LOCAL = "local"
    DOCKER = "docker"
    SSH = "ssh"


@dataclass
class ToolboxConfig:
    name: str
    executor_type: ExecutorType
    # Docker settings
    container_name: Optional[str] = None
    image: Optional[str] = None
    # SSH settings
    ssh_host: Optional[str] = None
    ssh_port: int = 22
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_key_path: Optional[str] = None
    # MCP settings
    mcp_url: Optional[str] = None  # e.g., http://localhost:3001/mcp
    # Common
    working_dir: str = "/workspace"


class CLIExecutor:
    """Executes CLI commands locally, in Docker containers, or via SSH"""

    def __init__(self, config: ToolboxConfig):
        self.config = config
        self.ssh_client: Optional[asyncssh.SSHClientConnection] = None

    async def execute(self, command: str, timeout: int = 60) -> Dict[str, Any]:
        if self.config.executor_type == ExecutorType.LOCAL:
            return await self._execute_local(command, timeout)
        elif self.config.executor_type == ExecutorType.DOCKER:
            return await self._execute_docker(command, timeout)
        elif self.config.executor_type == ExecutorType.SSH:
            return await self._execute_ssh(command, timeout)
        else:
            return {"error": f"Unknown executor type: {self.config.executor_type}"}

    async def _execute_local(self, command: str, timeout: int) -> Dict[str, Any]:
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            return {
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
                "return_code": process.returncode,
                "success": process.returncode == 0
            }
        except asyncio.TimeoutError:
            return {"error": f"Command timed out after {timeout}s", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    async def _execute_docker(self, command: str, timeout: int) -> Dict[str, Any]:
        container = self.config.container_name
        if not container:
            return {"error": "No container name configured", "success": False}

        docker_cmd = f"docker exec {container} {command}"
        return await self._execute_local(docker_cmd, timeout)

    async def _get_ssh_client(self) -> asyncssh.SSHClientConnection:
        if self.ssh_client and not self.ssh_client.closed:
            return self.ssh_client

        connect_kwargs = {
            "host": self.config.ssh_host,
            "port": self.config.ssh_port,
            "username": self.config.ssh_user,
        }

        if self.config.ssh_key_path:
            connect_kwargs["client_keys"] = [self.config.ssh_key_path]
        elif self.config.ssh_password:
            connect_kwargs["password"] = self.config.ssh_password

        self.ssh_client = await asyncssh.connect(**connect_kwargs)
        return self.ssh_client

    async def _execute_ssh(self, command: str, timeout: int) -> Dict[str, Any]:
        try:
            client = await self._get_ssh_client()
            result = await asyncio.wait_for(
                client.run(command, cwd=self.config.working_dir),
                timeout=timeout
            )
            return {
                "stdout": str(result.stdout),
                "stderr": str(result.stderr),
                "return_code": result.exit_status,
                "success": result.exit_status == 0
            }
        except asyncio.TimeoutError:
            return {"error": f"Command timed out after {timeout}s", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    async def close(self):
        if self.ssh_client and not self.ssh_client.closed:
            self.ssh_client.close()
            self.ssh_client = None


class MCPClient:
    """Connects to MCP servers running in toolbox containers"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session_id: Optional[str] = None
        self.tools: list = []

    async def initialize(self) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "netactor", "version": "1.0.0"}
                    }
                },
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                data = response.json()
                self.session_id = response.headers.get("mcp-session-id")
                return data.get("result", {})
            return {"error": f"MCP init failed: {response.status_code}"}

    async def list_tools(self) -> list:
        async with httpx.AsyncClient() as client:
            headers = {"Content-Type": "application/json"}
            if self.session_id:
                headers["mcp-session-id"] = self.session_id

            response = await client.post(
                f"{self.base_url}",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {}
                },
                headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                self.tools = data.get("result", {}).get("tools", [])
                return self.tools
            return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"MCP call: {tool_name}({arguments})")
        
        async with httpx.AsyncClient() as client:
            headers = {"Content-Type": "application/json"}
            if self.session_id:
                headers["mcp-session-id"] = self.session_id

            try:
                response = await client.post(
                    f"{self.base_url}",
                    json={
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": tool_name,
                            "arguments": arguments
                        }
                    },
                    headers=headers,
                    timeout=120
                )
                if response.status_code == 200:
                    data = response.json()
                    result = data.get("result", {})
                    logger.info(f"MCP result: {tool_name} -> success")
                    return result
                logger.error(f"MCP call failed: {response.status_code}")
                return {"error": f"MCP call failed: {response.status_code}"}
            except Exception as e:
                logger.error(f"MCP call exception: {e}")
                return {"error": str(e)}

    async def execute_command(self, command: str) -> Dict[str, Any]:
        return await self.call_tool("execute", {"command": command})


class ToolboxManager:
    """Manages multiple toolbox connections"""

    def __init__(self):
        self.toolboxes: Dict[str, ToolboxConfig] = {}
        self.executors: Dict[str, CLIExecutor] = {}
        self.mcp_clients: Dict[str, MCPClient] = {}

    def register_toolbox(self, config: ToolboxConfig):
        self.toolboxes[config.name] = config

    def get_executor(self, toolbox_name: str) -> Optional[CLIExecutor]:
        if toolbox_name not in self.executors:
            config = self.toolboxes.get(toolbox_name)
            if config:
                self.executors[toolbox_name] = CLIExecutor(config)
        return self.executors.get(toolbox_name)

    def get_mcp_client(self, toolbox_name: str) -> Optional[MCPClient]:
        if toolbox_name not in self.mcp_clients:
            config = self.toolboxes.get(toolbox_name)
            if config and config.mcp_url:
                self.mcp_clients[toolbox_name] = MCPClient(config.mcp_url)
        return self.mcp_clients.get(toolbox_name)

    async def execute_on_toolbox(self, toolbox_name: str, command: str, timeout: int = 60) -> Dict[str, Any]:
        executor = self.get_executor(toolbox_name)
        if not executor:
            return {"error": f"Toolbox '{toolbox_name}' not found", "success": False}
        return await executor.execute(command, timeout)

    async def mcp_call(self, toolbox_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        client = self.get_mcp_client(toolbox_name)
        if not client:
            return {"error": f"MCP client for '{toolbox_name}' not found"}
        return await client.call_tool(tool_name, arguments)

    async def close_all(self):
        for executor in self.executors.values():
            await executor.close()
        self.executors.clear()
        self.mcp_clients.clear()


# Global toolbox manager
toolbox_manager = ToolboxManager()
