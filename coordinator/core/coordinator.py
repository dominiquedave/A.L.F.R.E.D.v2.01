# Load environment variables for API keys and configuration
from dotenv import load_dotenv
import os
import asyncio
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from openai import OpenAI
from shared.models import AgentInfo, Message, MessageType, CommandResult
import logging
import ipaddress
import socket
import json
import time

# Load environment variables from .env file
load_dotenv()

# Configure logging for coordinator operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Coordinator:
    """
    Central coordinator for managing distributed agents, parsing natural language commands, 
    and delegating execution across multiple systems.
    
    This class serves as the brain of the A.L.F.R.E.D. system, handling:
    - Agent discovery and registration
    - Health monitoring and status tracking
    - Natural language command parsing using OpenAI
    - Command routing and execution
    - Result aggregation and history tracking
    """
    def __init__(self):
        # Dictionary storing all registered agents indexed by their unique ID
        self.agents: Dict[str, AgentInfo] = {}
        
        # OpenAI client configured for OpenRouter API to parse natural language commands
        # Uses environment variable OPENAI_API_KEY for authentication
        self.openai_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
        # Historical record of all executed commands for auditing and debugging
        self.command_history: List[Dict] = []
        
        # Configuration settings for agent discovery loaded from file or defaults
        self.discovery_config = self._load_discovery_config()
        
        # Async lock to prevent concurrent health checks that could overwhelm agents
        self._health_check_lock = asyncio.Lock()
        # Timestamp of last health check for rate limiting
        self._last_health_check = datetime.min
    
    def _load_discovery_config(self) -> Dict:
        """
        Load agent discovery configuration from JSON file or return sensible defaults.
        
        Attempts to load from 'agent_discovery.json' in the coordinator directory.
        Falls back to default configuration if file doesn't exist or can't be parsed.
        
        Returns:
            Dict: Configuration containing discovery settings and network configs
        """
        config_path = os.path.join(os.path.dirname(__file__), '..', 'agent_discovery.json')
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded discovery config from {config_path}")
                return config
        except Exception as e:
            logger.warning(f"Could not load discovery config: {e}")
        
        # Return default configuration with sensible discovery settings
        return {
            "discovery_settings": {
                "use_broadcast": True,      # Enable UDP broadcast discovery
                "scan_network": False,     # Disable network scanning by default
                "broadcast_port": 5099,    # Port for agent discovery broadcasts
                "scan_timeout": 3,         # Timeout for network operations
                "manual_hosts": []         # List of manually specified agent hosts
            },
            "network_configs": {}          # Named network configurations
        }
    
    async def register_agent(self, agent_info: AgentInfo):
        """
        Register a new agent with the coordinator.
        
        Adds the agent to the internal registry, replacing any existing agent
        with the same ID. This handles both new agent registration and
        existing agent re-registration (e.g., after restart).
        
        Args:
            agent_info (AgentInfo): Complete agent information including capabilities and endpoints
        """
        if agent_info.id in self.agents:
            logger.warning(f"Agent {agent_info.id} already exists - replacing with new registration")
        
        self.agents[agent_info.id] = agent_info
        logger.info(f"Registered agent: {agent_info.name} ({agent_info.id}) at {agent_info.host}:{agent_info.port}")
        logger.info(f"Total agents registered: {len(self.agents)} - {list(self.agents.keys())}")
    
    def _get_local_network_range(self) -> List[str]:
        """
        Generate a list of IP addresses in the local network for agent discovery.
        
        Determines the local machine's IP address and generates a list of potential
        agent hosts within the same /24 subnet. Limits to first 20 hosts to avoid
        excessive network traffic.
        
        Returns:
            List[str]: List of IP addresses to scan for agents
        """
        try:
            # Get local IP address
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            # Create IPv4 network object assuming /24 subnet (most common for local networks)
            network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
            
            # Return first 20 host IPs to avoid scanning entire subnet (performance optimization)
            ips = []
            for i, ip in enumerate(network.hosts()):
                if i >= 20:  # Limit scan to first 20 hosts to prevent network flooding
                    break
                ips.append(str(ip))
            
            return ips
        except Exception as e:
            logger.warning(f"Could not determine local network range: {e}")
            return ["127.0.0.1"]

    async def discover_agents_broadcast(self) -> List[str]:
        """
        Discover agents using UDP broadcast discovery protocol.
        
        Sends a broadcast message on the configured port and listens for responses
        from agents. This is the most efficient discovery method as it doesn't
        require knowing specific IP addresses.
        
        Protocol:
        1. Send JSON broadcast message: {"type": "agent_discovery", "coordinator": "ALFRED"}
        2. Listen for JSON responses: {"type": "agent_response", "port": 5001, ...}
        3. Parse responses and return list of discovered agent endpoints
        
        Returns:
            List[str]: List of "host:port" strings for discovered agents
        """
        discovered_hosts = []
        try:
            # Create UDP socket configured for broadcast communication
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # Enable broadcast
            sock.settimeout(3)  # Set 3-second timeout for receive operations
            
            # Create and send discovery message as JSON
            discovery_msg = json.dumps({"type": "agent_discovery", "coordinator": "ALFRED"})
            broadcast_port = self.discovery_config.get('discovery_settings', {}).get('broadcast_port', 5099)
            
            logger.info(f"🔍 Starting UDP broadcast discovery on port {broadcast_port}")
            logger.info(f"📡 Broadcasting discovery message: {discovery_msg}")
            
            try:
                sock.sendto(discovery_msg.encode(), ('<broadcast>', broadcast_port))
                logger.info(f"✅ Broadcast sent successfully to <broadcast>:{broadcast_port}")
            except Exception as broadcast_error:
                logger.error(f"❌ Failed to send broadcast: {broadcast_error}")
                return discovered_hosts
            
            # Listen for agent responses with timeout handling
            start_time = time.time()
            response_count = 0
            logger.info(f"👂 Listening for agent responses for 3 seconds...")
            
            # Listen for responses within 3-second window
            while time.time() - start_time < 3:
                try:
                    # Receive response data from any agent
                    data, addr = sock.recvfrom(1024)  # 1KB buffer for response
                    response_count += 1
                    logger.info(f"📩 Received response #{response_count} from {addr[0]}:{addr[1]}")
                    logger.debug(f"Raw response data: {data.decode()}")
                    
                    response = json.loads(data.decode())
                    logger.info(f"📋 Parsed response: {response}")
                    
                    # Process valid agent responses
                    if response.get("type") == "agent_response":
                        agent_port = response.get('port', 5001)  # Default to port 5001
                        agent_host = f"{addr[0]}:{agent_port}"   # Combine IP and port
                        discovered_hosts.append(agent_host)
                        agent_name = response.get('name', 'unknown')
                        agent_os = response.get('os_type', 'unknown')
                        logger.info(f"✅ Valid agent response: {agent_name} ({agent_os}) at {agent_host}")
                    else:
                        logger.warning(f"⚠️ Invalid response type: {response.get('type')}")
                        
                except socket.timeout:
                    logger.debug("⏰ Socket timeout while listening for responses")
                    break
                except json.JSONDecodeError as json_error:
                    logger.warning(f"❌ Invalid JSON in response from {addr[0]}: {json_error}")
                except Exception as e:
                    logger.warning(f"❌ Error processing response from {addr[0]}: {e}")
                    break
            
            elapsed = time.time() - start_time
            logger.info(f"🏁 Broadcast discovery finished after {elapsed:.1f}s, received {response_count} responses")
            sock.close()
            
        except Exception as e:
            logger.error(f"❌ Broadcast discovery failed with exception: {e}")
            import traceback
            logger.debug(f"Full traceback: {traceback.format_exc()}")
        
        logger.info(f"📊 Broadcast discovery result: {len(discovered_hosts)} agents found: {discovered_hosts}")
        return discovered_hosts

    async def discover_agents(self, host_range: List[str] = None):
        """
        Comprehensive agent discovery using multiple methods and configurations.
        
        This is the main discovery method that orchestrates different discovery strategies:
        1. Environment variable-based host lists (AGENT_DISCOVERY_HOSTS)
        2. Named network configurations from config file
        3. UDP broadcast discovery (if enabled)
        4. Local network scanning (if enabled)
        5. Default localhost fallback
        
        The method uses concurrent HTTP requests to check agent endpoints and
        registers any responding agents with the coordinator.
        
        Args:
            host_range (List[str], optional): Explicit list of "host:port" strings to check.
                                            If None, uses configuration-based discovery.
        """
        logger.info("🚀 Starting agent discovery process...")
        logger.info(f"📋 Current discovery config: {self.discovery_config}")
        
        if not host_range:
            logger.info("🔍 No host_range provided, determining discovery method...")
            
            # Check for environment variable first
            env_hosts = os.getenv('AGENT_DISCOVERY_HOSTS')
            network_name = os.getenv('AGENT_NETWORK_CONFIG')
            
            logger.info(f"🌍 Environment variables: AGENT_DISCOVERY_HOSTS='{env_hosts}', AGENT_NETWORK_CONFIG='{network_name}'")
            
            if env_hosts:
                host_range = [host.strip() for host in env_hosts.split(',')]
                logger.info(f"✅ Using environment variable AGENT_DISCOVERY_HOSTS: {host_range}")
            elif network_name and network_name in self.discovery_config.get('network_configs', {}):
                # Use predefined network configuration
                network_config = self.discovery_config['network_configs'][network_name]
                host_range = network_config.get('hosts', [])
                logger.info(f"✅ Using network config '{network_name}': {host_range}")
            else:
                # Use discovery settings from config
                discovery_settings = self.discovery_config.get('discovery_settings', {})
                logger.info(f"📊 Discovery settings: {discovery_settings}")
                
                use_broadcast_env = os.getenv('AGENT_USE_BROADCAST')
                use_broadcast_config = discovery_settings.get('use_broadcast', True)
                use_broadcast = str(use_broadcast_env if use_broadcast_env is not None else use_broadcast_config).lower() == 'true'
                
                logger.info(f"📻 Broadcast setting - ENV: '{use_broadcast_env}', CONFIG: {use_broadcast_config}, FINAL: {use_broadcast}")
                
                # Start with manual hosts
                manual_hosts = discovery_settings.get('manual_hosts', [])
                host_range = manual_hosts.copy() if manual_hosts else []
                logger.info(f"📝 Starting with manual hosts: {host_range}")
                
                if use_broadcast:
                    logger.info("🔄 Attempting broadcast discovery...")
                    broadcast_hosts = await self.discover_agents_broadcast()
                    if broadcast_hosts:
                        # Add broadcast hosts to manual hosts (avoid duplicates)
                        for bcast_host in broadcast_hosts:
                            if bcast_host not in host_range:
                                host_range.append(bcast_host)
                        logger.info(f"✅ Found {len(broadcast_hosts)} agents via broadcast: {broadcast_hosts}")
                        logger.info(f"🔗 Combined host list: {host_range}")
                    else:
                        logger.warning("⚠️ No agents found via broadcast")
                else:
                    logger.info("❌ Broadcast discovery disabled")
                
                if not host_range:
                    # Auto-discover based on network scanning
                    scan_network_env = os.getenv('AGENT_SCAN_NETWORK')
                    scan_network_config = discovery_settings.get('scan_network', False)
                    scan_network = str(scan_network_env if scan_network_env is not None else scan_network_config).lower() == 'true'
                    
                    logger.info(f"🌐 Network scanning setting - ENV: '{scan_network_env}', CONFIG: {scan_network_config}, FINAL: {scan_network}")
                    
                    if scan_network:
                        logger.info("🔍 Scanning local network for agents...")
                        network_ips = self._get_local_network_range()
                        logger.info(f"📍 Network IPs to scan: {network_ips}")
                        host_range = []
                        # Try common agent ports on each IP
                        for ip in network_ips:
                            host_range.extend([f"{ip}:5001", f"{ip}:5002", f"{ip}:5003"])
                        logger.info(f"🎯 Generated scan targets: {len(host_range)} hosts")
                    else:
                        # If no manual hosts and no scanning, use default localhost
                        if not host_range:
                            host_range = [
                                "localhost:5001", 
                                "localhost:5002",
                                "127.0.0.1:5001", 
                                "127.0.0.1:5002"
                            ]
                            logger.info(f"🏠 Using default localhost targets: {host_range}")
        else:
            logger.info(f"📋 Using provided host_range: {host_range}")
        
        if not host_range:
            logger.error("❌ No hosts to discover! Discovery configuration may be incorrect.")
            return
        
        logger.info(f"🎯 Final discovery target list: {len(host_range)} hosts - {host_range}")
        
        # Use semaphore to limit concurrent HTTP connections (prevent overwhelming network)
        semaphore = asyncio.Semaphore(10)  # Maximum 10 concurrent agent checks
        
        async def check_host(host_port):
            """Check a single host:port for an active agent"""
            async with semaphore:  # Limit concurrent connections
                try:
                    logger.info(f"🔍 Checking agent at {host_port}...")
                    async with aiohttp.ClientSession() as session:
                        # Query agent's capabilities endpoint to verify it's an agent
                        url = f"http://{host_port}/capabilities"
                        logger.debug(f"📡 Making request to: {url}")
                        
                        # Make HTTP request with 3-second timeout
                        async with session.get(url, timeout=3) as resp:
                            logger.debug(f"📊 Response from {host_port}: status={resp.status}")
                            
                            if resp.status == 200:
                                agent_data = await resp.json()
                                logger.info(f"📋 Agent data received from {host_port}: {agent_data}")
                                
                                # Override agent's self-reported address with discovery address
                                # This ensures we use the address that actually worked for discovery
                                discovery_host, discovery_port = host_port.split(':')
                                agent_data['host'] = discovery_host
                                agent_data['port'] = int(discovery_port)
                                
                                # Create AgentInfo object and register with coordinator
                                agent_info = AgentInfo(**agent_data)
                                await self.register_agent(agent_info)
                                logger.info(f"✅ Successfully found and registered agent at {host_port}")
                                return True
                            else:
                                response_text = await resp.text()
                                logger.warning(f"⚠️ Agent at {host_port} returned status {resp.status}: {response_text}")
                                
                except aiohttp.ClientError as http_error:
                    logger.warning(f"🌐 HTTP error connecting to {host_port}: {http_error}")
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ Timeout connecting to {host_port}")
                except Exception as e:
                    logger.warning(f"❌ Unexpected error connecting to {host_port}: {type(e).__name__}: {e}")
                    
                return False
        
        # Run discovery concurrently
        logger.info(f"🚀 Starting concurrent discovery on {len(host_range)} hosts...")
        tasks = [check_host(host_port) for host_port in host_range]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        successful_connections = sum(1 for r in results if r is True)
        failed_connections = sum(1 for r in results if r is False)
        exceptions = sum(1 for r in results if isinstance(r, Exception))
        
        logger.info(f"🏁 Agent discovery complete!")
        logger.info(f"📊 Results: {successful_connections} agents found, {failed_connections} failed connections, {exceptions} exceptions")
        logger.info(f"🤖 Registered agents: {len(self.agents)} total")
        for agent_id, agent_info in self.agents.items():
            logger.info(f"   - {agent_info.name} ({agent_id}) at {agent_info.host}:{agent_info.port} - healthy: {agent_info.is_healthy}")
        
        if exceptions > 0:
            exception_details = [str(r) for r in results if isinstance(r, Exception)]
            logger.warning(f"⚠️ Exceptions encountered: {exception_details}")
    
    async def health_check_agents(self, force: bool = False):
        """
        Perform health checks on all registered agents with retry logic and rate limiting.
        
        Contacts each agent's /health endpoint to verify they are still responsive.
        Implements intelligent retry logic (3 attempts per agent) and only marks
        agents as unhealthy after multiple consecutive failures. Uses rate limiting
        to prevent excessive health checking.
        
        Args:
            force (bool): If True, bypass 10-second rate limiting and run check immediately.
                         Useful for on-demand health checks from UI or critical operations.
        """
        async with self._health_check_lock:  # Ensure only one health check runs at a time
            # Rate limiting: don't check more than once per 10 seconds unless forced
            time_since_last_check = datetime.now() - self._last_health_check
            if not force and time_since_last_check < timedelta(seconds=10):
                logger.debug(f"Health check skipped - last check was {time_since_last_check.total_seconds():.1f}s ago")
                return
            
            logger.debug("Starting health check of all agents...")
            self._last_health_check = datetime.now()
            
            # Iterate over copy of agents dict to handle concurrent modifications
            for agent_id, agent_info in list(self.agents.items()):
                health_check_passed = False
                
                # Try health check with retry logic (3 attempts with 1-second delays)
                for attempt in range(3):
                    try:
                        async with aiohttp.ClientSession() as session:
                            url = f"http://{agent_info.host}:{agent_info.port}/health"
                            logger.debug(f"Health check attempt {attempt + 1}/3 for agent {agent_id} at {url}")
                            
                            # Health check with 5-second timeout per attempt
                            async with session.get(url, timeout=5) as resp:
                                if resp.status == 200:
                                    health_data = await resp.json()
                                    logger.debug(f"Agent {agent_id} health check passed: {health_data.get('status', 'unknown')}")
                                    
                                    # Update agent status if it still exists in registry
                                    if agent_id in self.agents:
                                        self.agents[agent_id].is_healthy = True
                                        self.agents[agent_id].last_seen = datetime.now()
                                    health_check_passed = True
                                    break  # Exit retry loop on success
                                else:
                                    logger.warning(f"Agent {agent_id} health check returned status {resp.status}")
                                    
                    except Exception as e:
                        logger.warning(f"Agent {agent_id} health check attempt {attempt + 1} failed: {e}")
                        if attempt < 2:  # If not the last attempt
                            await asyncio.sleep(1)  # Wait 1 second before retry
                
                # Update agent status based on health check result
                if agent_id in self.agents:
                    if not health_check_passed:
                        self.agents[agent_id].is_healthy = False
                        logger.warning(f"Agent {agent_id} marked as unhealthy after 3 failed attempts")
                    
                    # Log current status
                    status = "healthy" if self.agents[agent_id].is_healthy else "unhealthy"
                    time_since_last_seen = datetime.now() - self.agents[agent_id].last_seen
                    logger.info(f"Agent {agent_id} status: {status}, last seen: {time_since_last_seen.total_seconds():.1f}s ago")
    
    async def test_agent_connectivity(self, agent_id: str) -> Dict:
        """
        Test connectivity to a specific agent for debugging purposes.
        """
        if agent_id not in self.agents:
            return {"error": f"Agent {agent_id} not found"}
            
        agent_info = self.agents[agent_id]
        results = {}
        
        # Test health endpoint
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{agent_info.host}:{agent_info.port}/health"
                async with session.get(url, timeout=5) as resp:
                    results["health_status"] = resp.status
                    results["health_response"] = await resp.json() if resp.status == 200 else await resp.text()
        except Exception as e:
            results["health_error"] = str(e)
        
        # Test capabilities endpoint
        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{agent_info.host}:{agent_info.port}/capabilities"
                async with session.get(url, timeout=5) as resp:
                    results["capabilities_status"] = resp.status
                    results["capabilities_response"] = await resp.json() if resp.status == 200 else await resp.text()
        except Exception as e:
            results["capabilities_error"] = str(e)
            
        return results
    
    async def parse_command(self, user_input: str) -> Dict:
        """
        Parse natural language commands into structured format using OpenAI.
        
        Takes user input in natural language and converts it into a structured
        command format that can be executed by agents. Uses OpenRouter API with
        Google's Gemma model for cost-effective parsing.
        
        The parsing prompt guides the AI to:
        - Identify the type of operation (file_operations, process_info, system_info)
        - Determine target OS compatibility (windows, linux, any)
        - Generate the actual shell command to execute
        - Provide a human-readable description of the operation
        
        Args:
            user_input (str): Natural language command from user
            
        Returns:
            Dict: Structured command with keys: action, target_os, command, description
        """
        try:
            # Create OpenAI chat completion request for command parsing
            response = self.openai_client.chat.completions.create(
                model="google/gemma-3n-e2b-it:free",  # Free Google Gemma model via OpenRouter
                messages=[
                    {
                        "role": "user", 
                        "content": f"""You are a command parser for a distributed system assistant. 
                        Parse user commands into structured format.
                        
                        Available capabilities:
                        - file_operations: list, create, delete, move files
                        - process_info: list processes, check status
                        - system_info: cpu, memory, disk usage
                        
                        Respond ONLY with valid JSON in this exact format:
                        {{
                            "action": "command_type",
                            "target_os": "windows|linux|any", 
                            "command": "actual command to run",
                            "description": "what this will do"
                        }}
                        
                        User command: {user_input}
                        
                        Remember: Respond with ONLY the JSON object, no other text."""
                    }
                ],
                max_tokens=200,    # Limit response length for cost control
                temperature=0.1    # Low temperature for consistent, deterministic parsing
            )
            
            content = response.choices[0].message.content.strip()
            
            # Log the raw AI response for debugging purposes
            logger.debug(f"Raw AI response: {content}")
            
            # Handle empty response from AI model
            if not content:
                raise ValueError("Empty response from AI model")
            
            # Clean up response if it contains markdown JSON blocks
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            
            # Parse the JSON response from the AI model
            import json
            return json.loads(content)
        
        except json.JSONDecodeError as e:
            # Handle malformed JSON responses from AI model
            logger.error(f"JSON parsing failed. Raw response: {response.choices[0].message.content}")
            logger.error(f"JSON error: {e}")
            # Fallback to direct command execution
            return {
                "action": "unknown",
                "target_os": "any", 
                "command": user_input,
                "description": "Direct command execution (JSON parse failed)"
            }
        except Exception as e:
            # Handle any other errors in command parsing (API failures, etc.)
            logger.error(f"Command parsing failed: {e}")
            # Fallback to direct command execution
            return {
                "action": "unknown",
                "target_os": "any",
                "command": user_input,
                "description": "Direct command execution"
            }
    
    def select_agent(self, parsed_command: Dict) -> Optional[AgentInfo]:
        """
        Select the optimal agent to execute a parsed command.
        
        Uses intelligent agent selection based on:
        1. Agent health status (only healthy agents considered)
        2. OS compatibility (matches target_os if specified)
        3. Available capabilities (future enhancement)
        4. Load balancing (currently simple first-match selection)
        
        Args:
            parsed_command (Dict): Parsed command containing target_os and action
            
        Returns:
            Optional[AgentInfo]: Selected agent info, or None if no suitable agent found
        """
        target_os = parsed_command.get("target_os", "any")
        action = parsed_command.get("action", "")
        
        # Filter to only healthy agents that can accept commands
        healthy_agents = [agent for agent in self.agents.values() if agent.is_healthy]
        
        if not healthy_agents:
            logger.warning("No healthy agents available for command execution")
            return None
        
        # Prefer OS-specific agents if target OS is specified
        if target_os != "any":
            os_agents = [agent for agent in healthy_agents if agent.os_type.lower() == target_os.lower()]
            if os_agents:
                # TODO: Implement load balancing instead of simple first-match
                return os_agents[0]
            else:
                logger.warning(f"No healthy {target_os} agents found, will try any available agent")
        
        # Fallback to first available healthy agent
        return healthy_agents[0]
    
    async def execute_command(self, user_input: str) -> CommandResult:
        """
        Execute a natural language command through the complete A.L.F.R.E.D. pipeline.
        
        This is the main entry point for command execution that orchestrates:
        1. Natural language parsing (convert to structured command)
        2. Agent selection (find best agent for the command)
        3. Command transmission (send HTTP request to selected agent)
        4. Result processing (parse response and store in history)
        5. Error handling (graceful failure with informative messages)
        
        Args:
            user_input (str): Natural language command from user
            
        Returns:
            CommandResult: Execution result including success status, output, timing, etc.
        """
        logger.info(f"Executing command: {user_input}")

        # Step 1: Parse natural language into structured command
        parsed_command = await self.parse_command(user_input)
        logger.info(f"Parsed command: {parsed_command}")

        # Step 2: Select best available agent for this command
        agent = self.select_agent(parsed_command)
        if not agent:
            # No suitable agents available - return error result
            return CommandResult(
                success=False,
                error="No healthy agents available",
                execution_time_ms=0,
                command=user_input,
                agent_id="none"
            )

        # Step 3: Create message object for agent communication
        message = Message(
            type=MessageType.COMMAND,
            source="coordinator",
            target=agent.id,
            payload={"command": parsed_command["command"]}
        )

        try:
            # Step 4: Send HTTP request to selected agent's execute endpoint
            async with aiohttp.ClientSession() as session:
                url = f"http://{agent.host}:{agent.port}/execute"
                async with session.post(url, json=message.model_dump(mode='json')) as resp:
                    if resp.status == 200:
                        # Parse successful response into CommandResult object
                        result_data = await resp.json()
                        result = CommandResult(**result_data)

                        # Step 5: Store execution details in command history for auditing
                        self.command_history.append({
                            "timestamp": datetime.now().isoformat(),
                            "user_input": user_input,
                            "parsed_command": parsed_command,
                            "agent_used": agent.name,
                            "result": result.model_dump(mode='json')
                        })

                        return result
                    else:
                        error_text = await resp.text()
                        return CommandResult(
                            success=False,
                            error=f"Agent returned status {resp.status}: {error_text}",
                            execution_time_ms=0,
                            command=user_input,
                            agent_id=agent.id
                        )

        except Exception as e:
            return CommandResult(
                success=False,
                error=f"Failed to communicate with agent: {str(e)}",
                execution_time_ms=0,
                command=user_input,
                agent_id=agent.id
            )