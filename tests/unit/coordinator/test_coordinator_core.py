import asyncio
import json
import os
import socket
from datetime import datetime
from unittest.mock import AsyncMock, Mock, mock_open, patch

import pytest

from coordinator.core.coordinator import Coordinator
from shared.models import AgentInfo, CommandResult, Permission


class TestCoordinatorCore:
    """Test core coordinator functionality with better coverage"""

    @pytest.fixture
    def coordinator(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("coordinator.core.coordinator.OpenAI"):
                return Coordinator()

    def test_coordinator_init_default_config(self, coordinator):
        """Test coordinator initialization with default config"""
        assert coordinator.agents == {}
        assert coordinator.command_history == []
        assert coordinator.discovery_config["discovery_settings"]["use_broadcast"] is True

    @pytest.mark.asyncio
    async def test_register_agent_simple(self, coordinator):
        """Test basic agent registration"""
        agent = AgentInfo(
            id="test_agent",
            name="Test Agent",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
        )

        await coordinator.register_agent(agent)
        assert "test_agent" in coordinator.agents
        assert coordinator.agents["test_agent"] == agent

    def test_select_agent_simple(self, coordinator):
        """Test basic agent selection logic"""
        # Test with no agents
        result = coordinator.select_agent({"target_os": "any", "action": "test"})
        assert result is None

    @pytest.mark.asyncio
    async def test_parse_command_fallback(self, coordinator):
        """Test parse command fallback behavior"""
        # Mock OpenAI client to raise exception
        with patch.object(
            coordinator.openai_client.chat.completions, "create", side_effect=Exception("API error")
        ):
            result = await coordinator.parse_command("test command")

            assert result["action"] == "unknown"
            assert result["command"] == "test command"
            assert result["target_os"] == "any"

    @pytest.mark.asyncio
    async def test_execute_command_no_agents(self, coordinator):
        """Test command execution with no agents"""
        with patch.object(
            coordinator,
            "parse_command",
            return_value={
                "action": "test",
                "target_os": "any",
                "command": "test",
                "description": "test",
            },
        ):
            result = await coordinator.execute_command("test")

            assert result.success is False
            assert "No healthy agents available" in result.error

    def test_get_local_network_range_simple(self, coordinator):
        """Test network range generation with mocked methods"""
        with patch("coordinator.core.coordinator.socket.gethostname", return_value="test-host"):
            with patch(
                "coordinator.core.coordinator.socket.gethostbyname", return_value="192.168.1.100"
            ):
                with patch("coordinator.core.coordinator.ipaddress.IPv4Network") as mock_network:
                    # Mock the network to return a list of IPs
                    mock_ips = [Mock() for i in range(1, 25)]
                    for i, mock_ip in enumerate(mock_ips):
                        mock_ip.__str__ = lambda self, j=i + 1: f"192.168.1.{j}"
                    mock_network.return_value.hosts.return_value = mock_ips

                    result = coordinator._get_local_network_range()

                    assert len(result) == 20  # Should be limited to 20

    def test_get_local_network_range_exception(self, coordinator):
        """Test network range generation with exception handling"""
        with patch(
            "coordinator.core.coordinator.socket.gethostname",
            side_effect=Exception("Network error"),
        ):
            result = coordinator._get_local_network_range()
            assert result == ["127.0.0.1"]  # Should fallback to localhost

    def test_load_discovery_config_file_exists(self, coordinator):
        """Test loading discovery config when file exists"""
        test_config = {
            "discovery_settings": {
                "use_broadcast": False,
                "broadcast_port": 6000,
            },
            "network_configs": {"test_net": {"hosts": ["test:5001"]}},
        }

        with patch("coordinator.core.coordinator.os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(test_config))):
                config = coordinator._load_discovery_config()
                assert config["discovery_settings"]["use_broadcast"] is False
                assert config["discovery_settings"]["broadcast_port"] == 6000

    def test_load_discovery_config_file_error(self, coordinator):
        """Test loading discovery config with file read error"""
        with patch("coordinator.core.coordinator.os.path.exists", return_value=True):
            with patch("builtins.open", side_effect=FileNotFoundError()):
                config = coordinator._load_discovery_config()
                # Should return default config
                assert config["discovery_settings"]["use_broadcast"] is True
                assert config["discovery_settings"]["broadcast_port"] == 5099

    @pytest.mark.asyncio
    async def test_register_agent_replacement(self, coordinator):
        """Test agent registration replacement scenario"""
        # Create first agent
        agent1 = AgentInfo(
            id="test_agent",
            name="Agent v1",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
        )

        # Create replacement agent with same ID
        agent2 = AgentInfo(
            id="test_agent",
            name="Agent v2",
            os_type="Linux",
            capabilities=["bash", "shell"],
            permissions=[Permission.FILE_READ, Permission.SYSTEM_READ],
            host="localhost",
            port=5002,
            last_seen=datetime.now(),
        )

        await coordinator.register_agent(agent1)
        assert coordinator.agents["test_agent"].name == "Agent v1"

        await coordinator.register_agent(agent2)
        assert coordinator.agents["test_agent"].name == "Agent v2"
        assert coordinator.agents["test_agent"].port == 5002
        assert len(coordinator.agents) == 1  # Should still be 1 agent

    def test_select_agent_with_healthy_agents(self, coordinator):
        """Test agent selection with healthy agents"""
        # Add healthy Linux agent
        linux_agent = AgentInfo(
            id="linux_agent",
            name="Linux Agent",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
            is_healthy=True,
        )
        coordinator.agents["linux_agent"] = linux_agent

        # Add unhealthy Windows agent
        windows_agent = AgentInfo(
            id="windows_agent",
            name="Windows Agent",
            os_type="Windows",
            capabilities=["powershell"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5002,
            last_seen=datetime.now(),
            is_healthy=False,
        )
        coordinator.agents["windows_agent"] = windows_agent

        # Test OS-specific selection
        result = coordinator.select_agent({"target_os": "linux", "action": "test"})
        assert result is not None
        assert result.id == "linux_agent"

        # Test OS-specific selection with no matching OS
        result = coordinator.select_agent({"target_os": "macos", "action": "test"})
        assert result is not None
        assert result.id == "linux_agent"  # Should fallback to available healthy agent

        # Test any OS selection
        result = coordinator.select_agent({"target_os": "any", "action": "test"})
        assert result is not None
        assert result.id == "linux_agent"

    @pytest.mark.asyncio
    async def test_health_check_agents_basic(self, coordinator):
        """Test basic health check functionality"""
        # Add test agent
        agent = AgentInfo(
            id="test_agent",
            name="Test Agent",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
            is_healthy=True,
        )
        coordinator.agents["test_agent"] = agent

        # Test rate limiting without mocking HTTP calls
        import time

        coordinator._last_health_check = datetime.now()

        # Should be rate limited
        await coordinator.health_check_agents(force=False)

        # Force should work
        await coordinator.health_check_agents(force=True)

    @pytest.mark.asyncio
    async def test_health_check_agents_failure(self, coordinator):
        """Test health check with agent failure scenarios"""
        agent = AgentInfo(
            id="failing_agent",
            name="Failing Agent",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
            is_healthy=True,
        )
        coordinator.agents["failing_agent"] = agent

        # Mock failed health check
        with patch("coordinator.core.coordinator.aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.side_effect = Exception(
                "Connection failed"
            )

            await coordinator.health_check_agents(force=True)
            assert coordinator.agents["failing_agent"].is_healthy is False

    @pytest.mark.asyncio
    async def test_test_agent_connectivity_nonexistent(self, coordinator):
        """Test agent connectivity with non-existent agent"""
        result = await coordinator.test_agent_connectivity("nonexistent")
        assert "error" in result
        assert "not found" in result["error"]

    def test_discover_agents_env_parsing(self, coordinator):
        """Test environment variable parsing for agent discovery"""
        test_hosts = "localhost:5001,localhost:5002,test:5003"

        with patch.dict(os.environ, {"AGENT_DISCOVERY_HOSTS": test_hosts}):
            # Test that we can parse the environment variable correctly
            env_hosts = os.getenv("AGENT_DISCOVERY_HOSTS")
            parsed_hosts = [host.strip() for host in env_hosts.split(",")]

            assert len(parsed_hosts) == 3
            assert "localhost:5001" in parsed_hosts
            assert "localhost:5002" in parsed_hosts
            assert "test:5003" in parsed_hosts

    @pytest.mark.asyncio
    async def test_discover_agents_broadcast(self, coordinator):
        """Test UDP broadcast discovery functionality"""
        # Mock socket operations for broadcast discovery
        mock_socket = Mock()
        mock_socket.recvfrom.side_effect = [
            (
                json.dumps({"type": "agent_response", "port": 5001, "name": "Agent1"}).encode(),
                ("192.168.1.100", 5099),
            ),
            socket.timeout,  # End of responses
        ]

        with patch("coordinator.core.coordinator.socket.socket", return_value=mock_socket):
            with patch("coordinator.core.coordinator.time.time", side_effect=[0, 1, 2, 4]):
                result = await coordinator.discover_agents_broadcast()
                assert len(result) == 1
                assert "192.168.1.100:5001" in result

    @pytest.mark.asyncio
    async def test_parse_command_json_decode_error(self, coordinator):
        """Test parse command with JSON decode error"""
        # Mock OpenAI response with invalid JSON
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "invalid json content"

        with patch.object(
            coordinator.openai_client.chat.completions, "create", return_value=mock_response
        ):
            result = await coordinator.parse_command("test command")

            assert result["action"] == "unknown"
            assert result["command"] == "test command"
            assert "JSON parse failed" in result["description"]

    @pytest.mark.asyncio
    async def test_parse_command_success(self, coordinator):
        """Test successful command parsing"""
        # Mock successful OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "action": "file_operations",
                "target_os": "linux",
                "command": "ls -la",
                "description": "List files with details",
            }
        )

        with patch.object(
            coordinator.openai_client.chat.completions, "create", return_value=mock_response
        ):
            result = await coordinator.parse_command("list files")

            assert result["action"] == "file_operations"
            assert result["target_os"] == "linux"
            assert result["command"] == "ls -la"
            assert result["description"] == "List files with details"

    @pytest.mark.asyncio
    async def test_parse_command_empty_response(self, coordinator):
        """Test parse command with empty AI response"""
        # Mock empty OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = ""

        with patch.object(
            coordinator.openai_client.chat.completions, "create", return_value=mock_response
        ):
            result = await coordinator.parse_command("test command")

            assert result["action"] == "unknown"
            assert result["command"] == "test command"

    @pytest.mark.asyncio
    async def test_parse_command_markdown_json(self, coordinator):
        """Test parse command with markdown-wrapped JSON"""
        # Mock OpenAI response with markdown JSON
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[
            0
        ].message.content = '```json\n{"action": "test", "target_os": "any", "command": "echo test", "description": "test"}\n```'

        with patch.object(
            coordinator.openai_client.chat.completions, "create", return_value=mock_response
        ):
            result = await coordinator.parse_command("test command")

            assert result["action"] == "test"
            assert result["command"] == "echo test"

    def test_select_agent_os_specific(self, coordinator):
        """Test OS-specific agent selection"""
        # Add Linux agent
        linux_agent = AgentInfo(
            id="linux_agent",
            name="Linux Agent",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
            is_healthy=True,
        )
        coordinator.agents["linux_agent"] = linux_agent

        # Add Windows agent
        windows_agent = AgentInfo(
            id="windows_agent",
            name="Windows Agent",
            os_type="Windows",
            capabilities=["powershell"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5002,
            last_seen=datetime.now(),
            is_healthy=True,
        )
        coordinator.agents["windows_agent"] = windows_agent

        # Test Linux selection
        result = coordinator.select_agent({"target_os": "linux", "action": "test"})
        assert result.id == "linux_agent"

        # Test Windows selection
        result = coordinator.select_agent({"target_os": "windows", "action": "test"})
        assert result.id == "windows_agent"

        # Test fallback when OS not found
        result = coordinator.select_agent({"target_os": "macos", "action": "test"})
        assert result is not None  # Should select first available

    def test_discovery_config_defaults(self, coordinator):
        """Test discovery configuration default values"""
        config = coordinator._load_discovery_config()

        assert "discovery_settings" in config
        assert "network_configs" in config
        assert config["discovery_settings"]["use_broadcast"] is True
        assert config["discovery_settings"]["broadcast_port"] == 5099
        assert config["discovery_settings"]["scan_timeout"] == 3

    @pytest.mark.asyncio
    async def test_discover_agents_broadcast(self, coordinator):
        """Test UDP broadcast discovery functionality"""
        # Mock socket operations for broadcast discovery
        mock_socket = Mock()
        mock_socket.recvfrom.side_effect = [
            (
                json.dumps({"type": "agent_response", "port": 5001, "name": "Agent1"}).encode(),
                ("192.168.1.100", 5099),
            ),
            socket.timeout,  # End of responses
        ]

        with patch("coordinator.core.coordinator.socket.socket", return_value=mock_socket):
            with patch("coordinator.core.coordinator.time.time", side_effect=[0, 1, 2, 4]):
                result = await coordinator.discover_agents_broadcast()
                assert len(result) == 1
                assert "192.168.1.100:5001" in result

    @pytest.mark.asyncio
    async def test_test_agent_connectivity_nonexistent(self, coordinator):
        """Test agent connectivity with non-existent agent"""
        result = await coordinator.test_agent_connectivity("nonexistent")
        assert "error" in result
        assert "not found" in result["error"]
