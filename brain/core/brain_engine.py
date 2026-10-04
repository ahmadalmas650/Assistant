"""
Brain Engine - Core Intelligence Controller
Handles all cognitive functions and coordinates between modules
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto

from ..utils.logger import Logger
from ..utils.resource_monitor import ResourceMonitor
from ..utils.error_handler import ErrorHandler
from ..modules.input_processor import InputProcessor
from ..modules.command_parser import CommandParser
from .decision_maker import DecisionMaker
from .confidence_engine import ConfidenceEngine
from .task_planner import TaskPlanner
from .execution_controller import ExecutionController
from ..memory.memory_manager import MemoryManager
from ..learning.learning_manager import LearningManager
from ..tasks.task_manager import TaskManager
from ..utils.privacy_guard import PrivacyGuard


class BrainState(Enum):
    """Current state of the brain"""
    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    EXECUTING = auto()
    LEARNING = auto()
    SLEEPING = auto()
    ERROR = auto()


class BrainMode(Enum):
    """Operating mode of the brain"""
    NORMAL = auto()
    FAST = auto()
    EFFICIENT = auto()
    LEARNING = auto()
    DEBUG = auto()


@dataclass
class BrainConfig:
    """Configuration for the brain engine"""
    name: str = "JARVIS"
    wake_word: str = "jarvis"
    max_memory_usage: float = 2.0  # GB
    max_cpu_usage: float = 0.8  # 80%
    min_confidence_threshold: float = 0.7
    learning_enabled: bool = True
    cloud_sync_enabled: bool = True
    privacy_mode: bool = True
    debug_mode: bool = False
    
    # Performance settings
    response_timeout: int = 30  # seconds
    task_timeout: int = 300  # seconds
    max_concurrent_tasks: int = 3
    
    # App integration
    allowed_apps: List[str] = field(default_factory=lambda: [
        "com.android.chrome",
        "com.google.android.youtube",
        "com.chatgpt",
        "com.deepseek",
        "com.grok",
        "com.kinemaster",
        "com.lexa.fakegapp",  # YouTube
        "org.telegram.messenger",
        "com.whatsapp"
    ])


@dataclass
class BrainContext:
    """Runtime context for the brain"""
    current_task: Optional[Dict] = None
    recent_commands: List[str] = field(default_factory=list)
    active_sources: List[str] = field(default_factory=list)
    learning_data: Dict = field(default_factory=dict)
    user_preferences: Dict = field(default_factory=dict)
    device_info: Dict = field(default_factory=dict)
    session_id: str = field(default_factory=lambda: str(time.time()))


class BrainEngine:
    """
    Main Brain Engine - Orchestrates all AI functions
    """
    
    def __init__(self, config: Optional[BrainConfig] = None):
        """Initialize the brain engine"""
        self.config = config or BrainConfig()
        self.context = BrainContext()
        self.state = BrainState.IDLE
        self.mode = BrainMode.NORMAL
        
        # Initialize all components
        self.logger = Logger("BrainEngine", debug=self.config.debug_mode)
        self.resource_monitor = ResourceMonitor(
            max_memory=self.config.max_memory_usage,
            max_cpu=self.config.max_cpu_usage
        )
        self.error_handler = ErrorHandler(self.logger)
        
        # Core modules
        self.input_processor = InputProcessor(self.config, self.logger)
        self.command_parser = CommandParser(self.config, self.logger)
        self.decision_maker = DecisionMaker(self.config, self.logger)
        self.confidence_engine = ConfidenceEngine(self.config, self.logger)
        self.task_planner = TaskPlanner(self.config, self.logger)
        self.execution_controller = ExecutionController(self.config, self.logger)
        
        # Memory and learning
        self.memory_manager = MemoryManager(self.config, self.logger)
        self.learning_manager = LearningManager(self.config, self.logger)
        self.task_manager = TaskManager(self.config, self.logger)
        
        # Security
        self.privacy_guard = PrivacyGuard(self.config, self.logger)
        
        # Event callbacks
        self._on_state_change: List[callable] = []
        self._on_task_complete: List[callable] = []
        self._on_learning_update: List[callable] = []
        
        self.logger.info("Brain Engine initialized successfully")
        self._start_monitoring()
    
    def _start_monitoring(self):
        """Start resource monitoring"""
        asyncio.create_task(self._monitor_loop())
    
    async def _monitor_loop(self):
        """Resource monitoring loop"""
        while True:
            await asyncio.sleep(5)
            resource_status = self.resource_monitor.get_status()
            if resource_status["memory_usage"] > self.config.max_memory_usage * 0.9:
                self.logger.warning(f"High memory usage: {resource_status['memory_usage']:.2f}GB")
                await self._handle_high_load()
    
    async def _handle_high_load(self):
        """Handle high resource usage"""
        # Switch to efficient mode
        old_mode = self.mode
        self.set_mode(BrainMode.EFFICIENT)
        self.logger.info("Switched to EFFICIENT mode due to high load")
        
        # Try to free resources
        await self.memory_manager.cleanup_temp_data()
        
        # Wait and restore mode
        await asyncio.sleep(30)
        self.set_mode(old_mode)
    
    def set_mode(self, mode: BrainMode):
        """Set operating mode"""
        self.mode = mode
        self.logger.info(f"Mode changed to {mode.name}")
    
    def set_state(self, state: BrainState):
        """Set current state"""
        old_state = self.state
        self.state = state
        self.logger.debug(f"State changed from {old_state.name} to {state.name}")
        
        # Notify listeners
        for callback in self._on_state_change:
            try:
                callback(old_state, state)
            except Exception as e:
                self.error_handler.handle_error(e, "state_change_callback")
    
    def on_state_change(self, callback: callable):
        """Register state change callback"""
        self._on_state_change.append(callback)
    
    def on_task_complete(self, callback: callable):
        """Register task completion callback"""
        self._on_task_complete.append(callback)
    
    def on_learning_update(self, callback: callable):
        """Register learning update callback"""
        self._on_learning_update.append(callback)
    
    async def process_input(self, input_data: str, input_type: str = "text") -> Dict:
        """
        Main input processing pipeline
        
        Args:
            input_data: The raw input (text or audio path)
            input_type: Type of input ('text' or 'voice')
            
        Returns:
            Dictionary with processing results
        """
        start_time = time.time()
        self.set_state(BrainState.PROCESSING)
        
        try:
            # Step 1: Process input
            self.logger.info(f"Processing {input_type} input: {input_data[:50]}...")
            processed_input = await self.input_processor.process(input_data, input_type)
            
            # Step 2: Check for wake word
            if not self._check_wake_word(processed_input.get("text", "")):
                self.set_state(BrainState.IDLE)
                return {"status": "ignored", "reason": "no_wake_word"}
            
            # Step 3: Parse command
            command_data = await self.command_parser.parse(processed_input["text"])
            
            if not command_data.get("valid", False):
                self.set_state(BrainState.IDLE)
                return {"status": "error", "error": "invalid_command"}
            
            # Step 4: Check privacy
            privacy_check = self.privacy_guard.check_input(command_data)
            if privacy_check.get("blocked", False):
                self.set_state(BrainState.IDLE)
                return {"status": "error", "error": "privacy_violation"}
            
            # Step 5: Plan task
            task_plan = await self.task_planner.plan(command_data)
            
            # Step 6: Get confidence
            confidence = self.confidence_engine.calculate_confidence(
                command_data, task_plan
            )
            
            # Step 7: Make decision
            decision = self.decision_maker.make_decision(
                command_data, task_plan, confidence
            )
            
            if decision.get("action", "") == "ask_user":
                self.set_state(BrainState.IDLE)
                return {
                    "status": "needs_input",
                    "decision": decision,
                    "preview": task_plan
                }
            
            # Step 8: Execute task
            self.set_state(BrainState.EXECUTING)
            execution_result = await self.execution_controller.execute(
                task_plan, confidence
            )
            
            # Step 9: Handle learning
            if self.config.learning_enabled:
                self.set_state(BrainState.LEARNING)
                await self.learning_manager.learn_from_execution(
                    command_data, task_plan, execution_result
                )
            
            # Step 10: Cleanup and return
            self.set_state(BrainState.IDLE)
            
            # Notify task completion
            for callback in self._on_task_complete:
                try:
                    callback(execution_result)
                except Exception as e:
                    self.error_handler.handle_error(e, "task_complete_callback")
            
            processing_time = time.time() - start_time
            self.logger.info(f"Input processed in {processing_time:.2f}s")
            
            return {
                "status": "success",
                "result": execution_result,
                "processing_time": processing_time,
                "confidence": confidence
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, "process_input")
            self.set_state(BrainState.ERROR)
            return {"status": "error", "error": str(e)}
    
    def _check_wake_word(self, text: str) -> bool:
        """Check if wake word is present"""
        text_lower = text.lower().strip()
        return (
            text_lower.startswith(self.config.wake_word) or
            f" {self.config.wake_word} " in text_lower or
            text_lower.endswith(self.config.wake_word)
        )
    
    async def execute_command(self, command: str, preview_only: bool = False) -> Dict:
        """
        Direct command execution (bypasses wake word check)
        
        Args:
            command: The command to execute
            preview_only: If True, only return preview without execution
            
        Returns:
            Dictionary with execution results
        """
        try:
            # Parse command
            command_data = await self.command_parser.parse(command)
            
            if not command_data.get("valid", False):
                return {"status": "error", "error": "invalid_command"}
            
            # Plan task
            task_plan = await self.task_planner.plan(command_data)
            
            if preview_only:
                return {
                    "status": "preview",
                    "plan": task_plan,
                    "command": command_data
                }
            
            # Calculate confidence
            confidence = self.confidence_engine.calculate_confidence(
                command_data, task_plan
            )
            
            # Execute
            execution_result = await self.execution_controller.execute(
                task_plan, confidence
            )
            
            # Learn from execution
            if self.config.learning_enabled:
                await self.learning_manager.learn_from_execution(
                    command_data, task_plan, execution_result
                )
            
            return {
                "status": "success",
                "result": execution_result,
                "confidence": confidence
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, "execute_command")
            return {"status": "error", "error": str(e)}
    
    async def get_preview(self, command: str) -> Dict:
        """Get preview for a command without execution"""
        return await self.execute_command(command, preview_only=True)
    
    async def stop_current_task(self) -> bool:
        """Stop the currently executing task"""
        try:
            await self.execution_controller.stop_current_task()
            self.set_state(BrainState.IDLE)
            return True
        except Exception as e:
            self.error_handler.handle_error(e, "stop_current_task")
            return False
    
    async def modify_current_task(self, modification: str) -> bool:
        """Modify the currently executing task"""
        try:
            await self.execution_controller.modify_current_task(modification)
            return True
        except Exception as e:
            self.error_handler.handle_error(e, "modify_current_task")
            return False
    
    async def get_status(self) -> Dict:
        """Get current brain status"""
        return {
            "state": self.state.name,
            "mode": self.mode.name,
            "current_task": self.context.current_task,
            "resource_usage": self.resource_monitor.get_status(),
            "recent_commands": self.context.recent_commands[-5:],
            "active_sources": self.context.active_sources,
            "uptime": time.time() - self._start_time if hasattr(self, '_start_time') else 0
        }
    
    async def initialize(self):
        """Initialize all components"""
        self._start_time = time.time()
        
        # Initialize memory
        await self.memory_manager.initialize()
        
        # Load preferences
        self.context.user_preferences = await self.memory_manager.load_preferences()
        
        # Initialize learning
        await self.learning_manager.initialize()
        
        # Initialize task manager
        await self.task_manager.initialize()
        
        # Get device info
        self.context.device_info = await self._get_device_info()
        
        self.logger.info("Brain Engine fully initialized")
    
    async def _get_device_info(self) -> Dict:
        """Get device information"""
        # This will be implemented with Android bridge
        return {
            "platform": "Android",
            "version": "15",
            "ram": "3GB",
            "storage": "36GB",
            "architecture": "ARM64"
        }
    
    async def shutdown(self):
        """Clean shutdown of all components"""
        self.logger.info("Shutting down Brain Engine...")
        
        try:
            await self.execution_controller.stop_all_tasks()
            await self.memory_manager.cleanup_temp_data()
            await self.learning_manager.save_state()
            await self.task_manager.shutdown()
            
            self.set_state(BrainState.SLEEPING)
            self.logger.info("Brain Engine shutdown complete")
            
        except Exception as e:
            self.error_handler.handle_error(e, "shutdown")
    
    async def learn_from_feedback(self, feedback: Dict) -> bool:
        """Learn from user feedback"""
        try:
            await self.learning_manager.learn_from_feedback(feedback)
            
            for callback in self._on_learning_update:
                try:
                    callback(feedback)
                except Exception as e:
                    self.error_handler.handle_error(e, "learning_callback")
            
            return True
        except Exception as e:
            self.error_handler.handle_error(e, "learn_from_feedback")
            return False
    
    async def get_knowledge(self, query: str) -> Dict:
        """Query the knowledge base"""
        try:
            return await self.memory_manager.query_knowledge(query)
        except Exception as e:
            self.error_handler.handle_error(e, "get_knowledge")
            return {"status": "error", "error": str(e)}
    
    async def sync_with_cloud(self) -> bool:
        """Sync knowledge with cloud storage"""
        try:
            if not self.config.cloud_sync_enabled:
                return False
            
            await self.memory_manager.sync_with_cloud()
            return True
        except Exception as e:
            self.error_handler.handle_error(e, "sync_with_cloud")
            return False
    
    def get_config(self) -> BrainConfig:
        """Get current configuration"""
        return self.config
    
    def update_config(self, **kwargs):
        """Update configuration"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                self.logger.info(f"Config updated: {key}={value}")
    
    async def get_capabilities(self) -> List[str]:
        """Get list of available capabilities"""
        return [
            "voice_input",
            "text_input",
            "wake_word_detection",
            "command_parsing",
            "task_planning",
            "task_execution",
            "confidence_calculation",
            "multi_source_learning",
            "knowledge_management",
            "privacy_protection",
            "cloud_sync",
            "accessibility_control",
            "read_screen",
            "live_text_extraction",
            "app_integration",
            "real_time_control",
            "background_processing",
            "resource_monitoring"
        ]
