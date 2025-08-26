from typing import Optional
import speech_recognition as sr
import pyttsx3
from gtts import gTTS
import pygame
import io
import asyncio
import os
import platform
from coordinator.core.coordinator import Coordinator
import logging

logger = logging.getLogger(__name__)

# Bat Cave Console Colors (for terminal output)
class BatColors:
    BLACK = '\033[40m'
    PURPLE = '\033[45m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    SILVER = '\033[37m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'
    
    # Bat-themed combinations
    BAT_TITLE = BOLD + MAGENTA
    BAT_SUCCESS = GREEN + BOLD
    BAT_ERROR = RED + BOLD
    BAT_INFO = CYAN
    BAT_WARNING = YELLOW
    BAT_PROMPT = PURPLE + BOLD

class VoiceInterface:
    """
    Bat Cave Voice Interface - A dark, atmospheric voice interface for the A.L.F.R.E.D. system.
    Provides voice recognition and synthesis with bat-themed console output.
    """
    def __init__(self, coordinator: Coordinator):
        self.coordinator = coordinator
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Initialize pygame for audio playback
        pygame.mixer.init()
        
        # Adjust for ambient noise
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
        
        # Display bat-themed startup
        self._display_bat_startup()
        logger.info("Bat Cave Voice Interface initialized")
    
    def _display_bat_startup(self):
        """Display atmospheric bat-themed startup screen"""
        if not os.getenv('NO_ANSI'):  # Allow disabling for CI/CD
            os.system('clear' if platform.system() != 'Windows' else 'cls')
        
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
    
    def listen_for_command(self, timeout=10) -> Optional[str]:
        """
        Listen for a voice command and return the recognized text with bat-themed output.
        """
        try:
            print(f"{BatColors.BAT_INFO}🦇 The bats are listening... Speak your command{BatColors.RESET}")
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=5)
            
            print(f"{BatColors.BAT_WARNING}🌙 Processing your dark whispers...{BatColors.RESET}")
            command = self.recognizer.recognize_google(audio)
            
            print(f"{BatColors.BAT_SUCCESS}✨ Command received: {BatColors.CYAN}'{command}'{BatColors.RESET}")
            logger.info(f"Voice command recognized: {command}")
            return command
        
        except sr.WaitTimeoutError:
            print(f"{BatColors.BAT_WARNING}⏰ Timeout - The cave grows silent...{BatColors.RESET}")
            logger.info("Listening timeout")
            return None
        except sr.UnknownValueError:
            print(f"{BatColors.BAT_ERROR}🦇 Could not decipher your whispers in the darkness{BatColors.RESET}")
            logger.warning("Could not understand audio")
            return None
        except sr.RequestError as e:
            print(f"{BatColors.BAT_ERROR}💀 Recognition service failed: {e}{BatColors.RESET}")
            logger.error(f"Recognition service error: {e}")
            return None
    
    def speak_response(self, text: str):
        """
        Convert text to speech and play it using gTTS with bat-themed console output.
        Falls back to themed text display if synthesis fails.
        """
        # Display the response with bat theming
        print(f"{BatColors.BAT_PROMPT}🦇 A.L.F.R.E.D. speaks from the shadows:{BatColors.RESET}")
        print(f"{BatColors.BAT_SUCCESS}💬 {text}{BatColors.RESET}")
        
        try:
            # Use gTTS for better quality
            tts = gTTS(text=text, lang='en')
            
            # Save to BytesIO instead of file
            mp3_fp = io.BytesIO()
            tts.write_to_fp(mp3_fp)
            mp3_fp.seek(0)
            
            # Play using pygame
            pygame.mixer.music.load(mp3_fp)
            pygame.mixer.music.play()
            
            print(f"{BatColors.BAT_INFO}🔊 Echoing through the bat cave...{BatColors.RESET}")
            
            # Wait for playback to complete
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)
                
        except Exception as e:
            logger.error(f"Speech synthesis error: {e}")
            print(f"{BatColors.BAT_ERROR}🔇 Voice synthesis failed, using text only{BatColors.RESET}")
    
    def _display_agent_status(self, healthy_count: int, total_count: int):
        """Display bat-themed agent status in console"""
        print(f"\n{BatColors.BAT_PROMPT}┌─────────────────────────────────────────────────────────────────┐")
        print(f"│                     🦇 BAT COLONY STATUS 🦇                    │")
        print(f"└─────────────────────────────────────────────────────────────────┘{BatColors.RESET}")
        
        if total_count == 0:
            print(f"{BatColors.BAT_WARNING}🌙 No bats detected in the cave...{BatColors.RESET}")
        else:
            health_percentage = (healthy_count / total_count) * 100
            status_color = BatColors.BAT_SUCCESS if health_percentage > 75 else \
                          BatColors.BAT_WARNING if health_percentage > 50 else BatColors.BAT_ERROR
            
            print(f"{BatColors.BAT_INFO}🦇 Colony Size: {BatColors.CYAN}{total_count} bats{BatColors.RESET}")
            print(f"{status_color}❤️  Healthy: {healthy_count} ({health_percentage:.1f}%){BatColors.RESET}")
            
            if healthy_count < total_count:
                unhealthy_count = total_count - healthy_count
                print(f"{BatColors.BAT_ERROR}💀 Unhealthy: {unhealthy_count} bats{BatColors.RESET}")
        print()
    
    async def run_voice_loop(self):
        """
        Main bat cave voice interaction loop: atmospheric command processing.
        """
        # Initial system status display
        await self.coordinator.health_check_agents(force=True)
        healthy_count = sum(1 for agent in self.coordinator.agents.values() if agent.is_healthy)
        total_count = len(self.coordinator.agents)
        self._display_agent_status(healthy_count, total_count)
        
        self.speak_response("The Bat Cave is awakened. Your digital domain awaits your commands. Say 'exit' to return to the shadows.")
        
        print(f"{BatColors.BAT_PROMPT}═══════════════════════════════════════════════════════════════════")
        print(f"🎤 VOICE COMMANDS: 'status', 'agents', 'exit', or any system command")
        print(f"⌨️  KEYBOARD SHORTCUTS: Ctrl+C to exit gracefully")
        print(f"═══════════════════════════════════════════════════════════════════{BatColors.RESET}\n")
        
        while True:
            try:
                command = self.listen_for_command()
                
                if not command:
                    continue
                
                # Exit commands
                if command.lower() in ['exit', 'quit', 'stop', 'return to shadows', 'goodbye']:
                    print(f"{BatColors.BAT_SUCCESS}🌙 Returning to the darkness...{BatColors.RESET}")
                    self.speak_response("The darkness calls me back. Until we meet again in the shadows.")
                    break
                
                # Status commands with enhanced display
                if command.lower() in ['status', 'agents', 'colony status', 'bat status']:
                    print(f"{BatColors.BAT_INFO}🔍 Scanning the bat colony...{BatColors.RESET}")
                    await self.coordinator.health_check_agents(force=True)
                    healthy_count = sum(1 for agent in self.coordinator.agents.values() if agent.is_healthy)
                    total_count = len(self.coordinator.agents)
                    
                    self._display_agent_status(healthy_count, total_count)
                    
                    # Voice response
                    if total_count == 0:
                        response = "The bat cave appears empty, my lord. No agents have been discovered in our digital domain."
                    else:
                        response = f"Colony report: {healthy_count} healthy bats out of {total_count} total in our digital domain."
                        if healthy_count < total_count:
                            unhealthy_count = total_count - healthy_count
                            response += f" {unhealthy_count} bats require attention, master."
                    
                    self.speak_response(response)
                    continue
                
                # Execute command with enhanced feedback
                print(f"{BatColors.BAT_WARNING}⚡ Dispatching command to the digital realm...{BatColors.RESET}")
                result = await self.coordinator.execute_command(command)
                
                if result.success:
                    print(f"{BatColors.BAT_SUCCESS}✅ Command executed successfully in {result.execution_time_ms}ms{BatColors.RESET}")
                    if result.output:
                        # Display output in console
                        print(f"{BatColors.BAT_INFO}📤 Output from agent {result.agent_id}:{BatColors.RESET}")
                        print(f"{BatColors.CYAN}{result.output[:500]}{BatColors.RESET}")
                        if len(result.output) > 500:
                            print(f"{BatColors.BAT_WARNING}... (output truncated for voice){BatColors.RESET}")
                        
                        # Truncated voice output
                        output = result.output[:200] + "..." if len(result.output) > 200 else result.output
                        self.speak_response(f"Command executed successfully. Output: {output}")
                    else:
                        self.speak_response("Command completed successfully with no output.")
                else:
                    print(f"{BatColors.BAT_ERROR}❌ Command failed: {result.error}{BatColors.RESET}")
                    error_msg = result.error[:100] + "..." if len(result.error) > 100 else result.error
                    self.speak_response(f"Command failed in the digital realm: {error_msg}")
                
                print(f"{BatColors.BAT_PROMPT}─────────────────────────────────────────────────────────────────────{BatColors.RESET}")
            
            except KeyboardInterrupt:
                print(f"\n{BatColors.BAT_WARNING}🦇 Interrupted by the master...{BatColors.RESET}")
                self.speak_response("As you command, master. Returning to the shadows.")
                break
            except Exception as e:
                print(f"{BatColors.BAT_ERROR}💀 Unexpected error in the bat cave: {e}{BatColors.RESET}")
                logger.error(f"Voice loop error: {e}")
                continue