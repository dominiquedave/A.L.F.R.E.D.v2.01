# A.L.F.R.E.D. Coordinator Main Entry Point
#
# This is the primary startup script for the A.L.F.R.E.D. coordinator system.
# Supports multiple interface modes: voice, web, or hybrid operation.

import argparse
import os
import sys
import threading
import time
import webbrowser

import uvicorn

# Add project root to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import asyncio

# Import A.L.F.R.E.D. core components
from core.coordinator import Coordinator
from voice.interface import VoiceInterface
from web.interface import WebInterface


async def main():
    """
    Main entry point for A.L.F.R.E.D. coordinator system.

    Initializes the coordinator, discovers agents, and starts the specified
    interface(s) along with background monitoring tasks.

    Supports three operational modes:
    - voice: Batman-themed voice interface only
    - web: Web dashboard interface only
    - hybrid: Both voice and web interfaces simultaneously

    Also runs background tasks for:
    - Agent health monitoring (every 45 seconds)
    - Periodic agent discovery (every 5 minutes)
    """
    # Parse command line arguments for interface configuration
    parser = argparse.ArgumentParser(
        description="A.L.F.R.E.D. Coordinator - Distributed Agent Management System"
    )
    parser.add_argument(
        "--mode",
        choices=["voice", "web", "hybrid"],
        default="hybrid",
        help="Interface mode: voice, web, or hybrid (default)",
    )
    parser.add_argument(
        "--web-port", type=int, default=8000, help="Web interface port (default: 8000)"
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind web server to (default: 0.0.0.0)"
    )
    args = parser.parse_args()

    # Initialize the A.L.F.R.E.D. coordinator system
    coordinator = Coordinator()

    # Perform initial agent discovery to populate agent registry
    await coordinator.discover_agents()

    # Define background monitoring tasks
    async def health_monitor():
        """
        Continuous health monitoring of all registered agents.
        Runs every 45 seconds to maintain agent status without overwhelming them.
        """
        while True:
            try:
                # Perform non-intrusive health checks (respects rate limiting)
                await coordinator.health_check_agents(force=False)
            except Exception as e:
                print(f"Background health check error: {e}")
            await asyncio.sleep(45)  # Check every 45 seconds

    async def discovery_monitor():
        """
        Periodic agent discovery to find new agents that join the network.
        Runs every 5 minutes to refresh agent registry without excessive network traffic.
        """
        while True:
            await asyncio.sleep(300)  # Wait 5 minutes between discovery cycles
            try:
                # Re-discover agents to find new ones
                await coordinator.discover_agents()
            except Exception as e:
                print(f"Background discovery error: {e}")

    # Initialize task list with background monitoring
    tasks = [health_monitor(), discovery_monitor()]

    # Start voice interface if requested
    if args.mode in ["voice", "hybrid"]:
        voice = VoiceInterface(coordinator)
        tasks.append(voice.run_voice_loop())
        print(f"🦇 Voice interface enabled - Batman-themed voice control active")

    # Start web interface if requested
    if args.mode in ["web", "hybrid"]:
        web = WebInterface(coordinator)

        # Add periodic web updates task
        tasks.append(web.start_periodic_updates())

        # Define web server startup
        async def run_web_server():
            """
            Start the FastAPI web server for the Bat Cave Console.
            """
            config = uvicorn.Config(
                app=web.app,
                host=args.host,
                port=args.web_port,
                log_level="info",
                access_log=False,  # Disable access logs for cleaner output
            )
            server = uvicorn.Server(config)
            print(f"🦇 Bat Cave Console starting at http://{args.host}:{args.web_port}")

            # Launch browser automatically in web and hybrid modes after a short delay
            if args.mode in ["web", "hybrid"]:

                def launch_browser():
                    time.sleep(3)  # Wait 3 seconds for server to fully start
                    browser_url = f"http://127.0.0.1:{args.web_port}"
                    print(f"🌐 Launching browser at {browser_url}")
                    try:
                        webbrowser.open(browser_url)
                    except Exception as e:
                        print(f"⚠️ Could not launch browser automatically: {e}")

                # Launch browser in background thread
                browser_thread = threading.Thread(target=launch_browser, daemon=True)
                browser_thread.start()

            await server.serve()

        tasks.append(run_web_server())

    # Validate that at least one interface is enabled
    if len(tasks) <= 2:  # Only background tasks, no interfaces
        print("❌ No interface selected! Use --mode voice, web, or hybrid")
        return

    print(f"🦇 A.L.F.R.E.D. starting in {args.mode} mode...")
    print(f"🎯 Background monitoring: Health checks every 45s, Discovery every 5min")

    # Run all tasks concurrently (interfaces + background monitoring)
    await asyncio.gather(*tasks)


# Entry point - start A.L.F.R.E.D. coordinator system
if __name__ == "__main__":
    try:
        # Run the main coordinator system
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🦇 A.L.F.R.E.D. shutting down gracefully...")
    except Exception as e:
        print(f"❌ Fatal error starting A.L.F.R.E.D.: {e}")
        raise
