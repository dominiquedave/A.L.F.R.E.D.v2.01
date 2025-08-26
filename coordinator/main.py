# coordinator/main.py
import sys
import os
import argparse
import uvicorn
# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.coordinator import Coordinator
from voice.interface import VoiceInterface
from web.interface import WebInterface
import asyncio

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='A.L.F.R.E.D. Coordinator')
    parser.add_argument('--mode', choices=['voice', 'web', 'hybrid'], default='hybrid',
                        help='Interface mode: voice, web, or hybrid (default)')
    parser.add_argument('--web-port', type=int, default=8000,
                        help='Web interface port (default: 8000)')
    parser.add_argument('--host', default='0.0.0.0',
                        help='Host to bind to (default: 0.0.0.0)')
    args = parser.parse_args()

    # Initialize coordinator
    coordinator = Coordinator()
    
    # Discover agents
    await coordinator.discover_agents()
    
    # Start health monitoring and periodic discovery
    async def health_monitor():
        while True:
            try:
                # Background health checks - no force, respects rate limiting
                await coordinator.health_check_agents(force=False)
            except Exception as e:
                print(f"Background health check error: {e}")
            await asyncio.sleep(45)  # Increased interval to reduce interference
    
    async def discovery_monitor():
        while True:
            await asyncio.sleep(300)  # Re-discover every 5 minutes (reduced frequency)
            try:
                await coordinator.discover_agents()
            except Exception as e:
                print(f"Background discovery error: {e}")
    
    tasks = [health_monitor(), discovery_monitor()]
    
    if args.mode in ['voice', 'hybrid']:
        # Start voice interface
        voice = VoiceInterface(coordinator)
        tasks.append(voice.run_voice_loop())
        print(f"🦇 Voice interface enabled")
    
    if args.mode in ['web', 'hybrid']:
        # Start web interface
        web = WebInterface(coordinator)
        
        # Start web interface periodic updates
        tasks.append(web.start_periodic_updates())
        
        # Start web server
        async def run_web_server():
            config = uvicorn.Config(
                app=web.app,
                host=args.host,
                port=args.web_port,
                log_level="info",
                access_log=False
            )
            server = uvicorn.Server(config)
            print(f"🦇 Bat Cave Console starting at http://{args.host}:{args.web_port}")
            await server.serve()
        
        tasks.append(run_web_server())
    
    if not tasks:
        print("❌ No interface selected!")
        return
    
    print(f"🦇 A.L.F.R.E.D. starting in {args.mode} mode...")
    
    # Run all concurrently
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())