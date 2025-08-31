import asyncio
import json
import platform
import socket
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from agent.core.agent import Agent
from shared.models import CommandResult, Message, MessageType, Permission


class TestAgent:
    @pytest.fixture
    def mock_agent(self):
        with patch("agent.core.agent.platform.node", return_value="test-host"):
            with patch("agent.core.agent.platform.system", return_value="Linux"):
                with patch.object(Agent, "_get_external_ip", return_value="192.168.1.100"):
                    with patch.object(Agent, "_start_broadcast_listener"):
                        agent = Agent("test_agent", port=5001)
                        return agent

    def test_agent_initialization(self, mock_agent):
        assert mock_agent.info.name == "test_agent"
        assert mock_agent.info.host == "192.168.1.100"
        assert mock_agent.info.port == 5001
        assert mock_agent.info.os_type == "Linux"
        assert "bash" in mock_agent.info.capabilities
        assert "shell" in mock_agent.info.capabilities
        assert "file_operations" in mock_agent.info.capabilities
        assert Permission.FILE_READ in mock_agent.info.permissions
        assert Permission.PROCESS_READ in mock_agent.info.permissions

    def test_detect_capabilities_linux(self):
        with patch("agent.core.agent.platform.system", return_value="Linux"):
            with patch.object(Agent, "_get_external_ip", return_value="localhost"):
                with patch.object(Agent, "_start_broadcast_listener"):
                    agent = Agent("test", port=5001)

                    caps = agent._detect_capabilities()
                    assert "file_operations" in caps
                    assert "process_info" in caps
                    assert "system_info" in caps
                    assert "bash" in caps
                    assert "shell" in caps

    def test_detect_capabilities_windows(self):
        with patch("agent.core.agent.platform.system", return_value="Windows"):
            with patch.object(Agent, "_get_external_ip", return_value="localhost"):
                with patch.object(Agent, "_start_broadcast_listener"):
                    agent = Agent("test", port=5001)

                    caps = agent._detect_capabilities()
                    assert "file_operations" in caps
                    assert "process_info" in caps
                    assert "system_info" in caps
                    assert "powershell" in caps
                    assert "cmd" in caps

    def test_get_default_permissions(self, mock_agent):
        permissions = mock_agent._get_default_permissions()
        expected = [Permission.FILE_READ, Permission.PROCESS_READ, Permission.SYSTEM_READ]
        assert permissions == expected

    @patch("agent.core.agent.socket.socket")
    def test_get_external_ip_success(self, mock_socket):
        mock_sock = Mock()
        mock_sock.getsockname.return_value = ("192.168.1.50", 12345)
        mock_socket.return_value.__enter__.return_value = mock_sock

        with patch.object(Agent, "_start_broadcast_listener"):
            agent = Agent("test", host="localhost", port=5001)
            # The external IP detection happens during init
            assert agent.info.host == "192.168.1.50"

    @patch("agent.core.agent.socket.socket")
    @patch("agent.core.agent.socket.gethostname")
    @patch("agent.core.agent.socket.gethostbyname")
    def test_get_external_ip_fallback_to_hostname(
        self, mock_gethostbyname, mock_gethostname, mock_socket
    ):
        # Mock socket connection to fail
        mock_socket.return_value.__enter__.side_effect = Exception("Connection failed")

        # Mock hostname resolution
        mock_gethostname.return_value = "test-hostname"
        mock_gethostbyname.return_value = "192.168.1.75"

        with patch.object(Agent, "_start_broadcast_listener"):
            agent = Agent("test", host="localhost", port=5001)
            assert agent.info.host == "192.168.1.75"

    def test_validate_command_safe_commands(self, mock_agent):
        safe_commands = ["ls -la", "ps aux", "cat /etc/hosts", "echo 'Hello World'", "whoami"]

        for command in safe_commands:
            assert mock_agent._validate_command(command) is True

    def test_validate_command_dangerous_commands(self, mock_agent):
        dangerous_commands = [
            "rm -rf /",
            "del /f /q C:\\*",
            "format c:",
            "shutdown -h now",
            "reboot now",
        ]

        for command in dangerous_commands:
            assert mock_agent._validate_command(command) is False

    def test_validate_command_case_insensitive(self, mock_agent):
        dangerous_commands = [
            "RM -RF /home",
            "DEL /F important.txt",
            "FORMAT D:",
            "SHUTDOWN -r",
            "REBOOT",
        ]

        for command in dangerous_commands:
            assert mock_agent._validate_command(command) is False

    @patch("agent.core.agent.threading.Thread")
    @patch("agent.core.agent.socket.socket")
    def test_start_broadcast_listener(self, mock_socket, mock_thread):
        mock_sock = Mock()
        mock_socket.return_value = mock_sock

        with patch.object(Agent, "_get_external_ip", return_value="localhost"):
            agent = Agent("test", port=5001)

            # Verify thread was started
            mock_thread.assert_called_once()
            thread_args = mock_thread.call_args
            assert thread_args[1]["daemon"] is True

    def test_agent_id_format(self, mock_agent):
        # Agent ID should be in format: hostname-OS-port
        expected_format = "test-host-Linux-5001"
        assert mock_agent.info.id == expected_format


