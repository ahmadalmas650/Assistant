#!/usr/bin/env python3
"""
JARVIS - Main Entry Point
Production-grade Android AI Assistant

This is the main entry point for the JARVIS AI Assistant.
It initializes the brain, starts the server, and handles all incoming requests.
"""

import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import configuration
from configs.config import Config
from brain.core.brain_engine import BrainEngine, BrainConfig, BrainState
from brain.utils.logger import Logger
from brain.utils.error_handler import ErrorHandler
from brain.utils.resource_monitor import ResourceMonitor
from brain.utils.cloud_sync import CloudSync
from brain.modules.input_processor import InputProcessor
from brain.modules.command_parser import CommandParser
from brain.modules.wake_word_detector import WakeWordDetector
from brain.modules.accessibility_controller import AccessibilityController
from brain.modules.screenshot_manager import ScreenshotManager
from brain.modules.ocr_engine import OCREngine
from brain.modules.app_integrator import AppIntegrator
from brain.modules.output_generator import OutputGenerator
from brain.learning.learning_manager import LearningManager
from brain.memory.memory_manager import MemoryManager
from brain.tasks.task_manager import TaskManager
from brain.tasks.preview_system import PreviewSystem
from brain.tasks.live_control_system import LiveControlSystem


class JARVIS:
    """
    Main JARVIS class - orchestrates all components
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize JARVIS"""
        self.logger = Logger("JARVIS", debug=config.debug_mode if config else False)
        self.error_handler = ErrorHandler(self.logger)
        
        # Load configuration
        self.config = config or Config()
        
        # Initialize components
        self.brain: Optional[BrainEngine] = None
        self.input_processor: Optional[InputProcessor] = None
        self.command_parser: Optional[CommandParser] = None
        self.wake_word_detector: Optional[WakeWordDetector] = None
        self.accessibility_controller: Optional[AccessibilityController] = None
        self.screenshot_manager: Optional[ScreenshotManager] = None
        self.ocr_engine: Optional[OCREngine] = None
        self.app_integrator: Optional[AppIntegrator] = None
        self.output_generator: Optional[OutputGenerator] = None
        self.learning_manager: Optional[LearningManager] = None
        self.memory_manager: Optional[MemoryManager] = None
        self.task_manager: Optional[TaskManager] = None
        self.preview_system: Optional[PreviewSystem] = None
        self.live_control_system: Optional[LiveControlSystem] = None
        self.cloud_sync: Optional[CloudSync] = None
        self.resource_monitor: Optional[ResourceMonitor] = None
        
        # State
        self.is_running = False
        self.start_time = 0.0
        self.last_command_time = 0.0
        self.command_count = 0
        
        # Event tracking
        self._shutdown_requested = False
        
        self.logger.info("JARVIS initialized")
    
    async def initialize(self):
        """Initialize all JARVIS components"""
        start_time = time.time()
        self.logger.info("Initializing JARVIS components...")
        
        try:
            # Initialize resource monitor
            self.resource_monitor = ResourceMonitor(
                max_memory=self.config.brain.max_memory_usage_gb,
                max_cpu=self.config.brain.max_cpu_usage
            )
            
            # Initialize memory manager
            self.memory_manager = MemoryManager(self.config, self.logger)
            await self.memory_manager.initialize()
            
            # Initialize cloud sync
            self.cloud_sync = CloudSync(self.config, self.logger)
            
            # Initialize brain
            brain_config = BrainConfig(
                name=self.config.app_name,
                wake_word=self.config.brain.wake_word,
                max_memory_usage=self.config.brain.max_memory_usage_gb,
                max_cpu_usage=self.config.brain.max_cpu_usage,
                min_confidence_threshold=self.config.brain.min_confidence_threshold,
                learning_enabled=self.config.brain.learning_enabled,
                cloud_sync_enabled=self.config.brain.cloud_sync_enabled,
                privacy_mode=self.config.brain.privacy_mode,
                debug_mode=self.config.brain.debug_mode,
                response_timeout=self.config.brain.response_timeout_seconds,
                task_timeout=self.config.brain.task_timeout_seconds,
                max_concurrent_tasks=self.config.brain.max_concurrent_tasks,
                allowed_apps=self.config.apps.allowed_apps
            )
            
            self.brain = BrainEngine(brain_config)
            await self.brain.initialize()
            
            # Initialize modules
            self.input_processor = InputProcessor(self.config, self.logger)
            self.command_parser = CommandParser(self.config, self.logger)
            self.wake_word_detector = WakeWordDetector(self.config, self.logger)
            self.accessibility_controller = AccessibilityController(self.config, self.logger)
            self.screenshot_manager = ScreenshotManager(self.config, self.logger)
            self.ocr_engine = OCREngine(self.config, self.logger)
            self.app_integrator = AppIntegrator(self.config, self.logger)
            self.output_generator = OutputGenerator(self.config, self.logger)
            
            # Initialize learning
            self.learning_manager = LearningManager(self.config, self.logger)
            await self.learning_manager.initialize()
            
            # Initialize tasks
            self.task_manager = TaskManager(self.config, self.logger)
            await self.task_manager.initialize()
            
            # Initialize preview system
            self.preview_system = PreviewSystem(self.config, self.logger)
            
            # Initialize live control system
            self.live_control_system = LiveControlSystem(self.config, self.logger)
            await self.live_control_system.initialize()
            
            # Setup signal handlers
            self._setup_signal_handlers()
            
            # Setup callbacks
            self._setup_callbacks()
            
            self.is_running = True
            self.start_time = time.time()
            
            init_time = time.time() - start_time
            self.logger.info(f"JARVIS initialized successfully in {init_time:.2f}s")
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "jarvis_initialize")
            self.logger.error(f"Failed to initialize JARVIS: {str(e)}")
            return False
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def handle_shutdown(signame):
            self.logger.info(f"Received shutdown signal: {signame}")
            self._shutdown_requested = True
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, lambda s, f: handle_shutdown("SIGINT"))
        signal.signal(signal.SIGTERM, lambda s, f: handle_shutdown("SIGTERM"))
        signal.signal(signal.SIGQUIT, lambda s, f: handle_shutdown("SIGQUIT"))
    
    def _setup_callbacks(self):
        """Setup event callbacks"""
        if self.brain:
            self.brain.on_state_change(self._handle_brain_state_change)
            self.brain.on_task_complete(self._handle_task_complete)
            self.brain.on_learning_update(self._handle_learning_update)
    
    def _handle_brain_state_change(self, old_state: BrainState, new_state: BrainState):
        """Handle brain state changes"""
        self.logger.debug(f"Brain state changed: {old_state.name} -> {new_state.name}")
    
    def _handle_task_complete(self, result: Dict):
        """Handle task completion"""
        self.command_count += 1
        self.last_command_time = time.time()
        self.logger.info(f"Task completed: {result.get('status', 'unknown')}")
    
    def _handle_learning_update(self, feedback: Dict):
        """Handle learning updates"""
        self.logger.info(f"Learning update: {feedback.get('type', 'unknown')}")
    
    async def process_command(self, command: str, input_type: str = "text") -> Dict:
        """
        Process a command
        
        Args:
            command: The command to process
            input_type: Type of input ('text' or 'voice')
            
        Returns:
            Dictionary with processing results
        """
        start_time = time.time()
        
        try:
            if not self.brain:
                return {"status": "error", "error": "Brain not initialized"}
            
            # Process through brain
            result = await self.brain.process_input(command, input_type)
            
            # Update statistics
            self.command_count += 1
            self.last_command_time = time.time()
            
            processing_time = time.time() - start_time
            self.logger.info(f"Command processed in {processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, "process_command")
            return {"status": "error", "error": str(e)}
    
    async def execute_direct(self, command: str) -> Dict:
        """
        Execute a command directly (bypasses wake word)
        
        Args:
            command: The command to execute
            
        Returns:
            Dictionary with execution results
        """
        if not self.brain:
            return {"status": "error", "error": "Brain not initialized"}
        
        return await self.brain.execute_command(command)
    
    async def get_preview(self, command: str) -> Dict:
        """
        Get preview for a command
        
        Args:
            command: The command to preview
            
        Returns:
            Dictionary with preview data
        """
        if not self.brain:
            return {"status": "error", "error": "Brain not initialized"}
        
        return await self.brain.get_preview(command)
    
    async def stop_current_task(self) -> bool:
        """Stop the currently executing task"""
        if not self.brain:
            return False
        return await self.brain.stop_current_task()
    
    async def modify_current_task(self, modification: str) -> bool:
        """Modify the currently executing task"""
        if not self.brain:
            return False
        return await self.brain.modify_current_task(modification)
    
    async def get_status(self) -> Dict:
        """Get current JARVIS status"""
        if not self.brain:
            return {"status": "not_initialized"}
        
        brain_status = await self.brain.get_status()
        
        return {
            "status": "running",
            "uptime": time.time() - self.start_time,
            "command_count": self.command_count,
            "last_command_time": self.last_command_time,
            "brain": brain_status,
            "resources": self.resource_monitor.get_status() if self.resource_monitor else {}
        }
    
    async def get_capabilities(self) -> List[str]:
        """Get list of available capabilities"""
        if not self.brain:
            return []
        return await self.brain.get_capabilities()
    
    async def learn_from_feedback(self, feedback: Dict) -> bool:
        """Learn from user feedback"""
        if not self.brain:
            return False
        return await self.brain.learn_from_feedback(feedback)
    
    async def get_knowledge(self, query: str) -> Dict:
        """Query the knowledge base"""
        if not self.brain:
            return {"status": "error", "error": "Brain not initialized"}
        return await self.brain.get_knowledge(query)
    
    async def sync_with_cloud(self) -> bool:
        """Sync knowledge with cloud storage"""
        if not self.brain:
            return False
        return await self.brain.sync_with_cloud()
    
    async def start_listening(self) -> bool:
        """Start listening for voice input"""
        if not self.input_processor:
            return False
        return await self.input_processor.start_listening()
    
    async def stop_listening(self) -> bool:
        """Stop listening for voice input"""
        if not self.input_processor:
            return False
        return await self.input_processor.stop_listening()
    
    async def shutdown(self):
        """Shutdown JARVIS gracefully"""
        if self._shutdown_requested:
            return
        
        self._shutdown_requested = True
        self.logger.info("Shutting down JARVIS...")
        
        try:
            # Stop listening
            if self.input_processor:
                await self.input_processor.stop_listening()
            
            # Stop current tasks
            if self.brain:
                await self.brain.shutdown()
            
            # Cleanup modules
            if self.task_manager:
                await self.task_manager.shutdown()
            
            if self.learning_manager:
                await self.learning_manager.save_state()
            
            if self.memory_manager:
                await self.memory_manager.cleanup_temp_data()
            
            if self.cloud_sync:
                await self.cloud_sync.sync()
            
            self.is_running = False
            
            uptime = time.time() - self.start_time
            self.logger.info(f"JARVIS shutdown complete. Uptime: {uptime:.2f}s, Commands: {self.command_count}")
            
        except Exception as e:
            self.error_handler.handle_error(e, "shutdown")
            self.logger.error(f"Error during shutdown: {str(e)}")
    
    async def run(self):
        """Main run loop"""
        if not await self.initialize():
            self.logger.error("Failed to initialize JARVIS")
            return
        
        self.logger.info("JARVIS is ready!")
        self.logger.info("Type 'help' for available commands")
        
        # Start interactive mode
        await self._run_interactive()
    
    async def _run_interactive(self):
        """Run in interactive mode"""
        self.logger.info("Starting interactive mode...")
        
        while not self._shutdown_requested:
            try:
                # Read input
                command = input("\n> ").strip()
                
                if not command:
                    continue
                
                # Handle special commands
                if command.lower() in ['exit', 'quit', 'stop']:
                    self._shutdown_requested = True
                    break
                
                elif command.lower() in ['help', '?']:
                    self._print_help()
                    continue
                
                elif command.lower() in ['status']:
                    status = await self.get_status()
                    print(json.dumps(status, indent=2))
                    continue
                
                elif command.lower() in ['capabilities']:
                    capabilities = await self.get_capabilities()
                    print("Available capabilities:")
                    for cap in capabilities:
                        print(f"  - {cap}")
                    continue
                
                elif command.lower() in ['clear']:
                    os.system('clear' if os.name == 'posix' else 'cls')
                    continue
                
                # Process command
                start_time = time.time()
                result = await self.process_command(command, "text")
                processing_time = time.time() - start_time
                
                # Display result
                if result.get("status") == "needs_input":
                    print(f"\nDecision: {result.get('decision', {}).get('action', 'unknown')}")
                    print("Preview:")
                    preview = result.get("preview", {})
                    print(json.dumps(preview, indent=2))
                    
                    # Ask for confirmation
                    while True:
                        choice = input("Execute? (y/n/edit): ").strip().lower()
                        if choice in ['y', 'yes']:
                            result = await self.execute_direct(command)
                            break
                        elif choice in ['n', 'no']:
                            print("Command cancelled")
                            break
                        elif choice.startswith('edit:'):
                            modification = choice[5:].strip()
                            result = await self.modify_current_task(modification)
                            if result:
                                print("Task modified")
                            else:
                                print("Failed to modify task")
                        else:
                            print("Invalid choice. Please enter y, n, or edit:...")
                
                elif result.get("status") == "preview":
                    print("\nPreview:")
                    print(json.dumps(result.get("plan", {}), indent=2))
                
                elif result.get("status") == "success":
                    print(f"\nSuccess! (Confidence: {result.get('confidence', 0):.2f}, Time: {processing_time:.2f}s)")
                    if result.get("result"):
                        print("Result:")
                        print(json.dumps(result.get("result"), indent=2))
                
                else:
                    print(f"\nError: {result.get('error', 'Unknown error')}")
                
            except KeyboardInterrupt:
                print("\nUse 'exit' to quit")
            except EOFError:
                self._shutdown_requested = True
                break
            except Exception as e:
                self.error_handler.handle_error(e, "interactive_loop")
                print(f"\nError: {str(e)}")
        
        # Shutdown
        await self.shutdown()
    
    def _print_help(self):
        """Print help information"""
        print("\n" + "=" * 60)
        print("JARVIS AI Assistant - Help")
        print("=" * 60)
        print("\nCommands:")
        print("  help, ?             - Show this help")
        print("  exit, quit, stop    - Exit JARVIS")
        print("  status             - Show current status")
        print("  capabilities       - Show available capabilities")
        print("  clear             - Clear screen")
        print("\nExample Commands:")
        print("  Jarvis, upload video to YouTube")
        print("  Jarvis, take a screenshot")
        print("  Jarvis, search for AI news")
        print("  Jarvis, edit this photo")
        print("  Upload this video")
        print("\nNote: Commands can be spoken or typed")
        print("=" * 60 + "\n")


async def main():
    """Main entry point"""
    print("\n" + "=" * 60)
    print("  JARVIS - Android AI Assistant")
    print("  Production-grade AI for Android")
    print("=" * 60 + "\n")
    
    # Load configuration
    config = Config()
    
    # Create JARVIS instance
    jarvis = JARVIS(config)
    
    try:
        # Run JARVIS
        await jarvis.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        await jarvis.shutdown()
    except Exception as e:
        print(f"\nFatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        await jarvis.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
