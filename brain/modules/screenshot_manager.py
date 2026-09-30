"""
Screenshot Manager Module
Handles screenshot capture and management
"""

import asyncio
import json
import time
import os
import uuid
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum, auto

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler


class ScreenshotFormat(Enum):
    """Screenshot image formats"""
    PNG = auto()
    JPEG = auto()
    WEBP = auto()


class ScreenshotQuality(Enum):
    """Screenshot quality levels"""
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    MAXIMUM = auto()


@dataclass
class Screenshot:
    """Represents a captured screenshot"""
    id: str
    path: str
    timestamp: float
    width: int = 0
    height: int = 0
    format: ScreenshotFormat = ScreenshotFormat.PNG
    quality: ScreenshotQuality = ScreenshotQuality.HIGH
    size: int = 0  # bytes
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "path": self.path,
            "timestamp": self.timestamp,
            "width": self.width,
            "height": self.height,
            "format": self.format.name,
            "quality": self.quality.name,
            "size": self.size,
            "metadata": self.metadata
        }
    
    def get_age(self) -> float:
        """Get age in seconds"""
        return time.time() - self.timestamp


@dataclass
class ScreenshotRegion:
    """Region of a screenshot"""
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
    
    def get_area(self) -> int:
        """Get area of the region"""
        return self.width * self.height


