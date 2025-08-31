import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from shared.models import AgentInfo, CommandResult, Message, MessageType, Permission


class TestMessageType:
    def test_message_type_values(self):
        assert MessageType.COMMAND == "command"
        assert MessageType.QUERY == "query"
        assert MessageType.RESPONSE == "response"
        assert MessageType.STATUS == "status"
        assert MessageType.HEALTH_CHECK == "health_check"


class TestPermission:
    def test_permission_values(self):
        assert Permission.FILE_READ == "file_read"
        assert Permission.FILE_WRITE == "file_write"
        assert Permission.PROCESS_READ == "process_read"
        assert Permission.PROCESS_CONTROL == "process_control"
        assert Permission.SYSTEM_READ == "system_read"
        assert Permission.ADMIN == "admin"


class TestMessage:
    def test_message_creation_with_required_fields(self):
        message = Message(
            type=MessageType.COMMAND,
            source="test_source",
            target="test_target",
            payload={"command": "ls -la"},
        )

        assert message.type == MessageType.COMMAND
        assert message.source == "test_source"
        assert message.target == "test_target"
        assert message.payload == {"command": "ls -la"}
        assert message.requires_permissions == []

        # Verify auto-generated fields
        assert isinstance(message.id, str)
        assert isinstance(uuid.UUID(message.id), uuid.UUID)
        assert isinstance(message.timestamp, datetime)

    def test_message_creation_with_permissions(self):
        permissions = [Permission.FILE_READ, Permission.SYSTEM_READ]
        message = Message(
            type=MessageType.QUERY,
            source="coordinator",
            target="agent_1",
            payload={"query": "status"},
            requires_permissions=permissions,
        )

        assert message.requires_permissions == permissions

    def test_message_validation_error_missing_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            Message()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}

        expected_fields = {"type", "source", "target", "payload"}
        assert expected_fields.issubset(error_fields)

    def test_message_serialization(self):
        message = Message(
            type=MessageType.RESPONSE,
            source="agent_1",
            target="coordinator",
            payload={"result": "success"},
        )

        data = message.model_dump(mode="json")

        assert data["type"] == "response"
        assert data["source"] == "agent_1"
        assert data["target"] == "coordinator"
        assert data["payload"] == {"result": "success"}
        assert "id" in data
        assert "timestamp" in data


class TestAgentInfo:
    def test_agent_info_creation(self):
        capabilities = ["bash", "file_operations"]
        permissions = [Permission.FILE_READ, Permission.PROCESS_READ]
        last_seen = datetime.now()

        agent = AgentInfo(
            id="test_agent",
            name="Test Agent",
            os_type="Linux",
            capabilities=capabilities,
            permissions=permissions,
            host="192.168.1.100",
            port=5001,
            last_seen=last_seen,
        )

        assert agent.id == "test_agent"
        assert agent.name == "Test Agent"
        assert agent.os_type == "Linux"
        assert agent.capabilities == capabilities
        assert agent.permissions == permissions
        assert agent.host == "192.168.1.100"
        assert agent.port == 5001
        assert agent.last_seen == last_seen
        assert agent.is_healthy is True

    def test_agent_info_unhealthy_status(self):
        agent = AgentInfo(
            id="unhealthy_agent",
            name="Unhealthy Agent",
            os_type="Windows",
            capabilities=["powershell"],
            permissions=[Permission.SYSTEM_READ],
            host="localhost",
            port=5002,
            last_seen=datetime.now(),
            is_healthy=False,
        )

        assert agent.is_healthy is False

    def test_agent_info_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            AgentInfo(id="test", name="test", port="invalid_port")  # Should be int

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("port",) for error in errors)

    def test_agent_info_serialization(self):
        agent = AgentInfo(
            id="serialization_test",
            name="Serialization Test",
            os_type="Darwin",
            capabilities=["bash", "shell"],
            permissions=[Permission.ADMIN],
            host="localhost",
            port=5003,
            last_seen=datetime.now(),
        )

        data = agent.model_dump(mode="json")

        assert data["id"] == "serialization_test"
        assert data["name"] == "Serialization Test"
        assert data["os_type"] == "Darwin"
        assert data["capabilities"] == ["bash", "shell"]
        assert data["permissions"] == ["admin"]
        assert data["host"] == "localhost"
        assert data["port"] == 5003
        assert "last_seen" in data
        assert data["is_healthy"] is True


class TestCommandResult:
    def test_command_result_success(self):
        result = CommandResult(
            success=True,
            output="Hello World\n",
            execution_time_ms=150,
            command="echo 'Hello World'",
            agent_id="test_agent",
        )

        assert result.success is True
        assert result.output == "Hello World\n"
        assert result.error is None
        assert result.execution_time_ms == 150
        assert result.command == "echo 'Hello World'"
        assert result.agent_id == "test_agent"

    def test_command_result_failure(self):
        result = CommandResult(
            success=False,
            error="Command not found",
            execution_time_ms=50,
            command="nonexistent_command",
            agent_id="test_agent",
        )

        assert result.success is False
        assert result.output is None
        assert result.error == "Command not found"
        assert result.execution_time_ms == 50
        assert result.command == "nonexistent_command"
        assert result.agent_id == "test_agent"

    def test_command_result_with_both_output_and_error(self):
        result = CommandResult(
            success=False,
            output="Some output",
            error="Some error",
            execution_time_ms=200,
            command="test_command",
            agent_id="test_agent",
        )

        assert result.success is False
        assert result.output == "Some output"
        assert result.error == "Some error"

    def test_command_result_serialization(self):
        result = CommandResult(
            success=True,
            output="test output",
            execution_time_ms=100,
            command="test command",
            agent_id="agent_123",
        )

        data = result.model_dump(mode="json")

        assert data["success"] is True
        assert data["output"] == "test output"
        assert data["error"] is None
        assert data["execution_time_ms"] == 100
        assert data["command"] == "test command"
        assert data["agent_id"] == "agent_123"

    def test_command_result_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            CommandResult(
                success="invalid", execution_time_ms="invalid"  # Should be bool  # Should be int
            )

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}

        expected_fields = {"success", "execution_time_ms"}
        assert expected_fields.issubset(error_fields)
