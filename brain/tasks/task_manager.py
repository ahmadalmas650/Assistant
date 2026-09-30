"""
Task Manager Module
Manages all task lifecycle operations
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
from ..core.task_planner import TaskPlan, TaskStep, StepStatus
from ..core.execution_controller import ExecutionController, ExecutionStatus


class TaskPriority(Enum):
    """Task priority levels"""
    LOW = auto()
    NORMAL = auto()
    HIGH = auto()
    CRITICAL = auto()


class TaskState(Enum):
    """Task state"""
    PENDING = auto()
    QUEUED = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class TaskInfo:
    """Information about a task"""
    task_id: str
    plan_id: str
    name: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    state: TaskState = TaskState.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    progress: float = 0.0  # 0-1
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "plan_id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority.name,
            "state": self.state.name,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata
        }


@dataclass
class TaskQueue:
    """Task queue information"""
    queued_tasks: List[str] = field(default_factory=list)
    running_tasks: List[str] = field(default_factory=list)
    completed_tasks: List[str] = field(default_factory=list)
    failed_tasks: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "queued": self.queued_tasks,
            "running": self.running_tasks,
            "completed": self.completed_tasks,
            "failed": self.failed_tasks
        }


class TaskManager:
    """
    Manages the lifecycle of all tasks
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Task storage
        self._tasks: Dict[str, TaskInfo] = {}
        self._task_queue: List[str] = []
        self._running_tasks: List[str] = []
        self._completed_tasks: List[str] = []
        self._failed_tasks: List[str] = []
        
        # Execution controller
        self.execution_controller = ExecutionController(config, logger)
        
        # Callbacks
        self._on_task_created: List[Callable] = []
        self._on_task_started: List[Callable] = []
        self._on_task_completed: List[Callable] = []
        self._on_task_failed: List[Callable] = []
        self._on_task_cancelled: List[Callable] = []
        
        # Locks
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize the task manager"""
        self.logger.info("Task Manager initialized")
    
    async def create_task(self, plan: TaskPlan, priority: TaskPriority = TaskPriority.NORMAL,
                         metadata: Optional[Dict] = None) -> TaskInfo:
        """
        Create a new task from a plan
        
        Args:
            plan: The task plan
            priority: Task priority
            metadata: Additional metadata
            
        Returns:
            TaskInfo object
        """
        async with self._lock:
            task_id = str(uuid.uuid4())
            
            task_info = TaskInfo(
                task_id=task_id,
                plan_id=plan.id,
                name=plan.intent,
                description=plan.description,
                priority=priority,
                state=TaskState.PENDING,
                metadata=metadata or {}
            )
            
            self._tasks[task_id] = task_info
            self._task_queue.append(task_id)
            
            self.logger.info(f"Created task: {task_id} ({plan.intent})")
            
            # Notify callbacks
            for callback in self._on_task_created:
                try:
                    callback(task_info)
                except Exception as e:
                    self.error_handler.handle_error(e, "task_created_callback")
            
            return task_info
    
    async def queue_task(self, task_id: str) -> bool:
        """Queue a task for execution"""
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            if task.state != TaskState.PENDING:
                return False
            
            task.state = TaskState.QUEUED
            
            # Add to queue if not already there
            if task_id not in self._task_queue:
                self._task_queue.append(task_id)
            
            self.logger.info(f"Queued task: {task_id}")
            return True
    
    async def start_task(self, task_id: str) -> bool:
        """Start a task"""
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            if task.state != TaskState.QUEUED:
                return False
            
            task.state = TaskState.RUNNING
            task.started_at = time.time()
            
            # Move to running
            if task_id in self._task_queue:
                self._task_queue.remove(task_id)
            self._running_tasks.append(task_id)
            
            self.logger.info(f"Started task: {task_id}")
            
            # Notify callbacks
            for callback in self._on_task_started:
                try:
                    callback(task)
                except Exception as e:
                    self.error_handler.handle_error(e, "task_started_callback")
            
            return True
    
    async def execute_task(self, task_id: str, plan: TaskPlan) -> Tuple[bool, Any]:
        """
        Execute a task
        
        Args:
            task_id: The task ID
            plan: The task plan to execute
            
        Returns:
            Tuple of (success, result)
        """
        async with self._lock:
            if task_id not in self._tasks:
                return False, {"error": "Task not found"}
            
            task = self._tasks[task_id]
            
            # Update state
            if task.state == TaskState.PENDING:
                await self.queue_task(task_id)
            
            if task.state == TaskState.QUEUED:
                await self.start_task(task_id)
            
            # Execute the plan
            try:
                result = await self.execution_controller.execute(plan)
                
                # Update task
                task.completed_at = time.time()
                task.progress = 1.0
                task.result = result.to_dict() if hasattr(result, 'to_dict') else result
                
                if result.status.value >= ExecutionStatus.COMPLETED.value:
                    task.state = TaskState.COMPLETED
                    self._running_tasks.remove(task_id)
                    self._completed_tasks.append(task_id)
                    
                    self.logger.info(f"Completed task: {task_id}")
                    
                    # Notify callbacks
                    for callback in self._on_task_completed:
                        try:
                            callback(task)
                        except Exception as e:
                            self.error_handler.handle_error(e, "task_completed_callback")
                    
                    return True, result
                else:
                    task.state = TaskState.FAILED
                    task.error = result.error if hasattr(result, 'error') else "Execution failed"
                    self._running_tasks.remove(task_id)
                    self._failed_tasks.append(task_id)
                    
                    self.logger.warning(f"Failed task: {task_id}")
                    
                    # Notify callbacks
                    for callback in self._on_task_failed:
                        try:
                            callback(task)
                        except Exception as e:
                            self.error_handler.handle_error(e, "task_failed_callback")
                    
                    return False, result
                    
            except Exception as e:
                self.error_handler.handle_error(e, f"task_execution_{task_id}")
                
                task.state = TaskState.FAILED
                task.error = str(e)
                task.completed_at = time.time()
                
                if task_id in self._running_tasks:
                    self._running_tasks.remove(task_id)
                self._failed_tasks.append(task_id)
                
                # Notify callbacks
                for callback in self._on_task_failed:
                    try:
                        callback(task)
                    except Exception as e2:
                        self.error_handler.handle_error(e2, "task_failed_callback")
                
                return False, {"error": str(e)}
    
    async def cancel_task(self, task_id: str, reason: str = "") -> bool:
        """Cancel a task"""
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            if task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
                return False
            
            # Stop execution
            await self.execution_controller.stop_current_task()
            
            # Update task
            task.state = TaskState.CANCELLED
            task.completed_at = time.time()
            task.error = reason or "Task cancelled by user"
            
            # Update queues
            if task_id in self._task_queue:
                self._task_queue.remove(task_id)
            if task_id in self._running_tasks:
                self._running_tasks.remove(task_id)
            self._failed_tasks.append(task_id)
            
            self.logger.info(f"Cancelled task: {task_id}")
            
            # Notify callbacks
            for callback in self._on_task_cancelled:
                try:
                    callback(task)
                except Exception as e:
                    self.error_handler.handle_error(e, "task_cancelled_callback")
            
            return True
    
    async def pause_task(self, task_id: str) -> bool:
        """Pause a task"""
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            if task.state != TaskState.RUNNING:
                return False
            
            # Pause execution
            await self.execution_controller.pause_current_task()
            
            task.state = TaskState.PAUSED
            
            self.logger.info(f"Paused task: {task_id}")
            return True
    
    async def resume_task(self, task_id: str) -> bool:
        """Resume a paused task"""
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            if task.state != TaskState.PAUSED:
                return False
            
            # Resume execution
            await self.execution_controller.resume_current_task()
            
            task.state = TaskState.RUNNING
            
            self.logger.info(f"Resumed task: {task_id}")
            return True
    
    async def modify_task(self, task_id: str, modification: str) -> bool:
        """Modify a running task"""
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            if task.state != TaskState.RUNNING:
                return False
            
            # Request modification
            await self.execution_controller.modify_current_task(modification)
            
            self.logger.info(f"Modified task: {task_id}")
            return True
    
    async def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """Get task information"""
        async with self._lock:
            return self._tasks.get(task_id)
    
    async def get_all_tasks(self) -> List[TaskInfo]:
        """Get all tasks"""
        async with self._lock:
            return list(self._tasks.values())
    
    async def get_tasks_by_state(self, state: TaskState) -> List[TaskInfo]:
        """Get tasks by state"""
        async with self._lock:
            return [t for t in self._tasks.values() if t.state == state]
    
    async def get_queue_status(self) -> TaskQueue:
        """Get task queue status"""
        async with self._lock:
            return TaskQueue(
                queued_tasks=self._task_queue,
                running_tasks=self._running_tasks,
                completed_tasks=self._completed_tasks,
                failed_tasks=self._failed_tasks
            )
    
    async def cleanup_completed_tasks(self, older_than: int = 86400) -> int:
        """
        Cleanup completed tasks older than specified seconds
        
        Args:
            older_than: Remove tasks completed more than this many seconds ago
            
        Returns:
            Number of tasks removed
        """
        async with self._lock:
            cutoff = time.time() - older_than
            removed = 0
            
            for task_id, task in list(self._tasks.items()):
                if (task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED] and
                    task.completed_at < cutoff):
                    del self._tasks[task_id]
                    if task_id in self._completed_tasks:
                        self._completed_tasks.remove(task_id)
                    if task_id in self._failed_tasks:
                        self._failed_tasks.remove(task_id)
                    removed += 1
            
            self.logger.info(f"Cleaned up {removed} old tasks")
            return removed
    
    async def cleanup_all_tasks(self) -> int:
        """Cleanup all tasks"""
        async with self._lock:
            count = len(self._tasks)
            self._tasks.clear()
            self._task_queue.clear()
            self._running_tasks.clear()
            self._completed_tasks.clear()
            self._failed_tasks.clear()
            
            self.logger.info(f"Cleaned up all {count} tasks")
            return count
    
    async def shutdown(self):
        """Shutdown the task manager"""
        self.logger.info("Shutting down Task Manager...")
        
        # Cancel all running tasks
        for task_id in list(self._running_tasks):
            await self.cancel_task(task_id, "Shutdown requested")
        
        # Cleanup
        await self.cleanup_all_tasks()
        
        self.logger.info("Task Manager shutdown complete")
    
    # Callback Registration
    
    def on_task_created(self, callback: Callable):
        """Register task created callback"""
        self._on_task_created.append(callback)
    
    def on_task_started(self, callback: Callable):
        """Register task started callback"""
        self._on_task_started.append(callback)
    
    def on_task_completed(self, callback: Callable):
        """Register task completed callback"""
        self._on_task_completed.append(callback)
    
    def on_task_failed(self, callback: Callable):
        """Register task failed callback"""
        self._on_task_failed.append(callback)
    
    def on_task_cancelled(self, callback: Callable):
        """Register task cancelled callback"""
        self._on_task_cancelled.append(callback)
    
    # Utility Methods
    
    async def get_task_count(self) -> Dict[str, int]:
        """Get count of tasks by state"""
        async with self._lock:
            counts = {
                "total": len(self._tasks),
                "pending": 0,
                "queued": 0,
                "running": 0,
                "paused": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0
            }
            
            for task in self._tasks.values():
                counts[task.state.name.lower()] += 1
            
            return counts
    
    async def get_highest_priority_task(self) -> Optional[TaskInfo]:
        """Get the highest priority queued task"""
        async with self._lock:
            priority_order = [
                TaskPriority.CRITICAL,
                TaskPriority.HIGH,
                TaskPriority.NORMAL,
                TaskPriority.LOW
            ]
            
            for priority in priority_order:
                queued_tasks = [t for t in self._tasks.values() 
                               if t.state == TaskState.QUEUED and t.priority == priority]
                if queued_tasks:
                    # Return oldest task of this priority
                    queued_tasks.sort(key=lambda t: t.created_at)
                    return queued_tasks[0]
            
            return None
