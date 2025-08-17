import asyncio
from datetime import datetime
import json
import platform
import subprocess
import time
from typing import List
import psutil
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
import os

# Add parent directory to sys.path for shared imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from shared.models import Message, CommandResult, AgentInfo, Permission

class Agent:
    """
    Represents an agent that can execute commands and report system info.
    Exposes a FastAPI app with endpoints for command execution, health, and capabilities.
    """
    def __init__(self, name: str, host: str = "localhost", port: int = 5001):
        # Initialize agent info and FastAPI app
        self.info = AgentInfo(
            id=f"{platform.node()}-{port}",
            name=name,
            os_type=platform.system(),
            capabilities=self._detect_capabilities(),
            permissions=self._get_default_permissions(),
            host=host,
            port=port,
            last_seen=datetime.now()
        )
        self.app = FastAPI(title=f"Agent-{name}")
        self._setup_routes()
    
    def _detect_capabilities(self) -> List[str]:
        """
        Detect agent's capabilities based on OS.
        """
        caps = ["file_operations", "process_info", "system_info"]
        if platform.system() == "Windows":
            caps.extend(["powershell", "cmd"])
        else:
            caps.extend(["bash", "shell"])
        return caps
    
    def _get_default_permissions(self) -> List[Permission]:
        """
        Return default permissions for the agent.
        """
        return [Permission.FILE_READ, Permission.PROCESS_READ, Permission.SYSTEM_READ]
    
    def _setup_routes(self):
        """
        Define FastAPI routes for the agent.
        """
        @self.app.post("/execute")
        async def execute_command(message: Message):
            """
            Execute a shell command sent in the message payload.
            Returns a CommandResult.
            """
            start_time = time.time()
            
            try:
                command = message.payload.get("command", "")
                if not self._validate_command(command):
                    raise HTTPException(status_code=403, detail="Command not allowed")
                
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                execution_time = int((time.time() - start_time) * 1000)
                
                return CommandResult(
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr,
                    execution_time_ms=execution_time,
                    command=command,
                    agent_id=self.info.id
                )
            
            except subprocess.TimeoutExpired:
                # Handle command timeout
                return CommandResult(
                    success=False,
                    error="Command timed out",
                    execution_time_ms=30000,
                    command=command,
                    agent_id=self.info.id
                )
            except Exception as e:
                # Handle other errors
                return CommandResult(
                    success=False,
                    error=str(e),
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    command=command,
                    agent_id=self.info.id
                )
        
        @self.app.get("/health")
        async def health_check():
            """
            Return health status and system stats.
            """
            return {
                "status": "healthy",
                "agent_info": self.info.dict(),
                "system_stats": {
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_percent": psutil.disk_usage('/').percent if platform.system() != "Windows" else psutil.disk_usage('C:').percent
                }
            }
        
        @self.app.get("/capabilities")
        async def get_capabilities():
            """
            Return agent info and capabilities.
            """
            return self.info.model_dump(mode='json')
    
    def _validate_command(self, command: str) -> bool:
        """
        Basic validation to block dangerous commands.
        """
        dangerous_patterns = ["rm -rf", "del /f", "format", "shutdown", "reboot"]
        return not any(pattern in command.lower() for pattern in dangerous_patterns)

# Agent startup script
if __name__ == "__main__":
    import uvicorn
    
    agent_name = sys.argv[1] if len(sys.argv) > 1 else "default"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5001
    
    agent = Agent(agent_name, port=port)
    uvicorn.run(agent.app, host="0.0.0.0", port=port)