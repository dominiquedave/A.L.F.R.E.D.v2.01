# coordinator/main.py
import sys
import os
import argparse
# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.coordinator import Coordinator
from voice.interface import VoiceInterface
from web_interface import WebInterface
import asyncio

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='A.L.F.R.E.D. Coordinator')
    parser.add_argument('--interface', choices=['voice', 'web', 'both'], default='voice',
                      help='Interface to use (default: voice)')
    parser.add_argument('--web-port', type=int, default=8000,
                      help='Web interface port (default: 8000)')
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
    
    # Prepare tasks based on interface selection
    tasks = [
        health_monitor(),
        discovery_monitor()
    ]
    
    if args.interface in ['voice', 'both']:
        # Start voice interface
        voice = VoiceInterface(coordinator)
        tasks.append(voice.run_voice_loop())
    
    if args.interface in ['web', 'both']:
        # Start web interface
        web = WebInterface(coordinator, port=args.web_port)
        print(f"🌐 Starting web interface on http://0.0.0.0:{args.web_port}")
        tasks.append(web.start())
    
    # Run all concurrently
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())