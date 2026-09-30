"""
Input Processor Module
Handles both voice and text input processing
"""

import asyncio
import json
import time
import os
import tempfile
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
from pathlib import Path

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler


@dataclass
class ProcessedInput:
    """Processed input data"""
    text: str
    input_type: str  # 'text' or 'voice'
    language: str = "en"
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
    raw_data: Optional[Any] = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "input_type": self.input_type,
            "language": self.language,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


class InputProcessor:
    """
    Processes both voice and text input
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Voice processing setup
        self._voice_enabled = True
        self._current_language = "en"
        self._temp_dir = tempfile.mkdtemp(prefix="jarvis_input_")
        
        # State
        self._is_listening = False
        self._recording = False
        
        # Callbacks
        self._on_voice_start: List[callable] = []
        self._on_voice_stop: List[callable] = []
        self._on_text_input: List[callable] = []
    
    async def process(self, input_data: Union[str, bytes, Path], 
                     input_type: str = "text") -> ProcessedInput:
        """
        Process input data
        
        Args:
            input_data: The input data (text string, audio bytes, or file path)
            input_type: Type of input ('text' or 'voice')
            
        Returns:
            ProcessedInput object
        """
        try:
            if input_type == "voice":
                return await self._process_voice(input_data)
            else:
                return await self._process_text(input_data)
        except Exception as e:
            self.error_handler.handle_error(e, f"process_input_{input_type}")
            return ProcessedInput(
                text="",
                input_type=input_type,
                confidence=0.0,
                metadata={"error": str(e)}
            )
    
    async def _process_text(self, text: Union[str, bytes, Path]) -> ProcessedInput:
        """Process text input"""
        start_time = time.time()
        
        # Convert to string if needed
        if isinstance(text, bytes):
            text = text.decode('utf-8')
        elif isinstance(text, Path):
            with open(text, 'r', encoding='utf-8') as f:
                text = f.read()
        
        # Clean and normalize text
        cleaned_text = self._clean_text(text)
        
        # Extract metadata
        metadata = {
            "original_length": len(text),
            "cleaned_length": len(cleaned_text),
            "processing_time": time.time() - start_time
        }
        
        self.logger.debug(f"Processed text input: {cleaned_text[:50]}...")
        
        # Notify callbacks
        for callback in self._on_text_input:
            try:
                callback(cleaned_text)
            except Exception as e:
                self.error_handler.handle_error(e, "text_input_callback")
        
        return ProcessedInput(
            text=cleaned_text,
            input_type="text",
            language=self._detect_language(cleaned_text),
            confidence=1.0,
            metadata=metadata
        )
    
    async def _process_voice(self, audio_data: Union[bytes, Path]) -> ProcessedInput:
        """Process voice input"""
        start_time = time.time()
        
        # Save audio to temp file if needed
        audio_path = None
        if isinstance(audio_data, bytes):
            audio_path = os.path.join(self._temp_dir, f"voice_{int(time.time())}.wav")
            with open(audio_path, 'wb') as f:
                f.write(audio_data)
        elif isinstance(audio_data, Path):
            audio_path = str(audio_data)
        
        self.logger.info(f"Processing voice input: {audio_path}")
        
        try:
            # Simulate speech recognition
            # In production, this would use a speech recognition library
            # For Termux, we might use pocketsphinx or a cloud API
            
            # Mock implementation
            await asyncio.sleep(1)  # Simulate processing time
            
            # Generate mock transcription
            text = self._mock_speech_recognition(audio_path)
            
            # Clean text
            cleaned_text = self._clean_text(text)
            
            # Calculate confidence (mock value)
            confidence = 0.95
            
            # Extract metadata
            metadata = {
                "audio_path": audio_path,
                "audio_duration": 3.5,  # Mock duration
                "processing_time": time.time() - start_time,
                "language": self._current_language
            }
            
            self.logger.info(f"Voice recognized: {cleaned_text[:50]}...")
            
            return ProcessedInput(
                text=cleaned_text,
                input_type="voice",
                language=self._current_language,
                confidence=confidence,
                raw_data=audio_path,
                metadata=metadata
            )
            
        finally:
            # Cleanup temp file
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except:
                    pass
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove special characters that might cause issues
        # Keep basic punctuation and letters/numbers
        cleaned = []
        for char in text:
            if char.isalnum() or char in ' .,!?;:\'\"-()[]{}@#$%&*+/\\<>=':
                cleaned.append(char)
            else:
                cleaned.append(' ')
        
        text = ''.join(cleaned)
        
        # Remove multiple spaces
        text = ' '.join(text.split())
        
        # Capitalize first letter
        if text:
            text = text[0].upper() + text[1:] if text else text
        
        return text.strip()
    
    def _detect_language(self, text: str) -> str:
        """Detect language of text"""
        # Simple language detection based on common words
        text_lower = text.lower()
        
        # English
        if any(word in text_lower for word in ['the', 'and', 'is', 'are', 'of']):
            return "en"
        
        # Urdu/Hindi (common words)
        if any(word in text_lower for word in ['hai', 'aur', 'ye', 'kya', 'main']):
            return "ur"
        
        # Default to English
        return "en"
    
    def _mock_speech_recognition(self, audio_path: str) -> str:
        """Mock speech recognition for testing"""
        # In a real implementation, this would use a speech recognition API
        # For now, return a sample transcription
        
        # Extract base name for variety
        base_name = os.path.basename(audio_path).replace('.wav', '')
        
        if "voice" in base_name:
            return "Please upload this video to YouTube and make sure it has a good title and description"
        else:
            return "Take a screenshot and extract the text from it"
    
    # Voice Input Methods
    
    async def start_listening(self) -> bool:
        """Start listening for voice input"""
        if self._is_listening:
            return False
        
        self._is_listening = True
        self._recording = False
        
        # Notify callbacks
        for callback in self._on_voice_start:
            try:
                callback()
            except Exception as e:
                self.error_handler.handle_error(e, "voice_start_callback")
        
        self.logger.info("Started listening for voice input")
        return True
    
    async def stop_listening(self) -> bool:
        """Stop listening for voice input"""
        if not self._is_listening:
            return False
        
        self._is_listening = False
        self._recording = False
        
        # Notify callbacks
        for callback in self._on_voice_stop:
            try:
                callback()
            except Exception as e:
                self.error_handler.handle_error(e, "voice_stop_callback")
        
        self.logger.info("Stopped listening for voice input")
        return True
    
    async def start_recording(self) -> str:
        """Start recording audio"""
        if not self._is_listening or self._recording:
            return ""
        
        self._recording = True
        recording_path = os.path.join(self._temp_dir, f"recording_{int(time.time())}.wav")
        
        self.logger.info(f"Started recording: {recording_path}")
        
        # In a real implementation, this would start the actual recording
        # For now, just return the path
        return recording_path
    
    async def stop_recording(self, recording_path: str = "") -> Optional[bytes]:
        """Stop recording and return audio data"""
        if not self._recording:
            return None
        
        self._recording = False
        
        if not recording_path:
            # Find the latest recording
            files = [f for f in os.listdir(self._temp_dir) if f.endswith('.wav')]
            if files:
                files.sort()
                recording_path = os.path.join(self._temp_dir, files[-1])
        
        if os.path.exists(recording_path):
            with open(recording_path, 'rb') as f:
                audio_data = f.read()
            
            self.logger.info(f"Stopped recording: {len(audio_data)} bytes")
            return audio_data
        
        return None
    
    def is_listening(self) -> bool:
        """Check if currently listening"""
        return self._is_listening
    
    def is_recording(self) -> bool:
        """Check if currently recording"""
        return self._recording
    
    # Language Methods
    
    def set_language(self, language: str) -> bool:
        """Set the current language"""
        supported = ["en", "ur", "hi", "es", "fr", "de"]
        if language in supported:
            self._current_language = language
            self.logger.info(f"Language set to: {language}")
            return True
        return False
    
    def get_language(self) -> str:
        """Get current language"""
        return self._current_language
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages"""
        return ["en", "ur", "hi", "es", "fr", "de", "it", "pt", "ru", "zh", "ja"]
    
    # Callback Registration
    
    def on_voice_start(self, callback: callable):
        """Register voice start callback"""
        self._on_voice_start.append(callback)
    
    def on_voice_stop(self, callback: callable):
        """Register voice stop callback"""
        self._on_voice_stop.append(callback)
    
    def on_text_input(self, callback: callable):
        """Register text input callback"""
        self._on_text_input.append(callback)
    
    # Wake Word Detection Integration
    
    async def check_wake_word(self, text: str, wake_word: str = None) -> bool:
        """Check if text contains wake word"""
        if wake_word is None:
            wake_word = self.config.wake_word if hasattr(self.config, 'wake_word') else "jarvis"
        
        text_lower = text.lower().strip()
        wake_word_lower = wake_word.lower()
        
        # Check various positions
        return (
            text_lower.startswith(wake_word_lower) or
            f" {wake_word_lower} " in text_lower or
            text_lower.endswith(wake_word_lower) or
            text_lower == wake_word_lower
        )
    
    async def process_with_wake_word(self, input_data: Union[str, bytes, Path], 
                                    input_type: str = "text") -> Tuple[bool, ProcessedInput]:
        """
        Process input and check for wake word
        
        Returns:
            Tuple of (has_wake_word, processed_input)
        """
        processed = await self.process(input_data, input_type)
        has_wake_word = await self.check_wake_word(processed.text)
        return has_wake_word, processed
    
    # Continuous Listening
    
    async def start_continuous_listening(self):
        """Start continuous listening mode"""
        self._is_listening = True
        
        while self._is_listening:
            # Simulate continuous listening
            await asyncio.sleep(0.1)
            
            # In a real implementation, this would use a streaming speech recognition API
            # For now, just wait
    
    async def stop_continuous_listening(self):
        """Stop continuous listening mode"""
        self._is_listening = False
    
    # Cleanup
    
    async def cleanup(self):
        """Clean up temporary files"""
        try:
            for file in os.listdir(self._temp_dir):
                file_path = os.path.join(self._temp_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(self._temp_dir)
            self.logger.info("Cleaned up temporary files")
        except Exception as e:
            self.error_handler.handle_error(e, "input_cleanup")
