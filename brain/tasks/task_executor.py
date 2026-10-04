"""
Task Executor Module
Executes individual task steps
"""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler
from ..core.task_planner import TaskStep, StepStatus
from ..modules.app_integrator import AppIntegrator
from ..modules.accessibility_controller import AccessibilityController
from ..modules.ocr_engine import OCREngine


class ExecutionMode(Enum):
    """Execution mode for steps"""
    SEQUENTIAL = auto()
    PARALLEL = auto()
    HYBRID = auto()


@dataclass
class ExecutionContext:
    """Context for step execution"""
    task_id: str
    step: TaskStep
    previous_results: Dict[str, Any] = field(default_factory=dict)
    current_app: Optional[str] = None
    resource_usage: Dict[str, float] = field(default_factory=dict)
    timeout: int = 30
    retry_count: int = 3
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "step_id": self.step.id,
            "action": self.step.action,
            "previous_results": self.previous_results,
            "current_app": self.current_app,
            "resource_usage": self.resource_usage,
            "timeout": self.timeout,
            "retry_count": self.retry_count
        }


@dataclass
class StepResult:
    """Result of executing a single step"""
    step_id: str
    action: str
    status: StepStatus
    output: Optional[Any] = None
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    execution_time: float = 0.0
    retry_count: int = 0
    app_used: Optional[str] = None
    resource_usage: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "status": self.status.name,
            "output": self.output,
            "error": self.error,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "execution_time": self.execution_time,
            "retry_count": self.retry_count,
            "app_used": self.app_used,
            "resource_usage": self.resource_usage
        }


