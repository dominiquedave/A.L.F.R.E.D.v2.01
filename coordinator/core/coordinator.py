from dotenv import load_dotenv
import os
import asyncio
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from openai import OpenAI
from shared.models import AgentInfo, Message, MessageType, CommandResult
import logging

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
    
    async def register_agent(self, agent_info: AgentInfo):
        """Register a new agent"""
        self.agents[agent_info.id] = agent_info
        logger.info(f"Registered agent: {agent_info.name} ({agent_info.id})")
    
    async def discover_agents(self, host_range: List[str] = None):
        """
        Discover agents on the network by querying known host:port pairs.
        """
        if not host_range:
            host_range = ["localhost:5001", "10.0.2.15:5002"]
        
        for host_port in host_range:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"http://{host_port}/capabilities", timeout=5) as resp:
                        if resp.status == 200:
                            agent_data = await resp.json()
                            agent_info = AgentInfo(**agent_data)
                            await self.register_agent(agent_info)
            except Exception as e:
                logger.debug(f"Could not connect to {host_port}: {e}")
    
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