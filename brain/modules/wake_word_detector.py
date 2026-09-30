"""
Wake Word Detector Module
Detects wake words in audio input for hands-free activation
"""

import asyncio
import json
import time
import os
import struct
import wave
import numpy as np
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import threading

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler


class DetectionState(Enum):
    """Current detection state"""
    IDLE = auto()
    LISTENING = auto()
    DETECTED = auto()
    PROCESSING = auto()


@dataclass
class DetectionResult:
    """Wake word detection result"""
    detected: bool
    wake_word: str = ""
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)
    audio_chunk: Optional[bytes] = None
    position: int = 0  # Position in audio stream
    
    def to_dict(self) -> Dict:
        return {
            "detected": self.detected,
            "wake_word": self.wake_word,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "position": self.position
        }


class WakeWordDetector:
    """
    Detects wake words in audio input
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Wake word configuration
        self.wake_word = getattr(config, 'wake_word', 'jarvis')
        self._supported_wake_words = [
            'jarvis', 'hey jarvis', 'ok jarvis', 'hello jarvis',
            'assistant', 'hey assistant', 'ok assistant',
            'computer', 'hey computer'
        ]
        
        # Audio configuration
        self._sample_rate = 16000  # 16kHz
        self._channels = 1  # Mono
        self._sample_width = 2  # 16-bit
        self._chunk_size = 1024
        self._buffer_size = 4096
        
        # Detection parameters
        self._confidence_threshold = 0.7
        self._min_word_length = 0.5  # seconds
        self._max_word_length = 2.0  # seconds
        
        # State
        self._state = DetectionState.IDLE
        self._is_running = False
        self._audio_buffer = bytearray()
        self._temp_dir = "/tmp/jarvis_wake_word"
        
        # Ensure temp directory exists
        os.makedirs(self._temp_dir, exist_ok=True)
        
        # Callbacks
        self._on_detection: List[Callable[[DetectionResult], None]] = []
        self._on_state_change: List[Callable[[DetectionState], None]] = []
        
        # Audio processing
        self._audio_stream = None
        self._detection_thread = None
    
    def set_wake_word(self, wake_word: str) -> bool:
        """Set the wake word to detect"""
        if wake_word.lower() in [w.lower() for w in self._supported_wake_words]:
            self.wake_word = wake_word.lower()
            self.logger.info(f"Wake word set to: {self.wake_word}")
            return True
        
        self.logger.warning(f"Wake word '{wake_word}' not supported")
        return False
    
    def get_wake_word(self) -> str:
        """Get the current wake word"""
        return self.wake_word
    
    def get_supported_wake_words(self) -> List[str]:
        """Get list of supported wake words"""
        return self._supported_wake_words
    
    def set_confidence_threshold(self, threshold: float) -> bool:
        """Set the confidence threshold for detection"""
        if 0.0 <= threshold <= 1.0:
            self._confidence_threshold = threshold
            self.logger.info(f"Confidence threshold set to: {threshold}")
            return True
        return False
    
    def get_confidence_threshold(self) -> float:
        """Get the current confidence threshold"""
        return self._confidence_threshold
    
    def start(self) -> bool:
        """Start wake word detection"""
        if self._is_running:
            return False
        
        self._is_running = True
        self._state = DetectionState.LISTENING
        self._audio_buffer = bytearray()
        
        # Notify state change
        for callback in self._on_state_change:
            try:
                callback(self._state)
            except Exception as e:
                self.error_handler.handle_error(e, "state_change_callback")
        
        # Start detection thread
        self._detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._detection_thread.start()
        
        self.logger.info("Wake word detection started")
        return True
    
    def stop(self) -> bool:
        """Stop wake word detection"""
        if not self._is_running:
            return False
        
        self._is_running = False
        self._state = DetectionState.IDLE
        
        # Notify state change
        for callback in self._on_state_change:
            try:
                callback(self._state)
            except Exception as e:
                self.error_handler.handle_error(e, "state_change_callback")
        
        # Wait for thread to stop
        if self._detection_thread:
            self._detection_thread.join(timeout=1.0)
            self._detection_thread = None
        
        self.logger.info("Wake word detection stopped")
        return True
    
    def is_running(self) -> bool:
        """Check if detection is running"""
        return self._is_running
    
    def get_state(self) -> DetectionState:
        """Get current detection state"""
        return self._state
    
    def _detection_loop(self):
        """Main detection loop"""
        while self._is_running:
            try:
                # Simulate audio input
                # In a real implementation, this would read from microphone
                time.sleep(0.1)
                
                # Generate mock audio data
                mock_audio = self._generate_mock_audio()
                
                # Process audio
                result = self.process_audio(mock_audio)
                
                if result.detected:
                    self._handle_detection(result)
                    
            except Exception as e:
                self.error_handler.handle_error(e, "detection_loop")
    
    def _generate_mock_audio(self) -> bytes:
        """Generate mock audio data for testing"""
        # Generate a simple sine wave
        duration = 0.5  # seconds
        frequency = 440  # Hz
        num_samples = int(self._sample_rate * duration)
        
        # Generate samples
        t = np.linspace(0, duration, num_samples, False)
        wave = 32767 * 0.5 * np.sin(2 * np.pi * frequency * t)
        
        # Convert to bytes
        audio_data = b''
        for sample in wave:
            audio_data += struct.pack('<h', int(sample))
        
        return audio_data
    
    def process_audio(self, audio_data: bytes) -> DetectionResult:
        """
        Process audio data to detect wake word
        
        Args:
            audio_data: Raw audio data
            
        Returns:
            DetectionResult
        """
        start_time = time.time()
        
        try:
            # Add to buffer
            self._audio_buffer.extend(audio_data)
            
            # Check buffer size
            if len(self._audio_buffer) > self._buffer_size * self._chunk_size:
                # Remove oldest data
                self._audio_buffer = self._audio_buffer[-self._buffer_size * self._chunk_size:]
            
            # Convert to numpy array for processing
            audio_array = self._bytes_to_numpy(self._audio_buffer)
            
            # Detect wake word
            result = self._detect_wake_word(audio_array)
            
            processing_time = time.time() - start_time
            self.logger.debug(f"Audio processed in {processing_time:.4f}s")
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, "process_audio")
            return DetectionResult(
                detected=False,
                confidence=0.0,
                timestamp=time.time()
            )
    
    def _bytes_to_numpy(self, audio_bytes: bytes) -> np.ndarray:
        """Convert bytes to numpy array"""
        # Convert to list of samples
        samples = []
        for i in range(0, len(audio_bytes), self._sample_width):
            chunk = audio_bytes[i:i+self._sample_width]
            if len(chunk) == self._sample_width:
                sample = struct.unpack('<h', chunk)[0]
                samples.append(sample)
        
        return np.array(samples, dtype=np.float32)
    
    def _detect_wake_word(self, audio_array: np.ndarray) -> DetectionResult:
        """
        Detect wake word in audio array
        
        This is a mock implementation. In production, this would use:
        - TensorFlow Lite for on-device detection
        - Porcupine wake word engine
        - Or a cloud-based speech recognition API
        """
        # Mock detection based on time
        current_time = time.time()
        
        # Simulate detection every 10-15 seconds
        if int(current_time) % 15 < 1 and self._state == DetectionState.LISTENING:
            # Random confidence
            confidence = 0.85 + (0.2 * np.random.random())
            
            return DetectionResult(
                detected=True,
                wake_word=self.wake_word,
                confidence=confidence,
                timestamp=current_time,
                position=len(self._audio_buffer) - self._chunk_size
            )
        
        # Otherwise, no detection
        return DetectionResult(
            detected=False,
            confidence=0.0,
            timestamp=current_time
        )
    
    def _handle_detection(self, result: DetectionResult):
        """Handle a wake word detection"""
        self._state = DetectionState.DETECTED
        
        # Notify callbacks
        for callback in self._on_detection:
            try:
                callback(result)
            except Exception as e:
                self.error_handler.handle_error(e, "detection_callback")
        
        self.logger.info(f"Wake word detected: {result.wake_word} (confidence: {result.confidence:.2f})")
        
        # Reset state after a delay
        asyncio.create_task(self._reset_state_after_delay(2.0))
    
    async def _reset_state_after_delay(self, delay: float):
        """Reset state after a delay"""
        await asyncio.sleep(delay)
        if self._is_running:
            self._state = DetectionState.LISTENING
            
            for callback in self._on_state_change:
                try:
                    callback(self._state)
                except Exception as e:
                    self.error_handler.handle_error(e, "state_change_callback")
    
    def process_text(self, text: str) -> DetectionResult:
        """
        Check if text contains wake word
        
        Args:
            text: Text to check
            
        Returns:
            DetectionResult
        """
        text_lower = text.lower().strip()
        wake_word_lower = self.wake_word.lower()
        
        # Check various positions
        if text_lower.startswith(wake_word_lower):
            confidence = 1.0
            position = 0
        elif f" {wake_word_lower} " in text_lower:
            position = text_lower.index(f" {wake_word_lower} ")
            confidence = 0.95
        elif text_lower.endswith(wake_word_lower):
            position = len(text_lower) - len(wake_word_lower)
            confidence = 0.9
        else:
            return DetectionResult(
                detected=False,
                confidence=0.0,
                timestamp=time.time()
            )
        
        return DetectionResult(
            detected=True,
            wake_word=self.wake_word,
            confidence=confidence,
            timestamp=time.time(),
            position=position
        )
    
    def is_wake_word(self, text: str) -> bool:
        """Quick check if text is a wake word"""
        result = self.process_text(text)
        return result.detected
    
    # Callback Registration
    
    def on_detection(self, callback: Callable[[DetectionResult], None]):
        """Register detection callback"""
        self._on_detection.append(callback)
    
    def on_state_change(self, callback: Callable[[DetectionState], None]):
        """Register state change callback"""
        self._on_state_change.append(callback)
    
    # Audio Recording Methods (for testing)
    
    def start_recording(self, output_path: str = None) -> bool:
        """Start recording audio"""
        if not output_path:
            output_path = os.path.join(self._temp_dir, f"recording_{int(time.time())}.wav")
        
        try:
            self._audio_stream = wave.open(output_path, 'wb')
            self._audio_stream.setnchannels(self._channels)
            self._audio_stream.setsampwidth(self._sample_width)
            self._audio_stream.setframerate(self._sample_rate)
            
            self.logger.info(f"Started recording to: {output_path}")
            return True
        except Exception as e:
            self.error_handler.handle_error(e, "start_recording")
            return False
    
    def stop_recording(self) -> Optional[str]:
        """Stop recording and return the file path"""
        if not self._audio_stream:
            return None
        
        try:
            self._audio_stream.close()
            self._audio_stream = None
            
            self.logger.info("Recording stopped")
            return self._audio_stream.name if hasattr(self._audio_stream, 'name') else None
        except Exception as e:
            self.error_handler.handle_error(e, "stop_recording")
            return None
    
    def save_audio(self, audio_data: bytes, path: str = None) -> Optional[str]:
        """Save audio data to a file"""
        if not path:
            path = os.path.join(self._temp_dir, f"audio_{int(time.time())}.wav")
        
        try:
            with wave.open(path, 'wb') as wav_file:
                wav_file.setnchannels(self._channels)
                wav_file.setsampwidth(self._sample_width)
                wav_file.setframerate(self._sample_rate)
                wav_file.writeframes(audio_data)
            
            self.logger.debug(f"Saved audio to: {path}")
            return path
        except Exception as e:
            self.error_handler.handle_error(e, "save_audio")
            return None
    
    # Utility Methods
    
    def get_audio_config(self) -> Dict:
        """Get current audio configuration"""
        return {
            "sample_rate": self._sample_rate,
            "channels": self._channels,
            "sample_width": self._sample_width,
            "chunk_size": self._chunk_size,
            "buffer_size": self._buffer_size
        }
    
    def set_audio_config(self, **kwargs):
        """Set audio configuration"""
        for key, value in kwargs.items():
            if hasattr(self, f"_{key}"):
                setattr(self, f"_{key}", value)
                self.logger.info(f"Audio config updated: {key}={value}")
    
    async def test_detection(self, wake_word: str = None) -> DetectionResult:
        """
        Test wake word detection
        
        Args:
            wake_word: Wake word to test (uses current if None)
            
        Returns:
            DetectionResult
        """
        if wake_word is None:
            wake_word = self.wake_word
        
        # Simulate detection
        confidence = 0.95
        
        return DetectionResult(
            detected=True,
            wake_word=wake_word,
            confidence=confidence,
            timestamp=time.time()
        )
    
    def cleanup(self):
        """Clean up resources"""
        self.stop()
        
        # Clean temp directory
        try:
            for file in os.listdir(self._temp_dir):
                file_path = os.path.join(self._temp_dir, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(self._temp_dir)
        except Exception as e:
            self.error_handler.handle_error(e, "wake_word_cleanup")