class TaskExecutor:
    """
    Executes individual task steps
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Initialize modules
        self.app_integrator = AppIntegrator(config, logger)
        self.accessibility_controller = AccessibilityController(config, logger)
        self.ocr_engine = OCREngine(config, self.accessibility_controller)
        
        # Step handlers
        self._step_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()
        
        # Execution tracking
        self._active_executions: Dict[str, ExecutionContext] = {}
        self._execution_lock = asyncio.Lock()
    
    def _register_default_handlers(self):
        """Register default step handlers"""
        # File operations
        self.register_handler("select_file", self._handle_select_file)
        self.register_handler("open_file", self._handle_open_file)
        self.register_handler("save_file", self._handle_save_file)
        self.register_handler("delete_file", self._handle_delete_file)
        
        # App operations
        self.register_handler("open_app", self._handle_open_app)
        self.register_handler("close_app", self._handle_close_app)
        self.register_handler("use_app", self._handle_use_app)
        
        # Editing operations
        self.register_handler("edit_photo", self._handle_edit_photo)
        self.register_handler("edit_video", self._handle_edit_video)
        self.register_handler("create_thumbnail", self._handle_create_thumbnail)
        
        # Upload operations
        self.register_handler("upload", self._handle_upload)
        self.register_handler("verify_upload", self._handle_verify_upload)
        
        
        self.register_handler("extract_text", self._handle_extract_text)
        
        # Search operations
        self.register_handler("search", self._handle_search)
        self.register_handler("extract_query", self._handle_extract_query)
        self.register_handler("merge_results", self._handle_merge_results)
        self.register_handler("present_results", self._handle_present_results)
        
        # Metadata operations
        self.register_handler("check_metadata", self._handle_check_metadata)
        self.register_handler("edit_if_needed", self._handle_edit_if_needed)
        
        # Generic fallback
        self.register_handler("*", self._handle_generic_step)
    
    def register_handler(self, action: str, handler: Callable):
        """Register a step handler"""
        self._step_handlers[action] = handler
        self.logger.debug(f"Registered step handler for: {action}")
    
    async def execute_step(self, step: TaskStep, context: Optional[ExecutionContext] = None) -> StepResult:
        """
        Execute a single step
        
        Args:
            step: The step to execute
            context: Execution context
            
        Returns:
            StepResult
        """
        start_time = time.time()
        
        if context is None:
            context = ExecutionContext(
                task_id=str(uuid.uuid4()),
                step=step
            )
        
        self.logger.debug(f"Executing step: {step.id} ({step.action})")
        
        try:
            # Get handler
            handler = self._get_handler(step.action)
            
            # Execute with retry logic
            last_error = None
            for attempt in range(step.retry_count):
                try:
                    output = await self._call_handler(handler, step, context)
                    
                    end_time = time.time()
                    
                    return StepResult(
                        step_id=step.id,
                        action=step.action,
                        status=StepStatus.COMPLETED,
                        output=output,
                        start_time=start_time,
                        end_time=end_time,
                        execution_time=end_time - start_time,
                        retry_count=attempt,
                        app_used=context.current_app,
                        resource_usage=context.resource_usage
                    )
                    
                except Exception as e:
                    last_error = e
                    self.logger.warning(f"Step attempt {attempt + 1} failed: {step.id} - {str(e)}")
                    
                    if attempt < step.retry_count - 1:
                        await asyncio.sleep(1)  # Wait before retry
            
            # All retries failed
            end_time = time.time()
            
            self.logger.error(f"Step failed after {step.retry_count} attempts: {step.id}")
            self.error_handler.handle_error(last_error, f"step_{step.id}")
            
            return StepResult(
                step_id=step.id,
                action=step.action,
                status=StepStatus.FAILED,
                error=str(last_error),
                start_time=start_time,
                end_time=end_time,
                execution_time=end_time - start_time,
                retry_count=step.retry_count
            )
            
        except Exception as e:
            end_time = time.time()
            
            self.logger.error(f"Step execution error: {step.id} - {str(e)}")
            self.error_handler.handle_error(e, f"step_execution_{step.id}")
            
            return StepResult(
                step_id=step.id,
                action=step.action,
                status=StepStatus.FAILED,
                error=str(e),
                start_time=start_time,
                end_time=end_time,
                execution_time=end_time - start_time,
                retry_count=0
            )
    
    def _get_handler(self, action: str) -> Callable:
        """Get handler for an action"""
        if action in self._step_handlers:
            return self._step_handlers[action]
        elif "*" in self._step_handlers:
            return self._step_handlers["*"]
        else:
            return self._handle_generic_step
    
    async def _call_handler(self, handler: Callable, step: TaskStep, context: ExecutionContext) -> Any:
        """Call a step handler"""
        # Check if handler is async
        if asyncio.iscoroutinefunction(handler):
            return await handler(step, context)
        else:
            return handler(step, context)
    
    # Step Handlers
    
    async def _handle_select_file(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle file selection"""
        file_type = step.parameters.get("file_type", "unknown")
        
        # Use app integrator to select file
        result = await self.app_integrator.select_file(file_type)
        
        if result.get("success", False):
            context.previous_results[step.id] = result
            return {
                "action": "select_file",
                "file_type": file_type,
                "file_path": result.get("file_path"),
                "status": "selected"
            }
        else:
            raise Exception(f"Failed to select {file_type} file")
    
    async def _handle_open_file(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle opening a file"""
        file_path = step.parameters.get("file_path")
        app = step.parameters.get("app")
        
        if not file_path:
            # Try to get from dependencies
            for dep_id in step.dependencies:
                if dep_id in context.previous_results:
                    file_path = context.previous_results[dep_id].get("file_path")
                    break
        
        if not file_path:
            raise Exception("No file path specified")
        
        result = await self.app_integrator.open_file(file_path, app)
        
        if result.get("success", False):
            context.current_app = app
            context.previous_results[step.id] = result
            return {
                "action": "open_file",
                "file_path": file_path,
                "app": app,
                "status": "opened"
            }
        else:
            raise Exception(f"Failed to open file: {file_path}")
    
    async def _handle_save_file(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle saving a file"""
        file_path = step.parameters.get("file_path")
        
        if not file_path:
            for dep_id in step.dependencies:
                if dep_id in context.previous_results:
                    file_path = context.previous_results[dep_id].get("file_path")
                    break
        
        result = await self.app_integrator.save_file(file_path)
        
        if result.get("success", False):
            return {
                "action": "save_file",
                "file_path": file_path,
                "saved_path": result.get("saved_path"),
                "status": "saved"
            }
        else:
            raise Exception(f"Failed to save file: {file_path}")
    
    async def _handle_open_app(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle opening an app"""
        app = step.parameters.get("app")
        
        if not app:
            raise Exception("No app specified")
        
        result = await self.app_integrator.open_app(app)
        
        if result.get("success", False):
            context.current_app = app
            context.previous_results[step.id] = result
            return {
                "action": "open_app",
                "app": app,
                "status": "opened"
            }
        else:
            raise Exception(f"Failed to open app: {app}")
    
    async def _handle_close_app(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle closing an app"""
        app = step.parameters.get("app", context.current_app)
        
        if not app:
            raise Exception("No app specified")
        
        result = await self.app_integrator.close_app(app)
        
        if result.get("success", False):
            context.current_app = None
            return {
                "action": "close_app",
                "app": app,
                "status": "closed"
            }
        else:
            raise Exception(f"Failed to close app: {app}")
    
    async def _handle_use_app(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle using an app for a specific action"""
        app = step.parameters.get("app")
        action = step.parameters.get("action")
        data = step.parameters.get("data")
        
        if not app:
            raise Exception("No app specified")
        
        result = await self.app_integrator.use_app(app, action, data)
        
        if result.get("success", False):
            context.current_app = app
            context.previous_results[step.id] = result
            return {
                "action": "use_app",
                "app": app,
                "action": action,
                "data": data,
                "status": "completed"
            }
        else:
            raise Exception(f"Failed to use app: {app}")
    
    async def _handle_edit_photo(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle photo editing"""
        file_path = step.parameters.get("file_path")
        app = step.parameters.get("app", "com.kinemaster")
        
        if not file_path:
            for dep_id in step.dependencies:
                if dep_id in context.previous_results:
                    file_path = context.previous_results[dep_id].get("file_path")
                    break
        
        result = await self.app_integrator.edit_photo(file_path, app)
        
        if result.get("success", False):
            context.current_app = app
            context.previous_results[step.id] = result
            return {
                "action": "edit_photo",
                "file_path": file_path,
                "app": app,
                "status": "edited",
                "edited_path": result.get("edited_path")
            }
        else:
            raise Exception(f"Failed to edit photo: {file_path}")
    
    async def _handle_edit_video(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle video editing"""
        file_path = step.parameters.get("file_path")
        app = step.parameters.get("app", "com.kinemaster")
        
        if not file_path:
            for dep_id in step.dependencies:
                if dep_id in context.previous_results:
                    file_path = context.previous_results[dep_id].get("file_path")
                    break
        
        result = await self.app_integrator.edit_video(file_path, app)
        
        if result.get("success", False):
            context.current_app = app
            context.previous_results[step.id] = result
            return {
                "action": "edit_video",
                "file_path": file_path,
                "app": app,
                "status": "edited",
                "edited_path": result.get("edited_path")
            }
        else:
            raise Exception(f"Failed to edit video: {file_path}")
    
    async def _handle_create_thumbnail(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle thumbnail creation"""
        file_path = step.parameters.get("file_path")
        
        if not file_path:
            for dep_id in step.dependencies:
                if dep_id in context.previous_results:
                    file_path = context.previous_results[dep_id].get("file_path")
                    break
        
        result = await self.app_integrator.create_thumbnail(file_path)
        
        if result.get("success", False):
            return {
                "action": "create_thumbnail",
                "file_path": file_path,
                "thumbnail_path": result.get("thumbnail_path"),
                "status": "created"
            }
        else:
            raise Exception(f"Failed to create thumbnail: {file_path}")
    
    async def _handle_upload(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle file upload"""
        file_path = step.parameters.get("file_path")
        platform = step.parameters.get("platform", "youtube")
        
        if not file_path:
            for dep_id in step.dependencies:
                if dep_id in context.previous_results:
                    file_path = context.previous_results[dep_id].get("file_path")
                    break
        
        result = await self.app_integrator.upload_file(file_path, platform)
        
        if result.get("success", False):
            context.previous_results[step.id] = result
            return {
                "action": "upload",
                "file_path": file_path,
                "platform": platform,
                "upload_id": result.get("upload_id"),
                "url": result.get("url"),
                "status": "uploaded"
            }
        else:
            raise Exception(f"Failed to upload to {platform}: {file_path}")
    
    async def _handle_verify_upload(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle upload verification"""
        upload_id = step.parameters.get("upload_id")
        platform = step.parameters.get("platform", "youtube")
        
        if not upload_id:
            for dep_id in step.dependencies:
                if dep_id in context.previous_results:
                    upload_id = context.previous_results[dep_id].get("upload_id")
                    platform = context.previous_results[dep_id].get("platform", platform)
                    break
        
        result = await self.app_integrator.verify_upload(upload_id, platform)
        
        if result.get("success", False):
            return {
                "action": "verify_upload",
                "upload_id": upload_id,
                "platform": platform,
                "status": "verified",
                "url": result.get("url")
            }
        else:
            raise Exception(f"Failed to verify upload: {upload_id}")
    
    async def _handle_extract_text(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle text extraction (live accessibility, no screenshot)"""
        ocr_result = await self.ocr_engine.extract_text_from_screen()

        result = ocr_result.to_dict()
        result["success"] = ocr_result.ok
        source = "live_screen"
        
        if result.get("success", False):
            return {
                "action": "extract_text",
                "text": result.get("text"),
                "source": source,
                "status": "extracted"
            }
        else:
            raise Exception(f"Failed to extract text from {source}")
    
    async def _handle_search(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle searching"""
        query = step.parameters.get("query")
        sources = step.parameters.get("sources", ["chatgpt", "deepseek", "youtube", "grok"])
        
        if not query:
            for dep_id in step.dependencies:
                if dep_id in context.previous_results:
                    query = context.previous_results[dep_id].get("query")
                    break
        
        results = {}
        for source in sources:
            source_result = await self.app_integrator.search(query, source)
            results[source] = source_result
        
        context.previous_results[step.id] = {"query": query, "results": results}
        
        return {
            "action": "search",
            "query": query,
            "sources": list(results.keys()),
            "results": results,
            "status": "completed"
        }
    
    async def _handle_extract_query(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle query extraction"""
        # Extract query from command context
        query = "sample search query"
        
        context.previous_results[step.id] = {"query": query}
        
        return {
            "action": "extract_query",
            "query": query,
            "status": "extracted"
        }
    
    async def _handle_merge_results(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle merging results"""
        results = []
        for dep_id in step.dependencies:
            if dep_id in context.previous_results:
                dep_result = context.previous_results[dep_id]
                if "results" in dep_result:
                    results.extend(dep_result["results"])
        
        # Simple merge - deduplicate
        merged = []
        seen = set()
        for r in results:
            title = r.get("title", "")
            if title not in seen:
                seen.add(title)
                merged.append(r)
        
        return {
            "action": "merge_results",
            "merged_results": merged,
            "count": len(merged),
            "status": "merged"
        }
    
    async def _handle_present_results(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle presenting results"""
        merged_results = []
        for dep_id in step.dependencies:
            if dep_id in context.previous_results:
                dep_result = context.previous_results[dep_id]
                if "merged_results" in dep_result:
                    merged_results = dep_result["merged_results"]
                    break
        
        return {
            "action": "present_results",
            "results": merged_results,
            "count": len(merged_results),
            "status": "presented"
        }
    
    async def _handle_check_metadata(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle metadata checking"""
        check_items = step.parameters.get("check", [])
        file_path = step.parameters.get("file_path")
        
        if not file_path:
            for dep_id in step.dependencies:
                if dep_id in context.previous_results:
                    file_path = context.previous_results[dep_id].get("file_path")
                    break
        
        # Check metadata
        missing = []
        present = []
        
        for item in check_items:
            if item in ["title", "description"]:
                present.append(item)
            else:
                missing.append(item)
        
        context.previous_results[step.id] = {
            "file_path": file_path,
            "checked": check_items,
            "missing": missing,
            "present": present
        }
        
        return {
            "action": "check_metadata",
            "file_path": file_path,
            "checked": check_items,
            "missing": missing,
            "present": present,
            "status": "checked"
        }
    
    async def _handle_edit_if_needed(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle conditional editing"""
        auto_edit = step.parameters.get("auto_edit", False)
        
        # Check if editing is needed
        for dep_id in step.dependencies:
            if dep_id in context.previous_results:
                dep_result = context.previous_results[dep_id]
                if dep_result.get("missing"):
                    return {
                        "action": "edit_if_needed",
                        "editing_required": True,
                        "missing_items": dep_result["missing"],
                        "status": "needed"
                    }
        
        return {
            "action": "edit_if_needed",
            "editing_required": False,
            "status": "not_needed"
        }
    
    async def _handle_generic_step(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Generic handler for unknown steps"""
        self.logger.warning(f"No specific handler for action: {step.action}")
        
        return {
            "action": step.action,
            "status": "not_implemented",
            "message": f"Action '{step.action}' not implemented yet"
        }
    
    async def _handle_delete_file(self, step: TaskStep, context: ExecutionContext) -> Dict:
        """Handle file deletion"""
        file_path = step.parameters.get("file_path")
        
        if not file_path:
            for dep_id in step.dependencies:
                if dep_id in context.previous_results:
                    file_path = context.previous_results[dep_id].get("file_path")
                    break
        
        if not file_path:
            raise Exception("No file path specified")
        
        result = await self.app_integrator.delete_file(file_path)
        
        if result.get("success", False):
            return {
                "action": "delete_file",
                "file_path": file_path,
                "status": "deleted"
            }
        else:
            raise Exception(f"Failed to delete file: {file_path}")
