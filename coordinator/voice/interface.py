# Voice interface dependencies
import asyncio  # For non-blocking async operations
import logging
import os
import platform
from typing import Optional

import boto3  # Amazon Web Services SDK for Polly TTS
import pygame  # Audio playback for TTS
import pyttsx3  # Text-to-speech library (offline)
import speech_recognition as sr  # Google Speech Recognition for voice input

from coordinator.core.coordinator import Coordinator

# Configure logging for voice interface
logger = logging.getLogger(__name__)


# ANSI color codes for Batman/Bat Cave themed terminal output
class BatColors:
    """ANSI color escape codes for Batman-themed console styling."""

    # Basic colors
    BLACK = "\033[40m"
    PURPLE = "\033[45m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    SILVER = "\033[37m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"

    # Text formatting
    BOLD = "\033[1m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"  # Reset all formatting

    # Batman/Bat Cave themed color combinations
    BAT_TITLE = BOLD + MAGENTA  # For headers and titles
    BAT_SUCCESS = GREEN + BOLD  # For successful operations
    BAT_ERROR = RED + BOLD  # For errors and failures
    BAT_INFO = CYAN  # For informational messages
    BAT_WARNING = YELLOW  # For warnings and cautions
    BAT_PROMPT = PURPLE + BOLD  # For user prompts and input requests


class VoiceInterface:
    """
    Batman-themed voice interface for A.L.F.R.E.D. coordinator control.

    Provides a complete voice-controlled interface with:
    - Speech recognition using Google's speech-to-text API
    - Natural language command processing through coordinator
    - High-quality text-to-speech responses using Amazon Polly
    - Batman/Bat Cave themed console output and ASCII art
    - Atmospheric voice prompts and responses

    Features:
    - Continuous voice command loop with Batman-themed prompts
    - Real-time agent status monitoring and reporting
    - Command execution with voice feedback
    - Error handling with themed error messages
    - Graceful exit commands ("exit", "return to shadows")

    The interface creates an immersive Batman experience while providing
    full access to A.L.F.R.E.D.'s distributed agent management capabilities.
    """

    def __init__(self, coordinator: Coordinator):
        """
        Initialize the Batman-themed voice interface.

        Sets up speech recognition, audio playback, and displays the
        atmospheric Bat Cave startup screen with ASCII art.

        Args:
            coordinator (Coordinator): A.L.F.R.E.D. coordinator instance for command execution
        """
        self.coordinator = coordinator
        self.recognizer = sr.Recognizer()  # Google Speech Recognition
        self.microphone = sr.Microphone()  # Default system microphone

        # Initialize pygame mixer for TTS audio playback
        pygame.mixer.init()

        # Initialize Amazon Polly configuration
        # These should be set as environment variables for security
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = os.getenv("AWS_REGION", "us-east-1")

        if aws_access_key and aws_secret_key:
            try:
                self.polly_client = boto3.Session(
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region,
                ).client("polly")

                # Use British male neural voice (Brian - mature British male voice)
                self.voice_id = "Brian"
                logger.info("Amazon Polly TTS initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Amazon Polly: {e}")
                self.polly_client = None
        else:
            logger.warning("AWS credentials not found. TTS will be disabled.")
            self.polly_client = None

        # Calibrate microphone for ambient noise (improves recognition accuracy)
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)

        # Display dramatic Batman-themed startup screen
        self._display_bat_startup()
        logger.info("Bat Cave Voice Interface initialized")

    def _display_bat_startup(self):
        """
        Display dramatic Batman-themed startup screen with ASCII art.

        Shows the iconic "BAT CAVE" ASCII art title and system status information
        in Batman-themed colors. Clears screen first unless NO_ANSI environment
        variable is set (useful for CI/CD environments).
        """
        # Clear screen for dramatic effect (skip in CI/CD environments)
        if not os.getenv("NO_ANSI"):
            os.system("clear" if platform.system() != "Windows" else "cls")

        # ASCII art banner with Batman theming
        startup_art = f"""
{BatColors.BAT_TITLE}
    ██████╗  █████╗ ████████╗     ██████╗ █████╗ ██╗   ██╗███████╗
    ██╔══██╗██╔══██╗╚══██╔══╝    ██╔════╝██╔══██╗██║   ██║██╔════╝
    ██████╔╝███████║   ██║       ██║     ███████║██║   ██║█████╗
    ██╔══██╗██╔══██║   ██║       ██║     ██╔══██║╚██╗ ██╔╝██╔══╝
    ██████╔╝██║  ██║   ██║       ╚██████╗██║  ██║ ╚████╔╝ ███████╗
    ╚═════╝ ╚═╝  ╚═╝   ╚═╝        ╚═════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝
{BatColors.RESET}

{BatColors.BAT_INFO}            🦇 A.L.F.R.E.D. Voice Interface v2.01 🦇{BatColors.RESET}
{BatColors.SILVER}          Welcome to the Bat Cave Voice Command Center{BatColors.RESET}
{BatColors.BAT_WARNING}             Where darkness meets digital mastery{BatColors.RESET}

{BatColors.BAT_PROMPT}┌─────────────────────────────────────────────────────────────────┐
│                        🌙 SYSTEM STATUS 🌙                        │
└─────────────────────────────────────────────────────────────────┘{BatColors.RESET}

"""
        print(startup_art)

    async def listen_for_command(self, timeout=10) -> Optional[str]:
        """
        Listen for voice commands using speech recognition with Batman-themed feedback.

        Captures audio from the microphone, processes it through Google's speech
        recognition service, and returns the recognized text. Provides atmospheric
        Batman-themed console output during the process.

        Args:
            timeout (int): Maximum seconds to wait for speech input

        Returns:
            Optional[str]: Recognized command text, or None if no speech detected/recognized
        """
        try:
            # Atmospheric listening prompt
            print(
                f"{BatColors.BAT_INFO}🦇 The bats are listening... Speak your command{BatColors.RESET}"
            )

            def capture_audio():
                # Capture audio with timeout and phrase limits
                with self.microphone as source:
                    return self.recognizer.listen(source, timeout=timeout, phrase_time_limit=5)

            # Run audio capture in thread pool to avoid blocking
            audio = await asyncio.to_thread(capture_audio)

            # Processing feedback with Batman theme
            print(f"{BatColors.BAT_WARNING}🌙 Processing your dark whispers...{BatColors.RESET}")

            # Use Google Speech Recognition for high accuracy (also in thread pool)
            command = await asyncio.to_thread(self.recognizer.recognize_google, audio)

            # Success feedback with recognized command
            print(
                f"{BatColors.BAT_SUCCESS}✨ Command received: {BatColors.CYAN}'{command}'{BatColors.RESET}"
            )
            logger.info(f"Voice command recognized: {command}")
            return command

        except sr.WaitTimeoutError:
            # Handle timeout with atmospheric message
            print(f"{BatColors.BAT_WARNING}⏰ Timeout - The cave grows silent...{BatColors.RESET}")
            logger.info("Listening timeout")
            return None

        except sr.UnknownValueError:
            # Handle unrecognizable speech with Batman theme
            print(
                f"{BatColors.BAT_ERROR}🦇 Could not decipher your whispers in the darkness{BatColors.RESET}"
            )
            logger.warning("Could not understand audio")
            return None

        except sr.RequestError as e:
            # Handle speech recognition service errors
            print(f"{BatColors.BAT_ERROR}💀 Recognition service failed: {e}{BatColors.RESET}")
            logger.error(f"Recognition service error: {e}")
            return None

    def speak_response(self, text: str):
        """
        Convert text to high-quality speech using Amazon Polly.

        Uses Amazon Polly's TTS service with British male neural voice for natural-sounding
        voice output with Batman-themed console feedback. Falls back gracefully to
        text-only output if speech synthesis fails or Polly is not configured.

        Args:
            text (str): Text to convert to speech and speak
        """
        # Display response text with Batman-themed formatting
        print(f"{BatColors.BAT_PROMPT}🦇 A.L.F.R.E.D. speaks from the shadows:{BatColors.RESET}")
        print(f"{BatColors.BAT_SUCCESS}💬 {text}{BatColors.RESET}")

        # Skip TTS if Amazon Polly is not configured
        if not self.polly_client:
            print(
                f"{BatColors.BAT_WARNING}🔇 Amazon Polly not configured, using text only{BatColors.RESET}"
            )
            return

        try:
            # Generate high-quality speech using Amazon Polly (British male neural voice)
            response = self.polly_client.synthesize_speech(
                Text=text,
                OutputFormat="mp3",
                VoiceId=self.voice_id,
                Engine="neural",  # Use neural engine for higher quality
            )

            # Atmospheric playback feedback
            print(f"{BatColors.BAT_INFO}🔊 Echoing through the bat cave...{BatColors.RESET}")

            # Get audio stream from Polly response
            audio_stream = response["AudioStream"]

            # Save temporary audio file and play with pygame
            import tempfile

            try:
                # Try /tmp first, then fallback to system temp with unique filename
                if os.path.exists("/tmp") and os.access("/tmp", os.W_OK):
                    temp_file = "/tmp/polly_speech.mp3"
                else:
                    # Use tempfile to create a unique, writable temporary file
                    temp_fd, temp_file = tempfile.mkstemp(suffix=".mp3", prefix="polly_speech_")
                    os.close(temp_fd)  # Close the file descriptor, we'll reopen for writing

                with open(temp_file, "wb") as f:
                    f.write(audio_stream.read())
            except PermissionError as e:
                logger.error(f"Permission denied writing audio file: {e}")
                print(
                    f"{BatColors.BAT_ERROR}🔇 Cannot write audio file, using text only{BatColors.RESET}"
                )
                return

            # Play audio using pygame
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()

            # Wait for playback to complete
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)

            # Clean up temporary file
            if os.path.exists(temp_file):
                os.remove(temp_file)

        except Exception as e:
            # Handle TTS failures gracefully (network issues, etc.)
            logger.error(f"Speech synthesis error: {e}")
            print(
                f"{BatColors.BAT_ERROR}🔇 Voice synthesis failed, using text only{BatColors.RESET}"
            )

    def _display_agent_status(self, healthy_count: int, total_count: int):
        """
        Display agent status with Batman-themed console formatting.

        Shows agent health statistics in an atmospheric "Bat Colony Status"
        format with appropriate color coding based on health percentages.

        Args:
            healthy_count (int): Number of healthy agents
            total_count (int): Total number of registered agents
        """
        # Draw atmospheric status box header
        print(
            f"\n{BatColors.BAT_PROMPT}┌─────────────────────────────────────────────────────────────────┐"
        )
        print(f"│                     🦇 BAT COLONY STATUS 🦇                    │")
        print(
            f"└─────────────────────────────────────────────────────────────────┘{BatColors.RESET}"
        )

        if total_count == 0:
            # No agents found - atmospheric message
            print(f"{BatColors.BAT_WARNING}🌙 No bats detected in the cave...{BatColors.RESET}")
        else:
            # Calculate health percentage for color coding
            health_percentage = (healthy_count / total_count) * 100

            # Choose status color based on health percentage
            status_color = (
                BatColors.BAT_SUCCESS
                if health_percentage > 75
                else BatColors.BAT_WARNING
                if health_percentage > 50
                else BatColors.BAT_ERROR
            )

            # Display colony statistics with Batman theme
            print(
                f"{BatColors.BAT_INFO}🦇 Colony Size: {BatColors.CYAN}{total_count} bats{BatColors.RESET}"
            )
            print(
                f"{status_color}❤️  Healthy: {healthy_count} ({health_percentage:.1f}%){BatColors.RESET}"
            )

            # Show unhealthy count if any agents are down
            if healthy_count < total_count:
                unhealthy_count = total_count - healthy_count
                print(f"{BatColors.BAT_ERROR}💀 Unhealthy: {unhealthy_count} bats{BatColors.RESET}")
        print()  # Add spacing after status display

    async def run_voice_loop(self):
        """
        Main Batman-themed voice interaction loop for A.L.F.R.E.D. control.

        Provides continuous voice command processing with:
        - Initial system status check and Batman-themed greeting
        - Continuous speech recognition loop with atmospheric prompts
        - Special command handling for status checks and system exit
        - Natural language command execution through coordinator
        - Comprehensive error handling with Batman-themed feedback
        - Graceful exit options ("exit", "return to shadows", etc.)

        The loop maintains the Batman atmosphere throughout while providing
        full access to A.L.F.R.E.D.'s distributed command capabilities.
        """
        # Initialize with dramatic system status check
        await self.coordinator.health_check_agents(force=True)
        healthy_count = sum(1 for agent in self.coordinator.agents.values() if agent.is_healthy)
        total_count = len(self.coordinator.agents)
        self._display_agent_status(healthy_count, total_count)

        # Atmospheric Batman-themed greeting
        self.speak_response(
            "The Bat Cave is awakened. Your digital domain awaits your commands. Say 'exit' to return to the shadows."
        )

        # Display command interface instructions with Batman styling
        print(
            f"{BatColors.BAT_PROMPT}═══════════════════════════════════════════════════════════════════"
        )
        print(f"🎤 VOICE COMMANDS: 'status', 'agents', 'exit', or any system command")
        print(f"⌨️  KEYBOARD SHORTCUTS: Ctrl+C to exit gracefully")
        print(
            f"═══════════════════════════════════════════════════════════════════{BatColors.RESET}\n"
        )

        # Main voice command processing loop
        while True:
            try:
                # Listen for voice input with Batman-themed prompts
                command = await self.listen_for_command()

                # Skip if no command detected (timeout, etc.)
                if not command:
                    # Add small async sleep to yield control and prevent blocking
                    await asyncio.sleep(0.1)
                    continue

                # Handle exit commands with atmospheric Batman theme
                if command.lower() in ["exit", "quit", "stop", "return to shadows", "goodbye"]:
                    print(
                        f"{BatColors.BAT_SUCCESS}🌙 Voice interface returning to the darkness...{BatColors.RESET}"
                    )
                    self.speak_response(
                        "Voice interface returning to the shadows. The web console remains active."
                    )
                    break

                # Handle status/agent information commands with Batman theme
                if command.lower() in ["status", "agents", "colony status", "bat status"]:
                    print(f"{BatColors.BAT_INFO}🔍 Scanning the bat colony...{BatColors.RESET}")

                    # Force fresh health check for accurate status
                    await self.coordinator.health_check_agents(force=True)
                    healthy_count = sum(
                        1 for agent in self.coordinator.agents.values() if agent.is_healthy
                    )
                    total_count = len(self.coordinator.agents)

                    # Display visual status with Batman theming
                    self._display_agent_status(healthy_count, total_count)

                    # Generate atmospheric voice response
                    if total_count == 0:
                        response = "The bat cave appears empty, my lord. No agents have been discovered in our digital domain."
                    else:
                        response = f"Colony report: {healthy_count} healthy bats out of {total_count} total in our digital domain."
                        if healthy_count < total_count:
                            unhealthy_count = total_count - healthy_count
                            response += f" {unhealthy_count} bats require attention, master."

                    self.speak_response(response)
                    continue

                # Execute general commands through coordinator with atmospheric feedback
                print(
                    f"{BatColors.BAT_WARNING}⚡ Dispatching command to the digital realm...{BatColors.RESET}"
                )
                result = await self.coordinator.execute_command(command)

                if result.success:
                    # Handle successful command execution
                    print(
                        f"{BatColors.BAT_SUCCESS}✅ Command executed successfully in {result.execution_time_ms}ms{BatColors.RESET}"
                    )

                    if result.output:
                        # Display command output in console (truncated if too long)
                        print(
                            f"{BatColors.BAT_INFO}📤 Output from agent {result.agent_id}:{BatColors.RESET}"
                        )
                        print(f"{BatColors.CYAN}{result.output[:500]}{BatColors.RESET}")
                        if len(result.output) > 500:
                            print(
                                f"{BatColors.BAT_WARNING}... (output truncated for voice){BatColors.RESET}"
                            )

                        # Provide truncated voice output (speech is slower than reading)
                        output = (
                            result.output[:200] + "..."
                            if len(result.output) > 200
                            else result.output
                        )
                        self.speak_response(f"Command executed successfully. Output: {output}")
                    else:
                        # Command succeeded but produced no output
                        self.speak_response("Command completed successfully with no output.")
                else:
                    # Handle command execution failures
                    print(f"{BatColors.BAT_ERROR}❌ Command failed: {result.error}{BatColors.RESET}")
                    error_msg = (
                        result.error[:100] + "..." if len(result.error) > 100 else result.error
                    )
                    self.speak_response(f"Command failed in the digital realm: {error_msg}")

                # Visual separator between commands for better readability
                print(
                    f"{BatColors.BAT_PROMPT}─────────────────────────────────────────────────────────────────────{BatColors.RESET}"
                )

                # Yield control to allow other async tasks to run
                await asyncio.sleep(0.1)

            except KeyboardInterrupt:
                # Handle Ctrl+C gracefully with Batman theme
                print(f"\n{BatColors.BAT_WARNING}🦇 Interrupted by the master...{BatColors.RESET}")
                self.speak_response("As you command, master. Returning to the shadows.")
                break

            except Exception as e:
                # Handle unexpected errors and continue operation
                print(
                    f"{BatColors.BAT_ERROR}💀 Unexpected error in the bat cave: {e}{BatColors.RESET}"
                )
                logger.error(f"Voice loop error: {e}")
                continue  # Continue voice loop despite errors
