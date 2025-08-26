from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List
import json
import asyncio
import logging
from datetime import datetime
from coordinator.core.coordinator import Coordinator

logger = logging.getLogger(__name__)

class WebInterface:
    """
    Bat-themed web interface for the A.L.F.R.E.D. coordinator.
    Provides a dark, gothic UI for managing agents and executing commands.
    """
    
    def __init__(self, coordinator: Coordinator):
        self.coordinator = coordinator
        self.app = FastAPI(title="A.L.F.R.E.D. Bat Cave Console")
        self.templates = Jinja2Templates(directory="web/templates")
        self.active_websockets: List[WebSocket] = []
        
        # Mount static files
        self.app.mount("/static", StaticFiles(directory="web/static"), name="static")
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup all web interface routes"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            """Main dashboard - The Bat Cave"""
            # Get agent status
            await self.coordinator.health_check_agents(force=True)
            healthy_agents = [agent for agent in self.coordinator.agents.values() if agent.is_healthy]
            total_agents = len(self.coordinator.agents)
            
            return self.templates.TemplateResponse("dashboard.html", {
                "request": request,
                "title": "A.L.F.R.E.D. Bat Cave Console",
                "healthy_agents": len(healthy_agents),
                "total_agents": total_agents,
                "agents": list(self.coordinator.agents.values()),
                "recent_commands": self.coordinator.command_history[-10:] if self.coordinator.command_history else []
            })
        
        @self.app.post("/execute")
        async def execute_command_web(command: str = Form(...)):
            """Execute a command via web interface"""
            try:
                result = await self.coordinator.execute_command(command)
                
                # Broadcast to websockets
                await self._broadcast_to_websockets({
                    "type": "command_result",
                    "command": command,
                    "result": result.model_dump(mode='json'),
                    "timestamp": datetime.now().isoformat()
                })
                
                return JSONResponse({
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                    "execution_time_ms": result.execution_time_ms,
                    "agent_id": result.agent_id
                })
                
            except Exception as e:
                logger.error(f"Web command execution failed: {e}")
                return JSONResponse({
                    "success": False,
                    "error": str(e),
                    "output": "",
                    "execution_time_ms": 0,
                    "agent_id": "none"
                }, status_code=500)
        
        @self.app.get("/agents/status")
        async def get_agents_status():
            """Get current agent status"""
            await self.coordinator.health_check_agents(force=True)
            
            agents_data = []
            for agent in self.coordinator.agents.values():
                agents_data.append({
                    "id": agent.id,
                    "name": agent.name,
                    "os_type": agent.os_type,
                    "host": agent.host,
                    "port": agent.port,
                    "is_healthy": agent.is_healthy,
                    "last_seen": agent.last_seen.isoformat(),
                    "capabilities": agent.capabilities
                })
            
            return JSONResponse({
                "agents": agents_data,
                "healthy_count": sum(1 for agent in self.coordinator.agents.values() if agent.is_healthy),
                "total_count": len(self.coordinator.agents)
            })
        
        @self.app.post("/agents/discover")
        async def discover_agents_endpoint():
            """Trigger agent discovery"""
            try:
                await self.coordinator.discover_agents()
                
                # Broadcast discovery complete
                await self._broadcast_to_websockets({
                    "type": "agents_discovered",
                    "count": len(self.coordinator.agents),
                    "timestamp": datetime.now().isoformat()
                })
                
                return JSONResponse({
                    "success": True,
                    "message": f"Discovery complete. Found {len(self.coordinator.agents)} agents."
                })
            except Exception as e:
                return JSONResponse({
                    "success": False,
                    "error": str(e)
                }, status_code=500)
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket for real-time updates"""
            await websocket.accept()
            self.active_websockets.append(websocket)
            
            try:
                # Send initial status
                await websocket.send_text(json.dumps({
                    "type": "connection_established",
                    "message": "Connected to A.L.F.R.E.D. Bat Cave Console",
                    "timestamp": datetime.now().isoformat()
                }))
                
                # Keep connection alive
                while True:
                    await websocket.receive_text()
                    
            except WebSocketDisconnect:
                self.active_websockets.remove(websocket)
                logger.info("WebSocket client disconnected")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                if websocket in self.active_websockets:
                    self.active_websockets.remove(websocket)
    
    async def _broadcast_to_websockets(self, message: dict):
        """Broadcast message to all active websockets"""
        if not self.active_websockets:
            return
        
        disconnected = []
        for websocket in self.active_websockets:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                disconnected.append(websocket)
        
        # Remove disconnected websockets
        for ws in disconnected:
            if ws in self.active_websockets:
                self.active_websockets.remove(ws)
    
    async def start_periodic_updates(self):
        """Start periodic updates for the web interface"""
        while True:
            try:
                # Health check every 30 seconds
                await self.coordinator.health_check_agents(force=False)
                
                # Broadcast agent status
                await self._broadcast_to_websockets({
                    "type": "agent_status_update",
                    "healthy_count": sum(1 for agent in self.coordinator.agents.values() if agent.is_healthy),
                    "total_count": len(self.coordinator.agents),
                    "timestamp": datetime.now().isoformat()
                })
                
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Periodic update error: {e}")
                await asyncio.sleep(30)