class ScreenshotManager:
    """
    Manages screenshot capture, storage, and retrieval
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Configuration
        self._storage_dir = "/storage/emulated/0/Pictures/JARVIS_Screenshots"
        self._max_screenshots = 100
        self._default_format = ScreenshotFormat.PNG
        self._default_quality = ScreenshotQuality.HIGH
        
        # State
        self._screenshots: Dict[str, Screenshot] = {}
        self._screenshot_counter = 0
        
        # Callbacks
        self._on_screenshot_captured: List[Callable[[Screenshot], None]] = []
        self._on_screenshot_deleted: List[Callable[[str], None]] = []
        
        # Ensure storage directory exists
        self._ensure_storage_dir()
    
    def _ensure_storage_dir(self):
        """Ensure storage directory exists"""
        try:
            os.makedirs(self._storage_dir, exist_ok=True)
            self.logger.info(f"Screenshot storage directory: {self._storage_dir}")
        except Exception as e:
            self.error_handler.handle_error(e, "ensure_storage_dir")
    
    async def capture_screenshot(self, name: str = None, 
                               format: ScreenshotFormat = None,
                               quality: ScreenshotQuality = None) -> Optional[Screenshot]:
        """
        Capture a screenshot
        
        Args:
            name: Optional custom name for the screenshot
            format: Image format (defaults to PNG)
            quality: Quality level (defaults to HIGH)
            
        Returns:
            Screenshot object or None if failed
        """
        try:
            # Generate ID and name
            screenshot_id = str(uuid.uuid4())
            if not name:
                name = f"screenshot_{int(time.time())}_{self._screenshot_counter}"
                self._screenshot_counter += 1
            
            # Set format and quality
            if format is None:
                format = self._default_format
            if quality is None:
                quality = self._default_quality
            
            # Generate filename
            ext_map = {
                ScreenshotFormat.PNG: "png",
                ScreenshotFormat.JPEG: "jpg",
                ScreenshotFormat.WEBP: "webp"
            }
            filename = f"{name}.{ext_map[format]}"
            path = os.path.join(self._storage_dir, filename)
            
            # In a real implementation, this would use:
            # - Android AccessibilityService to capture screen
            # - Shizuku for advanced capture
            # - Or termux command: termux-screenshot
            
            # Mock implementation - create a dummy file
            self.logger.info(f"Capturing screenshot: {path}")
            
            # Simulate screen dimensions
            width, height = 1080, 2340
            
            # Create a dummy image file (in production, this would be the actual screenshot)
            self._create_dummy_screenshot(path, width, height, format)
            
            # Get file size
            size = os.path.getsize(path) if os.path.exists(path) else 0
            
            # Create screenshot object
            screenshot = Screenshot(
                id=screenshot_id,
                path=path,
                timestamp=time.time(),
                width=width,
                height=height,
                format=format,
                quality=quality,
                size=size,
                metadata={
                    "device": "Android",
                    "orientation": "portrait" if height > width else "landscape"
                }
            )
            
            # Store screenshot
            self._screenshots[screenshot_id] = screenshot
            
            # Cleanup old screenshots if needed
            await self._cleanup_old_screenshots()
            
            # Notify callbacks
            for callback in self._on_screenshot_captured:
                try:
                    callback(screenshot)
                except Exception as e:
                    self.error_handler.handle_error(e, "screenshot_captured_callback")
            
            self.logger.info(f"Screenshot captured: {screenshot_id}")
            return screenshot
            
        except Exception as e:
            self.error_handler.handle_error(e, "capture_screenshot")
            return None
    
    def _create_dummy_screenshot(self, path: str, width: int, height: int, 
                                format: ScreenshotFormat):
        """Create a dummy screenshot for testing"""
        try:
            if format == ScreenshotFormat.PNG:
                # Create a simple PNG file
                # This is a placeholder - in production, use PIL or similar
                with open(path, 'wb') as f:
                    # Write a minimal PNG header
                    f.write(b'\x89PNG\r\n\x1a\n')
                    # Write some dummy data
                    f.write(b'\x00' * 1000)
            else:
                # Create a simple file for other formats
                with open(path, 'wb') as f:
                    f.write(b'DUMMY_SCREENSHOT_DATA')
        except Exception as e:
            self.error_handler.handle_error(e, "create_dummy_screenshot")
    
    async def capture_region(self, region: ScreenshotRegion, 
                            name: str = None) -> Optional[Screenshot]:
        """
        Capture a specific region of the screen
        
        Args:
            region: The region to capture
            name: Optional custom name
            
        Returns:
            Screenshot object or None if failed
        """
        try:
            # In a real implementation, this would use AccessibilityService
            # to capture a specific region
            
            # For now, just capture full screen and note the region
            screenshot = await self.capture_screenshot(name)
            
            if screenshot:
                # Store region information in metadata
                screenshot.metadata["region"] = region.to_dict()
                screenshot.metadata["is_region"] = True
            
            return screenshot
            
        except Exception as e:
            self.error_handler.handle_error(e, "capture_region")
            return None
    
    async def get_screenshot(self, screenshot_id: str) -> Optional[Screenshot]:
        """Get a screenshot by ID"""
        return self._screenshots.get(screenshot_id)
    
    async def get_all_screenshots(self) -> List[Screenshot]:
        """Get all screenshots"""
        return list(self._screenshots.values())
    
    async def get_recent_screenshots(self, count: int = 10) -> List[Screenshot]:
        """Get recent screenshots"""
        screenshots = list(self._screenshots.values())
        screenshots.sort(key=lambda s: s.timestamp, reverse=True)
        return screenshots[:count]
    
    async def delete_screenshot(self, screenshot_id: str) -> bool:
        """Delete a screenshot"""
        try:
            screenshot = self._screenshots.get(screenshot_id)
            if not screenshot:
                return False
            
            # Delete file
            if os.path.exists(screenshot.path):
                os.remove(screenshot.path)
            
            # Remove from cache
            del self._screenshots[screenshot_id]
            
            # Notify callbacks
            for callback in self._on_screenshot_deleted:
                try:
                    callback(screenshot_id)
                except Exception as e:
                    self.error_handler.handle_error(e, "screenshot_deleted_callback")
            
            self.logger.info(f"Screenshot deleted: {screenshot_id}")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "delete_screenshot")
            return False
    
    async def delete_all_screenshots(self) -> int:
        """Delete all screenshots"""
        count = 0
        
        for screenshot_id, screenshot in list(self._screenshots.items()):
            if await self.delete_screenshot(screenshot_id):
                count += 1
        
        self.logger.info(f"Deleted {count} screenshots")
        return count
    
    async def _cleanup_old_screenshots(self):
        """Clean up old screenshots if over limit"""
        if len(self._screenshots) <= self._max_screenshots:
            return
        
        # Sort by timestamp (oldest first)
        sorted_screenshots = sorted(
            self._screenshots.items(),
            key=lambda x: x[1].timestamp
        )
        
        # Delete oldest screenshots
        to_delete = len(self._screenshots) - self._max_screenshots
        for screenshot_id, _ in sorted_screenshots[:to_delete]:
            await self.delete_screenshot(screenshot_id)
        
        self.logger.info(f"Cleaned up {to_delete} old screenshots")
    
    async def save_screenshot(self, image_data: bytes, name: str = None,
                           format: ScreenshotFormat = None) -> Optional[Screenshot]:
        """
        Save image data as a screenshot
        
        Args:
            image_data: Raw image data
            name: Optional custom name
            format: Image format
            
        Returns:
            Screenshot object or None if failed
        """
        try:
            # Generate ID and name
            screenshot_id = str(uuid.uuid4())
            if not name:
                name = f"screenshot_{int(time.time())}_{self._screenshot_counter}"
                self._screenshot_counter += 1
            
            # Set format
            if format is None:
                format = self._default_format
            
            # Generate filename
            ext_map = {
                ScreenshotFormat.PNG: "png",
                ScreenshotFormat.JPEG: "jpg",
                ScreenshotFormat.WEBP: "webp"
            }
            filename = f"{name}.{ext_map[format]}"
            path = os.path.join(self._storage_dir, filename)
            
            # Save image data
            with open(path, 'wb') as f:
                f.write(image_data)
            
            # Get dimensions (in production, would parse image header)
            width, height = 1080, 2340  # Default
            
            # Get file size
            size = len(image_data)
            
            # Create screenshot object
            screenshot = Screenshot(
                id=screenshot_id,
                path=path,
                timestamp=time.time(),
                width=width,
                height=height,
                format=format,
                quality=self._default_quality,
                size=size,
                metadata={"source": "external"}
            )
            
            # Store screenshot
            self._screenshots[screenshot_id] = screenshot
            
            # Notify callbacks
            for callback in self._on_screenshot_captured:
                try:
                    callback(screenshot)
                except Exception as e:
                    self.error_handler.handle_error(e, "screenshot_captured_callback")
            
            self.logger.info(f"Screenshot saved: {screenshot_id}")
            return screenshot
            
        except Exception as e:
            self.error_handler.handle_error(e, "save_screenshot")
            return None
    
    async def get_screenshot_image(self, screenshot_id: str) -> Optional[bytes]:
        """Get image data for a screenshot"""
        try:
            screenshot = self._screenshots.get(screenshot_id)
            if not screenshot or not os.path.exists(screenshot.path):
                return None
            
            with open(screenshot.path, 'rb') as f:
                return f.read()
            
        except Exception as e:
            self.error_handler.handle_error(e, "get_screenshot_image")
            return None
    
    async def crop_screenshot(self, screenshot_id: str, 
                            region: ScreenshotRegion) -> Optional[bytes]:
        """
        Crop a screenshot to a specific region
        
        Args:
            screenshot_id: ID of the screenshot to crop
            region: The region to crop to
            
        Returns:
            Cropped image data or None if failed
        """
        try:
            image_data = await self.get_screenshot_image(screenshot_id)
            if not image_data:
                return None
            
            # In a real implementation, this would use PIL or similar
            # to crop the image
            
            # For now, just return the original data
            # (cropping would be implemented with actual image processing)
            
            self.logger.info(f"Cropping screenshot {screenshot_id} to region: {region.to_dict()}")
            return image_data
            
        except Exception as e:
            self.error_handler.handle_error(e, "crop_screenshot")
            return None
    
    async def get_screenshot_info(self, screenshot_id: str) -> Optional[Dict]:
        """Get detailed information about a screenshot"""
        screenshot = self._screenshots.get(screenshot_id)
        if not screenshot:
            return None
        
        # Add file info
        info = screenshot.to_dict()
        info["exists"] = os.path.exists(screenshot.path)
        info["age_seconds"] = screenshot.get_age()
        
        return info
    
    async def search_screenshots(self, query: str) -> List[Screenshot]:
        """Search screenshots by metadata or content"""
        results = []
        
        for screenshot in self._screenshots.values():
            # Search in metadata
            if self._metadata_matches(screenshot.metadata, query):
                results.append(screenshot)
            
            # In a real implementation, would also search image content
            # using OCR or image recognition
        
        return results
    
    def _metadata_matches(self, metadata: Dict, query: str) -> bool:
        """Check if metadata matches query"""
        query_lower = query.lower()
        
        for key, value in metadata.items():
            if isinstance(value, str) and query_lower in value.lower():
                return True
            elif isinstance(value, dict) and self._metadata_matches(value, query):
                return True
        
        return False
    
    async def get_storage_info(self) -> Dict:
        """Get storage information"""
        try:
            # Count files in directory
            file_count = 0
            total_size = 0
            
            if os.path.exists(self._storage_dir):
                for filename in os.listdir(self._storage_dir):
                    filepath = os.path.join(self._storage_dir, filename)
                    if os.path.isfile(filepath):
                        file_count += 1
                        total_size += os.path.getsize(filepath)
            
            return {
                "directory": self._storage_dir,
                "file_count": file_count,
                "total_size": total_size,
                "max_screenshots": self._max_screenshots,
                "cached_screenshots": len(self._screenshots)
            }
        except Exception as e:
            self.error_handler.handle_error(e, "get_storage_info")
            return {
                "directory": self._storage_dir,
                "file_count": 0,
                "total_size": 0
            }
    
    def set_storage_dir(self, directory: str) -> bool:
        """Set the storage directory"""
        try:
            os.makedirs(directory, exist_ok=True)
            self._storage_dir = directory
            self.logger.info(f"Storage directory set to: {directory}")
            return True
        except Exception as e:
            self.error_handler.handle_error(e, "set_storage_dir")
            return False
    
    def set_max_screenshots(self, max_count: int) -> bool:
        """Set maximum number of screenshots to keep"""
        if max_count > 0:
            self._max_screenshots = max_count
            self.logger.info(f"Max screenshots set to: {max_count}")
            return True
        return False
    
    def set_default_format(self, format: ScreenshotFormat) -> bool:
        """Set default screenshot format"""
        self._default_format = format
        self.logger.info(f"Default format set to: {format.name}")
        return True
    
    def set_default_quality(self, quality: ScreenshotQuality) -> bool:
        """Set default screenshot quality"""
        self._default_quality = quality
        self.logger.info(f"Default quality set to: {quality.name}")
        return True
    
    # Callback Registration
    
    def on_screenshot_captured(self, callback: Callable[[Screenshot], None]):
        """Register screenshot captured callback"""
        self._on_screenshot_captured.append(callback)
    
    def on_screenshot_deleted(self, callback: Callable[[str], None]):
        """Register screenshot deleted callback"""
        self._on_screenshot_deleted.append(callback)
    
    # Cleanup
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            # Delete all screenshots
            await self.delete_all_screenshots()
            
            # Remove directory if empty
            if os.path.exists(self._storage_dir) and not os.listdir(self._storage_dir):
                os.rmdir(self._storage_dir)
            
            self.logger.info("Screenshot Manager cleaned up")
        except Exception as e:
            self.error_handler.handle_error(e, "screenshot_cleanup")
