import asyncio
import json
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import aiohttp
import pytest

from coordinator.core.coordinator import Coordinator
from shared.models import AgentInfo, CommandResult, MessageType, Permission


class TestCoordinator:
    @pytest.fixture
    def coordinator(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("coordinator.core.coordinator.OpenAI"):
                return Coordinator()

    def test_coordinator_initialization(self, coordinator):
        assert coordinator.agents == {}
        assert coordinator.command_history == []
        assert coordinator.discovery_config is not None
        assert "discovery_settings" in coordinator.discovery_config

    def test_load_discovery_config_default(self, coordinator):
        config = coordinator.discovery_config
        assert config["discovery_settings"]["use_broadcast"] is True
        assert config["discovery_settings"]["broadcast_port"] == 5099
        assert config["discovery_settings"]["scan_network"] is False

    @patch("coordinator.core.coordinator.os.path.exists", return_value=True)
    @patch("builtins.open")
    def test_load_discovery_config_from_file(self, mock_open, mock_exists):
        test_config = {
            "discovery_settings": {
                "use_broadcast": False,
                "broadcast_port": 5100,
                "scan_network": True,
            }
        }

        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(test_config)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("coordinator.core.coordinator.OpenAI"):
                coordinator = Coordinator()

        assert coordinator.discovery_config["discovery_settings"]["use_broadcast"] is False
        assert coordinator.discovery_config["discovery_settings"]["broadcast_port"] == 5100

    @pytest.mark.asyncio
    async def test_register_agent(self, coordinator):
        agent_info = AgentInfo(
            id="test_agent",
            name="Test Agent",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
        )

        await coordinator.register_agent(agent_info)

        assert "test_agent" in coordinator.agents
        assert coordinator.agents["test_agent"] == agent_info

    @pytest.mark.asyncio
    async def test_register_agent_replacement(self, coordinator):
        # Register first agent
        agent1 = AgentInfo(
            id="duplicate_agent",
            name="First Agent",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
        )
        await coordinator.register_agent(agent1)

        # Register second agent with same ID
        agent2 = AgentInfo(
            id="duplicate_agent",
            name="Second Agent",
            os_type="Windows",
            capabilities=["powershell"],
            permissions=[Permission.ADMIN],
            host="localhost",
            port=5002,
            last_seen=datetime.now(),
        )
        await coordinator.register_agent(agent2)

        assert len(coordinator.agents) == 1
        assert coordinator.agents["duplicate_agent"].name == "Second Agent"
        assert coordinator.agents["duplicate_agent"].os_type == "Windows"

    @patch("coordinator.core.coordinator.socket.gethostname", return_value="test-host")
    @patch("coordinator.core.coordinator.socket.gethostbyname", return_value="192.168.1.100")
    @patch("coordinator.core.coordinator.ipaddress.IPv4Network")
    def test_get_local_network_range(
        self, mock_network, mock_gethostbyname, mock_gethostname, coordinator
    ):
        # Mock network hosts
        mock_network.return_value.hosts.return_value = [
            Mock(__str__=lambda self: f"192.168.1.{i}") for i in range(1, 30)
        ]

        network_range = coordinator._get_local_network_range()

        assert len(network_range) == 20  # Limited to first 20
        assert "192.168.1.1" in network_range
        assert "192.168.1.20" in network_range

    @patch("coordinator.core.coordinator.socket.socket")
    @patch("coordinator.core.coordinator.json.dumps")
    @patch("coordinator.core.coordinator.json.loads")
    @patch("coordinator.core.coordinator.time.time")
    @pytest.mark.asyncio
    async def test_discover_agents_broadcast(
        self, mock_time, mock_json_loads, mock_json_dumps, mock_socket, coordinator
    ):
        # Mock time for timeout calculation
        mock_time.side_effect = [0, 0, 1, 4]  # start, listen start, response, end

        # Mock socket
        mock_sock = Mock()
        mock_socket.return_value = mock_sock

        # Mock broadcast response
        mock_response = {
            "type": "agent_response",
            "port": 5001,
            "name": "Test Agent",
            "os_type": "Linux",
        }
        mock_json_loads.return_value = mock_response
        mock_sock.recvfrom.return_value = (b'{"type":"agent_response"}', ("192.168.1.100", 5099))

        result = await coordinator.discover_agents_broadcast()

        assert len(result) == 1
        assert result[0] == "192.168.1.100:5001"

    @patch("coordinator.core.coordinator.aiohttp.ClientSession")
    @pytest.mark.asyncio
    async def test_discover_agents_http_success(self, mock_session, coordinator):
        # Mock successful HTTP response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "id": "test_agent",
                "name": "Test Agent",
                "os_type": "Linux",
                "capabilities": ["bash"],
                "permissions": ["file_read"],
                "host": "192.168.1.100",
                "port": 5001,
                "last_seen": datetime.now().isoformat(),
                "is_healthy": True,
            }
        )

        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = (
            mock_response
        )

        await coordinator.discover_agents(["192.168.1.100:5001"])

        assert len(coordinator.agents) == 1
        assert "test_agent" in coordinator.agents

    @patch("coordinator.core.coordinator.aiohttp.ClientSession")
    @pytest.mark.asyncio
    async def test_health_check_agents_success(self, mock_session, coordinator):
        # Add test agent
        agent_info = AgentInfo(
            id="health_test_agent",
            name="Health Test",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
        )
        await coordinator.register_agent(agent_info)

        # Mock successful health response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "healthy"})

        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = (
            mock_response
        )

        await coordinator.health_check_agents(force=True)

        assert coordinator.agents["health_test_agent"].is_healthy is True

    @patch("coordinator.core.coordinator.aiohttp.ClientSession")
    @pytest.mark.asyncio
    async def test_health_check_agents_failure(self, mock_session, coordinator):
        # Add test agent
        agent_info = AgentInfo(
            id="unhealthy_agent",
            name="Unhealthy Test",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
        )
        await coordinator.register_agent(agent_info)

        # Mock failed health response (raises exception)
        mock_session.return_value.__aenter__.return_value.get.side_effect = aiohttp.ClientError(
            "Connection failed"
        )

        await coordinator.health_check_agents(force=True)

        assert coordinator.agents["unhealthy_agent"].is_healthy is False

    @pytest.mark.asyncio
    async def test_health_check_agents_rate_limiting(self, coordinator):
        # Set recent health check time
        coordinator._last_health_check = datetime.now() - timedelta(seconds=5)

        # Mock to track if health check actually runs
        with patch.object(coordinator, "_health_check_lock") as mock_lock:
            mock_lock.__aenter__ = AsyncMock()
            mock_lock.__aexit__ = AsyncMock()

            await coordinator.health_check_agents(force=False)

            # Should be skipped due to rate limiting
            mock_lock.__aenter__.assert_not_called()

    @pytest.mark.asyncio
    async def test_test_agent_connectivity(self, coordinator):
        # Add test agent
        agent_info = AgentInfo(
            id="connectivity_test",
            name="Connectivity Test",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
        )
        await coordinator.register_agent(agent_info)

        with patch("coordinator.core.coordinator.aiohttp.ClientSession") as mock_session:
            # Mock health endpoint response
            health_response = Mock()
            health_response.status = 200
            health_response.json = AsyncMock(return_value={"status": "healthy"})

            # Mock capabilities endpoint response
            capabilities_response = Mock()
            capabilities_response.status = 200
            capabilities_response.json = AsyncMock(return_value={"capabilities": ["bash"]})

            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.side_effect = [
                health_response,
                capabilities_response,
            ]

            result = await coordinator.test_agent_connectivity("connectivity_test")

            assert "health_status" in result
            assert result["health_status"] == 200
            assert "capabilities_status" in result
            assert result["capabilities_status"] == 200

    @pytest.mark.asyncio
    async def test_test_agent_connectivity_not_found(self, coordinator):
        result = await coordinator.test_agent_connectivity("nonexistent_agent")

        assert "error" in result
        assert "not found" in result["error"]

    @patch("coordinator.core.coordinator.json.loads")
    @pytest.mark.asyncio
    async def test_parse_command_success(self, mock_json_loads, coordinator):
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[
            0
        ].message.content = '{"action": "file_operations", "target_os": "linux", "command": "ls -la", "description": "List files"}'

        coordinator.openai_client.chat.completions.create = Mock(return_value=mock_response)

        mock_json_loads.return_value = {
            "action": "file_operations",
            "target_os": "linux",
            "command": "ls -la",
            "description": "List files",
        }

        result = await coordinator.parse_command("list files")

        assert result["action"] == "file_operations"
        assert result["target_os"] == "linux"
        assert result["command"] == "ls -la"

    @pytest.mark.asyncio
    async def test_parse_command_json_error(self, coordinator):
        # Mock OpenAI response with invalid JSON
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "invalid json"

        coordinator.openai_client.chat.completions.create = Mock(return_value=mock_response)

        result = await coordinator.parse_command("test command")

        assert result["action"] == "unknown"
        assert result["target_os"] == "any"
        assert result["command"] == "test command"

    def test_select_agent_no_agents(self, coordinator):
        parsed_command = {"target_os": "any", "action": "test"}

        result = coordinator.select_agent(parsed_command)

        assert result is None

    @pytest.mark.asyncio
    async def test_select_agent_os_preference(self, coordinator):
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
        await coordinator.register_agent(linux_agent)

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
        await coordinator.register_agent(windows_agent)

        # Test Linux preference
        parsed_command = {"target_os": "linux", "action": "test"}
        result = coordinator.select_agent(parsed_command)

        assert result.id == "linux_agent"

        # Test Windows preference
        parsed_command = {"target_os": "windows", "action": "test"}
        result = coordinator.select_agent(parsed_command)

        assert result.id == "windows_agent"

    @pytest.mark.asyncio
    async def test_select_agent_healthy_only(self, coordinator):
        # Add healthy agent
        healthy_agent = AgentInfo(
            id="healthy_agent",
            name="Healthy Agent",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
            is_healthy=True,
        )
        await coordinator.register_agent(healthy_agent)

        # Add unhealthy agent
        unhealthy_agent = AgentInfo(
            id="unhealthy_agent",
            name="Unhealthy Agent",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5002,
            last_seen=datetime.now(),
            is_healthy=False,
        )
        await coordinator.register_agent(unhealthy_agent)

        parsed_command = {"target_os": "any", "action": "test"}
        result = coordinator.select_agent(parsed_command)

        assert result.id == "healthy_agent"

    @patch("coordinator.core.coordinator.aiohttp.ClientSession")
    @pytest.mark.asyncio
    async def test_execute_command_success(self, mock_session, coordinator):
        # Add test agent
        agent_info = AgentInfo(
            id="exec_test_agent",
            name="Execution Test",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
            is_healthy=True,
        )
        await coordinator.register_agent(agent_info)

        # Mock parse command
        with patch.object(
            coordinator,
            "parse_command",
            return_value={
                "action": "file_operations",
                "target_os": "linux",
                "command": "ls -la",
                "description": "List files",
            },
        ):
            # Mock HTTP response
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={
                    "success": True,
                    "output": "file1.txt\nfile2.txt\n",
                    "error": "",
                    "execution_time_ms": 100,
                    "command": "ls -la",
                    "agent_id": "exec_test_agent",
                }
            )

            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = (
                mock_response
            )

            result = await coordinator.execute_command("list files")

            assert result.success is True
            assert result.output == "file1.txt\nfile2.txt\n"
            assert len(coordinator.command_history) == 1

    @pytest.mark.asyncio
    async def test_execute_command_no_healthy_agents(self, coordinator):
        # Add unhealthy agent
        unhealthy_agent = AgentInfo(
            id="unhealthy_agent",
            name="Unhealthy Agent",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
            is_healthy=False,
        )
        await coordinator.register_agent(unhealthy_agent)

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
            result = await coordinator.execute_command("test command")

            assert result.success is False
            assert "No healthy agents available" in result.error
