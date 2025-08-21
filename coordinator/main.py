# coordinator/main.py
import sys
import os
# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.coordinator import Coordinator
from voice.interface import VoiceInterface
import asyncio

async def main():
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
    
    # Start voice interface
    voice = VoiceInterface(coordinator)
    
    # Run all concurrently
    await asyncio.gather(
        health_monitor(),
        discovery_monitor(),
        voice.run_voice_loop()
    )

if __name__ == "__main__":
    asyncio.run(main())