"""
Execution Controller Module
Handles the actual execution of task plans
"""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum, auto
import traceback
import os

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler
from ..utils.resource_monitor import ResourceMonitor
from .task_planner import TaskPlan, TaskStep, StepStatus, TaskComplexity
from ..modules.input_processor import InputProcessor
from ..memory.memory_manager import MemoryManager


class ExecutionStatus(Enum):
    """Execution status"""
    PENDING = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class ExecutionMode(Enum):
    """Execution mode"""
    SEQUENTIAL = auto()
    PARALLEL = auto()
    HYBRID = auto()


@dataclass
class ExecutionResult:
    """Result of a task execution"""
    status: ExecutionStatus
    plan_id: str
    step_results: List[Dict] = field(default_factory=list)
    final_output: Optional[Any] = None
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    execution_time: float = 0.0
    resource_usage: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "status": self.status.name,
            "plan_id": self.plan_id,
            "step_results": self.step_results,
            "final_output": self.final_output,
            "error": self.error,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "execution_time": self.execution_time,
            "resource_usage": self.resource_usage,
            "metadata": self.metadata
        }


@dataclass
class StepExecutionResult:
    """Result of a single step execution"""
    step_id: str
    status: StepStatus
    output: Optional[Any] = None
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    retry_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "step_id": self.step_id,
            "status": self.status.name,
            "output": self.output,
            "error": self.error,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "retry_count": self.retry_count
        }


