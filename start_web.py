#!/usr/bin/env python3
"""
A.L.F.R.E.D. Web Interface Launcher
Simple script to start the web interface with proper configuration.
"""

import sys
import os
import asyncio

# Add project root to Python path
sys.path.append(os.path.dirname(__file__))

from coordinator.core.coordinator import Coordinator
from coordinator.web_interface import WebInterface

async def main():
    print("🤖 A.L.F.R.E.D. Web Interface Starting...")
    print("=====================================")
    
    try:
        # Initialize coordinator
        print("📋 Initializing coordinator...")
        coordinator = Coordinator()
        
        # Discover agents
        print("🔍 Discovering agents...")
        await coordinator.discover_agents()
        
        # Initialize web interface
        web_port = 8000
        print(f"🌐 Starting web interface on port {web_port}...")
        web_interface = WebInterface(coordinator, port=web_port)
        
        # Start background monitoring
        async def monitor_agents():
            while True:
                try:
                    await coordinator.health_check_agents(force=False)
                except Exception as e:
                    print(f"⚠️  Health check error: {e}")
                await asyncio.sleep(30)
        
        async def periodic_discovery():
            while True:
                await asyncio.sleep(300)  # Every 5 minutes
                try:
                    await coordinator.discover_agents()
                except Exception as e:
                    print(f"⚠️  Discovery error: {e}")
        
        print(f"✅ Web interface ready at: http://localhost:{web_port}")
        print("📊 Dashboard: http://localhost:8000")
        print("🤖 Agents: http://localhost:8000/agents")  
        print("⚡ Commands: http://localhost:8000/command")
        print("\n🔄 Starting background services...")
        
        # Run web interface and monitoring concurrently
        await asyncio.gather(
            web_interface.start(),
            monitor_agents(),
            periodic_discovery()
        )
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down A.L.F.R.E.D. web interface...")
    except Exception as e:
        print(f"❌ Error starting web interface: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())