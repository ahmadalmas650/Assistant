"""
Wake Word Detector Module
Detects wake words for hands-free activation.

The actual listening happens inside the Bridge APK (Android
SpeechRecognizer), so the Python side stays tiny: no heavy audio
processing and no large audio buffers. The detector asks the
bridge over the local JSON-RPC socket whether the wake word was
heard and fires the registered callbacks when it was. Text-based
detection (typed commands that start with the wake word) also
works.
"""

import asyncio
import time
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler
from .bridge_client import BridgeClient, BridgeError


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
    position: int = 0  # Character position in a text command

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
    Detects the wake word by delegating listening to the Bridge APK.
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

        # Detection parameters
        self._confidence_threshold = 0.7

        # Bridge connection (listening runs inside the APK)
        bridge_cfg = getattr(config, 'bridge', None)
        self._bridge = BridgeClient(
            host=getattr(bridge_cfg, 'host', '127.0.0.1'),
            port=getattr(bridge_cfg, 'port', 8080),
        )
        self._listen_timeout = 10.0  # per-iteration listening window

        # State
        self._state = DetectionState.IDLE
        self._is_running = False
        self._detection_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Callbacks
        self._on_detection: List[Callable[[DetectionResult], None]] = []
        self._on_state_change: List[Callable[[DetectionState], None]] = []

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
        self._stop_event.clear()
        self._state = DetectionState.LISTENING

        for callback in self._on_state_change:
            try:
                callback(self._state)
            except Exception as e:
                self.error_handler.handle_error(e, "state_change_callback")

        self._detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._detection_thread.start()

        self.logger.info("Wake word detection started")
        return True

    def stop(self) -> bool:
        """Stop wake word detection"""
        if not self._is_running:
            return False

        self._is_running = False
        self._stop_event.set()
        self._state = DetectionState.IDLE

        for callback in self._on_state_change:
            try:
                callback(self._state)
            except Exception as e:
                self.error_handler.handle_error(e, "state_change_callback")

        if self._detection_thread:
            # The bridge call can block for up to _listen_timeout plus the
            # socket timeout; give the loop enough time to notice the stop.
            self._detection_thread.join(timeout=self._listen_timeout + 15.0)
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
        """Main detection loop: ask the bridge whether the wake word was heard."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            while self._is_running and not self._stop_event.is_set():
                try:
                    result = loop.run_until_complete(
                        self._bridge.listen_wake_word(self.wake_word, self._listen_timeout)
                    )
                    if result.get("detected"):
                        detection = DetectionResult(
                            detected=True,
                            wake_word=self.wake_word,
                            confidence=result.get("confidence", 0.99),
                            timestamp=time.time()
                        )
                        if detection.confidence >= self._confidence_threshold:
                            self._handle_detection(detection)
                except BridgeError as e:
                    self.logger.warning(f"Bridge unavailable for wake word listening: {e}")
                    self._stop_event.wait(2.0)
                except Exception as e:
                    self.error_handler.handle_error(e, "detection_loop")
                    self._stop_event.wait(1.0)
        finally:
            try:
                loop.run_until_complete(self._bridge.close())
            except Exception:
                pass
            loop.close()
            asyncio.set_event_loop(None)

    def _handle_detection(self, result: DetectionResult):
        """Handle a wake word detection"""
        self._state = DetectionState.DETECTED

        for callback in self._on_detection:
            try:
                callback(result)
            except Exception as e:
                self.error_handler.handle_error(e, "detection_callback")

        self.logger.info(f"Wake word detected: {result.wake_word} (confidence: {result.confidence:.2f})")

        # Reset state after a delay (thread-safe; no event loop required)
        timer = threading.Timer(2.0, self._reset_state)
        timer.daemon = True
        timer.start()

    def _reset_state(self):
        """Reset state back to LISTENING after a detection"""
        if self._is_running:
            self._state = DetectionState.LISTENING

            for callback in self._on_state_change:
                try:
                    callback(self._state)
                except Exception as e:
                    self.error_handler.handle_error(e, "state_change_callback")

    def process_text(self, text: str) -> DetectionResult:
        """
        Check if text contains the wake word

        Args:
            text: Text to check

        Returns:
            DetectionResult
        """
        text_lower = text.lower().strip()
        wake_word_lower = self.wake_word.lower()

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
        """Quick check if text is/contains the wake word"""
        result = self.process_text(text)
        return result.detected

    # Callback Registration

    def on_detection(self, callback: Callable[[DetectionResult], None]):
        """Register detection callback"""
        self._on_detection.append(callback)

    def on_state_change(self, callback: Callable[[DetectionState], None]):
        """Register state change callback"""
        self._on_state_change.append(callback)

    def cleanup(self):
        """Clean up resources"""
        self.stop()
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._bridge.close())
            loop.close()
        except Exception as e:
            self.error_handler.handle_error(e, "wake_word_cleanup")
