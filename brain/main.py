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
from configs import Config
from brain.core.brain_engine import BrainEngine, BrainConfig, BrainState
from brain.utils.logger import Logger
from brain.utils.error_handler import ErrorHandler
from brain.utils.resource_monitor import ResourceMonitor
from brain.utils.cloud_sync import CloudSync
from brain.modules.input_processor import InputProcessor
from brain.modules.command_parser import CommandParser
from brain.modules.wake_word_detector import WakeWordDetector
from brain.modules.accessibility_controller import AccessibilityController
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
        self._voice_sessions_enabled = False
        
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
            self.ocr_engine = OCREngine(self.config, self.accessibility_controller)
            self.app_integrator = AppIntegrator(self.config, self.logger)
            self.output_generator = OutputGenerator(self.config, self.logger)
            
            # Initialize learning
            self.learning_manager = LearningManager(self.config, self.logger)
            await self.learning_manager.initialize()
            
            # Wire real device components into the ExecutionController so
            # task steps run against the live device (no simulated results)
            if self.brain is not None:
                self.brain.execution_controller.set_device_context(
                    accessibility=self.accessibility_controller,
                    ocr_engine=self.ocr_engine,
                    search_provider=self._real_search
                )
            
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
    
    async def _real_search(self, query: str, sources=None) -> Dict:
        """Real search provider wired into the ExecutionController.
        
        Searches the local knowledge base and every requested real source
        through the multi-source learner. Results come only from real
        sources; nothing is fabricated.
        """
        if sources is None:
            sources = []
        if not isinstance(sources, list):
            sources = [sources]
        
        results: Dict = {}
        
        # Local knowledge base (real stored knowledge)
        try:
            kb_items = await self.learning_manager.query_knowledge(query, limit=10)
            results["knowledge_base"] = {
                "query": query,
                "results": [
                    item.to_dict() if hasattr(item, "to_dict") else dict(item)
                    for item in kb_items
                ]
            }
        except Exception as e:
            results["knowledge_base"] = {"query": query, "results": [], "error": str(e)}
        
        # Requested external sources via the real multi-source learner
        for source in sources:
            if source == "knowledge_base":
                continue
            try:
                learned = await self.learning_manager.learn_from_multiple_sources(
                    query, [source]
                )
                results[source] = learned.get(source, {
                    "query": query, "results": []
                })
            except Exception as e:
                results[source] = {"query": query, "results": [], "error": str(e)}
        
        return results
    
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
    
    # Hands-free voice session: wake word -> live command (mic stays on,
    # word-by-word preview) -> execute keyword -> mic off -> speak answer.
    
    async def start_voice_sessions(self) -> bool:
        """Enable hands-free wake-word voice sessions."""
        if not self.wake_word_detector or not self.input_processor:
            self.logger.warning("Voice modules unavailable; hands-free mode off")
            return False
        self._voice_sessions_enabled = True
        self.wake_word_detector.on_detection(self._on_wake_word_detected)
        self.wake_word_detector.start()
        self.logger.info(
            f"Hands-free voice sessions enabled (say '{self.wake_word_detector.get_wake_word()}')")
        return True
    
    def _on_wake_word_detected(self, detection):
        """Wake word heard (called from the detector thread)."""
        self.logger.info("Wake word detected; capturing command")
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            loop.call_soon_threadsafe(
                asyncio.ensure_future, self._capture_and_execute_command())
    
    async def _capture_and_execute_command(self):
        """Command phase: poll the live preview until the execute keyword."""
        try:
            processed = await self.input_processor.wait_for_command(timeout_s=90.0)
            command = (processed.text or "").strip()
            if not command:
                self.logger.info("Empty command; back to wake listening")
                return
            self.logger.info(f"Voice command: {command}")
            result = await self.process_command(command, "voice")
            response = self._extract_response_text(result)
            if response:
                # Streaming Urdu TTS: the first sentence starts at once.
                # speak_wait blocks until the APK finishes playing, so the
                # wake phase (microphone) restarts only AFTER the assistant
                # has stopped speaking, exactly as required.
                await self.output_generator.speak_wait(response, "ur-PK")
        except ValueError as e:
            self.logger.warning(f"Voice session ended: {e}")
        except Exception as e:
            self.error_handler.handle_error(e, "voice_command")
        finally:
            # Restart the wake phase for the next session
            if self._voice_sessions_enabled and not self._shutdown_requested:
                if self.wake_word_detector and not self.wake_word_detector.is_running():
                    self.wake_word_detector.start()
    
    def _extract_response_text(self, result: Dict) -> str:
        """Best-effort extraction of the spoken response from a result.

        The brain returns {"status", "result", ...} where result is the
        ExecutionResult dict; individual step outputs carry their own
        "response" strings. This walks every layer so the assistant
        always has something honest to speak.
        """
        if not isinstance(result, dict):
            return ""

        def _clean(value) -> str:
            return value.strip() if isinstance(value, str) else ""

        # Layer 1: top-level plain response keys
        for key in ("response", "message", "text", "final_output"):
            value = result.get(key)
            if _clean(value):
                return _clean(value)
            if isinstance(value, dict):
                for sub in ("response", "message", "text", "output"):
                    if _clean(value.get(sub)):
                        return _clean(value.get(sub))

        # Layer 2: nested execution result
        inner = result.get("result")
        if isinstance(inner, dict):
            for key in ("response", "message", "text", "final_output", "output"):
                if _clean(inner.get(key)):
                    return _clean(inner.get(key))
            # Layer 2b: attributes/summary inside the result payload
            payload = inner.get("result") if isinstance(inner.get("result"), dict) else None
            if payload:
                for key in ("response", "message", "text", "summary", "output"):
                    if _clean(payload.get(key)):
                        return _clean(payload.get(key))
            # Layer 2c: final_output of the execution (often the last
            # step's output dict, e.g. open_app's spoken response)
            final_output = inner.get("final_output")
            if isinstance(final_output, dict):
                for key in ("response", "message", "text", "summary", "output"):
                    if _clean(final_output.get(key)):
                        return _clean(final_output.get(key))

        # Layer 3: step outputs (open_app, search, present_results, ...)
        step_results = None
        if isinstance(inner, dict):
            step_results = inner.get("step_results")
        if not step_results and isinstance(result.get("step_results"), list):
            step_results = result.get("step_results")
        if isinstance(step_results, list):
            for step in reversed(step_results):
                if not isinstance(step, dict):
                    continue
                output = step.get("output")
                if isinstance(output, dict):
                    for key in ("response", "message", "text", "summary", "output"):
                        if _clean(output.get(key)):
                            return _clean(output.get(key))
                if _clean(step.get("response")):
                    return _clean(step.get("response"))
                if _clean(output):
                    return _clean(output)

        # Honest status-based fallbacks so the user always gets feedback
        status = str(result.get("status", "")).lower()
        if status == "success":
            return "Kaam mukammal ho gaya hai."
        if status == "needs_input":
            decision = result.get("decision")
            if isinstance(decision, dict):
                required = decision.get("required_info")
                if isinstance(required, list) and required:
                    return "Tasdeeq chahiye: " + "; ".join(str(r) for r in required)
                if _clean(decision.get("reason")):
                    return _clean(decision.get("reason"))
            return "Is kaam ke liye mazeed maloomat chahiye."
        if status == "rejected":
            decision = result.get("decision")
            if isinstance(decision, dict) and _clean(decision.get("reason")):
                return "Ye kaam manzur nahi: " + _clean(decision.get("reason"))
            return "Ye kaam manzur nahi hai."
        if status == "error":
            error = result.get("error")
            if _clean(error):
                return f"Masla paida hua: {_clean(error)}"
            return "Kaam mukammal nahi ho saka."
        if status == "ignored":
            return "Wake word nahi mila."
        return ""
    
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
                # Turn the microphone off and discard any open session
                await self.input_processor.cancel_session()
            
            # Stop wake word detection
            self._voice_sessions_enabled = False
            if self.wake_word_detector:
                self.wake_word_detector.stop()
            
            # Stop any ongoing speech
            if self.output_generator:
                await self.output_generator.stop_speaking()
            
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
        
        # Hands-free voice sessions (wake word -> command -> execute);
        # falls back to text-only if the bridge is unavailable.
        try:
            await self.start_voice_sessions()
        except Exception as e:
            self.logger.warning(f"Voice sessions unavailable: {e}")
        
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
        print("  Jarvis, read my screen")
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
