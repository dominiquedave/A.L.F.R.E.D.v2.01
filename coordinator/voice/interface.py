from typing import Optional
import speech_recognition as sr
import pyttsx3
from gtts import gTTS
import pygame
import io
import asyncio
from coordinator.core.coordinator import Coordinator
import logging

logger = logging.getLogger(__name__)

class VoiceInterface:
    """
    Provides a voice interface for interacting with the coordinator using speech recognition and synthesis.
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
            logger.info("Voice interface initialized")
    
    def listen_for_command(self, timeout=10) -> Optional[str]:
        """
        Listen for a voice command and return the recognized text.
        """
        try:
            with self.microphone as source:
                logger.info("Listening for command...")
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=5)
            
            logger.info("Processing speech...")
            command = self.recognizer.recognize_google(audio)
            logger.info(f"Recognized: {command}")
            return command
        
        except sr.WaitTimeoutError:
            logger.info("Listening timeout")
            return None
        except sr.UnknownValueError:
            logger.warning("Could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"Recognition service error: {e}")
            return None
    
    def speak_response(self, text: str):
        """
        Convert text to speech and play it using gTTS and pygame.
        Falls back to printing if synthesis fails.
        """
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
            
            # Wait for playback to complete
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)
                
        except Exception as e:
            logger.error(f"Speech synthesis error: {e}")
            print(f"Assistant: {text}")  # Fallback to text
    
    async def run_voice_loop(self):
        """
        Main loop for voice interaction: listens, processes, and responds to commands.
        """
        self.speak_response("Assistant activated. Say a command or 'exit' to quit.")
        
        while True:
            command = self.listen_for_command()
            
            if not command:
                continue
            
            if command.lower() in ['exit', 'quit', 'stop']:
                self.speak_response("Goodbye!")
                break
            
            if command.lower() in ['status', 'agents']:
                # Trigger fresh health check before reporting status
                await self.coordinator.health_check_agents()
                healthy_count = sum(1 for agent in self.coordinator.agents.values() if agent.is_healthy)
                total_count = len(self.coordinator.agents)
                response = f"I have {healthy_count} healthy agents out of {total_count} total agents."
                self.speak_response(response)
                continue
            
            # Execute command
            result = await self.coordinator.execute_command(command)
            
            if result.success:
                if result.output:
                    # Truncate long outputs for voice
                    output = result.output[:200] + "..." if len(result.output) > 200 else result.output
                    self.speak_response(f"Command completed. Output: {output}")
                else:
                    self.speak_response("Command completed successfully.")
            else:
                error_msg = result.error[:100] + "..." if len(result.error) > 100 else result.error
                self.speak_response(f"Command failed: {error_msg}")