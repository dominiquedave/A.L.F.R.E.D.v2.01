import json
from datetime import datetime

import pytest

from shared.models import AgentInfo, CommandResult, Message, MessageType, Permission


class TestModelsIntegration:
    """Test model serialization and real-world usage patterns"""

    def test_message_json_roundtrip(self):
        """Test Message model JSON serialization roundtrip"""
        original_message = Message(
            type=MessageType.COMMAND,
            source="coordinator",
            target="agent_1",
            payload={"command": "ls -la", "timeout": 30},
            requires_permissions=[Permission.FILE_READ, Permission.SYSTEM_READ],
        )

        # Serialize to JSON
        json_data = original_message.model_dump(mode="json")
        json_string = json.dumps(json_data)

        # Deserialize from JSON
        loaded_data = json.loads(json_string)
        reconstructed_message = Message(**loaded_data)

        assert reconstructed_message.type == original_message.type
        assert reconstructed_message.source == original_message.source
        assert reconstructed_message.target == original_message.target
        assert reconstructed_message.payload == original_message.payload
        assert reconstructed_message.requires_permissions == original_message.requires_permissions

    def test_agent_info_complete_workflow(self):
        """Test AgentInfo in a complete workflow scenario"""
        agent = AgentInfo(
            id="production_agent_1",
            name="Production Linux Agent",
            os_type="Linux",
            capabilities=["bash", "shell", "file_operations", "process_info", "system_info"],
            permissions=[Permission.FILE_READ, Permission.PROCESS_READ, Permission.SYSTEM_READ],
            host="192.168.1.100",
            port=5001,
            last_seen=datetime.now(),
            is_healthy=True,
        )

        # Simulate health check failure
        agent.is_healthy = False

        # Verify state changes
        assert not agent.is_healthy
        assert agent.capabilities == [
            "bash",
            "shell",
            "file_operations",
            "process_info",
            "system_info",
        ]

        # Test serialization for storage/transmission
        data = agent.model_dump(mode="json")
        assert data["id"] == "production_agent_1"
        assert data["is_healthy"] is False

    def test_command_result_error_scenarios(self):
        """Test CommandResult with various error scenarios"""
        # Timeout scenario
        timeout_result = CommandResult(
            success=False,
            error="Command timed out after 30 seconds",
            execution_time_ms=30000,
            command="long_running_command --wait",
            agent_id="agent_1",
        )

        assert not timeout_result.success
        assert timeout_result.execution_time_ms == 30000
        assert "timed out" in timeout_result.error

        # Permission denied scenario
        permission_result = CommandResult(
            success=False,
            error="Permission denied: insufficient privileges",
            execution_time_ms=50,
            command="sudo restricted_command",
            agent_id="agent_1",
        )

        assert not permission_result.success
        assert "Permission denied" in permission_result.error

        # Successful command with both output and error streams
        mixed_result = CommandResult(
            success=True,
            output="Operation completed successfully",
            error="Warning: deprecated flag used",
            execution_time_ms=1500,
            command="command --deprecated-flag",
            agent_id="agent_1",
        )

        assert mixed_result.success
        assert mixed_result.output is not None
        assert mixed_result.error is not None

    def test_complex_message_scenarios(self):
        """Test complex message scenarios with nested data"""
        # Multi-step command message
        complex_message = Message(
            type=MessageType.COMMAND,
            source="coordinator",
            target="agent_cluster_1",
            payload={
                "commands": [
                    "mkdir -p /tmp/test_workspace",
                    "cd /tmp/test_workspace && echo 'test' > test.txt",
                    "cat /tmp/test_workspace/test.txt",
                ],
                "execution_mode": "sequential",
                "timeout_per_command": 10,
                "cleanup": True,
            },
            requires_permissions=[Permission.FILE_WRITE, Permission.FILE_READ],
        )

        assert complex_message.type == MessageType.COMMAND
        assert len(complex_message.payload["commands"]) == 3
        assert Permission.FILE_WRITE in complex_message.requires_permissions

        # Health check response message
        health_response = Message(
            type=MessageType.RESPONSE,
            source="agent_1",
            target="coordinator",
            payload={
                "status": "healthy",
                "metrics": {
                    "cpu_percent": 25.5,
                    "memory_percent": 60.2,
                    "disk_percent": 45.8,
                    "uptime_seconds": 86400,
                },
                "last_command_time": datetime.now().isoformat(),
            },
        )

        assert health_response.type == MessageType.RESPONSE
        assert health_response.payload["status"] == "healthy"
        assert "metrics" in health_response.payload
