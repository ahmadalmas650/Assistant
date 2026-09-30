"""
Accessibility Controller Module
Controls Android accessibility features for device interaction
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler


class AccessibilityAction(Enum):
    """Accessibility action types"""
    CLICK = auto()
    DOUBLE_CLICK = auto()
    LONG_CLICK = auto()
    SWIPE = auto()
    SCROLL = auto()
    TYPE = auto()
    PASTE = auto()
    COPY = auto()
    CUT = auto()
    SELECT = auto()
    BACK = auto()
    HOME = auto()
    RECENTS = auto()
    MENU = auto()
    POWER = auto()
    VOLUME_UP = auto()
    VOLUME_DOWN = auto()
    OPEN_APP = auto()
    CLOSE_APP = auto()
    SWITCH_APP = auto()
    TAKE_SCREENSHOT = auto()
    EXTRACT_TEXT = auto()
    GET_NODES = auto()
    FIND_NODE = auto()


class SwipeDirection(Enum):
    """Swipe directions"""
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    UP_LEFT = auto()
    UP_RIGHT = auto()
    DOWN_LEFT = auto()
    DOWN_RIGHT = auto()


class ScrollDirection(Enum):
    """Scroll directions"""
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()


@dataclass
class AccessibilityNode:
    """Represents a UI node on screen"""
    node_id: str
    text: str = ""
    content_description: str = ""
    class_name: str = ""
    package_name: str = ""
    bounds: Dict[str, int] = field(default_factory=dict)  # {left, top, right, bottom}
    clickable: bool = False
    checkable: bool = False
    checked: bool = False
    enabled: bool = True
    focused: bool = False
    focusable: bool = False
    long_clickable: bool = False
    scrollable: bool = False
    selected: bool = False
    child_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "text": self.text,
            "content_description": self.content_description,
            "class_name": self.class_name,
            "package_name": self.package_name,
            "bounds": self.bounds,
            "clickable": self.clickable,
            "checkable": self.checkable,
            "checked": self.checked,
            "enabled": self.enabled,
            "focused": self.focused,
            "focusable": self.focusable,
            "long_clickable": self.long_clickable,
            "scrollable": self.scrollable,
            "selected": self.selected,
            "child_count": self.child_count
        }
    
    def is_clickable(self) -> bool:
        return self.clickable and self.enabled
    
    def get_center(self) -> Tuple[int, int]:
        """Get center coordinates of the node"""
        if self.bounds:
            left = self.bounds.get("left", 0)
            top = self.bounds.get("top", 0)
            right = self.bounds.get("right", 0)
            bottom = self.bounds.get("bottom", 0)
            return ((left + right) // 2, (top + bottom) // 2)
        return (0, 0)
    
    def contains_text(self, text: str) -> bool:
        """Check if node contains specific text"""
        return text.lower() in self.text.lower() or \
               text.lower() in self.content_description.lower()


@dataclass
class ActionResult:
    """Result of an accessibility action"""
    action: AccessibilityAction
    success: bool
    message: str = ""
    node: Optional[AccessibilityNode] = None
    data: Optional[Any] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "action": self.action.name,
            "success": self.success,
            "message": self.message,
            "node": self.node.to_dict() if self.node else None,
            "data": self.data,
            "timestamp": self.timestamp
        }


class AccessibilityController:
    """
    Controls Android accessibility features
    
    This module interacts with:
    - Android AccessibilityService
    - Shizuku for advanced APIs
    - Termux for command execution
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Service state
        self._service_connected = False
        self._service_enabled = False
        self._shizuku_available = False
        
        # Screen state
        self._screen_width = 1080
        self._screen_height = 2340
        self._screen_density = 420
        
        # Node cache
        self._node_cache: Dict[str, AccessibilityNode] = {}
        self._cache_timestamp = 0.0
        self._cache_validity = 1.0  # seconds
        
        # Callbacks
        self._on_action_complete: List[Callable[[ActionResult], None]] = []
        self._on_service_state_change: List[Callable[[bool], None]] = []
        
        # Initialize
        self._initialize()
    
    def _initialize(self):
        """Initialize the controller"""
        # Check if accessibility service is available
        # In a real implementation, this would check the actual service
        self._service_connected = True
        self._service_enabled = True
        
        # Check Shizuku availability
        self._shizuku_available = False  # Would be True if Shizuku is running
        
        self.logger.info("Accessibility Controller initialized")
    
    # Service Management
    
    async def check_service_status(self) -> Dict:
        """Check accessibility service status"""
        return {
            "connected": self._service_connected,
            "enabled": self._service_enabled,
            "shizuku_available": self._shizuku_available,
            "screen_resolution": {
                "width": self._screen_width,
                "height": self._screen_height,
                "density": self._screen_density
            }
        }
    
    async def enable_service(self) -> bool:
        """Enable accessibility service"""
        # In a real implementation, this would open settings for the user
        self.logger.info("Requesting accessibility service enable")
        
        # Mock: assume user enables it
        self._service_enabled = True
        
        for callback in self._on_service_state_change:
            try:
                callback(True)
            except Exception as e:
                self.error_handler.handle_error(e, "service_state_callback")
        
        return True
    
    async def disable_service(self) -> bool:
        """Disable accessibility service"""
        self._service_enabled = False
        
        for callback in self._on_service_state_change:
            try:
                callback(False)
            except Exception as e:
                self.error_handler.handle_error(e, "service_state_callback")
        
        return True
    
    def is_service_enabled(self) -> bool:
        """Check if service is enabled"""
        return self._service_enabled
    
    def is_shizuku_available(self) -> bool:
        """Check if Shizuku is available"""
        return self._shizuku_available
    
    # Screen Information
    
    async def get_screen_info(self) -> Dict:
        """Get current screen information"""
        return {
            "width": self._screen_width,
            "height": self._screen_height,
            "density": self._screen_density,
            "orientation": "portrait" if self._screen_height > self._screen_width else "landscape",
            "current_app": await self.get_foreground_app()
        }
    
    async def get_foreground_app(self) -> Optional[str]:
        """Get the current foreground app package name"""
        # In a real implementation, this would use AccessibilityService or Shizuku
        # For now, return a mock value
        return "com.android.chrome"
    
    async def get_current_activity(self) -> Optional[str]:
        """Get the current activity name"""
        # Mock implementation
        return ".MainActivity"
    
    # Node Operations
    
    async def get_root_node(self) -> Optional[AccessibilityNode]:
        """Get the root accessibility node"""
        # Mock implementation
        return AccessibilityNode(
            node_id="root",
            text="",
            class_name="android.view.ViewRootImpl",
            package_name="android",
            bounds={"left": 0, "top": 0, "right": self._screen_width, "bottom": self._screen_height},
            clickable=False,
            child_count=1
        )
    
    async def get_all_nodes(self, refresh: bool = False) -> List[AccessibilityNode]:
        """Get all accessibility nodes on screen"""
        if not refresh and self._node_cache and \
           (time.time() - self._cache_timestamp) < self._cache_validity:
            return list(self._node_cache.values())
        
        # Mock implementation - generate sample nodes
        nodes = []
        
        # Add some sample nodes
        nodes.append(AccessibilityNode(
            node_id="node_1",
            text="YouTube",
            class_name="android.widget.TextView",
            package_name="com.google.android.youtube",
            bounds={"left": 100, "top": 50, "right": 300, "bottom": 100},
            clickable=True
        ))
        
        nodes.append(AccessibilityNode(
            node_id="node_2",
            text="Search",
            class_name="android.widget.Button",
            package_name="com.google.android.youtube",
            bounds={"left": 500, "top": 50, "right": 700, "bottom": 100},
            clickable=True
        ))
        
        nodes.append(AccessibilityNode(
            node_id="node_3",
            text="Home",
            class_name="android.widget.TabWidget",
            package_name="com.google.android.youtube",
            bounds={"left": 100, "top": 2000, "right": 300, "bottom": 2100},
            clickable=True
        ))
        
        # Cache nodes
        self._node_cache = {n.node_id: n for n in nodes}
        self._cache_timestamp = time.time()
        
        return nodes
    
    async def find_node_by_text(self, text: str, exact: bool = False) -> Optional[AccessibilityNode]:
        """Find a node by its text"""
        nodes = await self.get_all_nodes()
        
        for node in nodes:
            if exact:
                if node.text.lower() == text.lower():
                    return node
            else:
                if text.lower() in node.text.lower() or \
                   text.lower() in node.content_description.lower():
                    return node
        
        return None
    
    async def find_nodes_by_text(self, text: str) -> List[AccessibilityNode]:
        """Find all nodes containing specific text"""
        nodes = await self.get_all_nodes()
        
        result = []
        for node in nodes:
            if text.lower() in node.text.lower() or \
               text.lower() in node.content_description.lower():
                result.append(node)
        
        return result
    
    async def find_node_by_id(self, node_id: str) -> Optional[AccessibilityNode]:
        """Find a node by its ID"""
        nodes = await self.get_all_nodes()
        
        for node in nodes:
            if node.node_id == node_id:
                return node
        
        return None
    
    async def find_node_by_bounds(self, left: int, top: int, right: int, bottom: int) -> Optional[AccessibilityNode]:
        """Find a node by its bounds"""
        nodes = await self.get_all_nodes()
        
        for node in nodes:
            if (node.bounds.get("left", 0) == left and
                node.bounds.get("top", 0) == top and
                node.bounds.get("right", 0) == right and
                node.bounds.get("bottom", 0) == bottom):
                return node
        
        return None
    
    async def refresh_node_cache(self):
        """Refresh the node cache"""
        self._node_cache = {}
        await self.get_all_nodes(refresh=True)
    
    # Action Methods
    
    async def perform_action(self, action: AccessibilityAction, 
                            node: AccessibilityNode = None,
                            **kwargs) -> ActionResult:
        """
        Perform an accessibility action
        
        Args:
            action: The action to perform
            node: The node to perform the action on (if applicable)
            **kwargs: Additional parameters for the action
            
        Returns:
            ActionResult
        """
        try:
            # Check service
            if not self._service_enabled:
                return ActionResult(
                    action=action,
                    success=False,
                    message="Accessibility service not enabled"
                )
            
            # Dispatch to specific handlers
            handler_map = {
                AccessibilityAction.CLICK: self._handle_click,
                AccessibilityAction.DOUBLE_CLICK: self._handle_double_click,
                AccessibilityAction.LONG_CLICK: self._handle_long_click,
                AccessibilityAction.SWIPE: self._handle_swipe,
                AccessibilityAction.SCROLL: self._handle_scroll,
                AccessibilityAction.TYPE: self._handle_type,
                AccessibilityAction.PASTE: self._handle_paste,
                AccessibilityAction.BACK: self._handle_back,
                AccessibilityAction.HOME: self._handle_home,
                AccessibilityAction.RECENTS: self._handle_recents,
                AccessibilityAction.MENU: self._handle_menu,
                AccessibilityAction.POWER: self._handle_power,
                AccessibilityAction.VOLUME_UP: self._handle_volume_up,
                AccessibilityAction.VOLUME_DOWN: self._handle_volume_down,
                AccessibilityAction.OPEN_APP: self._handle_open_app,
                AccessibilityAction.CLOSE_APP: self._handle_close_app,
                AccessibilityAction.SWITCH_APP: self._handle_switch_app,
                AccessibilityAction.TAKE_SCREENSHOT: self._handle_screenshot,
                AccessibilityAction.EXTRACT_TEXT: self._handle_extract_text,
                AccessibilityAction.GET_NODES: self._handle_get_nodes
            }
            
            handler = handler_map.get(action)
            if handler:
                result = await handler(node, **kwargs)
            else:
                result = ActionResult(
                    action=action,
                    success=False,
                    message=f"Action {action.name} not supported"
                )
            
            # Notify callbacks
            for callback in self._on_action_complete:
                try:
                    callback(result)
                except Exception as e:
                    self.error_handler.handle_error(e, "action_complete_callback")
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, f"perform_action_{action.name}")
            return ActionResult(
                action=action,
                success=False,
                message=str(e)
            )
    
    # Action Handlers
    
    async def _handle_click(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle click action"""
        if node:
            self.logger.info(f"Clicking node: {node.node_id} ({node.text})")
            # In a real implementation, this would perform the click
            return ActionResult(
                action=AccessibilityAction.CLICK,
                success=True,
                message=f"Clicked node: {node.text}",
                node=node
            )
        else:
            # Click at specific coordinates
            x = kwargs.get("x", self._screen_width // 2)
            y = kwargs.get("y", self._screen_height // 2)
            self.logger.info(f"Clicking at: ({x}, {y})")
            return ActionResult(
                action=AccessibilityAction.CLICK,
                success=True,
                message=f"Clicked at ({x}, {y})"
            )
    
    async def _handle_double_click(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle double click action"""
        if node:
            self.logger.info(f"Double clicking node: {node.node_id}")
            return ActionResult(
                action=AccessibilityAction.DOUBLE_CLICK,
                success=True,
                message=f"Double clicked node: {node.text}",
                node=node
            )
        else:
            x = kwargs.get("x", self._screen_width // 2)
            y = kwargs.get("y", self._screen_height // 2)
            return ActionResult(
                action=AccessibilityAction.DOUBLE_CLICK,
                success=True,
                message=f"Double clicked at ({x}, {y})"
            )
    
    async def _handle_long_click(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle long click action"""
        if node:
            self.logger.info(f"Long clicking node: {node.node_id}")
            return ActionResult(
                action=AccessibilityAction.LONG_CLICK,
                success=True,
                message=f"Long clicked node: {node.text}",
                node=node
            )
        else:
            x = kwargs.get("x", self._screen_width // 2)
            y = kwargs.get("y", self._screen_height // 2)
            return ActionResult(
                action=AccessibilityAction.LONG_CLICK,
                success=True,
                message=f"Long clicked at ({x}, {y})"
            )
    
    async def _handle_swipe(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle swipe action"""
        direction = kwargs.get("direction", SwipeDirection.RIGHT)
        duration = kwargs.get("duration", 300)  # ms
        
        # Calculate swipe coordinates
        if direction == SwipeDirection.UP:
            start = (self._screen_width // 2, self._screen_height - 100)
            end = (self._screen_width // 2, 100)
        elif direction == SwipeDirection.DOWN:
            start = (self._screen_width // 2, 100)
            end = (self._screen_width // 2, self._screen_height - 100)
        elif direction == SwipeDirection.LEFT:
            start = (self._screen_width - 100, self._screen_height // 2)
            end = (100, self._screen_height // 2)
        elif direction == SwipeDirection.RIGHT:
            start = (100, self._screen_height // 2)
            end = (self._screen_width - 100, self._screen_height // 2)
        else:
            start = (self._screen_width // 2, self._screen_height // 2)
            end = (self._screen_width // 2, self._screen_height // 2)
        
        self.logger.info(f"Swiping {direction.name} from {start} to {end}")
        
        return ActionResult(
            action=AccessibilityAction.SWIPE,
            success=True,
            message=f"Swiped {direction.name} in {duration}ms",
            data={"start": start, "end": end, "duration": duration}
        )
    
    async def _handle_scroll(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle scroll action"""
        direction = kwargs.get("direction", ScrollDirection.DOWN)
        amount = kwargs.get("amount", 100)  # pixels
        
        self.logger.info(f"Scrolling {direction.name} by {amount} pixels")
        
        return ActionResult(
            action=AccessibilityAction.SCROLL,
            success=True,
            message=f"Scrolled {direction.name} by {amount} pixels",
            data={"direction": direction.name, "amount": amount}
        )
    
    async def _handle_type(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle type action"""
        text = kwargs.get("text", "")
        
        if node:
            self.logger.info(f"Typing '{text}' into node: {node.node_id}")
        else:
            self.logger.info(f"Typing: {text}")
        
        return ActionResult(
            action=AccessibilityAction.TYPE,
            success=True,
            message=f"Typed: {text}",
            data={"text": text, "length": len(text)}
        )
    
    async def _handle_paste(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle paste action"""
        text = kwargs.get("text", "")
        
        if node:
            self.logger.info(f"Pasting '{text[:20]}...' into node: {node.node_id}")
        else:
            self.logger.info(f"Pasting: {text[:20]}...")
        
        return ActionResult(
            action=AccessibilityAction.PASTE,
            success=True,
            message=f"Pasted {len(text)} characters",
            data={"text": text, "length": len(text)}
        )
    
    async def _handle_back(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle back button press"""
        self.logger.info("Pressing back button")
        return ActionResult(
            action=AccessibilityAction.BACK,
            success=True,
            message="Back button pressed"
        )
    
    async def _handle_home(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle home button press"""
        self.logger.info("Pressing home button")
        return ActionResult(
            action=AccessibilityAction.HOME,
            success=True,
            message="Home button pressed"
        )
    
    async def _handle_recents(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle recents button press"""
        self.logger.info("Pressing recents button")
        return ActionResult(
            action=AccessibilityAction.RECENTS,
            success=True,
            message="Recents button pressed"
        )
    
    async def _handle_menu(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle menu button press"""
        self.logger.info("Pressing menu button")
        return ActionResult(
            action=AccessibilityAction.MENU,
            success=True,
            message="Menu button pressed"
        )
    
    async def _handle_power(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle power button press"""
        self.logger.info("Pressing power button")
        return ActionResult(
            action=AccessibilityAction.POWER,
            success=True,
            message="Power button pressed"
        )
    
    async def _handle_volume_up(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle volume up press"""
        self.logger.info("Pressing volume up")
        return ActionResult(
            action=AccessibilityAction.VOLUME_UP,
            success=True,
            message="Volume up pressed"
        )
    
    async def _handle_volume_down(self, node: AccessabilityNode = None, **kwargs) -> ActionResult:
        """Handle volume down press"""
        self.logger.info("Pressing volume down")
        return ActionResult(
            action=AccessibilityAction.VOLUME_DOWN,
            success=True,
            message="Volume down pressed"
        )
    
    async def _handle_open_app(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle open app action"""
        package_name = kwargs.get("package_name", "")
        
        if not package_name:
            return ActionResult(
                action=AccessibilityAction.OPEN_APP,
                success=False,
                message="No package name provided"
            )
        
        self.logger.info(f"Opening app: {package_name}")
        
        # In a real implementation, this would launch the app
        return ActionResult(
            action=AccessibilityAction.OPEN_APP,
            success=True,
            message=f"Opened app: {package_name}",
            data={"package_name": package_name}
        )
    
    async def _handle_close_app(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle close app action"""
        package_name = kwargs.get("package_name", "")
        
        if not package_name:
            # Close current app
            current_app = await self.get_foreground_app()
            package_name = current_app
        
        self.logger.info(f"Closing app: {package_name}")
        
        return ActionResult(
            action=AccessibilityAction.CLOSE_APP,
            success=True,
            message=f"Closed app: {package_name}",
            data={"package_name": package_name}
        )
    
    async def _handle_switch_app(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle switch app action"""
        package_name = kwargs.get("package_name", "")
        
        if package_name:
            self.logger.info(f"Switching to app: {package_name}")
        else:
            self.logger.info("Switching to previous app")
        
        return ActionResult(
            action=AccessibilityAction.SWITCH_APP,
            success=True,
            message=f"Switched to app: {package_name}" if package_name else "Switched to previous app",
            data={"package_name": package_name}
        )
    
    async def _handle_screenshot(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle screenshot action"""
        self.logger.info("Taking screenshot")
        
        # In a real implementation, this would capture the screen
        return ActionResult(
            action=AccessibilityAction.TAKE_SCREENSHOT,
            success=True,
            message="Screenshot captured",
            data={
                "screenshot_path": "/storage/emulated/0/Pictures/Screenshots/screenshot.png",
                "width": self._screen_width,
                "height": self._screen_height
            }
        )
    
    async def _handle_extract_text(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle text extraction action"""
        if node:
            self.logger.info(f"Extracting text from node: {node.node_id}")
            return ActionResult(
                action=AccessibilityAction.EXTRACT_TEXT,
                success=True,
                message=f"Extracted text: {node.text}",
                node=node,
                data={"text": node.text}
            )
        else:
            # Extract text from entire screen
            self.logger.info("Extracting text from screen")
            return ActionResult(
                action=AccessibilityAction.EXTRACT_TEXT,
                success=True,
                message="Extracted text from screen",
                data={"text": "Sample text extracted from screen"}
            )
    
    async def _handle_get_nodes(self, node: AccessibilityNode = None, **kwargs) -> ActionResult:
        """Handle get nodes action"""
        nodes = await self.get_all_nodes(refresh=True)
        
        return ActionResult(
            action=AccessibilityAction.GET_NODES,
            success=True,
            message=f"Retrieved {len(nodes)} nodes",
            data={"nodes": [n.to_dict() for n in nodes]}
        )
    
    # Convenience Methods
    
    async def click_text(self, text: str, exact: bool = False) -> ActionResult:
        """Click on text"""
        node = await self.find_node_by_text(text, exact)
        if node:
            return await self.perform_action(AccessibilityAction.CLICK, node)
        else:
            return ActionResult(
                action=AccessibilityAction.CLICK,
                success=False,
                message=f"Text '{text}' not found"
            )
    
    async def click_coordinates(self, x: int, y: int) -> ActionResult:
        """Click at specific coordinates"""
        return await self.perform_action(AccessibilityAction.CLICK, x=x, y=y)
    
    async def type_text(self, text: str) -> ActionResult:
        """Type text"""
        return await self.perform_action(AccessibilityAction.TYPE, text=text)
    
    async def swipe(self, direction: SwipeDirection, duration: int = 300) -> ActionResult:
        """Perform a swipe"""
        return await self.perform_action(AccessibilityAction.SWIPE, direction=direction, duration=duration)
    
    async def scroll(self, direction: ScrollDirection, amount: int = 100) -> ActionResult:
        """Perform a scroll"""
        return await self.perform_action(AccessibilityAction.SCROLL, direction=direction, amount=amount)
    
    async def open_app(self, package_name: str) -> ActionResult:
        """Open an app"""
        return await self.perform_action(AccessibilityAction.OPEN_APP, package_name=package_name)
    
    async def close_app(self, package_name: str = "") -> ActionResult:
        """Close an app"""
        return await self.perform_action(AccessibilityAction.CLOSE_APP, package_name=package_name)
    
    async def take_screenshot(self) -> ActionResult:
        """Take a screenshot"""
        return await self.perform_action(AccessibilityAction.TAKE_SCREENSHOT)
    
    async def extract_screen_text(self) -> ActionResult:
        """Extract text from screen"""
        return await self.perform_action(AccessibilityAction.EXTRACT_TEXT)
    
    async def press_back(self) -> ActionResult:
        """Press back button"""
        return await self.perform_action(AccessibilityAction.BACK)
    
    async def press_home(self) -> ActionResult:
        """Press home button"""
        return await self.perform_action(AccessibilityAction.HOME)
    
    async def press_recents(self) -> ActionResult:
        """Press recents button"""
        return await self.perform_action(AccessibilityAction.RECENTS)
    
    # Callback Registration
    
    def on_action_complete(self, callback: Callable[[ActionResult], None]):
        """Register action completion callback"""
        self._on_action_complete.append(callback)
    
    def on_service_state_change(self, callback: Callable[[bool], None]):
        """Register service state change callback"""
        self._on_service_state_change.append(callback)
    
    # Utility Methods
    
    def get_supported_actions(self) -> List[str]:
        """Get list of supported actions"""
        return [action.name for action in AccessibilityAction]
    
    def get_supported_apps(self) -> List[str]:
        """Get list of supported apps"""
        return self.config.allowed_apps if hasattr(self.config, 'allowed_apps') else []
    
    async def is_app_installed(self, package_name: str) -> bool:
        """Check if an app is installed"""
        return package_name in self.get_supported_apps()
    
    # Cleanup
    
    async def cleanup(self):
        """Clean up resources"""
        self._node_cache = {}
        self.logger.info("Accessibility Controller cleaned up")
