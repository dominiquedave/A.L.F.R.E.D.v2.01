from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import uuid

class MessageType(str, Enum):
    """
    Types of messages exchanged between coordinator and agents.
    """
    COMMAND = "command"
    QUERY = "query"
    RESPONSE = "response"
    STATUS = "status"
    HEALTH_CHECK = "health_check"

class Permission(str, Enum):
    """
    Permissions that can be granted to agents or commands.
    """
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    PROCESS_READ = "process_read"
    PROCESS_CONTROL = "process_control"
    SYSTEM_READ = "system_read"
    ADMIN = "admin"

class Message(BaseModel):
    """
    Represents a message sent between coordinator and agents.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType
    source: str
    target: str
    timestamp: datetime = Field(default_factory=datetime.now)
    payload: Dict[str, Any]
    requires_permissions: List[Permission] = []

class AgentInfo(BaseModel):
    """
    Information about an agent, including capabilities and health.
    """
    id: str
    name: str
    os_type: str
    capabilities: List[str]
    permissions: List[Permission]
    host: str
    port: int
    last_seen: datetime
    is_healthy: bool = True

class CommandResult(BaseModel):
    """
    Result of executing a command on an agent.
    """
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time_ms: int
    command: str
    agent_id: str