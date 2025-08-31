# Core imports for agent functionality
import json
import logging
import os
import platform
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from typing import List

import psutil  # System monitoring (CPU, memory, disk)
from fastapi import FastAPI, HTTPException

# Add project root to Python path for shared model imports
if os.path.dirname(os.path.dirname(os.path.dirname(__file__))) not in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.models import AgentInfo, CommandResult, Message, Permission  # noqa: E402

# Configure logging for agent operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Agent:
    """
    A distributed system agent that executes commands and provides system information.

    The Agent class implements a RESTful API service using FastAPI that can:
    - Execute shell commands securely with validation and timeouts
    - Report system health and performance metrics
    - Advertise capabilities to coordinators
    - Auto-discover network configuration
    - Respond to coordinator discovery broadcasts

    Security features:
    - Command validation to block dangerous operations
    - Execution timeouts to prevent hanging processes
    - Capability-based permissions system

    Network features:
    - Automatic external IP detection for multi-machine setups
    - UDP broadcast listener for coordinator discovery
    - Health monitoring endpoints
    """

    def __init__(self, name: str, host: str = "localhost", port: int = 5001):
        """
        Initialize a new agent with specified configuration.

        Args:
            name (str): Human-readable name for this agent
            host (str): Host to bind to - "localhost" triggers auto-detection
            port (int): Port to listen on for HTTP API requests
        """
        # Auto-detect external IP if host is localhost for multi-machine compatibility
        if host == "localhost":
            host = self._get_external_ip()

        # Create agent information object with system detection
        self.info = AgentInfo(
            id=f"{platform.node()}-{platform.system()}-{port}",  # Unique ID: hostname-OS-port
            name=name,
            os_type=platform.system(),  # Windows, Linux, Darwin, etc.
            capabilities=self._detect_capabilities(),  # OS-specific command capabilities
            permissions=self._get_default_permissions(),  # Default security permissions
            host=host,
            port=port,
            last_seen=datetime.now(),
        )

        # Initialize FastAPI application with agent-specific title
        self.app = FastAPI(title=f"Agent-{name}")
        self._setup_routes()  # Configure REST API endpoints
        self._start_broadcast_listener()  # Start coordinator discovery service

    def _detect_capabilities(self) -> List[str]:
        """
        Auto-detect agent capabilities based on the operating system.

        Determines what command interfaces and operations are available
        on this system. Used by coordinators to route appropriate commands.

        Returns:
            List[str]: List of capability strings (e.g., ['bash', 'file_operations'])
        """
        # Base capabilities available on all platforms
        caps = ["file_operations", "process_info", "system_info"]

        # Add OS-specific command interfaces
        if platform.system() == "Windows":
            caps.extend(["powershell", "cmd"])  # Windows command interfaces
        else:
            caps.extend(["bash", "shell"])  # Unix-like shell interfaces

        return caps

    def _get_default_permissions(self) -> List[Permission]:
        """
        Get default security permissions for this agent.

        Defines what operations this agent is allowed to perform.
        Uses conservative defaults - only read operations are permitted
        initially for security.

        Returns:
            List[Permission]: List of permission enums
        """
        # Conservative default permissions - read-only access
        return [Permission.FILE_READ, Permission.PROCESS_READ, Permission.SYSTEM_READ]

    def _get_external_ip(self) -> str:
        """
        Auto-detect the external IP address for multi-machine coordinator access.

        Tries multiple methods to determine the externally accessible IP:
        1. Connect to remote host (Google DNS) to determine local interface IP
        2. Resolve hostname to IP address
        3. Fallback to localhost (coordinator must be on same machine)

        This is essential for distributed setups where coordinator and agents
        are on different machines.

        Returns:
            str: Best-guess external IP address or "localhost"
        """
        try:
            # Method 1: Connect to external host to determine which local interface is used
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))  # Google DNS - no data sent, just routing
                external_ip = s.getsockname()[0]  # Get local IP of the interface used
                logger.info(f"Auto-detected external IP: {external_ip}")
                return external_ip
        except Exception as e:
            logger.warning(f"Could not auto-detect external IP: {e}")

        try:
            # Method 2: Resolve hostname to IP address
            hostname = socket.gethostname()
            external_ip = socket.gethostbyname(hostname)
            if external_ip != "127.0.0.1":  # Ensure we got a real IP, not loopback
                logger.info(f"Using hostname IP: {external_ip}")
                return external_ip
        except Exception as e:
            logger.warning(f"Could not get hostname IP: {e}")

        # Fallback to localhost - only works if coordinator is on same machine
        logger.warning("Using localhost as fallback - health checks may fail in distributed setup")
        return "localhost"

    def _setup_routes(self):
        """
        Configure FastAPI REST API routes for agent communication.

        Sets up three main endpoints:
        - POST /execute: Execute shell commands sent by coordinator
        - GET /health: Return health status and system metrics
        - GET /capabilities: Return agent capabilities and configuration

        All endpoints include comprehensive error handling and logging.
        """

        @self.app.post("/execute")
        async def execute_command(message: Message):
            """
            Execute a shell command sent by the coordinator.

            Processes command execution requests with security validation,
            timeout handling, and comprehensive result reporting.

            Args:
                message (Message): Message object containing command in payload

            Returns:
                CommandResult: Execution results including output, timing, and status

            Raises:
                HTTPException: 403 if command is blocked by security validation
            """
            start_time = time.time()  # Track execution time for performance monitoring
            command = ""

            try:
                # Extract command from message payload
                command = message.payload.get("command", "")
                logger.info(f"Agent {self.info.id} executing command: {command}")

                # Security validation - block dangerous commands
                if not self._validate_command(command):
                    logger.warning(f"Agent {self.info.id} blocked dangerous command: {command}")
                    raise HTTPException(status_code=403, detail="Command not allowed")

                # Execute command with security constraints
                result = subprocess.run(
                    command,
                    shell=True,  # Enable shell interpretation (required for complex commands)
                    capture_output=True,  # Capture both stdout and stderr
                    text=True,  # Return string output instead of bytes
                    timeout=30,  # 30-second timeout to prevent hanging
                )

                # Calculate execution time in milliseconds for performance tracking
                execution_time = int((time.time() - start_time) * 1000)

                logger.info(
                    f"Agent {self.info.id} command completed in {execution_time}ms, returncode: {result.returncode}"
                )

                # Create structured result object
                return CommandResult(
                    success=result.returncode == 0,  # 0 = success in most shells
                    output=result.stdout,  # Standard output from command
                    error=result.stderr,  # Error output from command
                    execution_time_ms=execution_time,
                    command=command,
                    agent_id=self.info.id,
                )

            except subprocess.TimeoutExpired:
                # Handle command timeout after 30 seconds
                logger.error(f"Agent {self.info.id} command timed out: {command}")
                return CommandResult(
                    success=False,
                    error="Command timed out",
                    execution_time_ms=30000,  # Fixed timeout duration
                    command=command,
                    agent_id=self.info.id,
                )
            except Exception as e:
                # Handle other execution errors (permission denied, command not found, etc.)
                logger.error(f"Agent {self.info.id} command failed with exception: {e}")
                return CommandResult(
                    success=False,
                    error=str(e),
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    command=command,
                    agent_id=self.info.id,
                )

        @self.app.get("/health")
        async def health_check():
            """
            Health check endpoint for coordinator monitoring.

            Returns current agent status and system performance metrics.
            Used by coordinators to determine if agent is responsive and
            monitor system resource utilization.

            Returns:
                dict: Health status with system metrics (CPU, memory, disk usage)
            """
            try:
                # Gather system metrics using psutil
                return {
                    "status": "healthy",
                    "agent_info": self.info.model_dump(mode="json"),
                    "system_stats": {
                        "cpu_percent": psutil.cpu_percent(),  # Current CPU utilization
                        "memory_percent": psutil.virtual_memory().percent,  # RAM usage percentage
                        # Disk usage - handle OS-specific root paths
                        "disk_percent": (
                            psutil.disk_usage("/").percent
                            if platform.system() != "Windows"
                            else psutil.disk_usage("C:").percent
                        ),
                    },
                }
            except Exception as e:
                # Handle errors in health check (disk access issues, etc.)
                logger.error(f"Health check failed: {e}")
                return {"status": "unhealthy", "error": str(e)}

        @self.app.get("/capabilities")
        async def get_capabilities():
            """
            Capabilities endpoint for coordinator agent discovery.

            Returns complete agent information including OS type, capabilities,
            permissions, and network configuration. Used during agent discovery
            and registration process.

            Returns:
                dict: Complete agent information as JSON

            Raises:
                HTTPException: 500 if unable to serialize agent info
            """
            try:
                # Return agent info as JSON-serializable dictionary
                return self.info.model_dump(mode="json")
            except Exception as e:
                logger.error(f"Capabilities endpoint failed: {e}")
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    def _validate_command(self, command: str) -> bool:
        """
        Security validation to prevent execution of dangerous commands.

        Implements a simple blacklist approach to block obviously dangerous
        commands that could harm the system. This is not comprehensive security
        but provides basic protection against accidental destructive operations.

        Args:
            command (str): Shell command to validate

        Returns:
            bool: True if command is allowed, False if blocked

        Note:
            This is basic protection. For production use, consider:
            - Whitelist approach instead of blacklist
            - Sandboxed execution environment
            - More sophisticated pattern matching
        """
        # Basic blacklist of dangerous command patterns
        dangerous_patterns = [
            "rm -rf",  # Unix recursive file deletion
            "del /f",  # Windows forced file deletion
            "format",  # Disk formatting
            "shutdown",  # System shutdown
            "reboot",  # System restart
        ]

        # Check if any dangerous pattern appears in the command (case-insensitive)
        return not any(pattern in command.lower() for pattern in dangerous_patterns)

    def _start_broadcast_listener(self):
        """
        Start UDP broadcast listener for coordinator discovery protocol.

        Runs in a background daemon thread to listen for discovery broadcasts
        from coordinators. When a discovery message is received, responds with
        agent information to enable automatic registration.

        Discovery Protocol:
        1. Coordinator broadcasts: {"type": "agent_discovery", "coordinator": "ALFRED"}
        2. Agent responds with: {"type": "agent_response", "port": 5001, ...}
        3. Coordinator uses response to register agent

        The listener runs continuously until the agent shuts down.
        """

        def broadcast_listener():
            """Background thread function for handling discovery broadcasts"""
            try:
                # Create UDP socket for broadcast communication
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow port reuse
                sock.bind(("", 5099))  # Listen on standard discovery port 5099
                logger.info(f"Agent {self.info.id} listening for broadcasts on port 5099")

                # Main discovery listener loop
                while True:
                    try:
                        # Wait for discovery broadcast from coordinator
                        data, addr = sock.recvfrom(1024)  # 1KB buffer for discovery messages
                        message = json.loads(data.decode())

                        # Check if this is a valid discovery request
                        if message.get("type") == "agent_discovery":
                            # Create discovery response with essential agent info
                            response = {
                                "type": "agent_response",
                                "port": self.info.port,  # Agent's HTTP API port
                                "agent_id": self.info.id,  # Unique agent identifier
                                "name": self.info.name,  # Human-readable name
                                "os_type": self.info.os_type,  # Operating system type
                            }
                            # Send response back to coordinator
                            sock.sendto(json.dumps(response).encode(), addr)
                            logger.info(f"Responded to discovery from {addr[0]}")
                    except Exception as e:
                        # Handle individual message processing errors
                        logger.debug(f"Broadcast listener error: {e}")

            except Exception as e:
                # Handle socket creation or binding errors
                logger.warning(f"Failed to start broadcast listener: {e}")

        # Start discovery listener in daemon thread (dies when main process exits)
        listener_thread = threading.Thread(target=broadcast_listener, daemon=True)
        listener_thread.start()


# Agent startup script - entry point for running agents as standalone processes
if __name__ == "__main__":
    import uvicorn

    # Parse command line arguments with defaults
    agent_name = sys.argv[1] if len(sys.argv) > 1 else "default"  # Agent name
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5001  # HTTP API port
    host = (
        sys.argv[3] if len(sys.argv) > 3 else "localhost"
    )  # Bind host (localhost triggers auto-detection)

    logger.info(f"Starting agent '{agent_name}' on {host}:{port}")

    try:
        # Initialize agent with specified configuration
        agent = Agent(agent_name, host=host, port=port)
        logger.info(
            f"Agent {agent.info.id} initialized successfully at {agent.info.host}:{agent.info.port}"
        )

        # Start FastAPI server with uvicorn
        # Listen on 0.0.0.0 to accept connections from any network interface
        uvicorn.run(agent.app, host="0.0.0.0", port=port)

    except Exception as e:
        logger.error(f"Failed to start agent: {e}")
        raise  # Re-raise exception for proper exit code