class TestAgentRoutes:
    @pytest.fixture
    def client(self):
        with patch("agent.core.agent.platform.node", return_value="test-host"):
            with patch("agent.core.agent.platform.system", return_value="Linux"):
                with patch.object(Agent, "_get_external_ip", return_value="localhost"):
                    with patch.object(Agent, "_start_broadcast_listener"):
                        agent = Agent("test_agent", port=5001)
                        from fastapi.testclient import TestClient

                        return TestClient(agent.app), agent

    @patch("agent.core.agent.subprocess.run")
    def test_execute_command_success(self, mock_subprocess, client):
        test_client, agent = client

        # Mock successful command execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Hello World\n"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        message = Message(
            type=MessageType.COMMAND,
            source="coordinator",
            target=agent.info.id,
            payload={"command": "echo 'Hello World'"},
        )

        response = test_client.post("/execute", json=message.model_dump(mode="json"))

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["output"] == "Hello World\n"
        assert data["error"] == ""
        assert "execution_time_ms" in data
        assert data["command"] == "echo 'Hello World'"
        assert data["agent_id"] == agent.info.id

    @patch("agent.core.agent.subprocess.run")
    def test_execute_command_failure(self, mock_subprocess, client):
        test_client, agent = client

        # Mock failed command execution
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Command not found"
        mock_subprocess.return_value = mock_result

        message = Message(
            type=MessageType.COMMAND,
            source="coordinator",
            target=agent.info.id,
            payload={"command": "nonexistent_command"},
        )

        response = test_client.post("/execute", json=message.model_dump(mode="json"))

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Command not found"

    def test_execute_command_blocked(self, client):
        test_client, agent = client

        message = Message(
            type=MessageType.COMMAND,
            source="coordinator",
            target=agent.info.id,
            payload={"command": "rm -rf /"},
        )

        response = test_client.post("/execute", json=message.model_dump(mode="json"))

        # The HTTPException gets caught and returned as a CommandResult
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "403" in data["error"] or "Command not allowed" in data["error"]

    @patch("agent.core.agent.subprocess.run")
    def test_execute_command_timeout(self, mock_subprocess, client):
        test_client, agent = client

        # Mock timeout exception
        mock_subprocess.side_effect = subprocess.TimeoutExpired("echo test", 30)

        message = Message(
            type=MessageType.COMMAND,
            source="coordinator",
            target=agent.info.id,
            payload={"command": "echo test"},
        )

        response = test_client.post("/execute", json=message.model_dump(mode="json"))

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "timed out" in data["error"]
        assert data["execution_time_ms"] == 30000

    @patch("agent.core.agent.psutil.cpu_percent", return_value=25.5)
    @patch("agent.core.agent.psutil.virtual_memory")
    @patch("agent.core.agent.psutil.disk_usage")
    def test_health_endpoint_success(self, mock_disk, mock_memory, mock_cpu, client):
        test_client, agent = client

        # Mock system metrics
        mock_memory.return_value.percent = 60.0
        mock_disk.return_value.percent = 45.0

        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "agent_info" in data
        assert "system_stats" in data
        assert data["system_stats"]["cpu_percent"] == 25.5
        assert data["system_stats"]["memory_percent"] == 60.0
        assert data["system_stats"]["disk_percent"] == 45.0

    @patch("agent.core.agent.psutil.cpu_percent")
    def test_health_endpoint_error(self, mock_cpu, client):
        test_client, agent = client

        # Mock exception in health check
        mock_cpu.side_effect = Exception("psutil error")

        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data

    def test_capabilities_endpoint(self, client):
        test_client, agent = client

        response = test_client.get("/capabilities")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == agent.info.id
        assert data["name"] == agent.info.name
        assert data["os_type"] == agent.info.os_type
        assert data["host"] == agent.info.host
        assert data["port"] == agent.info.port
        assert "capabilities" in data
        assert "permissions" in data


# Import subprocess for the timeout test
import subprocess
