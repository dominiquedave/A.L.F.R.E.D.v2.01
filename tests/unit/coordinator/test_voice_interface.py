import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import boto3
import pygame
import pytest
import speech_recognition as sr

from coordinator.core.coordinator import Coordinator
from coordinator.voice.interface import BatColors, VoiceInterface
from shared.models import CommandResult


class TestBatColors:
    def test_bat_colors_constants(self):
        assert isinstance(BatColors.BLACK, str)
        assert isinstance(BatColors.PURPLE, str)
        assert isinstance(BatColors.CYAN, str)
        assert isinstance(BatColors.RESET, str)
        assert isinstance(BatColors.BAT_TITLE, str)
        assert isinstance(BatColors.BAT_SUCCESS, str)
        assert isinstance(BatColors.BAT_ERROR, str)


class TestVoiceInterface:
    @pytest.fixture
    def mock_coordinator(self):
        coordinator = Mock(spec=Coordinator)
        coordinator.agents = {}
        coordinator.health_check_agents = AsyncMock()
        coordinator.execute_command = AsyncMock()
        return coordinator

    @pytest.fixture
    def voice_interface(self, mock_coordinator):
        with patch("coordinator.voice.interface.sr.Recognizer"):
            with patch("coordinator.voice.interface.sr.Microphone"):
                with patch("coordinator.voice.interface.pygame.mixer.init"):
                    with patch.object(VoiceInterface, "_display_bat_startup"):
                        with patch.dict(
                            os.environ,
                            {
                                "AWS_ACCESS_KEY_ID": "test_key",
                                "AWS_SECRET_ACCESS_KEY": "test_secret",
                                "AWS_REGION": "us-east-1",
                            },
                        ):
                            with patch("coordinator.voice.interface.boto3.Session"):
                                return VoiceInterface(mock_coordinator)

    def test_voice_interface_initialization(self, mock_coordinator):
        with patch("coordinator.voice.interface.sr.Recognizer") as mock_recognizer:
            with patch("coordinator.voice.interface.sr.Microphone") as mock_microphone:
                with patch("coordinator.voice.interface.pygame.mixer.init"):
                    with patch.object(VoiceInterface, "_display_bat_startup"):
                        with patch.dict(
                            os.environ,
                            {
                                "AWS_ACCESS_KEY_ID": "test_key",
                                "AWS_SECRET_ACCESS_KEY": "test_secret",
                            },
                        ):
                            with patch("coordinator.voice.interface.boto3.Session") as mock_boto3:
                                mock_session = Mock()
                                mock_polly = Mock()
                                mock_session.client.return_value = mock_polly
                                mock_boto3.return_value = mock_session

                                voice_interface = VoiceInterface(mock_coordinator)

                                assert voice_interface.coordinator == mock_coordinator
                                assert voice_interface.recognizer is not None
                                assert voice_interface.microphone is not None
                                assert voice_interface.polly_client == mock_polly
                                assert voice_interface.voice_id == "Brian"

    def test_voice_interface_no_aws_credentials(self, mock_coordinator):
        with patch("coordinator.voice.interface.sr.Recognizer"):
            with patch("coordinator.voice.interface.sr.Microphone"):
                with patch("coordinator.voice.interface.pygame.mixer.init"):
                    with patch.object(VoiceInterface, "_display_bat_startup"):
                        with patch.dict(os.environ, {}, clear=True):
                            voice_interface = VoiceInterface(mock_coordinator)

                            assert voice_interface.polly_client is None

    @patch("coordinator.voice.interface.os.system")
    @patch("coordinator.voice.interface.platform.system", return_value="Linux")
    @patch.dict(os.environ, {}, clear=True)  # No NO_ANSI env var
    def test_display_bat_startup_clears_screen(self, mock_platform, mock_system, voice_interface):
        voice_interface._display_bat_startup()
        mock_system.assert_called_with("clear")

    @patch("coordinator.voice.interface.os.system")
    @patch("coordinator.voice.interface.platform.system", return_value="Windows")
    @patch.dict(os.environ, {}, clear=True)
    def test_display_bat_startup_clears_screen_windows(
        self, mock_platform, mock_system, voice_interface
    ):
        voice_interface._display_bat_startup()
        mock_system.assert_called_with("cls")

    @patch("coordinator.voice.interface.os.system")
    @patch.dict(os.environ, {"NO_ANSI": "1"})
    def test_display_bat_startup_no_clear(self, mock_system, voice_interface):
        voice_interface._display_bat_startup()
        mock_system.assert_not_called()

    @pytest.mark.asyncio
    async def test_listen_for_command_success(self, voice_interface):
        mock_audio = Mock()

        with patch.object(voice_interface.recognizer, "listen", return_value=mock_audio):
            with patch.object(
                voice_interface.recognizer, "recognize_google", return_value="test command"
            ):
                with patch("asyncio.to_thread", side_effect=lambda func, *args: func(*args)):
                    result = await voice_interface.listen_for_command()

                    assert result == "test command"

    @pytest.mark.asyncio
    async def test_listen_for_command_timeout(self, voice_interface):
        with patch.object(voice_interface.recognizer, "listen", side_effect=sr.WaitTimeoutError()):
            with patch("asyncio.to_thread", side_effect=lambda func, *args: func(*args)):
                result = await voice_interface.listen_for_command()

                assert result is None

    @pytest.mark.asyncio
    async def test_listen_for_command_unknown_value(self, voice_interface):
        mock_audio = Mock()

        with patch.object(voice_interface.recognizer, "listen", return_value=mock_audio):
            with patch.object(
                voice_interface.recognizer, "recognize_google", side_effect=sr.UnknownValueError()
            ):
                with patch("asyncio.to_thread", side_effect=lambda func, *args: func(*args)):
                    result = await voice_interface.listen_for_command()

                    assert result is None

    @pytest.mark.asyncio
    async def test_listen_for_command_request_error(self, voice_interface):
        mock_audio = Mock()

        with patch.object(voice_interface.recognizer, "listen", return_value=mock_audio):
            with patch.object(
                voice_interface.recognizer,
                "recognize_google",
                side_effect=sr.RequestError("API error"),
            ):
                with patch("asyncio.to_thread", side_effect=lambda func, *args: func(*args)):
                    result = await voice_interface.listen_for_command()

                    assert result is None

    def test_speak_response_no_polly(self, voice_interface):
        voice_interface.polly_client = None

        with patch("builtins.print") as mock_print:
            voice_interface.speak_response("test message")

            mock_print.assert_called()
            # Should print message but not attempt TTS

    def test_speak_response_with_polly_success(self, voice_interface):
        mock_polly_response = {"AudioStream": Mock()}
        mock_polly_response["AudioStream"].read.return_value = b"mock_audio_data"

        voice_interface.polly_client = Mock()
        voice_interface.polly_client.synthesize_speech.return_value = mock_polly_response

        with patch("coordinator.voice.interface.pygame.mixer.music") as mock_music:
            with patch("coordinator.voice.interface.os.path.exists", return_value=True):
                with patch("coordinator.voice.interface.os.access", return_value=True):
                    with patch("builtins.open", create=True) as mock_open:
                        with patch("coordinator.voice.interface.os.remove"):
                            mock_music.get_busy.return_value = False

                            voice_interface.speak_response("test message")

                            voice_interface.polly_client.synthesize_speech.assert_called_once()
                            mock_music.load.assert_called_once()
                            mock_music.play.assert_called_once()

    def test_speak_response_with_polly_permission_error(self, voice_interface):
        mock_polly_response = {"AudioStream": Mock()}
        mock_polly_response["AudioStream"].read.return_value = b"mock_audio_data"

        voice_interface.polly_client = Mock()
        voice_interface.polly_client.synthesize_speech.return_value = mock_polly_response

        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with patch("builtins.print") as mock_print:
                voice_interface.speak_response("test message")

                # Should handle error gracefully and continue with text-only output
                mock_print.assert_called()

    def test_speak_response_with_polly_error(self, voice_interface):
        voice_interface.polly_client = Mock()
        voice_interface.polly_client.synthesize_speech.side_effect = Exception("TTS error")

        with patch("builtins.print") as mock_print:
            voice_interface.speak_response("test message")

            # Should handle error gracefully
            mock_print.assert_called()

    def test_display_agent_status_no_agents(self, voice_interface):
        with patch("builtins.print") as mock_print:
            voice_interface._display_agent_status(0, 0)

            mock_print.assert_called()
            # Should display "No bats detected" message

    def test_display_agent_status_healthy_agents(self, voice_interface):
        with patch("builtins.print") as mock_print:
            voice_interface._display_agent_status(8, 10)

            mock_print.assert_called()
            # Should display agent counts and health percentage

    def test_display_agent_status_unhealthy_agents(self, voice_interface):
        with patch("builtins.print") as mock_print:
            voice_interface._display_agent_status(3, 10)

            mock_print.assert_called()
            # Should display unhealthy agent count

    @pytest.mark.asyncio
    async def test_run_voice_loop_exit_command(self, voice_interface):
        # Mock initial health check and agent status
        voice_interface.coordinator.agents = {}
        voice_interface.coordinator.health_check_agents = AsyncMock()

        # Mock voice commands: first "exit", then None to break loop
        with patch.object(voice_interface, "listen_for_command", side_effect=["exit", None]):
            with patch.object(voice_interface, "speak_response") as mock_speak:
                with patch("builtins.print"):
                    await voice_interface.run_voice_loop()

                    # Should call speak_response for exit message
                    mock_speak.assert_called()
                    exit_calls = [
                        call for call in mock_speak.call_args_list if "shadows" in str(call)
                    ]
                    assert len(exit_calls) > 0

    @pytest.mark.asyncio
    async def test_run_voice_loop_status_command(self, voice_interface):
        # Mock agents
        from datetime import datetime

        from shared.models import AgentInfo, Permission

        mock_agent = AgentInfo(
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
        voice_interface.coordinator.agents = {"test_agent": mock_agent}
        voice_interface.coordinator.health_check_agents = AsyncMock()

        # Mock voice commands: "status", then "exit"
        with patch.object(voice_interface, "listen_for_command", side_effect=["status", "exit"]):
            with patch.object(voice_interface, "speak_response") as mock_speak:
                with patch("builtins.print"):
                    await voice_interface.run_voice_loop()

                    # Should call speak_response for status and exit
                    assert mock_speak.call_count >= 2

    @pytest.mark.asyncio
    async def test_run_voice_loop_execute_command(self, voice_interface):
        # Mock agents
        from datetime import datetime

        from shared.models import AgentInfo, Permission

        mock_agent = AgentInfo(
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
        voice_interface.coordinator.agents = {"test_agent": mock_agent}
        voice_interface.coordinator.health_check_agents = AsyncMock()

        # Mock successful command execution
        mock_result = CommandResult(
            success=True,
            output="Command output",
            execution_time_ms=100,
            command="ls -la",
            agent_id="test_agent",
        )
        voice_interface.coordinator.execute_command = AsyncMock(return_value=mock_result)

        # Mock voice commands: "list files", then "exit"
        with patch.object(
            voice_interface, "listen_for_command", side_effect=["list files", "exit"]
        ):
            with patch.object(voice_interface, "speak_response") as mock_speak:
                with patch("builtins.print"):
                    await voice_interface.run_voice_loop()

                    # Should execute command and provide voice feedback
                    voice_interface.coordinator.execute_command.assert_called_with("list files")
                    mock_speak.assert_called()

    @pytest.mark.asyncio
    async def test_run_voice_loop_execute_command_failure(self, voice_interface):
        # Mock agents
        from datetime import datetime

        from shared.models import AgentInfo, Permission

        mock_agent = AgentInfo(
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
        voice_interface.coordinator.agents = {"test_agent": mock_agent}
        voice_interface.coordinator.health_check_agents = AsyncMock()

        # Mock failed command execution
        mock_result = CommandResult(
            success=False,
            error="Command failed",
            execution_time_ms=50,
            command="invalid command",
            agent_id="test_agent",
        )
        voice_interface.coordinator.execute_command = AsyncMock(return_value=mock_result)

        # Mock voice commands: "invalid command", then "exit"
        with patch.object(
            voice_interface, "listen_for_command", side_effect=["invalid command", "exit"]
        ):
            with patch.object(voice_interface, "speak_response") as mock_speak:
                with patch("builtins.print"):
                    await voice_interface.run_voice_loop()

                    # Should execute command and provide error feedback
                    voice_interface.coordinator.execute_command.assert_called_with(
                        "invalid command"
                    )
                    # Should speak error message
                    error_calls = [
                        call for call in mock_speak.call_args_list if "failed" in str(call)
                    ]
                    assert len(error_calls) > 0

    @pytest.mark.asyncio
    async def test_run_voice_loop_keyboard_interrupt(self, voice_interface):
        voice_interface.coordinator.agents = {}
        voice_interface.coordinator.health_check_agents = AsyncMock()

        # Mock KeyboardInterrupt
        with patch.object(voice_interface, "listen_for_command", side_effect=KeyboardInterrupt()):
            with patch.object(voice_interface, "speak_response") as mock_speak:
                with patch("builtins.print"):
                    await voice_interface.run_voice_loop()

                    # Should handle interrupt gracefully
                    interrupt_calls = [
                        call for call in mock_speak.call_args_list if "master" in str(call)
                    ]
                    assert len(interrupt_calls) > 0

    @pytest.mark.asyncio
    async def test_run_voice_loop_exception_handling(self, voice_interface):
        voice_interface.coordinator.agents = {}
        voice_interface.coordinator.health_check_agents = AsyncMock()

        # Mock exception, then exit
        with patch.object(
            voice_interface, "listen_for_command", side_effect=[Exception("Test error"), "exit"]
        ):
            with patch.object(voice_interface, "speak_response"):
                with patch("builtins.print"):
                    # Should handle exception and continue
                    await voice_interface.run_voice_loop()
