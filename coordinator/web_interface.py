from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import json
from datetime import datetime
from typing import Optional
from .core.coordinator import Coordinator
import asyncio
import uvicorn

class WebInterface:
    """
    Web interface for the A.L.F.R.E.D. coordinator system.
    Provides a dashboard for monitoring agents and executing commands.
    """
    def __init__(self, coordinator: Coordinator, port: int = 8000):
        self.coordinator = coordinator
        self.port = port
        self.app = FastAPI(title="A.L.F.R.E.D. Web Interface")
        
        # Setup static files and templates
        self._setup_directories()
        self.app.mount("/static", StaticFiles(directory="web/static"), name="static")
        self.templates = Jinja2Templates(directory="web/templates")
        
        # Setup routes
        self._setup_routes()
    
    def _setup_directories(self):
        """Create necessary directories for web assets"""
        os.makedirs("web/static", exist_ok=True)
        os.makedirs("web/templates", exist_ok=True)
    
    def _setup_routes(self):
        """Setup FastAPI routes for the web interface"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            """Main dashboard page"""
            agents = list(self.coordinator.agents.values())
            healthy_count = sum(1 for agent in agents if agent.is_healthy)
            
            return self.templates.TemplateResponse("dashboard.html", {
                "request": request,
                "agents": agents,
                "agent_count": len(agents),
                "healthy_count": healthy_count,
                "command_history": self.coordinator.command_history[-10:]  # Last 10 commands
            })
        
        @self.app.get("/agents", response_class=HTMLResponse)
        async def agents_page(request: Request):
            """Agents management page"""
            agents = list(self.coordinator.agents.values())
            return self.templates.TemplateResponse("agents.html", {
                "request": request,
                "agents": agents
            })
        
        @self.app.get("/command", response_class=HTMLResponse)
        async def command_page(request: Request):
            """Command execution page"""
            return self.templates.TemplateResponse("command.html", {
                "request": request,
                "agents": list(self.coordinator.agents.values())
            })
        
        @self.app.post("/execute")
        async def execute_command(command: str = Form(...)):
            """Execute a command via the web interface"""
            if not command.strip():
                raise HTTPException(status_code=400, detail="Command cannot be empty")
            
            result = await self.coordinator.execute_command(command)
            
            # Redirect to results page with result data
            return RedirectResponse(url=f"/result?success={result.success}&output={result.output or ''}&error={result.error or ''}&command={command}", status_code=303)
        
        @self.app.get("/result", response_class=HTMLResponse)
        async def result_page(request: Request, success: bool, command: str, output: str = "", error: str = ""):
            """Display command execution results"""
            return self.templates.TemplateResponse("result.html", {
                "request": request,
                "success": success,
                "command": command,
                "output": output,
                "error": error
            })
        
        @self.app.get("/api/agents")
        async def api_agents():
            """API endpoint to get agent status (for AJAX updates)"""
            agents = []
            for agent in self.coordinator.agents.values():
                agents.append({
                    "id": agent.id,
                    "name": agent.name,
                    "os_type": agent.os_type,
                    "host": agent.host,
                    "port": agent.port,
                    "is_healthy": agent.is_healthy,
                    "last_seen": agent.last_seen.isoformat(),
                    "capabilities": agent.capabilities
                })
            return {"agents": agents}
        
        @self.app.post("/api/discover")
        async def api_discover():
            """API endpoint to trigger agent discovery"""
            await self.coordinator.discover_agents()
            return {"status": "discovery_initiated"}
        
        @self.app.post("/api/health-check")
        async def api_health_check():
            """API endpoint to trigger health check"""
            await self.coordinator.health_check_agents(force=True)
            return {"status": "health_check_completed"}
    
    async def start(self):
        """Start the web interface server"""
        config = uvicorn.Config(self.app, host="0.0.0.0", port=self.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

# Main function to run web interface standalone
async def main():
    coordinator = Coordinator()
    await coordinator.discover_agents()
    
    web_interface = WebInterface(coordinator)
    
    # Run web interface and periodic agent monitoring concurrently
    async def monitor_agents():
        while True:
            try:
                await coordinator.health_check_agents(force=False)
            except Exception as e:
                print(f"Health check error: {e}")
            await asyncio.sleep(30)
    
    await asyncio.gather(
        web_interface.start(),
        monitor_agents()
    )

if __name__ == "__main__":
    asyncio.run(main())