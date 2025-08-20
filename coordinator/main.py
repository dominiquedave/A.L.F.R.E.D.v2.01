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
            await coordinator.health_check_agents()
            await asyncio.sleep(30)
    
    async def discovery_monitor():
        while True:
            await asyncio.sleep(60)  # Re-discover every 60 seconds
            await coordinator.discover_agents()
    
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