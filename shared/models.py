# Shared data models for A.L.F.R.E.D. distributed agent system
from pydantic import BaseModel, Field   # Data validation and serialization
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import uuid

class MessageType(str, Enum):
    """
    Enumeration of message types for coordinator-agent communication.
    
    Defines the different types of messages that can be exchanged in the
    A.L.F.R.E.D. system for proper message routing and handling.
    """
    COMMAND = "command"              # Execute a command on an agent
    QUERY = "query"                  # Request information from an agent
    RESPONSE = "response"            # Response to a query or command
    STATUS = "status"                # Status update message
    HEALTH_CHECK = "health_check"    # Health monitoring message

class Permission(str, Enum):
    """
    Security permissions for controlling agent capabilities and command execution.
    
    Implements a permission-based security model where agents and commands
    can be restricted to specific operations. Used for security validation
    and capability-based access control.
    """
    FILE_READ = "file_read"              # Read files and directories
    FILE_WRITE = "file_write"            # Write, create, delete files
    PROCESS_READ = "process_read"        # List and monitor processes
    PROCESS_CONTROL = "process_control"  # Start, stop, kill processes
    SYSTEM_READ = "system_read"          # Read system information (CPU, memory, etc.)
    ADMIN = "admin"                      # Full administrative access

class Message(BaseModel):
    """
    Standard message format for all coordinator-agent communication.
    
    Provides a structured, type-safe message format with automatic ID generation,
    timestamps, and permission requirements for security validation.
    
    Attributes:
        id: Unique message identifier (auto-generated UUID)
        type: Message type for proper routing and handling
        source: Sender identifier (coordinator ID or agent ID)
        target: Recipient identifier (coordinator ID or agent ID)
        timestamp: Message creation timestamp (auto-generated)
        payload: Message data (commands, responses, etc.)
        requires_permissions: Security permissions required to process this message
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # Auto-generate unique ID
    type: MessageType                                            # Message type for routing
    source: str                                                  # Sender identifier
    target: str                                                  # Recipient identifier  
    timestamp: datetime = Field(default_factory=datetime.now)    # Auto-generate timestamp
    payload: Dict[str, Any]                                      # Message data/content
    requires_permissions: List[Permission] = []                  # Required security permissions

class AgentInfo(BaseModel):
    """
    Complete agent information for registration and management.
    
    Stores all essential information about an agent including its identity,
    capabilities, network location, health status, and security permissions.
    Used by coordinators for agent discovery, selection, and monitoring.
    
    Attributes:
        id: Unique agent identifier (typically hostname-OS-port)
        name: Human-readable agent name
        os_type: Operating system (Windows, Linux, Darwin, etc.)
        capabilities: List of agent capabilities (bash, powershell, file_operations, etc.)
        permissions: Security permissions granted to this agent
        host: IP address or hostname for agent communication
        port: HTTP API port number
        last_seen: Timestamp of last successful communication
        is_healthy: Current health status (updated by health checks)
    """
    id: str                                # Unique agent identifier
    name: str                              # Human-readable name
    os_type: str                           # Operating system type
    capabilities: List[str]                # Agent capabilities
    permissions: List[Permission]          # Security permissions
    host: str                              # Network address
    port: int                              # HTTP API port
    last_seen: datetime                    # Last successful contact
    is_healthy: bool = True                # Current health status

class CommandResult(BaseModel):
    """
    Structured result of command execution on an agent.
    
    Provides comprehensive information about command execution including
    success status, output data, error information, performance metrics,
    and execution context for debugging and auditing purposes.
    
    Attributes:
        success: Whether command executed successfully (exit code 0)
        output: Standard output from command (stdout)
        error: Error output from command (stderr) 
        execution_time_ms: Command execution time in milliseconds
        command: Original command that was executed
        agent_id: ID of agent that executed the command
    """
    success: bool                          # Execution success status
    output: Optional[str] = None           # Command stdout output
    error: Optional[str] = None            # Command stderr output
    execution_time_ms: int                 # Execution time in milliseconds
    command: str                           # Original command executed
    agent_id: str                          # Executing agent identifier