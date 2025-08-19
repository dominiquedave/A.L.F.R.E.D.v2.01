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
        self.agents[agent_info.id] = agent_info
        logger.info(f"Registered agent: {agent_info.name} ({agent_info.id})")
    
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
            broadcast_port = 5099
            
            logger.info(f"Broadcasting agent discovery on port {broadcast_port}")
            sock.sendto(discovery_msg.encode(), ('<broadcast>', broadcast_port))
            
            # Listen for responses
            start_time = time.time()
            while time.time() - start_time < 3:  # Listen for 3 seconds
                try:
                    data, addr = sock.recvfrom(1024)
                    response = json.loads(data.decode())
                    if response.get("type") == "agent_response":
                        agent_host = f"{addr[0]}:{response.get('port', 5001)}"
                        discovered_hosts.append(agent_host)
                        logger.info(f"Agent responded from {agent_host}")
                except socket.timeout:
                    break
                except Exception as e:
                    logger.debug(f"Broadcast discovery error: {e}")
                    break
            
            sock.close()
        except Exception as e:
            logger.warning(f"Broadcast discovery failed: {e}")
        
        return discovered_hosts

    async def discover_agents(self, host_range: List[str] = None):
        """
        Discover agents on the network by querying known host:port pairs.
        Supports environment variables, network scanning, and manual host lists.
        """
        if not host_range:
            # Check for environment variable first
            env_hosts = os.getenv('AGENT_DISCOVERY_HOSTS')
            network_name = os.getenv('AGENT_NETWORK_CONFIG')
            
            if env_hosts:
                host_range = [host.strip() for host in env_hosts.split(',')]
                logger.info(f"Using environment variable AGENT_DISCOVERY_HOSTS: {host_range}")
            elif network_name and network_name in self.discovery_config.get('network_configs', {}):
                # Use predefined network configuration
                network_config = self.discovery_config['network_configs'][network_name]
                host_range = network_config.get('hosts', [])
                logger.info(f"Using network config '{network_name}': {host_range}")
            else:
                # Use discovery settings from config
                discovery_settings = self.discovery_config.get('discovery_settings', {})
                use_broadcast = os.getenv('AGENT_USE_BROADCAST', str(discovery_settings.get('use_broadcast', True))).lower() == 'true'
                
                if use_broadcast:
                    broadcast_hosts = await self.discover_agents_broadcast()
                    if broadcast_hosts:
                        host_range = broadcast_hosts
                        logger.info(f"Found {len(broadcast_hosts)} agents via broadcast")
                    else:
                        logger.info("No agents found via broadcast, falling back to scanning")
                
                if not host_range:
                    # Auto-discover based on network scanning
                    scan_network = os.getenv('AGENT_SCAN_NETWORK', str(discovery_settings.get('scan_network', False))).lower() == 'true'
                    if scan_network:
                        logger.info("Scanning local network for agents...")
                        network_ips = self._get_local_network_range()
                        host_range = []
                        # Try common agent ports on each IP
                        for ip in network_ips:
                            host_range.extend([f"{ip}:5001", f"{ip}:5002", f"{ip}:5003"])
                    else:
                        # Use manual hosts from config or default to localhost
                        manual_hosts = discovery_settings.get('manual_hosts', [])
                        if manual_hosts:
                            host_range = manual_hosts
                            logger.info(f"Using manual hosts from config: {host_range}")
                        else:
                            host_range = [
                                "localhost:5001", 
                                "localhost:5002",
                                "127.0.0.1:5001", 
                                "127.0.0.1:5002"
                            ]
        
        logger.info(f"Discovering agents on: {len(host_range)} hosts")
        
        # Use semaphore to limit concurrent connections
        semaphore = asyncio.Semaphore(10)
        
        async def check_host(host_port):
            async with semaphore:
                try:
                    logger.debug(f"Checking {host_port}")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"http://{host_port}/capabilities", timeout=3) as resp:
                            if resp.status == 200:
                                agent_data = await resp.json()
                                agent_info = AgentInfo(**agent_data)
                                await self.register_agent(agent_info)
                                logger.info(f"✓ Found agent at {host_port}")
                                return True
                except Exception as e:
                    logger.debug(f"Could not connect to {host_port}: {e}")
                return False
        
        # Run discovery concurrently
        tasks = [check_host(host_port) for host_port in host_range]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        found_count = sum(1 for r in results if r is True)
        logger.info(f"Agent discovery complete: {found_count} agents found")
    
    async def health_check_agents(self):
        """
        Check health of all registered agents by calling their /health endpoint.
        """
        for agent_id, agent_info in self.agents.items():
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"http://{agent_info.host}:{agent_info.port}/health"
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            self.agents[agent_id].is_healthy = True
                            self.agents[agent_id].last_seen = datetime.now()
                        else:
                            self.agents[agent_id].is_healthy = False
            except Exception as e:
                self.agents[agent_id].is_healthy = False
                logger.warning(f"Agent {agent_id} health check failed: {e}")
    
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