import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

from coordinator.core.coordinator import Coordinator
from coordinator.web.interface import WebInterface
from shared.models import AgentInfo, CommandResult, Permission


class TestWebInterface:
    @pytest.fixture
    def mock_coordinator(self):
        coordinator = Mock(spec=Coordinator)
        coordinator.agents = {}
        coordinator.command_history = []
        coordinator.discover_agents = AsyncMock()
        coordinator.execute_command = AsyncMock()
        return coordinator

    @pytest.fixture
    def web_interface(self, mock_coordinator):
        return WebInterface(mock_coordinator)

    @pytest.fixture
    def test_client(self, web_interface):
        return TestClient(web_interface.app)

    def test_web_interface_initialization(self, mock_coordinator):
        with patch("coordinator.web.interface.StaticFiles"):
            with patch("coordinator.web.interface.Jinja2Templates"):
                web_interface = WebInterface(mock_coordinator)

                assert web_interface.coordinator == mock_coordinator
                assert web_interface.app is not None
                assert web_interface.active_websockets == []

    def test_dashboard_route(self, test_client, mock_coordinator):
        # Mock some agents
        from shared.models import AgentInfo, Permission

        agent1 = AgentInfo(
            id="agent1",
            name="Agent 1",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
            is_healthy=True,
        )

        agent2 = AgentInfo(
            id="agent2",
            name="Agent 2",
            os_type="Windows",
            capabilities=["powershell"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5002,
            last_seen=datetime.now(),
            is_healthy=False,
        )

        mock_coordinator.agents = {"agent1": agent1, "agent2": agent2}
        mock_coordinator.command_history = [{"test": "history"}]

        response = test_client.get("/")

        assert response.status_code == 200
        # Should return HTML response
        assert "text/html" in response.headers.get("content-type", "")

    def test_execute_command_web_success(self, test_client, web_interface, mock_coordinator):
        # Mock successful command execution
        mock_result = CommandResult(
            success=True,
            output="Command successful",
            execution_time_ms=150,
            command="ls -la",
            agent_id="test_agent",
        )
        mock_coordinator.execute_command = AsyncMock(return_value=mock_result)

        # Mock broadcast function
        web_interface._broadcast_to_websockets = AsyncMock()

        response = test_client.post("/execute", data={"command": "list files"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["output"] == "Command successful"
        assert data["execution_time_ms"] == 150
        assert data["agent_id"] == "test_agent"

    def test_execute_command_web_failure(self, test_client, web_interface, mock_coordinator):
        # Mock failed command execution
        mock_result = CommandResult(
            success=False,
            error="Command failed",
            execution_time_ms=50,
            command="invalid command",
            agent_id="test_agent",
        )
        mock_coordinator.execute_command = AsyncMock(return_value=mock_result)

        # Mock broadcast function
        web_interface._broadcast_to_websockets = AsyncMock()

        response = test_client.post("/execute", data={"command": "invalid command"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Command failed"
        assert data["execution_time_ms"] == 50

    def test_execute_command_web_exception(self, test_client, web_interface, mock_coordinator):
        # Mock exception during command execution
        mock_coordinator.execute_command = AsyncMock(side_effect=Exception("Execution error"))

        # Mock broadcast function
        web_interface._broadcast_to_websockets = AsyncMock()

        response = test_client.post("/execute", data={"command": "test command"})

        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert "Execution error" in data["error"]

    def test_get_agents_status(self, test_client, mock_coordinator):
        # Mock agents
        agent1 = AgentInfo(
            id="agent1",
            name="Agent 1",
            os_type="Linux",
            capabilities=["bash"],
            permissions=[Permission.FILE_READ],
            host="localhost",
            port=5001,
            last_seen=datetime.now(),
            is_healthy=True,
        )

        agent2 = AgentInfo(
            id="agent2",
            name="Agent 2",
            os_type="Windows",
            capabilities=["powershell"],
            permissions=[Permission.ADMIN],
            host="localhost",
            port=5002,
            last_seen=datetime.now(),
            is_healthy=False,
        )

        mock_coordinator.agents = {"agent1": agent1, "agent2": agent2}

        response = test_client.get("/agents/status")

        assert response.status_code == 200
        data = response.json()
        assert len(data["agents"]) == 2
        assert data["healthy_count"] == 1
        assert data["total_count"] == 2

        # Check agent details
        agent_ids = [agent["id"] for agent in data["agents"]]
        assert "agent1" in agent_ids
        assert "agent2" in agent_ids

    def test_discover_agents_endpoint_success(self, test_client, web_interface, mock_coordinator):
        mock_coordinator.discover_agents = AsyncMock()
        mock_coordinator.agents = {"agent1": Mock(), "agent2": Mock()}

        # Mock broadcast function
        web_interface._broadcast_to_websockets = AsyncMock()

        response = test_client.post("/agents/discover")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Found 2 agents" in data["message"]

        # Should have called discover_agents
        mock_coordinator.discover_agents.assert_called_once()

    def test_discover_agents_endpoint_failure(self, test_client, web_interface, mock_coordinator):
        mock_coordinator.discover_agents = AsyncMock(side_effect=Exception("Discovery failed"))

        # Mock broadcast function
        web_interface._broadcast_to_websockets = AsyncMock()

        response = test_client.post("/agents/discover")

        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert "Discovery failed" in data["error"]

    @pytest.mark.asyncio
    async def test_broadcast_to_websockets_no_connections(self, web_interface):
        # Test with no active connections
        web_interface.active_websockets = []

        message = {"type": "test", "data": "test_data"}
        await web_interface._broadcast_to_websockets(message)

        # Should not raise any errors

    @pytest.mark.asyncio
    async def test_broadcast_to_websockets_success(self, web_interface):
        # Mock WebSocket connections
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws1.send_text = AsyncMock()

        mock_ws2 = Mock(spec=WebSocket)
        mock_ws2.send_text = AsyncMock()

        web_interface.active_websockets = [mock_ws1, mock_ws2]

        message = {"type": "test", "data": "test_data"}
        await web_interface._broadcast_to_websockets(message)

        # Both WebSockets should receive the message
        mock_ws1.send_text.assert_called_once_with(json.dumps(message))
        mock_ws2.send_text.assert_called_once_with(json.dumps(message))

    @pytest.mark.asyncio
    async def test_broadcast_to_websockets_with_disconnected(self, web_interface):
        # Mock WebSocket connections - one working, one failing
        mock_ws_working = Mock(spec=WebSocket)
        mock_ws_working.send_text = AsyncMock()

        mock_ws_failing = Mock(spec=WebSocket)
        mock_ws_failing.send_text = AsyncMock(side_effect=Exception("Connection failed"))

        web_interface.active_websockets = [mock_ws_working, mock_ws_failing]

        message = {"type": "test", "data": "test_data"}
        await web_interface._broadcast_to_websockets(message)

        # Working connection should receive message
        mock_ws_working.send_text.assert_called_once_with(json.dumps(message))

        # Failing connection should be removed from active_websockets
        assert mock_ws_working in web_interface.active_websockets
        assert mock_ws_failing not in web_interface.active_websockets

    @pytest.mark.asyncio
    async def test_start_periodic_updates(self, web_interface, mock_coordinator):
        # Mock sleep to avoid actual delays in test
        original_sleep = asyncio.sleep
        sleep_call_count = 0

        def mock_sleep(duration):
            nonlocal sleep_call_count
            sleep_call_count += 1
            # Only run one iteration to avoid infinite loop in test
            if sleep_call_count >= 2:  # Initial 60s wait + first iteration
                raise KeyboardInterrupt("Test termination")
            return original_sleep(0)  # Return immediately

        mock_coordinator.health_check_agents = AsyncMock()
        mock_coordinator.agents = {"agent1": Mock(is_healthy=True)}
        web_interface._broadcast_to_websockets = AsyncMock()

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(KeyboardInterrupt):
                await web_interface.start_periodic_updates()

        # Should have performed health check and broadcast
        mock_coordinator.health_check_agents.assert_called()
        web_interface._broadcast_to_websockets.assert_called()

    @pytest.mark.asyncio
    async def test_start_periodic_updates_exception_handling(self, web_interface, mock_coordinator):
        # Mock health check to raise exception
        mock_coordinator.health_check_agents = AsyncMock(
            side_effect=Exception("Health check failed")
        )
        mock_coordinator.agents = {}

        sleep_call_count = 0

        def mock_sleep(duration):
            nonlocal sleep_call_count
            sleep_call_count += 1
            # Terminate test after a few iterations
            if sleep_call_count >= 3:
                raise KeyboardInterrupt("Test termination")
            return asyncio.sleep(0)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(KeyboardInterrupt):
                await web_interface.start_periodic_updates()

        # Should have attempted health check multiple times despite exceptions
        assert mock_coordinator.health_check_agents.call_count > 0


class TestWebSocketEndpoint:
    @pytest.fixture
    def mock_coordinator(self):
        coordinator = Mock(spec=Coordinator)
        coordinator.agents = {}
        coordinator.command_history = []
        return coordinator

    @pytest.fixture
    def web_interface(self, mock_coordinator):
        return WebInterface(mock_coordinator)

    def test_websocket_connection(self, web_interface):
        # Test WebSocket connection handling with TestClient
        client = TestClient(web_interface.app)

        # Test WebSocket connection
        with client.websocket_connect("/ws") as websocket:
            # Should receive connection established message
            data = websocket.receive_json()
            assert data["type"] == "connection_established"
            assert "Connected to A.L.F.R.E.D." in data["message"]

            # Check that websocket was added to active connections
            # Note: In test environment, the actual WebSocket object might be different
            # but we can verify the endpoint works

    @pytest.mark.asyncio
    async def test_websocket_endpoint_flow(self, web_interface):
        # Mock WebSocket
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        mock_websocket.receive_text = AsyncMock(side_effect=["keepalive", "ping"])

        # Simulate WebSocket disconnection after 2 messages
        call_count = 0

        def mock_receive():
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                from fastapi.websockets import WebSocketDisconnect

                raise WebSocketDisconnect()
            return "message"

        mock_websocket.receive_text = AsyncMock(side_effect=mock_receive)

        # Call the endpoint coroutine directly
        websocket_endpoint = web_interface.app.routes[-1].endpoint  # Get websocket endpoint
        await websocket_endpoint(mock_websocket)

        # Should have accepted connection and sent welcome message
        mock_websocket.accept.assert_called_once()
        mock_websocket.send_text.assert_called_once()

        # WebSocket should have been added and then removed from active connections
        assert mock_websocket not in web_interface.active_websockets
