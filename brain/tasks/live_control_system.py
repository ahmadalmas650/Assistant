"""
Live Control System Module
Provides real-time control over task execution
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler
from ..core.task_planner import TaskPlan, TaskStep, StepStatus
from ..core.execution_controller import ExecutionController, ExecutionStatus


class ControlCommand(Enum):
    """Live control commands"""
    PAUSE = auto()
    RESUME = auto()
    STOP = auto()
    SKIP = auto()
    RETRY = auto()
    MODIFY = auto()
    ADD_STEP = auto()
    INSERT_STEP = auto()
    REMOVE_STEP = auto()
    CHANGE_SPEED = auto()
    GET_STATUS = auto()
    GET_PROGRESS = auto()


class ControlMode(Enum):
    """Control modes"""
    FULL = auto()
    STEP_BY_STEP = auto()
    AUTO = auto()


@dataclass
class ControlState:
    """Current control state"""
    task_id: str
    plan_id: str
    status: ExecutionStatus
    current_step: Optional[str] = None
    current_step_number: int = 0
    total_steps: int = 0
    progress: float = 0.0
    start_time: float = 0.0
    elapsed_time: float = 0.0
    estimated_remaining: float = 0.0
    last_update: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "plan_id": self.plan_id,
            "status": self.status.name,
            "current_step": self.current_step,
            "current_step_number": self.current_step_number,
            "total_steps": self.total_steps,
            "progress": self.progress,
            "start_time": self.start_time,
            "elapsed_time": self.elapsed_time,
            "estimated_remaining": self.estimated_remaining,
            "last_update": self.last_update
        }


@dataclass
class ControlResponse:
    """Response to a control command"""
    success: bool
    command: ControlCommand
    message: str = ""
    data: Optional[Dict] = None
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "command": self.command.name,
            "message": self.message,
            "data": self.data,
            "error": self.error,
            "timestamp": self.timestamp
        }


@dataclass
class ProgressUpdate:
    """Progress update notification"""
    task_id: str
    step_id: str
    step_number: int
    total_steps: int
    progress: float
    status: StepStatus
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "step_id": self.step_id,
            "step_number": self.step_number,
            "total_steps": self.total_steps,
            "progress": self.progress,
            "status": self.status.name,
            "message": self.message,
            "timestamp": self.timestamp
        }


class LiveControlSystem:
    """
    Provides real-time control over task execution
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Execution controller
        self.execution_controller = ExecutionController(config, logger)
        
        # Control state
        self._control_mode = ControlMode.AUTO
        self._current_task_id: Optional[str] = None
        self._current_plan: Optional[TaskPlan] = None
        self._current_step_index = 0
        self._paused = False
        self._stop_requested = False
        self._skip_requested = False
        self._modification_queue: List[Dict] = []
        
        # State tracking
        self._start_time = 0.0
        self._step_start_times: Dict[str, float] = {}
        self._step_completion_times: Dict[str, float] = {}
        
        # Callbacks
        self._on_control_command: List[Callable] = []
        self._on_progress_update: List[Callable] = []
        self._on_status_change: List[Callable] = []
        
        # Locks
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize the live control system"""
        self.logger.info("Live Control System initialized")
    
    async def start_task(self, task_id: str, plan: TaskPlan) -> ControlResponse:
        """
        Start a new task with live control
        
        Args:
            task_id: Unique task identifier
            plan: The task plan to execute
            
        Returns:
            ControlResponse
        """
        async with self._lock:
            if self._current_task_id:
                return ControlResponse(
                    success=False,
                    command=ControlCommand.STOP,
                    error="Another task is already running"
                )
            
            self._current_task_id = task_id
            self._current_plan = plan
            self._current_step_index = 0
            self._paused = False
            self._stop_requested = False
            self._skip_requested = False
            self._modification_queue = []
            self._start_time = time.time()
            self._step_start_times = {}
            self._step_completion_times = {}
            
            self.logger.info(f"Started task with live control: {task_id}")
            
            # Start execution in background
            asyncio.create_task(self._execute_with_control())
            
            return ControlResponse(
                success=True,
                command=ControlCommand.RESUME,
                message=f"Task {task_id} started",
                data={"task_id": task_id, "status": "running"}
            )
    
    async def _execute_with_control(self):
        """Execute task with live control"""
        if not self._current_plan:
            return
        
        try:
            # Execute each step with control checks
            for i, step in enumerate(self._current_plan.steps):
                if self._stop_requested:
                    await self._handle_stop()
                    return
                
                if self._paused:
                    await self._wait_for_resume()
                    if self._stop_requested:
                        await self._handle_stop()
                        return
                
                # Check for modifications
                if self._modification_queue:
                    await self._handle_modifications()
                    if self._stop_requested:
                        await self._handle_stop()
                        return
                
                # Execute step
                self._current_step_index = i
                self._step_start_times[step.id] = time.time()
                
                # Notify progress
                await self._notify_progress(step, i)
                
                # Check control mode
                if self._control_mode == ControlMode.STEP_BY_STEP:
                    await self._wait_for_step_approval(step)
                    if self._stop_requested:
                        await self._handle_stop()
                        return
                    if self._skip_requested:
                        self._skip_requested = False
                        self._step_completion_times[step.id] = time.time()
                        continue
                
                # Execute the step
                result = await self.execution_controller.execute_step(step)
                
                # Record completion
                self._step_completion_times[step.id] = time.time()
                
                # Check result
                if result.status == StepStatus.FAILED:
                    if self._control_mode == ControlMode.STEP_BY_STEP:
                        await self._handle_step_failure(step, result)
                        if self._stop_requested:
                            await self._handle_stop()
                            return
                    else:
                        # Auto-retry or continue based on config
                        pass
                
                # Notify progress update
                await self._notify_progress_update(step, i, result.status)
            
            # Task completed
            await self._handle_completion()
            
        except Exception as e:
            self.error_handler.handle_error(e, "execute_with_control")
            await self._handle_error(e)
    
    async def _wait_for_resume(self):
        """Wait for resume command"""
        self.logger.info("Task paused - waiting for resume")
        
        while self._paused and not self._stop_requested:
            await asyncio.sleep(0.1)
        
        if self._paused:
            self._paused = False
            self.logger.info("Task resumed")
    
    async def _wait_for_step_approval(self, step: TaskStep):
        """Wait for step approval in step-by-step mode"""
        self.logger.info(f"Waiting for approval to execute step: {step.id}")
        
        # Notify that we're waiting
        await self._notify_status_change({
            "status": "waiting_for_approval",
            "step_id": step.id,
            "step_number": self._current_step_index + 1
        })
        
        while not self._stop_requested and not self._skip_requested:
            await asyncio.sleep(0.1)
    
    async def _handle_stop(self):
        """Handle stop command"""
        self.logger.info("Handling stop command")
        
        await self.execution_controller.stop_current_task()
        
        # Cleanup
        self._cleanup()
        
        await self._notify_status_change({
            "status": "stopped",
            "message": "Task stopped by user"
        })
    
    async def _handle_completion(self):
        """Handle task completion"""
        self.logger.info("Task completed successfully")
        
        await self._notify_status_change({
            "status": "completed",
            "message": "Task completed successfully"
        })
        
        self._cleanup()
    
    async def _handle_error(self, error: Exception):
        """Handle execution error"""
        self.logger.error(f"Task error: {str(error)}")
        
        await self._notify_status_change({
            "status": "failed",
            "error": str(error)
        })
        
        self._cleanup()
    
    async def _handle_step_failure(self, step: TaskStep, result):
        """Handle step failure"""
        self.logger.warning(f"Step failed: {step.id} - {result.error}")
        
        await self._notify_status_change({
            "status": "step_failed",
            "step_id": step.id,
            "error": result.error
        })
        
        # Wait for user decision
        self.logger.info("Waiting for user decision on step failure")
        
        while not self._stop_requested:
            await asyncio.sleep(0.1)
    
    async def _handle_modifications(self):
        """Handle queued modifications"""
        self.logger.info(f"Handling {len(self._modification_queue)} modifications")
        
        for mod in self._modification_queue:
            if mod.get("command") == "modify":
                await self.execution_controller.modify_current_task(mod.get("data", ""))
            elif mod.get("command") == "add_step":
                # Add step logic
                pass
            elif mod.get("command") == "skip":
                self._skip_requested = True
        
        self._modification_queue = []
    
    async def _notify_progress(self, step: TaskStep, step_index: int):
        """Notify progress start"""
        total_steps = len(self._current_plan.steps) if self._current_plan else 1
        progress = step_index / total_steps if total_steps > 0 else 0
        
        update = ProgressUpdate(
            task_id=self._current_task_id or "",
            step_id=step.id,
            step_number=step_index + 1,
            total_steps=total_steps,
            progress=progress,
            status=StepStatus.RUNNING,
            message=f"Starting: {step.description}"
        )
        
        for callback in self._on_progress_update:
            try:
                callback(update)
            except Exception as e:
                self.error_handler.handle_error(e, "progress_update_callback")
    
    async def _notify_progress_update(self, step: TaskStep, step_index: int, status: StepStatus):
        """Notify progress update"""
        total_steps = len(self._current_plan.steps) if self._current_plan else 1
        progress = (step_index + (1 if status == StepStatus.COMPLETED else 0)) / total_steps
        
        status_msg = "Completed" if status == StepStatus.COMPLETED else "Failed"
        
        update = ProgressUpdate(
            task_id=self._current_task_id or "",
            step_id=step.id,
            step_number=step_index + 1,
            total_steps=total_steps,
            progress=progress,
            status=status,
            message=f"{status_msg}: {step.description}"
        )
        
        for callback in self._on_progress_update:
            try:
                callback(update)
            except Exception as e:
                self.error_handler.handle_error(e, "progress_update_callback")
    
    async def _notify_status_change(self, data: Dict):
        """Notify status change"""
        for callback in self._on_status_change:
            try:
                callback(data)
            except Exception as e:
                self.error_handler.handle_error(e, "status_change_callback")
    
    def _cleanup(self):
        """Clean up control state"""
        self._current_task_id = None
        self._current_plan = None
        self._current_step_index = 0
        self._paused = False
        self._stop_requested = False
        self._skip_requested = False
        self._modification_queue = []
        self._start_time = 0.0
        self._step_start_times = {}
        self._step_completion_times = {}
    
    async def send_command(self, command: ControlCommand, data: Optional[Dict] = None) -> ControlResponse:
        """
        Send a control command
        
        Args:
            command: The control command
            data: Additional data for the command
            
        Returns:
            ControlResponse
        """
        async with self._lock:
            # Notify command received
            for callback in self._on_control_command:
                try:
                    callback(command, data)
                except Exception as e:
                    self.error_handler.handle_error(e, "control_command_callback")
            
            if command == ControlCommand.PAUSE:
                return await self._handle_pause_command(data)
            elif command == ControlCommand.RESUME:
                return await self._handle_resume_command(data)
            elif command == ControlCommand.STOP:
                return await self._handle_stop_command(data)
            elif command == ControlCommand.SKIP:
                return await self._handle_skip_command(data)
            elif command == ControlCommand.RETRY:
                return await self._handle_retry_command(data)
            elif command == ControlCommand.MODIFY:
                return await self._handle_modify_command(data)
            elif command == ControlCommand.ADD_STEP:
                return await self._handle_add_step_command(data)
            elif command == ControlCommand.INSERT_STEP:
                return await self._handle_insert_step_command(data)
            elif command == ControlCommand.REMOVE_STEP:
                return await self._handle_remove_step_command(data)
            elif command == ControlCommand.CHANGE_SPEED:
                return await self._handle_change_speed_command(data)
            elif command == ControlCommand.GET_STATUS:
                return await self._handle_get_status_command(data)
            elif command == ControlCommand.GET_PROGRESS:
                return await self._handle_get_progress_command(data)
            else:
                return ControlResponse(
                    success=False,
                    command=command,
                    error=f"Unknown command: {command}"
                )
    
    async def _handle_pause_command(self, data: Optional[Dict]) -> ControlResponse:
        """Handle pause command"""
        if not self._current_task_id:
            return ControlResponse(
                success=False,
                command=ControlCommand.PAUSE,
                error="No task is currently running"
            )
        
        self._paused = True
        await self.execution_controller.pause_current_task()
        
        await self._notify_status_change({
            "status": "paused",
            "message": "Task paused"
        })
        
        return ControlResponse(
            success=True,
            command=ControlCommand.PAUSE,
            message="Task paused"
        )
    
    async def _handle_resume_command(self, data: Optional[Dict]) -> ControlResponse:
        """Handle resume command"""
        if not self._current_task_id:
            return ControlResponse(
                success=False,
                command=ControlCommand.RESUME,
                error="No task is currently running"
            )
        
        if not self._paused:
            return ControlResponse(
                success=False,
                command=ControlCommand.RESUME,
                error="Task is not paused"
            )
        
        self._paused = False
        await self.execution_controller.resume_current_task()
        
        await self._notify_status_change({
            "status": "running",
            "message": "Task resumed"
        })
        
        return ControlResponse(
            success=True,
            command=ControlCommand.RESUME,
            message="Task resumed"
        )
    
    async def _handle_stop_command(self, data: Optional[Dict]) -> ControlResponse:
        """Handle stop command"""
        if not self._current_task_id:
            return ControlResponse(
                success=False,
                command=ControlCommand.STOP,
                error="No task is currently running"
            )
        
        self._stop_requested = True
        await self.execution_controller.stop_current_task()
        
        self._cleanup()
        
        await self._notify_status_change({
            "status": "stopped",
            "message": "Task stopped"
        })
        
        return ControlResponse(
            success=True,
            command=ControlCommand.STOP,
            message="Task stopped"
        )
    
    async def _handle_skip_command(self, data: Optional[Dict]) -> ControlResponse:
        """Handle skip command"""
        if not self._current_task_id:
            return ControlResponse(
                success=False,
                command=ControlCommand.SKIP,
                error="No task is currently running"
            )
        
        self._skip_requested = True
        
        await self._notify_status_change({
            "status": "skipping",
            "message": "Current step will be skipped"
        })
        
        return ControlResponse(
            success=True,
            command=ControlCommand.SKIP,
            message="Step will be skipped"
        )
    
    async def _handle_retry_command(self, data: Optional[Dict]) -> ControlResponse:
        """Handle retry command"""
        if not self._current_task_id:
            return ControlResponse(
                success=False,
                command=ControlCommand.RETRY,
                error="No task is currently running"
            )
        
        # Queue retry
        self._modification_queue.append({
            "command": "retry",
            "data": data
        })
        
        await self._notify_status_change({
            "status": "retry_queued",
            "message": "Retry queued"
        })
        
        return ControlResponse(
            success=True,
            command=ControlCommand.RETRY,
            message="Retry queued"
        )
    
    async def _handle_modify_command(self, data: Optional[Dict]) -> ControlResponse:
        """Handle modify command"""
        if not self._current_task_id:
            return ControlResponse(
                success=False,
                command=ControlCommand.MODIFY,
                error="No task is currently running"
            )
        
        if not data:
            return ControlResponse(
                success=False,
                command=ControlCommand.MODIFY,
                error="No modification data provided"
            )
        
        # Queue modification
        self._modification_queue.append({
            "command": "modify",
            "data": data
        })
        
        await self._notify_status_change({
            "status": "modification_queued",
            "message": "Modification queued"
        })
        
        return ControlResponse(
            success=True,
            command=ControlCommand.MODIFY,
            message="Modification queued"
        )
    
    async def _handle_add_step_command(self, data: Optional[Dict]) -> ControlResponse:
        """Handle add step command"""
        if not self._current_task_id:
            return ControlResponse(
                success=False,
                command=ControlCommand.ADD_STEP,
                error="No task is currently running"
            )
        
        if not data:
            return ControlResponse(
                success=False,
                command=ControlCommand.ADD_STEP,
                error="No step data provided"
            )
        
        # Queue add step
        self._modification_queue.append({
            "command": "add_step",
            "data": data
        })
        
        return ControlResponse(
            success=True,
            command=ControlCommand.ADD_STEP,
            message="Add step queued"
        )
    
    async def _handle_insert_step_command(self, data: Optional[Dict]) -> ControlResponse:
        """Handle insert step command"""
        if not self._current_task_id:
            return ControlResponse(
                success=False,
                command=ControlCommand.INSERT_STEP,
                error="No task is currently running"
            )
        
        if not data:
            return ControlResponse(
                success=False,
                command=ControlCommand.INSERT_STEP,
                error="No step data provided"
            )
        
        # Queue insert step
        self._modification_queue.append({
            "command": "insert_step",
            "data": data
        })
        
        return ControlResponse(
            success=True,
            command=ControlCommand.INSERT_STEP,
            message="Insert step queued"
        )
    
    async def _handle_remove_step_command(self, data: Optional[Dict]) -> ControlResponse:
        """Handle remove step command"""
        if not self._current_task_id:
            return ControlResponse(
                success=False,
                command=ControlCommand.REMOVE_STEP,
                error="No task is currently running"
            )
        
        if not data or "step_id" not in data:
            return ControlResponse(
                success=False,
                command=ControlCommand.REMOVE_STEP,
                error="No step ID provided"
            )
        
        # Queue remove step
        self._modification_queue.append({
            "command": "remove_step",
            "data": data
        })
        
        return ControlResponse(
            success=True,
            command=ControlCommand.REMOVE_STEP,
            message="Remove step queued"
        )
    
    async def _handle_change_speed_command(self, data: Optional[Dict]) -> ControlResponse:
        """Handle change speed command"""
        if not self._current_task_id:
            return ControlResponse(
                success=False,
                command=ControlCommand.CHANGE_SPEED,
                error="No task is currently running"
            )
        
        if not data or "speed" not in data:
            return ControlResponse(
                success=False,
                command=ControlCommand.CHANGE_SPEED,
                error="No speed value provided"
            )
        
        # Change control mode based on speed
        speed = data["speed"]
        if speed == "slow":
            self._control_mode = ControlMode.STEP_BY_STEP
        elif speed == "normal":
            self._control_mode = ControlMode.AUTO
        elif speed == "fast":
            self._control_mode = ControlMode.AUTO
        
        return ControlResponse(
            success=True,
            command=ControlCommand.CHANGE_SPEED,
            message=f"Speed changed to {speed}"
        )
    
    async def _handle_get_status_command(self, data: Optional[Dict]) -> ControlResponse:
        """Handle get status command"""
        state = self.get_current_state()
        
        return ControlResponse(
            success=True,
            command=ControlCommand.GET_STATUS,
            message="Current status",
            data=state.to_dict() if state else None
        )
    
    async def _handle_get_progress_command(self, data: Optional[Dict]) -> ControlResponse:
        """Handle get progress command"""
        progress = self.get_current_progress()
        
        return ControlResponse(
            success=True,
            command=ControlCommand.GET_PROGRESS,
            message="Current progress",
            data=progress
        )
    
    def get_current_state(self) -> Optional[ControlState]:
        """Get current control state"""
        if not self._current_task_id or not self._current_plan:
            return None
        
        elapsed = time.time() - self._start_time if self._start_time > 0 else 0
        
        # Calculate estimated remaining time
        if self._current_step_index > 0:
            avg_step_time = elapsed / self._current_step_index
            remaining_steps = len(self._current_plan.steps) - self._current_step_index
            estimated_remaining = avg_step_time * remaining_steps
        else:
            estimated_remaining = 0
        
        current_step = None
        if self._current_step_index < len(self._current_plan.steps):
            current_step = self._current_plan.steps[self._current_step_index].id
        
        status = ExecutionStatus.RUNNING
        if self._paused:
            status = ExecutionStatus.PAUSED
        elif self._stop_requested:
            status = ExecutionStatus.CANCELLED
        
        return ControlState(
            task_id=self._current_task_id,
            plan_id=self._current_plan.id,
            status=status,
            current_step=current_step,
            current_step_number=self._current_step_index + 1,
            total_steps=len(self._current_plan.steps),
            progress=self.get_current_progress().get("progress", 0.0),
            start_time=self._start_time,
            elapsed_time=elapsed,
            estimated_remaining=estimated_remaining
        )
    
    def get_current_progress(self) -> Dict:
        """Get current progress"""
        if not self._current_task_id or not self._current_plan:
            return {"progress": 0.0, "message": "No task running"}
        
        total_steps = len(self._current_plan.steps)
        
        if self._current_step_index >= total_steps:
            return {"progress": 1.0, "message": "Task completed"}
        
        # Calculate progress based on completed steps
        completed_steps = self._current_step_index
        
        # Add partial progress for current step
        current_step_id = self._current_plan.steps[self._current_step_index].id
        if current_step_id in self._step_start_times:
            step_start = self._step_start_times[current_step_id]
            step_duration = time.time() - step_start
            step_timeout = self._current_plan.steps[self._current_step_index].timeout
            step_progress = min(step_duration / step_timeout, 1.0)
            completed_steps += step_progress
        
        progress = completed_steps / total_steps if total_steps > 0 else 0
        
        return {
            "progress": progress,
            "completed_steps": self._current_step_index,
            "total_steps": total_steps,
            "current_step": self._current_step_index + 1,
            "message": f"Step {self._current_step_index + 1} of {total_steps}"
        }
    
    async def set_control_mode(self, mode: ControlMode) -> bool:
        """Set the control mode"""
        self._control_mode = mode
        self.logger.info(f"Control mode set to: {mode.name}")
        return True
    
    async def get_control_mode(self) -> ControlMode:
        """Get the current control mode"""
        return self._control_mode
    
    # Callback Registration
    
    def on_control_command(self, callback: Callable):
        """Register control command callback"""
        self._on_control_command.append(callback)
    
    def on_progress_update(self, callback: Callable):
        """Register progress update callback"""
        self._on_progress_update.append(callback)
    
    def on_status_change(self, callback: Callable):
        """Register status change callback"""
        self._on_status_change.append(callback)
    
    # Utility Methods
    
    async def is_task_running(self) -> bool:
        """Check if a task is currently running"""
        return self._current_task_id is not None and not self._stop_requested
    
    async def is_paused(self) -> bool:
        """Check if the current task is paused"""
        return self._paused
    
    async def get_current_task_id(self) -> Optional[str]:
        """Get the current task ID"""
        return self._current_task_id
    
    async def get_current_plan(self) -> Optional[TaskPlan]:
        """Get the current task plan"""
        return self._current_plan
    
    async def cleanup(self):
        """Clean up the control system"""
        self._cleanup()
        self.logger.info("Live Control System cleaned up")
