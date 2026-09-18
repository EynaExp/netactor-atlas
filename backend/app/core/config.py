from pydantic_settings import BaseSettings
from pathlib import Path
import os


class Settings(BaseSettings):
    APP_NAME: str = "NetActor"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    DATABASE_URL: str = "sqlite+aiosqlite:///./netactor.db"

    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_API_KEY: str = "ollama"
    LLM_MODEL: str = "llama3.2"

    REPORT_DIR: str = "/home/none/projects/netactor/reports"
    TOOLBOX_CONTAINER: str = "netactor-toolbox"

    MAX_CONCURRENT_AGENTS: int = 5
    DEFAULT_MAX_TOKENS: int = 16384
    DEFAULT_TEMPERATURE: float = 0.7

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


# Default toolbox configurations
DEFAULT_TOOLBOXES = [
    {
        "name": "pentest-tools",
        "executor_type": "docker",
        "container_name": "netactor-toolbox",
        "image": "netactor/toolbox:latest",
        "mcp_url": os.environ.get("MCP_URL", "http://localhost:3001"),
        "working_dir": "/workspace"
    },
    {
        "name": "kali",
        "executor_type": "docker",
        "container_name": "kali-tools",
        "image": "kalilinux/kali-rolling",
        "working_dir": "/workspace"
    }
]
