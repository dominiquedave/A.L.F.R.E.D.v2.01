# FastAPI web interface imports
import asyncio
import json
import logging
from datetime import datetime
from typing import List

from fastapi import FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from coordinator.core.coordinator import Coordinator

# Configure logging for web interface
logger = logging.getLogger(__name__)


class WebInterface:
    """
    Batman/Bat Cave themed web interface for A.L.F.R.E.D. coordinator management.

    Provides a comprehensive web-based dashboard with:
    - Dark, gothic Batman-inspired UI theme
    - Real-time agent status monitoring via WebSockets
    - Command execution interface with live results
    - Agent discovery and health management
    - Command history and system metrics

    Features:
    - Responsive design for desktop and mobile
    - WebSocket connections for real-time updates
    - RESTful API endpoints for all operations
    - Integration with coordinator's agent management
    """

    def __init__(self, coordinator: Coordinator):
        """
        Initialize the web interface with Batman-themed styling.

        Args:
            coordinator (Coordinator): The A.L.F.R.E.D. coordinator instance to manage
        """
        self.coordinator = coordinator
        self.app = FastAPI(title="A.L.F.R.E.D. Bat Cave Console")
        self.templates = Jinja2Templates(directory="web/templates")  # HTML template engine
        self.active_websockets: List[WebSocket] = []  # Track active WebSocket connections

        # Mount static files (CSS, JavaScript, images) at /static URL path
        self.app.mount("/static", StaticFiles(directory="web/static"), name="static")

        # Configure all HTTP and WebSocket routes
        self._setup_routes()

    def _setup_routes(self):
        """
        Configure all FastAPI routes for the web interface.

        Sets up:
        - GET /: Main dashboard page with agent status and controls
        - POST /execute: Command execution endpoint
        - GET /agents/status: Agent status API endpoint
        - POST /agents/discover: Agent discovery trigger
        - WebSocket /ws: Real-time updates and notifications
        """

        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            """
            Main dashboard route - The Bat Cave command center.

            Renders the primary web interface with:
            - Real-time agent status overview
            - Agent health statistics and listings
            - Recent command execution history
            - System controls and command interface

            Args:
                request (Request): FastAPI request object

            Returns:
                TemplateResponse: Rendered dashboard.html with context data
            """
            # Calculate agent statistics from current data (no forced health check to avoid conflicts)
            healthy_agents = [
                agent for agent in self.coordinator.agents.values() if agent.is_healthy
            ]
            total_agents = len(self.coordinator.agents)

            # Render dashboard template with current system state
            return self.templates.TemplateResponse(
                "dashboard.html",
                {
                    "request": request,
                    "title": "A.L.F.R.E.D. Bat Cave Console",
                    "healthy_agents": len(healthy_agents),
                    "total_agents": total_agents,
                    "agents": list(self.coordinator.agents.values()),
                    "recent_commands": (
                        self.coordinator.command_history[-10:]
                        if self.coordinator.command_history
                        else []
                    ),
                },
            )

        @self.app.post("/execute")
        async def execute_command_web(command: str = Form(...)):
            """
            Execute a command through the web interface.

            Processes command execution requests from the web UI, executes them
            through the coordinator, and broadcasts results via WebSocket to all
            connected clients for real-time updates.

            Args:
                command (str): Natural language command from web form

            Returns:
                JSONResponse: Execution results including success status, output, and timing
            """
            try:
                # Execute command through coordinator pipeline
                result = await self.coordinator.execute_command(command)

                # Broadcast execution result to all connected WebSocket clients
                await self._broadcast_to_websockets(
                    {
                        "type": "command_result",
                        "command": command,
                        "result": result.model_dump(mode="json"),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                # Return structured JSON response for web interface
                return JSONResponse(
                    {
                        "success": result.success,
                        "output": result.output,
                        "error": result.error,
                        "execution_time_ms": result.execution_time_ms,
                        "agent_id": result.agent_id,
                    }
                )

            except Exception as e:
                # Handle command execution errors gracefully
                logger.error(f"Web command execution failed: {e}")
                return JSONResponse(
                    {
                        "success": False,
                        "error": str(e),
                        "output": "",
                        "execution_time_ms": 0,
                        "agent_id": "none",
                    },
                    status_code=500,
                )

        @self.app.get("/agents/status")
        async def get_agents_status():
            """
            API endpoint to retrieve current agent status information.

            Performs fresh health checks on all agents and returns detailed
            status information including health metrics, capabilities, and
            connection details. Used by the web UI for dynamic updates.

            Returns:
                JSONResponse: Agent status data with health counts and agent details
            """
            # Build detailed agent information for web UI (use existing data to avoid conflicts)
            # Note: Periodic background task handles regular health checks
            agents_data = []
            for agent in self.coordinator.agents.values():
                agents_data.append(
                    {
                        "id": agent.id,
                        "name": agent.name,
                        "os_type": agent.os_type,
                        "host": agent.host,
                        "port": agent.port,
                        "is_healthy": agent.is_healthy,
                        "last_seen": agent.last_seen.isoformat(),  # Convert datetime to ISO string
                        "capabilities": agent.capabilities,
                    }
                )

            # Return structured response with agent details and summary statistics
            return JSONResponse(
                {
                    "agents": agents_data,
                    "healthy_count": sum(
                        1 for agent in self.coordinator.agents.values() if agent.is_healthy
                    ),
                    "total_count": len(self.coordinator.agents),
                }
            )

        @self.app.post("/agents/discover")
        async def discover_agents_endpoint():
            """
            API endpoint to trigger manual agent discovery.

            Initiates the full agent discovery process including broadcast
            discovery, network scanning, and agent registration. Useful for
            refreshing the agent list when new agents are added to the network.

            Returns:
                JSONResponse: Discovery results with agent count and status
            """
            try:
                # Trigger full agent discovery process
                await self.coordinator.discover_agents()

                # Notify all WebSocket clients of discovery completion
                await self._broadcast_to_websockets(
                    {
                        "type": "agents_discovered",
                        "count": len(self.coordinator.agents),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                # Return success response with discovery results
                return JSONResponse(
                    {
                        "success": True,
                        "message": f"Discovery complete. Found {len(self.coordinator.agents)} agents.",
                    }
                )
            except Exception as e:
                # Handle discovery errors gracefully
                return JSONResponse({"success": False, "error": str(e)}, status_code=500)

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """
            WebSocket endpoint for real-time web interface updates.

            Establishes persistent bidirectional communication between the web UI
            and the coordinator for live updates including:
            - Command execution results
            - Agent status changes
            - Discovery completion notifications
            - System health updates

            The connection is maintained until client disconnects or errors occur.

            Args:
                websocket (WebSocket): FastAPI WebSocket connection object
            """
            # Accept WebSocket connection and add to active connections list
            await websocket.accept()
            self.active_websockets.append(websocket)

            try:
                # Send welcome message to confirm connection establishment
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "connection_established",
                            "message": "Connected to A.L.F.R.E.D. Bat Cave Console",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                )

                # Keep connection alive by continuously listening for messages
                # (Client may send keepalive pings or other messages)
                while True:
                    await websocket.receive_text()

            except WebSocketDisconnect:
                # Handle graceful client disconnection
                self.active_websockets.remove(websocket)
                logger.info("WebSocket client disconnected")
            except Exception as e:
                # Handle other WebSocket errors (network issues, etc.)
                logger.error(f"WebSocket error: {e}")
                if websocket in self.active_websockets:
                    self.active_websockets.remove(websocket)

    async def _broadcast_to_websockets(self, message: dict):
        """
        Broadcast a message to all active WebSocket connections.

        Sends JSON messages to all connected web clients simultaneously.
        Handles connection failures gracefully by removing disconnected
        clients from the active connections list.

        Args:
            message (dict): Message dictionary to broadcast (will be JSON encoded)
        """
        # Skip if no active connections
        if not self.active_websockets:
            return

        # Track connections that fail during broadcast
        disconnected = []
        for websocket in self.active_websockets:
            try:
                # Send JSON-encoded message to client
                await websocket.send_text(json.dumps(message))
            except Exception:
                # Mark for removal if send fails (connection broken)
                disconnected.append(websocket)

        # Clean up disconnected WebSocket connections
        for ws in disconnected:
            if ws in self.active_websockets:
                self.active_websockets.remove(ws)

    async def start_periodic_updates(self):
        """
        Start background task for periodic web interface updates.

        Runs continuously to provide regular status updates to web clients:
        - Waits 1 minute before starting health checks to avoid startup conflicts
        - Performs health checks on all agents every 60 seconds
        - Broadcasts agent status updates via WebSocket
        - Maintains real-time dashboard information

        This task runs in the background alongside the web server.
        """
        # Wait 1 minute before starting periodic health checks to avoid conflicts during startup
        logger.info("Web interface waiting 60 seconds before starting periodic health checks...")
        await asyncio.sleep(60)
        logger.info("Web interface starting periodic health checks (every 60 seconds)")

        while True:
            try:
                # Perform routine health checks (respects rate limiting)
                await self.coordinator.health_check_agents(force=False)

                # Broadcast current agent status to all connected clients
                await self._broadcast_to_websockets(
                    {
                        "type": "agent_status_update",
                        "healthy_count": sum(
                            1 for agent in self.coordinator.agents.values() if agent.is_healthy
                        ),
                        "total_count": len(self.coordinator.agents),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                # Wait 60 seconds before next update cycle
                await asyncio.sleep(60)

            except Exception as e:
                # Handle errors gracefully and continue periodic updates
                logger.error(f"Periodic update error: {e}")
                await asyncio.sleep(60)  # Still wait before retry