class ExecutionController:
    """
    Controls the execution of task plans
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        self.resource_monitor = ResourceMonitor(
            max_memory=config.max_memory_usage,
            max_cpu=config.max_cpu_usage
        )
        
        # Execution state
        self._current_execution: Optional[Dict] = None
        self._execution_queue: List[TaskPlan] = []
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._execution_lock = asyncio.Lock()
        self._pause_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._modification_request: Optional[str] = None
        
        # Device context (wired from main.py; handlers stay honest and
        # fail loudly when a required component is not wired)
        self._accessibility = None
        self._ocr_engine = None
        self._search_provider = None
        
        # Step handlers
        self._step_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()
        
        # Callbacks
        self._on_step_complete: List[Callable] = []
        self._on_execution_start: List[Callable] = []
        self._on_execution_complete: List[Callable] = []
    
    def _register_default_handlers(self):
        """Register default step handlers"""
        # Basic handlers
        self.register_handler("select_file", self._handle_select_file)
        self.register_handler("check_metadata", self._handle_check_metadata)
        self.register_handler("edit_if_needed", self._handle_edit_if_needed)
        self.register_handler("create_thumbnail", self._handle_create_thumbnail)
        self.register_handler("upload", self._handle_upload)
        self.register_handler("verify_upload", self._handle_verify_upload)
        self.register_handler("open_editor", self._handle_open_editor)
        self.register_handler("apply_edits", self._handle_apply_edits)
        self.register_handler("save_file", self._handle_save_file)
        self.register_handler("extract_query", self._handle_extract_query)
        self.register_handler("search", self._handle_search)
        self.register_handler("merge_results", self._handle_merge_results)
        self.register_handler("present_results", self._handle_present_results)
        self.register_handler("capture_screen", self._handle_capture_screen)
        self.register_handler("save_screenshot", self._handle_save_screenshot)
        self.register_handler("run_ocr", self._handle_run_ocr)
        self.register_handler("return_text", self._handle_return_text)
        
        # Generic fallback
        self.register_handler("*", self._handle_generic_step)
    
    def register_handler(self, action: str, handler: Callable):
        """Register a step handler"""
        self._step_handlers[action] = handler
        self.logger.debug(f"Registered handler for action: {action}")
    
    def set_device_context(self, accessibility=None, ocr_engine=None,
                           search_provider=None):
        """Wire real device components used by the default step handlers.
        
        Args:
            accessibility: AccessibilityController instance (live bridge)
            ocr_engine: OCREngine instance (live accessibility tree OCR)
            search_provider: async callable(query, sources) -> Dict that
                performs a real search and returns real results.
        """
        self._accessibility = accessibility
        self._ocr_engine = ocr_engine
        self._search_provider = search_provider
        self.logger.info("Device context wired into ExecutionController")
    
    async def execute(self, plan: TaskPlan, confidence: float = 1.0) -> ExecutionResult:
        """
        Execute a task plan
        
        Args:
            plan: The task plan to execute
            confidence: Confidence level for this execution
            
        Returns:
            ExecutionResult
        """
        async with self._execution_lock:
            # Check if we can start new execution
            if self._current_execution and self._current_execution["status"] == ExecutionStatus.RUNNING:
                if not self.config.max_concurrent_tasks or \
                   len(self._active_tasks) >= self.config.max_concurrent_tasks:
                    self.logger.info("Queueing execution - max concurrent tasks reached")
                    self._execution_queue.append(plan)
                    return ExecutionResult(
                        status=ExecutionStatus.PENDING,
                        plan_id=plan.id,
                        metadata={"message": "Queued for execution"}
                    )
            
            # Start execution
            return await self._start_execution(plan, confidence)
    
    async def _start_execution(self, plan: TaskPlan, confidence: float) -> ExecutionResult:
        """Start execution of a task plan"""
        execution_id = str(uuid.uuid4())
        start_time = time.time()
        
        self._current_execution = {
            "id": execution_id,
            "plan": plan,
            "status": ExecutionStatus.RUNNING,
            "start_time": start_time,
            "confidence": confidence,
            "step_results": [],
            "resource_usage": {}
        }
        
        self._stop_event.clear()
        self._pause_event.clear()
        self._modification_request = None
        
        self.logger.info(f"Starting execution of plan: {plan.id}")
        
        # Notify start
        for callback in self._on_execution_start:
            try:
                callback(plan)
            except Exception as e:
                self.error_handler.handle_error(e, "execution_start_callback")
        
        try:
            # Execute steps
            step_results = []
            
            # Determine execution mode
            mode = self._determine_execution_mode(plan)
            
            if mode == ExecutionMode.PARALLEL:
                step_results = await self._execute_parallel(plan)
            elif mode == ExecutionMode.HYBRID:
                step_results = await self._execute_hybrid(plan)
            else:
                step_results = await self._execute_sequential(plan)
            
            # Check if execution was stopped
            if self._stop_event.is_set():
                end_time = time.time()
                self.logger.info(f"Execution stopped: {plan.id}")
                
                return ExecutionResult(
                    status=ExecutionStatus.CANCELLED,
                    plan_id=plan.id,
                    step_results=[sr.to_dict() for sr in step_results],
                    start_time=start_time,
                    end_time=end_time,
                    execution_time=end_time - start_time,
                    resource_usage=self.resource_monitor.get_status(),
                    metadata={"stopped": True}
                )
            
            # Check for modification request
            if self._modification_request:
                # Handle modification
                modified_plan = await self._apply_modification(plan, self._modification_request)
                self._modification_request = None
                
                # Re-execute with modified plan
                self.logger.info(f"Re-executing with modification: {plan.id}")
                return await self._start_execution(modified_plan, confidence)
            
            # All steps completed successfully
            end_time = time.time()
            final_output = self._get_final_output(plan, step_results)
            
            self.logger.info(f"Execution completed: {plan.id}")
            
            # Notify completion
            for callback in self._on_execution_complete:
                try:
                    callback(self._current_execution)
                except Exception as e:
                    self.error_handler.handle_error(e, "execution_complete_callback")
            
            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                plan_id=plan.id,
                step_results=[sr.to_dict() for sr in step_results],
                final_output=final_output,
                start_time=start_time,
                end_time=end_time,
                execution_time=end_time - start_time,
                resource_usage=self.resource_monitor.get_status(),
                metadata={"confidence": confidence}
            )
            
        except Exception as e:
            end_time = time.time()
            self.logger.error(f"Execution failed: {plan.id} - {str(e)}")
            self.error_handler.handle_error(e, f"execution_{plan.id}")
            
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                plan_id=plan.id,
                error=str(e),
                start_time=start_time,
                end_time=end_time,
                execution_time=end_time - start_time,
                resource_usage=self.resource_monitor.get_status()
            )
        finally:
            self._current_execution = None
            self._stop_event.clear()
            self._modification_request = None
    
    def _determine_execution_mode(self, plan: TaskPlan) -> ExecutionMode:
        """Determine execution mode based on plan complexity"""
        if plan.complexity.value >= TaskComplexity.HIGH.value:
            return ExecutionMode.SEQUENTIAL
        elif plan.complexity == TaskComplexity.MEDIUM:
            return ExecutionMode.HYBRID
        else:
            return ExecutionMode.PARALLEL
    
    async def _execute_sequential(self, plan: TaskPlan) -> List[StepExecutionResult]:
        """Execute steps sequentially"""
        step_results = []
        step_map = {s.id: s for s in plan.steps}
        completed_steps = set()
        
        for step in plan.steps:
            # Check dependencies
            deps_met = all(dep in completed_steps for dep in step.dependencies)
            if not deps_met:
                # Skip this step for now, will be handled in next iteration
                continue
            
            # Check if paused
            if self._pause_event.is_set():
                await self._pause_event.wait()
                if self._stop_event.is_set():
                    break
            
            # Execute step
            result = await self._execute_step(step, step_map)
            step_results.append(result)
            
            if result.status == StepStatus.COMPLETED:
                completed_steps.add(step.id)
            elif result.status == StepStatus.FAILED:
                # Real retry logic: retry up to step.retry_count times
                max_retries = int(getattr(step, "retry_count", 0) or 0)
                attempt = 0
                while attempt < max_retries and not self._stop_event.is_set():
                    attempt += 1
                    self.logger.warning(
                        f"Step {step.id} failed, retrying "
                        f"({attempt}/{max_retries}): {step.error}"
                    )
                    await asyncio.sleep(min(2.0 ** attempt, 8.0))
                    result = await self._execute_step(step, step_map)
                    step_results.append(result)
                    if result.status == StepStatus.COMPLETED:
                        break
                
                if result.status == StepStatus.COMPLETED:
                    completed_steps.add(step.id)
                else:
                    break
            
            # Check for stop
            if self._stop_event.is_set():
                break
        
        return step_results
    
    async def _execute_parallel(self, plan: TaskPlan) -> List[StepExecutionResult]:
        """Execute steps (sequentially; parallel scheduling is disabled on
        this low-memory device to keep resource usage bounded)."""
        return await self._execute_sequential(plan)
    
    async def _execute_hybrid(self, plan: TaskPlan) -> List[StepExecutionResult]:
        """Execute steps in hybrid mode"""
        # This is a simplified implementation
        return await self._execute_sequential(plan)
    
    async def _execute_step(self, step: TaskStep, step_map: Dict) -> StepExecutionResult:
        """Execute a single step"""
        start_time = time.time()
        
        self.logger.debug(f"Executing step: {step.id} ({step.action})")
        
        # Update step status
        step.status = StepStatus.RUNNING
        
        try:
            # Get handler
            handler = self._get_handler(step.action)
            
            # Execute handler
            output = await self._call_handler(handler, step, step_map)
            
            end_time = time.time()
            
            # Update step status
            step.status = StepStatus.COMPLETED
            step.result = output
            
            result = StepExecutionResult(
                step_id=step.id,
                status=StepStatus.COMPLETED,
                output=output,
                start_time=start_time,
                end_time=end_time
            )
            
            # Notify step completion
            for callback in self._on_step_complete:
                try:
                    callback(step, result)
                except Exception as e:
                    self.error_handler.handle_error(e, "step_complete_callback")
            
            return result
            
        except Exception as e:
            end_time = time.time()
            
            # Update step status
            step.status = StepStatus.FAILED
            step.error = str(e)
            
            self.logger.error(f"Step failed: {step.id} - {str(e)}")
            self.error_handler.handle_error(e, f"step_{step.id}")
            
            result = StepExecutionResult(
                step_id=step.id,
                status=StepStatus.FAILED,
                error=str(e),
                start_time=start_time,
                end_time=end_time
            )
            
            return result
    
    def _get_handler(self, action: str) -> Callable:
        """Get handler for an action"""
        if action in self._step_handlers:
            return self._step_handlers[action]
        elif "*" in self._step_handlers:
            return self._step_handlers["*"]
        else:
            return self._handle_generic_step
    
    async def _call_handler(self, handler: Callable, step: TaskStep, step_map: Dict) -> Any:
        """Call a step handler"""
        # Check if handler is async
        if asyncio.iscoroutinefunction(handler):
            return await handler(step, step_map)
        else:
            return handler(step, step_map)
    
    # Default Step Handlers
    
    def _dep_result(self, step: TaskStep, step_map: Dict, *keys: str) -> Optional[Dict]:
        """Return the first dependency result containing one of the given keys."""
        for dep_id in step.dependencies:
            dep_step = step_map.get(dep_id)
            if dep_step and isinstance(dep_step.result, dict):
                for key in keys:
                    if dep_step.result.get(key) is not None:
                        return dep_step.result
        return None
    
    async def _handle_select_file(self, step: TaskStep, step_map: Dict) -> Dict:
        """Handle file selection (real: verifies the provided file exists)."""
        file_type = step.parameters.get("file_type", "unknown")
        file_path = step.parameters.get("file_path")
        
        if not file_path:
            raise ValueError(
                "select_file requires a 'file_path' parameter; none was provided"
            )
        
        if os.path.isfile(str(file_path)):
            self.logger.info(f"Selected existing file: {file_path}")
            return {
                "action": "select_file",
                "file_type": file_type,
                "file_path": file_path,
                "status": "selected"
            }
        
        raise FileNotFoundError(f"File not found on device: {file_path}")
    
    async def _handle_check_metadata(self, step: TaskStep, step_map: Dict) -> Dict:
        """Handle metadata checking against real metadata only."""
        check_items = step.parameters.get("check", [])
        if not isinstance(check_items, list):
            check_items = [check_items]
        
        dep_result = self._dep_result(step, step_map, "metadata")
        metadata = (dep_result or {}).get("metadata")
        if not isinstance(metadata, dict):
            metadata = step.parameters.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        
        if not metadata:
            return {
                "action": "check_metadata",
                "checked": check_items,
                "missing": [],
                "present": [],
                "status": "no_metadata_available",
                "message": "No real metadata was provided for this file"
            }
        
        missing = [item for item in check_items if not metadata.get(item)]
        present = [item for item in check_items if metadata.get(item)]
        
        return {
            "action": "check_metadata",
            "checked": check_items,
            "missing": missing,
            "present": present,
            "status": "checked"
        }
    
    async def _handle_edit_if_needed(self, step: TaskStep, step_map: Dict) -> Dict:
        """Handle conditional editing based on the real metadata check."""
        metadata_result = self._dep_result(step, step_map, "missing")
        
        if metadata_result and metadata_result.get("missing"):
            self.logger.info("Editing required - missing metadata")
            return {
                "action": "edit_if_needed",
                "editing_required": True,
                "missing_items": metadata_result["missing"],
                "app": step.parameters.get("app", "")
            }
        
        return {
            "action": "edit_if_needed",
            "editing_required": False
        }
    
    async def _handle_create_thumbnail(self, step: TaskStep, step_map: Dict) -> Dict:
        """Handle thumbnail creation (honest: no image tool on device)."""
        dep_result = self._dep_result(step, step_map, "file_path")
        file_path = (dep_result or {}).get("file_path")
        
        raise RuntimeError(
            "create_thumbnail is not available: no image-processing tool is "
            "installed on this device. Install one (for example Termux "
            "imagemagick) before planning thumbnail steps."
        )
    
    async def _handle_upload(self, step: TaskStep, step_map: Dict) -> Dict:
        """Handle file upload (honest: no platform credentials configured)."""
        platform = step.parameters.get("platform", "youtube")
        dep_result = self._dep_result(step, step_map, "file_path")
        file_path = (dep_result or {}).get("file_path")
        
        raise RuntimeError(
            f"upload to {platform} is not available: no {platform} account "
            f"credentials are configured on this device. Sign in manually "
            f"once and configure the account before planning upload steps."
        )
    
    async def _handle_verify_upload(self, step: TaskStep, step_map: Dict) -> Dict:
        """Handle upload verification against the real prior result only."""
        dep_result = self._dep_result(step, step_map, "upload_id")
        
        if not dep_result:
            raise ValueError(
                "verify_upload has no prior upload result to verify"
            )
        
        status = dep_result.get("status", "unknown")
        return {
            "action": "verify_upload",
            "upload_id": dep_result.get("upload_id"),
            "status": status,
            "url": dep_result.get("url"),
            "success": status in ("completed", "uploaded")
        }
    
    async def _handle_open_editor(self, step: TaskStep, step_map: Dict) -> Dict:
        """Handle opening an editor app (real, human-style launch via bridge)."""
        app = step.parameters.get("app")
        if not app:
            raise ValueError("open_editor requires an 'app' parameter")
        
        dep_result = self._dep_result(step, step_map, "file_path")
        file_path = (dep_result or {}).get("file_path")
        
        if self._accessibility is None:
            raise RuntimeError(
                "open_editor is not available: the accessibility controller "
                "is not wired into the ExecutionController"
            )
        
        bridge = getattr(self._accessibility, "bridge", None)
        launch_data: Optional[Dict] = None
        
        if bridge is not None and hasattr(bridge, "launch_app_by_name"):
            launch_data = await bridge.launch_app_by_name(str(app))
        
        if not (isinstance(launch_data, dict) and launch_data.get("ok")):
            raise RuntimeError(
                f"Could not launch '{app}' via the launcher search; it may "
                f"not be installed or the launcher search was unavailable"
            )
        
        self.logger.info(f"Launched {app} (package: {launch_data.get('package')})")
        return {
            "action": "open_editor",
            "app": app,
            "package": launch_data.get("package"),
            "file_path": file_path,
            "status": "opened"
        }
    
    async def _handle_apply_edits(self, step: TaskStep, step_map: Dict) -> Dict:
        """Handle applying edits (honest: no editing pipeline on device)."""
        raise RuntimeError(
            "apply_edits is not available: no real editing pipeline is "
            "installed on this device. Drive the target editor app through "
            "accessibility actions instead."
        )
    
    async def _handle_save_file(self, step: TaskStep, step_map: Dict) -> Dict:
        """Handle saving a file (honest: no editing pipeline on device)."""
        raise RuntimeError(
            "save_file is not available: no real editing pipeline is "
            "installed on this device. Drive the target editor app's save "
            "button through accessibility actions instead."
        )
    
    async def _handle_extract_query(self, step: TaskStep, step_map: Dict) -> Dict:
        """Handle query extraction from the real step parameters."""
        query = step.parameters.get("query")
        
        if not query or not str(query).strip():
            raise ValueError(
                "extract_query requires a 'query' parameter; none was provided"
            )
        
        self.logger.info(f"Extracted query: {query}")
        return {
            "action": "extract_query",
            "query": str(query).strip(),
            "status": "extracted"
        }
    
    async def _handle_search(self, step: TaskStep, step_map: Dict) -> Dict:
        """Handle searching through the real configured search provider."""
        sources = step.parameters.get("sources", [])
        if not isinstance(sources, list):
            sources = [sources]
        
        dep_result = self._dep_result(step, step_map, "query")
        query = (dep_result or {}).get("query") or step.parameters.get("query")
        
        if not query or not str(query).strip():
            raise ValueError("search requires a query; none was provided")
        
        if self._search_provider is None:
            raise RuntimeError(
                "search is not available: no search provider is wired into "
                "the ExecutionController"
            )
        
        query = str(query).strip()
        self.logger.info(f"Searching '{query}' in {sources}")
        results = await self._search_provider(query, sources)
        
        return {
            "action": "search",
            "query": query,
            "sources": sources,
            "results": results,
            "status": "completed"
        }
    
    async def _handle_merge_results(self, step: TaskStep, step_map: Dict) -> Dict:
        """Merge real result sets coming from dependency steps."""
        search_results = []
        for dep_id in step.dependencies:
            dep_step = step_map.get(dep_id)
            if dep_step and isinstance(dep_step.result, dict):
                search_results.append(dep_step.result)
        
        self.logger.info(f"Merging {len(search_results)} result sets")
        
        all_results = []
        for result in search_results:
            if not isinstance(result, dict):
                continue
            inner = result.get("results")
            if isinstance(inner, dict):
                for data in inner.values():
                    if isinstance(data, dict) and isinstance(data.get("results"), list):
                        all_results.extend(data["results"])
            elif isinstance(inner, list):
                all_results.extend(inner)
        
        unique_results = []
        seen = set()
        for r in all_results:
            if not isinstance(r, dict):
                continue
            title = r.get("title", "")
            if title not in seen:
                seen.add(title)
                unique_results.append(r)
        
        return {
            "action": "merge_results",
            "merged_results": unique_results,
            "source_count": len(search_results),
            "total_results": len(unique_results),
            "status": "merged"
        }
    
    async def _handle_present_results(self, step: TaskStep, step_map: Dict) -> Dict:
        """Present the real merged results from dependency steps."""
        dep_result = self._dep_result(step, step_map, "merged_results")
        
        if dep_result:
            results = dep_result.get("merged_results", [])
            self.logger.info(f"Presenting {len(results)} results")
            return {
                "action": "present_results",
                "results": results,
                "count": len(results),
                "status": "presented"
            }
        
        return {"action": "present_results", "status": "no_results"}
    
    async def _handle_capture_screen(self, step: TaskStep, step_map: Dict) -> Dict:
        """Capture the live on-screen text (real, via the accessibility bridge)."""
        if self._accessibility is None:
            raise RuntimeError(
                "capture_screen is not available: the accessibility "
                "controller is not wired into the ExecutionController"
            )
        
        action_result = await self._accessibility.extract_screen_text()
        
        if not getattr(action_result, "success", False):
            raise RuntimeError(
                f"Live screen read failed: {getattr(action_result, 'message', 'unknown error')}"
            )
        
        data = getattr(action_result, "data", None)
        text = ""
        if isinstance(data, dict):
            text = str(data.get("text", ""))
        elif isinstance(data, str):
            text = data
        
        if not text:
            raise RuntimeError(
                "The current screen exposes no readable text nodes"
            )
        
        return {
            "action": "capture_screen",
            "screen_text": text,
            "status": "captured"
        }
    
    async def _handle_save_screenshot(self, step: TaskStep, step_map: Dict) -> Dict:
        """Handle saving a screenshot (honest: image capture not supported)."""
        raise RuntimeError(
            "save_screenshot is not available: the Bridge APK does not "
            "capture screen images. Use capture_screen for live screen "
            "text instead."
        )
    
    async def _handle_run_ocr(self, step: TaskStep, step_map: Dict) -> Dict:
        """Run real live screen OCR through the accessibility tree."""
        if self._ocr_engine is None:
            raise RuntimeError(
                "run_ocr is not available: the OCR engine is not wired "
                "into the ExecutionController"
            )
        
        ocr_result = await self._ocr_engine.extract_text_from_screen()
        
        if not ocr_result.ok:
            raise RuntimeError(
                f"Live screen OCR failed: {getattr(ocr_result, 'error', 'unknown error')}"
            )
        
        text = str(getattr(ocr_result, "text", ""))
        return {
            "action": "run_ocr",
            "text": text,
            "language": "live-screen",
            "confidence": float(getattr(ocr_result, "confidence", 0.0)),
            "processing_time": float(getattr(ocr_result, "processing_time", 0.0)),
            "status": "completed"
        }
    
    async def _handle_return_text(self, step: TaskStep, step_map: Dict) -> Dict:
        """Return the real text produced by a dependency step."""
        dep_result = self._dep_result(step, step_map, "text", "screen_text")
        
        if dep_result:
            text = str(dep_result.get("text") or dep_result.get("screen_text") or "")
            if text:
                return {
                    "action": "return_text",
                    "text": text,
                    "source": dep_result.get("action", "dependency"),
                    "status": "returned"
                }
        
        raise ValueError("return_text found no text in any dependency step")
    
    async def _handle_generic_step(self, step: TaskStep, step_map: Dict) -> Dict:
        """Generic handler for unknown steps (honest, never simulated)."""
        self.logger.warning(f"No specific handler for action: {step.action}")
        
        return {
            "action": step.action,
            "status": "not_implemented",
            "message": f"Action '{step.action}' has no real implementation yet"
        }
    
    # Control Methods
    
    async def stop_current_task(self) -> bool:
        """Stop the currently executing task"""
        if self._current_execution:
            self._stop_event.set()
            self.logger.info("Stop signal sent to current execution")
            return True
        return False
    
    async def pause_current_task(self) -> bool:
        """Pause the currently executing task"""
        if self._current_execution:
            self._pause_event.set()
            self.logger.info("Pause signal sent to current execution")
            return True
        return False
    
    async def resume_current_task(self) -> bool:
        """Resume the paused task"""
        if self._current_execution:
            self._pause_event.clear()
            self.logger.info("Resume signal sent to current execution")
            return True
        return False
    
    async def modify_current_task(self, modification: str) -> bool:
        """Request modification of current task"""
        if self._current_execution:
            self._modification_request = modification
            self.logger.info(f"Modification requested: {modification}")
            return True
        return False
    
    async def _apply_modification(self, original_plan: TaskPlan, modification: str) -> TaskPlan:
        """Apply a modification request to a running plan.
        
        The modification text is recorded on the plan metadata so later
        processing can react to it. No step is silently changed: if the
        modification cannot be mapped to concrete steps, the original
        plan keeps running unchanged and the request stays visible.
        """
        self.logger.info(f"Applying modification: {modification}")
        
        try:
            metadata = getattr(original_plan, "metadata", None)
            if isinstance(metadata, dict):
                requests = metadata.setdefault("modification_requests", [])
                if isinstance(requests, list):
                    requests.append({
                        "text": modification,
                        "timestamp": time.time()
                    })
            else:
                self.logger.warning(
                    "Plan has no metadata dict; modification recorded in log only"
                )
        except Exception as e:
            self.error_handler.handle_error(e, "apply_modification")
        
        return original_plan
    
    def _get_final_output(self, plan: TaskPlan, step_results: List[StepExecutionResult]) -> Any:
        """Get the final output from step results"""
        if not step_results:
            return None
        
        # Return the last successful step's output
        for result in reversed(step_results):
            if result.status == StepStatus.COMPLETED:
                return result.output
        
        return None
    
    async def stop_all_tasks(self) -> int:
        """Stop all active tasks"""
        count = 0
        
        # Stop current execution
        if self._current_execution:
            self._stop_event.set()
            count += 1
        
        # Cancel queued tasks
        self._execution_queue = []
        
        # Cancel active tasks
        for task_id, task in self._active_tasks.items():
            if not task.done():
                task.cancel()
                count += 1
        
        self._active_tasks = {}
        
        self.logger.info(f"Stopped {count} tasks")
        return count
    
    # Callback Registration
    
    def on_step_complete(self, callback: Callable):
        """Register step completion callback"""
        self._on_step_complete.append(callback)
    
    def on_execution_start(self, callback: Callable):
        """Register execution start callback"""
        self._on_execution_start.append(callback)
    
    def on_execution_complete(self, callback: Callable):
        """Register execution complete callback"""
        self._on_execution_complete.append(callback)
    
    # Utility Methods
    
    def get_current_execution(self) -> Optional[Dict]:
        """Get current execution status"""
        return self._current_execution
    
    def get_queue_status(self) -> List[Dict]:
        """Get execution queue status"""
        return [
            {
                "plan_id": plan.id,
                "intent": plan.intent,
                "description": plan.description,
                "complexity": plan.complexity.name,
                "queued_at": time.time()
            }
            for plan in self._execution_queue
        ]
    
    def get_active_tasks(self) -> List[Dict]:
        """Get list of active tasks"""
        return [
            {
                "task_id": task_id,
                "status": "running" if not task.done() else "completed",
                "done": task.done()
            }
            for task_id, task in self._active_tasks.items()
        ]
    
    async def execute_in_background(self, plan: TaskPlan) -> str:
        """
        Execute a task in the background
        
        Args:
            plan: The task plan to execute
            
        Returns:
            Task ID for tracking
        """
        task_id = str(uuid.uuid4())
        
        async def background_execution():
            try:
                result = await self.execute(plan)
                self.logger.info(f"Background task {task_id} completed")
                return result
            except Exception as e:
                self.logger.error(f"Background task {task_id} failed: {str(e)}")
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    plan_id=plan.id,
                    error=str(e)
                )
        
        task = asyncio.create_task(background_execution())
        self._active_tasks[task_id] = task
        
        self.logger.info(f"Started background task: {task_id}")
        return task_id
    
    async def get_background_task_status(self, task_id: str) -> Optional[Dict]:
        """Get status of a background task"""
        task = self._active_tasks.get(task_id)
        if not task:
            return None
        
        if task.done():
            try:
                result = task.result()
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "result": result.to_dict() if hasattr(result, 'to_dict') else result
                }
            except Exception as e:
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(e)
                }
        else:
            return {
                "task_id": task_id,
                "status": "running",
                "started_at": time.time()
            }
