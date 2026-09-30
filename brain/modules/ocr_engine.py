"""
OCR Engine Module
Handles Optical Character Recognition for text extraction from images
"""

import asyncio
import json
import time
import os
import re
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum, auto

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler


class OCRLanguage(Enum):
    """Supported OCR languages"""
    ENGLISH = auto()
    URDU = auto()
    HINDI = auto()
    SPANISH = auto()
    FRENCH = auto()
    GERMAN = auto()
    ITALIAN = auto()
    PORTUGUESE = auto()
    RUSSIAN = auto()
    CHINESE = auto()
    JAPANESE = auto()
    ARABIC = auto()
    AUTO = auto()


class OCRMode(Enum):
    """OCR processing modes"""
    FAST = auto()
    ACCURATE = auto()
    BALANCED = auto()


@dataclass
class OCRResult:
    """Result of OCR processing"""
    text: str
    confidence: float = 0.0
    language: OCRLanguage = OCRLanguage.ENGLISH
    processing_time: float = 0.0
    word_count: int = 0
    line_count: int = 0
    detected_languages: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "language": self.language.name,
            "processing_time": self.processing_time,
            "word_count": self.word_count,
            "line_count": self.line_count,
            "detected_languages": self.detected_languages,
            "metadata": self.metadata
        }
    
    def is_valid(self) -> bool:
        """Check if OCR result is valid"""
        return bool(self.text.strip())
    
    def get_words(self) -> List[str]:
        """Get list of words"""
        return re.findall(r'\b\w+\b', self.text)
    
    def get_lines(self) -> List[str]:
        """Get list of lines"""
        return [line.strip() for line in self.text.split('\n') if line.strip()]


@dataclass
class OCRRegion:
    """Region for OCR processing"""
    x: int
    y: int
    width: int
    height: int
    
    def to_dict(self) -> Dict:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height
        }


@dataclass
class TextBlock:
    """Extracted text block with position"""
    text: str
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    confidence: float = 0.0
    language: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "confidence": self.confidence,
            "language": self.language
        }


