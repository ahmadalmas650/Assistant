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
from dataclasses import dataclass, field
from pathlib import Path

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler
from .bridge_client import BridgeClient, BridgeError


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

    # Dict compatibility so consumers written against plain dictionaries
    # (data.get("text"), data["valid"], "text" in data, ...) keep working.
    def get(self, key: str, default=None):
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str):
        d = self.to_dict()
        if key not in d:
            raise KeyError(key)
        return d[key]

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()

    def keys(self):
        return self.to_dict().keys()

    def items(self):
        return self.to_dict().items()


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
        
        # Bridge APK connection: speech recognition runs inside the APK
        bridge_cfg = getattr(config, 'bridge', None)
        self._bridge = BridgeClient(
            host=getattr(bridge_cfg, 'host', '127.0.0.1'),
            port=getattr(bridge_cfg, 'port', 8080),
        )
        
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
                # A non-empty string payload is the FINAL transcript of a
                # live voice session (mic on, word-by-word preview, edited
                # via stt_set_text). It is used as-is: re-running the
                # recognizer would start a brand-new one-shot recognition
                # instead of using the words the user already said.
                if isinstance(input_data, str) and input_data.strip():
                    cleaned = self._clean_text(input_data)
                    self.logger.debug(
                        f"Using live voice transcript: {cleaned[:50]}..."
                    )
                    for callback in self._on_text_input:
                        try:
                            callback(cleaned)
                        except Exception as e:
                            self.error_handler.handle_error(e, "text_input_callback")
                    return ProcessedInput(
                        text=cleaned,
                        input_type="voice",
                        confidence=1.0,
                        metadata={"source": "live_session_transcript"}
                    )
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
        """
        Process voice input via the Bridge APK speech recognizer.

        The Android SpeechRecognizer runs inside the Bridge APK, so
        recognition is always live and no audio is shipped to the
        Python side. If raw audio bytes or a path are supplied they
        are ignored by design (there is no local speech model).
        """
        start_time = time.time()

        if audio_data is not None:
            self.logger.info(
                "Voice recognition runs live in the Bridge APK; "
                "any supplied audio payload is ignored by design"
            )

        result = await self._bridge.speech_to_text()
        text = result.get("text", "")
        confidence = float(result.get("confidence", 0.9))

        if not text:
            raise ValueError("no speech recognized by the bridge")

        cleaned_text = self._clean_text(text)

        metadata = {
            "recognition": "bridge_speechrecognizer",
            "processing_time": time.time() - start_time,
            "language": self._current_language
        }

        self.logger.info(f"Voice recognized: {cleaned_text[:50]}...")

        return ProcessedInput(
            text=cleaned_text,
            input_type="voice",
            language=self._current_language,
            confidence=confidence,
            metadata=metadata
        )

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
    

    # Voice Input Methods
    
    # Live voice session (wake word -> command -> execute keyword).
    # The microphone stays on from the wake word until the user says an
    # execute keyword; the preview below updates word-by-word and can
    # be corrected with edit_session_text before execution.
    
    async def get_session_status(self) -> Dict:
        """Live session status with the word-by-word command preview."""
        try:
            status = await self._bridge.stt_status()
            return {
                "state": status.get("state", "idle"),
                "text": status.get("text", ""),
                "error": status.get("error", ""),
            }
        except BridgeError as e:
            self.logger.warning(f"Bridge unavailable for session status: {e}")
            return {"state": "error", "text": "", "error": str(e)}
    
    async def wait_for_command(self, timeout_s: float = 60.0) -> ProcessedInput:
        """
        Wait for the live command to finish.
        
        Polls the bridge session status (word-by-word preview available
        via get_session_status) until the user says an execute keyword
        (the APK then turns the microphone off and enters state
        'execute_ready'), or the timeout expires. The recognized text
        may already have been corrected by edit_session_text.
        """
        start_time = time.time()
        last_len = 0
        deadline = time.time() + float(timeout_s)
        
        while time.time() < deadline:
            status = await self.get_session_status()
            state = status.get("state", "idle")
            preview = status.get("text", "")
            
            # Live word-by-word preview: notify text callbacks as the
            # recognized text grows.
            if len(preview) > last_len:
                last_len = len(preview)
                for callback in self._on_text_input:
                    try:
                        callback(preview)
                    except Exception as e:
                        self.error_handler.handle_error(e, "preview_callback")
            
            if state == "execute_ready":
                # Microphone is off; the text is final.
                final_text = await self.finish_session()
                if not final_text:
                    final_text = preview
                cleaned_text = self._clean_text(final_text)
                return ProcessedInput(
                    text=cleaned_text,
                    input_type="voice",
                    language=self._current_language,
                    confidence=0.95,
                    metadata={
                        "recognition": "bridge_live_session",
                        "processing_time": time.time() - start_time,
                        "finished_by": "execute_keyword",
                    },
                )
            
            if state == "error":
                raise ValueError(
                    "voice session error: %s" % status.get("error", "unknown")
                )
            
            if state == "idle":
                # Session was cancelled or never started
                raise ValueError("voice session is not active")
            
            await asyncio.sleep(0.25)
        
        # Timeout: finish whatever was captured so far (microphone off)
        final_text = await self.finish_session()
        if not final_text:
            final_text = ""
        cleaned_text = self._clean_text(final_text)
        return ProcessedInput(
            text=cleaned_text,
            input_type="voice",
            language=self._current_language,
            confidence=0.6,
            metadata={
                "recognition": "bridge_live_session",
                "processing_time": time.time() - start_time,
                "finished_by": "timeout",
            },
        )
    
    async def edit_session_text(self, text: str) -> bool:
        """Correct the recognized command text before execution."""
        try:
            result = await self._bridge.stt_set_text(str(text))
            self.logger.info("Session text edited by user")
            return isinstance(result, dict) and result.get("ok", False) is not False
        except BridgeError as e:
            self.error_handler.handle_error(e, "edit_session_text")
            return False
    
    async def finish_session(self) -> str:
        """Finish the session: microphone off, returns the final text."""
        try:
            return await self._bridge.stt_finish()
        except BridgeError as e:
            self.error_handler.handle_error(e, "finish_session")
            return ""
    
    async def cancel_session(self) -> bool:
        """Cancel the session: microphone off, text discarded."""
        try:
            await self._bridge.stt_cancel()
            self.logger.info("Voice session cancelled")
            return True
        except BridgeError as e:
            self.error_handler.handle_error(e, "cancel_session")
            return False
    
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
        """
        Audio-file recording is not supported: voice recognition is
        performed live inside the Bridge APK. Returns an empty path.
        """
        self.logger.warning(
            "start_recording is not supported; voice is recognized "
            "live by the Bridge APK"
        )
        return ""

    async def stop_recording(self, recording_path: str = "") -> Optional[bytes]:
        """Audio-file recording is not supported; returns None."""
        self.logger.warning(
            "stop_recording is not supported; voice is recognized "
            "live by the Bridge APK"
        )
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
        """Start continuous listening mode (live recognition via bridge)."""
        self._is_listening = True
        self.logger.info("Continuous listening started")

        while self._is_listening:
            try:
                result = await self._bridge.speech_to_text()
                text = self._clean_text(result.get("text", ""))
                if text:
                    for callback in self._on_text_input:
                        try:
                            callback(text)
                        except Exception as e:
                            self.error_handler.handle_error(e, "text_input_callback")
            except BridgeError as e:
                self.logger.warning(f"Bridge unavailable, retrying: {e}")
                await asyncio.sleep(2.0)
            except Exception as e:
                self.error_handler.handle_error(e, "continuous_listening")
                await asyncio.sleep(1.0)

    async def stop_continuous_listening(self):
        """Stop continuous listening mode"""
        self._is_listening = False
    
    # Cleanup
    
    async def cleanup(self):
        """Clean up temporary files and close the bridge connection"""
        try:
            await self._bridge.close()
        except Exception as e:
            self.error_handler.handle_error(e, "bridge_close")

        try:
            for file in os.listdir(self._temp_dir):
                file_path = os.path.join(self._temp_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(self._temp_dir)
            self.logger.info("Cleaned up temporary files")
        except Exception as e:
            self.error_handler.handle_error(e, "input_cleanup")

