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

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Coordinator:
    """
    Central coordinator for managing agents, parsing commands, and delegating execution.
    """
    def __init__(self):
        # Registered agents by ID
        self.agents: Dict[str, AgentInfo] = {}
        # OpenAI client for command parsing
        self.openai_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv('OPENAI_API_KEY')
        )
        # History of executed commands
        self.command_history: List[Dict] = []
        # Load discovery configuration
        self.discovery_config = self._load_discovery_config()
    
    def _load_discovery_config(self) -> Dict:
        """
        Load agent discovery configuration from file or environment.
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
        
        # Return default config
        return {
            "discovery_settings": {
                "use_broadcast": True,
                "scan_network": False,
                "broadcast_port": 5099,
                "scan_timeout": 3,
                "manual_hosts": []
            },
            "network_configs": {}
        }
    
    async def register_agent(self, agent_info: AgentInfo):
        """Register a new agent"""
        if agent_info.id in self.agents:
            logger.warning(f"Agent {agent_info.id} already exists - replacing with new registration")
        
        self.agents[agent_info.id] = agent_info
        logger.info(f"Registered agent: {agent_info.name} ({agent_info.id}) at {agent_info.host}:{agent_info.port}")
        logger.info(f"Total agents registered: {len(self.agents)} - {list(self.agents.keys())}")
    
    def _get_local_network_range(self) -> List[str]:
        """
        Get the local network range for scanning.
        """
        try:
            # Get local IP address
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            # Create network object (assuming /24 subnet)
            network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
            
            # Return first 20 IPs to avoid scanning entire subnet
            ips = []
            for i, ip in enumerate(network.hosts()):
                if i >= 20:  # Limit scan to first 20 hosts
                    break
                ips.append(str(ip))
            
            return ips
        except Exception as e:
            logger.warning(f"Could not determine local network range: {e}")
            return ["127.0.0.1"]

    async def discover_agents_broadcast(self) -> List[str]:
        """
        Discover agents using UDP broadcast.
        Sends broadcast message and waits for agent responses.
        """
        discovered_hosts = []
        try:
            # Create UDP socket for broadcast
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(3)
            
            # Broadcast discovery message
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
            
            # Listen for responses
            start_time = time.time()
            response_count = 0
            logger.info(f"👂 Listening for agent responses for 3 seconds...")
            
            while time.time() - start_time < 3:  # Listen for 3 seconds
                try:
                    data, addr = sock.recvfrom(1024)
                    response_count += 1
                    logger.info(f"📩 Received response #{response_count} from {addr[0]}:{addr[1]}")
                    logger.debug(f"Raw response data: {data.decode()}")
                    
                    response = json.loads(data.decode())
                    logger.info(f"📋 Parsed response: {response}")
                    
                    if response.get("type") == "agent_response":
                        agent_port = response.get('port', 5001)
                        agent_host = f"{addr[0]}:{agent_port}"
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
        Discover agents on the network by querying known host:port pairs.
        Supports environment variables, network scanning, and manual host lists.
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
        
        # Use semaphore to limit concurrent connections
        semaphore = asyncio.Semaphore(10)
        
        async def check_host(host_port):
            async with semaphore:
                try:
                    logger.info(f"🔍 Checking agent at {host_port}...")
                    async with aiohttp.ClientSession() as session:
                        url = f"http://{host_port}/capabilities"
                        logger.debug(f"📡 Making request to: {url}")
                        
                        async with session.get(url, timeout=3) as resp:
                            logger.debug(f"📊 Response from {host_port}: status={resp.status}")
                            
                            if resp.status == 200:
                                agent_data = await resp.json()
                                logger.info(f"📋 Agent data received from {host_port}: {agent_data}")
                                
                                # Override agent's self-reported address with discovery address
                                discovery_host, discovery_port = host_port.split(':')
                                agent_data['host'] = discovery_host
                                agent_data['port'] = int(discovery_port)
                                
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
    
    async def health_check_agents(self):
        """
        Check health of all registered agents by calling their /health endpoint.
        Retry failed connections and only mark as unhealthy after multiple failures.
        """
        for agent_id, agent_info in list(self.agents.items()):
            health_check_passed = False
            
            # Try health check with retry logic
            for attempt in range(3):  # Try up to 3 times
                try:
                    async with aiohttp.ClientSession() as session:
                        url = f"http://{agent_info.host}:{agent_info.port}/health"
                        logger.debug(f"Health check attempt {attempt + 1}/3 for agent {agent_id} at {url}")
                        
                        async with session.get(url, timeout=5) as resp:
                            if resp.status == 200:
                                health_data = await resp.json()
                                logger.debug(f"Agent {agent_id} health check passed: {health_data.get('status', 'unknown')}")
                                
                                if agent_id in self.agents:  # Double-check agent still exists
                                    self.agents[agent_id].is_healthy = True
                                    self.agents[agent_id].last_seen = datetime.now()
                                health_check_passed = True
                                break
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
        Use OpenAI to parse a natural language command into a structured format.
        """
        try:
            response = self.openai_client.chat.completions.create(
                model="google/gemma-3n-e2b-it:free",
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
                max_tokens=200,
                temperature=0.1
            )
            
            content = response.choices[0].message.content.strip()
            
            # Log the raw response for debugging
            logger.debug(f"Raw AI response: {content}")
            
            # Handle empty response
            if not content:
                raise ValueError("Empty response from AI model")
            
            # Try to extract JSON if response has extra text
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            
            import json
            return json.loads(content)
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed. Raw response: {response.choices[0].message.content}")
            logger.error(f"JSON error: {e}")
            return {
                "action": "unknown",
                "target_os": "any", 
                "command": user_input,
                "description": "Direct command execution (JSON parse failed)"
            }
        except Exception as e:
            logger.error(f"Command parsing failed: {e}")
            return {
                "action": "unknown",
                "target_os": "any",
                "command": user_input,
                "description": "Direct command execution"
            }
    
    def select_agent(self, parsed_command: Dict) -> Optional[AgentInfo]:
        """
        Select the best agent for a command based on OS and health.
        """
        target_os = parsed_command.get("target_os", "any")
        action = parsed_command.get("action", "")
        
        # Filter healthy agents
        healthy_agents = [agent for agent in self.agents.values() if agent.is_healthy]
        
        if not healthy_agents:
            return None
        
        # OS-specific selection
        if target_os != "any":
            os_agents = [agent for agent in healthy_agents if agent.os_type.lower() == target_os.lower()]
            if os_agents:
                return os_agents[0]  # Simple selection - improve with load balancing
        
        # Return first healthy agent
        return healthy_agents[0]
    
    async def execute_command(self, user_input: str) -> CommandResult:
        """
        Main command execution flow: parse, select agent, send command, return result.
        """
        logger.info(f"Executing command: {user_input}")

        # Parse the command
        parsed_command = await self.parse_command(user_input)
        logger.info(f"Parsed command: {parsed_command}")

        # Select agent
        agent = self.select_agent(parsed_command)
        if not agent:
            return CommandResult(
                success=False,
                error="No healthy agents available",
                execution_time_ms=0,
                command=user_input,
                agent_id="none"
            )

        # Execute on selected agent
        message = Message(
            type=MessageType.COMMAND,
            source="coordinator",
            target=agent.id,
            payload={"command": parsed_command["command"]}
        )

        try:
            async with aiohttp.ClientSession() as session:
                url = f"http://{agent.host}:{agent.port}/execute"
                async with session.post(url, json=message.model_dump(mode='json')) as resp:
                    if resp.status == 200:
                        result_data = await resp.json()
                        result = CommandResult(**result_data)

                        # Store in history
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