class OCREngine:
    """
    Optical Character Recognition Engine
    
    Supports multiple OCR backends:
    - Tesseract (local)
    - Google ML Kit (via Android)
    - Online APIs (fallback)
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # OCR configuration
        self._default_language = OCRLanguage.ENGLISH
        self._default_mode = OCRMode.BALANCED
        self._supported_languages = [lang.name.lower() for lang in OCRLanguage]
        
        # Backend configuration
        self._backends = {
            "tesseract": {
                "enabled": True,
                "priority": 1,
                "available": False  # Would be True if Tesseract is installed
            },
            "google_ml": {
                "enabled": True,
                "priority": 2,
                "available": False  # Would be True if Google ML Kit is available
            },
            "online": {
                "enabled": True,
                "priority": 3,
                "available": True
            }
        }
        
        # State
        self._is_processing = False
        self._processing_queue = []
        
        # Callbacks
        self._on_ocr_complete: List[Callable[[OCRResult], None]] = []
        self._on_ocr_start: List[Callable[[str], None]] = []
        
        # Initialize
        self._initialize()
    
    def _initialize(self):
        """Initialize OCR engine"""
        # Check for Tesseract
        try:
            import pytesseract
            self._backends["tesseract"]["available"] = True
            self.logger.info("Tesseract OCR available")
        except ImportError:
            self.logger.warning("Tesseract OCR not available")
        
        # Check for other backends
        # In a real implementation, would check for Android ML Kit, etc.
    
    def set_default_language(self, language: OCRLanguage) -> bool:
        """Set default OCR language"""
        if language in OCRLanguage:
            self._default_language = language
            self.logger.info(f"Default OCR language set to: {language.name}")
            return True
        return False
    
    def get_default_language(self) -> OCRLanguage:
        """Get default OCR language"""
        return self._default_language
    
    def set_default_mode(self, mode: OCRMode) -> bool:
        """Set default OCR mode"""
        if mode in OCRMode:
            self._default_mode = mode
            self.logger.info(f"Default OCR mode set to: {mode.name}")
            return True
        return False
    
    def get_default_mode(self) -> OCRMode:
        """Get default OCR mode"""
        return self._default_mode
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages"""
        return self._supported_languages
    
    def get_available_backends(self) -> List[str]:
        """Get list of available OCR backends"""
        return [name for name, config in self._backends.items() if config["available"]]
    
    async def extract_text(self, image_data: bytes, 
                         language: OCRLanguage = None,
                         mode: OCRMode = None,
                         region: OCRRegion = None) -> Optional[OCRResult]:
        """
        Extract text from image data
        
        Args:
            image_data: Raw image data (bytes)
            language: Language to use (defaults to default)
            mode: OCR mode to use (defaults to default)
            region: Optional region to process
            
        Returns:
            OCRResult or None if failed
        """
        start_time = time.time()
        
        try:
            # Set defaults
            if language is None:
                language = self._default_language
            if mode is None:
                mode = self._default_mode
            
            # Notify start
            for callback in self._on_ocr_start:
                try:
                    callback(f"Starting OCR with {language.name} language")
                except Exception as e:
                    self.error_handler.handle_error(e, "ocr_start_callback")
            
            # Select backend
            backend = self._select_backend(mode)
            
            # Process with selected backend
            if backend == "tesseract":
                result = await self._process_with_tesseract(image_data, language, region)
            elif backend == "google_ml":
                result = await self._process_with_google_ml(image_data, language, region)
            else:
                result = await self._process_with_online(image_data, language, region)
            
            if result:
                # Calculate processing time
                result.processing_time = time.time() - start_time
                
                # Count words and lines
                result.word_count = len(result.get_words())
                result.line_count = len(result.get_lines())
                
                # Add metadata
                result.metadata = {
                    "backend": backend,
                    "mode": mode.name,
                    "language": language.name,
                    "timestamp": time.time()
                }
            
            # Notify completion
            for callback in self._on_ocr_complete:
                try:
                    callback(result)
                except Exception as e:
                    self.error_handler.handle_error(e, "ocr_complete_callback")
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, "extract_text")
            return None
    
    async def extract_text_from_file(self, image_path: str,
                                    language: OCRLanguage = None,
                                    mode: OCRMode = None,
                                    region: OCRRegion = None) -> Optional[OCRResult]:
        """
        Extract text from an image file
        
        Args:
            image_path: Path to the image file
            language: Language to use
            mode: OCR mode to use
            region: Optional region to process
            
        Returns:
            OCRResult or None if failed
        """
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            return await self.extract_text(image_data, language, mode, region)
            
        except Exception as e:
            self.error_handler.handle_error(e, "extract_text_from_file")
            return None
    
    async def extract_text_from_screenshot(self, screenshot_id: str,
                                         screenshot_manager: Any = None,
                                         language: OCRLanguage = None,
                                         mode: OCRMode = None) -> Optional[OCRResult]:
        """
        Extract text from a screenshot
        
        Args:
            screenshot_id: ID of the screenshot
            screenshot_manager: ScreenshotManager instance
            language: Language to use
            mode: OCR mode to use
            
        Returns:
            OCRResult or None if failed
        """
        try:
            if screenshot_manager:
                image_data = await screenshot_manager.get_screenshot_image(screenshot_id)
                if image_data:
                    return await self.extract_text(image_data, language, mode)
            
            return None
            
        except Exception as e:
            self.error_handler.handle_error(e, "extract_text_from_screenshot")
            return None
    
    def _select_backend(self, mode: OCRMode) -> str:
        """Select the best available backend for the mode"""
        # Sort backends by priority
        sorted_backends = sorted(
            self._backends.items(),
            key=lambda x: x[1]["priority"]
        )
        
        # Find first available backend
        for name, config in sorted_backends:
            if config["enabled"] and config["available"]:
                return name
        
        # Fallback to online if nothing else is available
        return "online"
    
    async def _process_with_tesseract(self, image_data: bytes,
                                    language: OCRLanguage,
                                    region: OCRRegion = None) -> Optional[OCRResult]:
        """Process with Tesseract OCR"""
        try:
            # In a real implementation, this would use pytesseract
            import pytesseract
            from PIL import Image
            import io
            
            # Load image
            image = Image.open(io.BytesIO(image_data))
            
            # Convert language to Tesseract format
            lang_map = {
                OCRLanguage.ENGLISH: "eng",
                OCRLanguage.URDU: "urd",
                OCRLanguage.HINDI: "hin",
                OCRLanguage.AUTO: ""
            }
            lang = lang_map.get(language, "eng")
            
            # Configure Tesseract based on mode
            config = ""
            if self._default_mode == OCRMode.FAST:
                config = "--psm 6 --oem 1"  # Fast mode
            elif self._default_mode == OCRMode.ACCURATE:
                config = "--psm 6 --oem 3"  # Best accuracy
            
            # Process image
            start_time = time.time()
            text = pytesseract.image_to_string(image, lang=lang, config=config)
            processing_time = time.time() - start_time
            
            # Calculate confidence (mock value - Tesseract doesn't provide this directly)
            confidence = 0.9 if text.strip() else 0.0
            
            return OCRResult(
                text=text,
                confidence=confidence,
                language=language,
                processing_time=processing_time
            )
            
        except ImportError:
            self.logger.warning("Tesseract not available")
            return None
        except Exception as e:
            self.error_handler.handle_error(e, "process_with_tesseract")
            return None
    
    async def _process_with_google_ml(self, image_data: bytes,
                                   language: OCRLanguage,
                                   region: OCRRegion = None) -> Optional[OCRResult]:
        """Process with Google ML Kit"""
        # This would integrate with Android's Google ML Kit via Shizuku or Bridge APK
        
        try:
            # Mock implementation
            self.logger.info("Processing with Google ML Kit")
            
            # Simulate processing
            await asyncio.sleep(1.0)
            
            # Mock result
            text = "Sample text extracted using Google ML Kit"
            
            return OCRResult(
                text=text,
                confidence=0.95,
                language=language,
                processing_time=1.0
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "process_with_google_ml")
            return None
    
    async def _process_with_online(self, image_data: bytes,
                                  language: OCRLanguage,
                                  region: OCRRegion = None) -> Optional[OCRResult]:
        """Process with online OCR API"""
        try:
            # In a real implementation, this would use a cloud OCR API
            # For now, use a mock implementation
            
            self.logger.info("Processing with online OCR")
            
            # Simulate network delay
            await asyncio.sleep(2.0)
            
            # Mock result
            text = "Sample text extracted using online OCR service"
            
            return OCRResult(
                text=text,
                confidence=0.9,
                language=language,
                processing_time=2.0,
                metadata={"backend": "online"}
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "process_with_online")
            return None
    
    async def extract_with_position(self, image_data: bytes,
                                   language: OCRLanguage = None,
                                   mode: OCRMode = None) -> Optional[List[TextBlock]]:
        """
        Extract text with position information
        
        Args:
            image_data: Raw image data
            language: Language to use
            mode: OCR mode to use
            
        Returns:
            List of TextBlock objects or None if failed
        """
        try:
            # In a real implementation, this would use Tesseract with page segmentation
            # to get word/line positions
            
            # For now, return mock data
            result = await self.extract_text(image_data, language, mode)
            
            if result and result.text:
                # Split into lines
                lines = result.get_lines()
                
                # Create text blocks with mock positions
                blocks = []
                y = 50
                
                for line in lines:
                    blocks.append(TextBlock(
                        text=line,
                        x=50,
                        y=y,
                        width=500,
                        height=30,
                        confidence=0.9,
                        language=result.language.name
                    ))
                    y += 40
                
                return blocks
            
            return None
            
        except Exception as e:
            self.error_handler.handle_error(e, "extract_with_position")
            return None
    
    async def detect_language(self, image_data: bytes) -> Optional[List[str]]:
        """
        Detect languages in an image
        
        Args:
            image_data: Raw image data
            
        Returns:
            List of detected languages or None if failed
        """
        try:
            # In a real implementation, this would use language detection
            # For now, return mock data
            
            # Process with default language
            result = await self.extract_text(image_data, OCRLanguage.AUTO)
            
            if result:
                # Mock language detection
                return ["en", "ur"]  # English and Urdu
            
            return None
            
        except Exception as e:
            self.error_handler.handle_error(e, "detect_language")
            return None
    
    async def process_multiple_images(self, image_paths: List[str],
                                     language: OCRLanguage = None,
                                     mode: OCRMode = None) -> Dict[str, OCRResult]:
        """
        Process multiple images
        
        Args:
            image_paths: List of image file paths
            language: Language to use
            mode: OCR mode to use
            
        Returns:
            Dictionary of path -> OCRResult
        """
        results = {}
        
        for path in image_paths:
            try:
                result = await self.extract_text_from_file(path, language, mode)
                if result:
                    results[path] = result
            except Exception as e:
                self.error_handler.handle_error(e, f"process_image_{path}")
        
        return results
    
    async def batch_process(self, image_data_list: List[bytes],
                          language: OCRLanguage = None,
                          mode: OCRMode = None) -> List[OCRResult]:
        """
        Batch process multiple image data
        
        Args:
            image_data_list: List of image data bytes
            language: Language to use
            mode: OCR mode to use
            
        Returns:
            List of OCRResults
        """
        results = []
        
        for image_data in image_data_list:
            result = await self.extract_text(image_data, language, mode)
            if result:
                results.append(result)
        
        return results
    
    def clean_text(self, text: str) -> str:
        """
        Clean extracted text
        
        Args:
            text: Raw OCR text
            
        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove non-printable characters
        text = re.sub(r'[^\x20-\x7E\n\r\t]', '', text)
        
        # Normalize line breaks
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\r', '\n', text)
        
        # Remove empty lines
        lines = [line for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        
        return text.strip()
    
    def extract_numbers(self, text: str) -> List[str]:
        """
        Extract numbers from OCR text
        
        Args:
            text: OCR text
            
        Returns:
            List of extracted numbers
        """
        # Extract integers
        integers = re.findall(r'\b[0-9]+\b', text)
        
        # Extract decimals
        decimals = re.findall(r'\b[0-9]+\.[0-9]+\b', text)
        
        return integers + decimals
    
    def extract_emails(self, text: str) -> List[str]:
        """
        Extract email addresses from OCR text
        
        Args:
            text: OCR text
            
        Returns:
            List of extracted emails
        """
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return re.findall(email_pattern, text)
    
    def extract_phone_numbers(self, text: str) -> List[str]:
        """
        Extract phone numbers from OCR text
        
        Args:
            text: OCR text
            
        Returns:
            List of extracted phone numbers
        """
        # International format
        intl_pattern = r'\+[0-9\s-]{10,}'
        
        # Local format
        local_pattern = r'[0-9\s-]{10,}'
        
        intl_numbers = re.findall(intl_pattern, text)
        local_numbers = re.findall(local_pattern, text)
        
        # Combine and deduplicate
        all_numbers = list(set(intl_numbers + local_numbers))
        
        # Filter out very short numbers
        return [n for n in all_numbers if len(re.sub(r'[^0-9]', '', n)) >= 7]
    
    def extract_links(self, text: str) -> List[str]:
        """
        Extract links/URLs from OCR text
        
        Args:
            text: OCR text
            
        Returns:
            List of extracted links
        """
        url_pattern = r'https?://[^\s]+|www\.[^\s]+'
        return re.findall(url_pattern, text, re.IGNORECASE)
    
    # Callback Registration
    
    def on_ocr_complete(self, callback: Callable[[OCRResult], None]):
        """Register OCR completion callback"""
        self._on_ocr_complete.append(callback)
    
    def on_ocr_start(self, callback: Callable[[str], None]):
        """Register OCR start callback"""
        self._on_ocr_start.append(callback)
    
    # Configuration Methods
    
    def set_backend_config(self, backend: str, **kwargs):
        """Configure a specific backend"""
        if backend in self._backends:
            for key, value in kwargs.items():
                if key in self._backends[backend]:
                    self._backends[backend][key] = value
                    self.logger.info(f"Backend {backend} config updated: {key}={value}")
    
    def get_backend_config(self, backend: str) -> Optional[Dict]:
        """Get configuration for a backend"""
        return self._backends.get(backend)
    
    # Cleanup
    
    async def cleanup(self):
        """Clean up resources"""
        self._processing_queue = []
        self._is_processing = False
        self.logger.info("OCR Engine cleaned up")
