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
import logging
import socket
import threading

# Add parent directory to sys.path for shared imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from shared.models import Message, CommandResult, AgentInfo, Permission

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Agent:
    """
    Represents an agent that can execute commands and report system info.
    Exposes a FastAPI app with endpoints for command execution, health, and capabilities.
    """
    def __init__(self, name: str, host: str = "localhost", port: int = 5001):
        # Auto-detect external IP if host is localhost
        if host == "localhost":
            host = self._get_external_ip()
            
        # Initialize agent info and FastAPI app
        self.info = AgentInfo(
            id=f"{platform.node()}-{platform.system()}-{port}",
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
        self._start_broadcast_listener()
    
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
    
    def _get_external_ip(self) -> str:
        """
        Auto-detect the external IP address of this machine.
        Falls back to localhost if detection fails.
        """
        try:
            # Method 1: Connect to remote host to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))  # Google DNS
                external_ip = s.getsockname()[0]
                logger.info(f"Auto-detected external IP: {external_ip}")
                return external_ip
        except Exception as e:
            logger.warning(f"Could not auto-detect external IP: {e}")
            
        try:
            # Method 2: Get hostname IP
            hostname = socket.gethostname()
            external_ip = socket.gethostbyname(hostname)
            if external_ip != "127.0.0.1":
                logger.info(f"Using hostname IP: {external_ip}")
                return external_ip
        except Exception as e:
            logger.warning(f"Could not get hostname IP: {e}")
            
        # Fallback to localhost
        logger.warning("Using localhost as fallback - health checks may fail")
        return "localhost"
    
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
            command = ""
            
            try:
                command = message.payload.get("command", "")
                logger.info(f"Agent {self.info.id} executing command: {command}")
                
                if not self._validate_command(command):
                    logger.warning(f"Agent {self.info.id} blocked dangerous command: {command}")
                    raise HTTPException(status_code=403, detail="Command not allowed")
                
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                execution_time = int((time.time() - start_time) * 1000)
                
                logger.info(f"Agent {self.info.id} command completed in {execution_time}ms, returncode: {result.returncode}")
                
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
                logger.error(f"Agent {self.info.id} command timed out: {command}")
                return CommandResult(
                    success=False,
                    error="Command timed out",
                    execution_time_ms=30000,
                    command=command,
                    agent_id=self.info.id
                )
            except Exception as e:
                # Handle other errors
                logger.error(f"Agent {self.info.id} command failed with exception: {e}")
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
            try:
                return {
                    "status": "healthy",
                    "agent_info": self.info.model_dump(mode='json'),
                    "system_stats": {
                        "cpu_percent": psutil.cpu_percent(),
                        "memory_percent": psutil.virtual_memory().percent,
                        "disk_percent": psutil.disk_usage('/').percent if platform.system() != "Windows" else psutil.disk_usage('C:').percent
                    }
                }
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        @self.app.get("/capabilities")
        async def get_capabilities():
            """
            Return agent info and capabilities.
            """
            try:
                return self.info.model_dump(mode='json')
            except Exception as e:
                logger.error(f"Capabilities endpoint failed: {e}")
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    def _validate_command(self, command: str) -> bool:
        """
        Basic validation to block dangerous commands.
        """
        dangerous_patterns = ["rm -rf", "del /f", "format", "shutdown", "reboot"]
        return not any(pattern in command.lower() for pattern in dangerous_patterns)

    def _start_broadcast_listener(self):
        """
        Start UDP broadcast listener in a background thread to respond to coordinator discovery.
        """
        def broadcast_listener():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('', 5099))  # Listen on broadcast port
                logger.info(f"Agent {self.info.id} listening for broadcasts on port 5099")
                
                while True:
                    try:
                        data, addr = sock.recvfrom(1024)
                        message = json.loads(data.decode())
                        
                        if message.get("type") == "agent_discovery":
                            # Respond with agent info
                            response = {
                                "type": "agent_response",
                                "port": self.info.port,
                                "agent_id": self.info.id,
                                "name": self.info.name,
                                "os_type": self.info.os_type
                            }
                            sock.sendto(json.dumps(response).encode(), addr)
                            logger.info(f"Responded to discovery from {addr[0]}")
                    except Exception as e:
                        logger.debug(f"Broadcast listener error: {e}")
                        
            except Exception as e:
                logger.warning(f"Failed to start broadcast listener: {e}")
        
        # Start listener in daemon thread
        listener_thread = threading.Thread(target=broadcast_listener, daemon=True)
        listener_thread.start()

# Agent startup script
if __name__ == "__main__":
    import uvicorn
    
    agent_name = sys.argv[1] if len(sys.argv) > 1 else "default"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5001
    host = sys.argv[3] if len(sys.argv) > 3 else "localhost"  # Allow manual host override
    
    logger.info(f"Starting agent '{agent_name}' on {host}:{port}")
    
    try:
        agent = Agent(agent_name, host=host, port=port)
        logger.info(f"Agent {agent.info.id} initialized successfully at {agent.info.host}:{agent.info.port}")
        uvicorn.run(agent.app, host="0.0.0.0", port=port)
    except Exception as e:
        logger.error(f"Failed to start agent: {e}")
        raise