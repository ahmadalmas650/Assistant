"""
Preview System Module
Provides command preview and editing capabilities
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler
from ..core.task_planner import TaskPlan, TaskStep, StepStatus, TaskComplexity


class PreviewMode(Enum):
    """Preview display modes"""
    FULL = auto()
    COMPACT = auto()
    STEP_BY_STEP = auto()
    INTERACTIVE = auto()


class EditAction(Enum):
    """Edit action types"""
    ADD_STEP = auto()
    REMOVE_STEP = auto()
    MODIFY_STEP = auto()
    REORDER_STEPS = auto()
    CHANGE_PARAMETERS = auto()
    CHANGE_PRIORITY = auto()


@dataclass
class PreviewData:
    """Preview data for a task plan"""
    plan_id: str
    intent: str
    description: str
    complexity: str
    estimated_duration: str
    step_count: int
    steps: List[Dict]
    required_apps: List[str]
    missing_requirements: List[str]
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "plan_id": self.plan_id,
            "intent": self.intent,
            "description": self.description,
            "complexity": self.complexity,
            "estimated_duration": self.estimated_duration,
            "step_count": self.step_count,
            "steps": self.steps,
            "required_apps": self.required_apps,
            "missing_requirements": self.missing_requirements,
            "warnings": self.warnings,
            "suggestions": self.suggestions
        }


@dataclass
class EditRequest:
    """Request to edit a task plan"""
    action: EditAction
    target: str  # step_id or parameter name
    value: Any = None
    old_value: Any = None
    position: int = -1
    
    def to_dict(self) -> Dict:
        return {
            "action": self.action.name,
            "target": self.target,
            "value": self.value,
            "old_value": self.old_value,
            "position": self.position
        }


@dataclass
class EditResult:
    """Result of editing a task plan"""
    success: bool
    plan: Optional[TaskPlan] = None
    message: str = ""
    changes: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "plan": self.plan.to_dict() if self.plan else None,
            "message": self.message,
            "changes": self.changes
        }


class PreviewSystem:
    """
    Provides preview and editing capabilities for task plans
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Preview cache
        self._preview_cache: Dict[str, PreviewData] = {}
        
        # Edit history
        self._edit_history: List[EditRequest] = []
        self._max_history = 100
        
        # Callbacks
        self._on_preview_generated: List[Callable] = []
        self._on_edit_applied: List[Callable] = []
    
    async def generate_preview(self, plan: TaskPlan, mode: PreviewMode = PreviewMode.FULL) -> PreviewData:
        """
        Generate a preview for a task plan
        
        Args:
            plan: The task plan
            mode: Preview display mode
            
        Returns:
            PreviewData object
        """
        start_time = time.time()
        
        self.logger.debug(f"Generating preview for plan: {plan.id}")
        
        # Create step previews
        step_previews = []
        for i, step in enumerate(plan.steps):
            step_preview = {
                "id": step.id,
                "number": i + 1,
                "action": step.action,
                "description": step.description,
                "required_apps": step.required_apps,
                "required_resources": step.required_resources,
                "dependencies": step.dependencies,
                "estimated_time": f"{step.timeout}s",
                "retry_count": step.retry_count
            }
            step_previews.append(step_preview)
        
        # Determine complexity display
        complexity_display = plan.complexity.name.replace("_", " ").title()
        
        # Format duration
        duration_hours = plan.estimated_duration / 3600
        if duration_hours >= 1:
            duration_str = f"{duration_hours:.1f} hours"
        elif plan.estimated_duration >= 60:
            duration_str = f"{plan.estimated_duration / 60:.1f} minutes"
        else:
            duration_str = f"{plan.estimated_duration:.0f} seconds"
        
        # Generate warnings and suggestions
        warnings = self._generate_warnings(plan)
        suggestions = self._generate_suggestions(plan)
        
        # Create preview data
        preview_data = PreviewData(
            plan_id=plan.id,
            intent=plan.intent,
            description=plan.description,
            complexity=complexity_display,
            estimated_duration=duration_str,
            step_count=len(plan.steps),
            steps=step_previews,
            required_apps=plan.required_apps,
            missing_requirements=plan.missing_requirements,
            warnings=warnings,
            suggestions=suggestions
        )
        
        # Cache preview
        self._preview_cache[plan.id] = preview_data
        
        # Notify callbacks
        for callback in self._on_preview_generated:
            try:
                callback(preview_data)
            except Exception as e:
                self.error_handler.handle_error(e, "preview_generated_callback")
        
        self.logger.debug(f"Preview generated in {time.time() - start_time:.4f}s")
        return preview_data
    
    def _generate_warnings(self, plan: TaskPlan) -> List[str]:
        """Generate warnings for a plan"""
        warnings = []
        
        # Check for missing requirements
        if plan.missing_requirements:
            for req in plan.missing_requirements:
                if req.startswith("app:"):
                    app = req[4:]
                    warnings.append(f"Required app not available: {app}")
                elif req.startswith("resource:"):
                    resource = req[9:]
                    warnings.append(f"Insufficient resource: {resource}")
                elif req.startswith("entity:"):
                    entity = req[7:]
                    warnings.append(f"Missing entity: {entity}")
        
        # Check for high complexity
        if plan.complexity.value >= TaskComplexity.HIGH.value:
            warnings.append(f"High complexity task - estimated {plan.estimated_duration:.0f} seconds")
        
        # Check for many steps
        if len(plan.steps) > 10:
            warnings.append(f"Task has {len(plan.steps)} steps - may take longer to complete")
        
        # Check for missing apps
        available_apps = self.config.allowed_apps
        for app in plan.required_apps:
            if app not in available_apps:
                warnings.append(f"Required app not in allowed list: {app}")
        
        return list(set(warnings))
    
    def _generate_suggestions(self, plan: TaskPlan) -> List[str]:
        """Generate suggestions for a plan"""
        suggestions = []
        
        # Suggest alternatives for missing apps (only alternatives that are
        # actually in the user's allowed apps list are suggested)
        missing_apps = [req[4:] for req in plan.missing_requirements if req.startswith("app:")]
        app_alternatives = {
            "com.kinemaster": ["com.adobe.premiererush", "com.cyberlink.powerdirector.DESKTOP"],
            "com.openai.chatgpt": ["com.deepseek.app", "com.grok"],
            "com.google.android.youtube": []
        }
        
        for app in missing_apps:
            if app in app_alternatives:
                available_apps = getattr(self.config, "allowed_apps", []) or []
                available_alts = [
                    alt for alt in app_alternatives[app]
                    if alt in available_apps
                ]
                if available_alts:
                    suggestions.append(f"Try using: {', '.join(available_alts)}")
        
        # Suggest breaking down complex tasks
        if plan.complexity.value >= TaskComplexity.HIGH.value:
            suggestions.append("Consider breaking this into smaller tasks")
        
        # Suggest previewing steps
        if len(plan.steps) > 5:
            suggestions.append("Review each step carefully before execution")
        
        return list(set(suggestions))
    
    async def display_preview(self, preview_data: PreviewData, mode: PreviewMode = PreviewMode.FULL) -> str:
        """
        Format preview data for display
        
        Args:
            preview_data: The preview data
            mode: Display mode
            
        Returns:
            Formatted string for display
        """
        if mode == PreviewMode.COMPACT:
            return self._format_compact_preview(preview_data)
        elif mode == PreviewMode.STEP_BY_STEP:
            return self._format_step_by_step_preview(preview_data)
        elif mode == PreviewMode.INTERACTIVE:
            return self._format_interactive_preview(preview_data)
        else:
            return self._format_full_preview(preview_data)
    
    def _format_full_preview(self, preview_data: PreviewData) -> str:
        """Format full preview"""
        lines = []
        
        # Header
        lines.append("=" * 60)
        lines.append("TASK PREVIEW")
        lines.append("=" * 60)
        lines.append("")
        
        # Basic info
        lines.append(f"Intent: {preview_data.intent}")
        lines.append(f"Description: {preview_data.description}")
        lines.append(f"Complexity: {preview_data.complexity}")
        lines.append(f"Estimated Duration: {preview_data.estimated_duration}")
        lines.append(f"Steps: {preview_data.step_count}")
        lines.append("")
        
        # Required apps
        if preview_data.required_apps:
            lines.append("Required Apps:")
            for app in preview_data.required_apps:
                lines.append(f"  - {app}")
            lines.append("")
        
        # Missing requirements
        if preview_data.missing_requirements:
            lines.append("Missing Requirements:")
            for req in preview_data.missing_requirements:
                lines.append(f"  - {req}")
            lines.append("")
        
        # Warnings
        if preview_data.warnings:
            lines.append("Warnings:")
            for warning in preview_data.warnings:
                lines.append(f"  ⚠ {warning}")
            lines.append("")
        
        # Suggestions
        if preview_data.suggestions:
            lines.append("Suggestions:")
            for suggestion in preview_data.suggestions:
                lines.append(f"  ✓ {suggestion}")
            lines.append("")
        
        # Steps
        lines.append("-" * 60)
        lines.append("EXECUTION STEPS")
        lines.append("-" * 60)
        
        for i, step in enumerate(preview_data.steps):
            lines.append(f"{i+1}. {step['action']}")
            lines.append(f"   Description: {step['description']}")
            
            if step.get('required_apps'):
                lines.append(f"   Apps: {', '.join(step['required_apps'])}")
            
            if step.get('dependencies'):
                lines.append(f"   Dependencies: {', '.join(step['dependencies'])}")
            
            lines.append(f"   Time: {step['estimated_time']}")
            lines.append("")
        
        lines.append("=" * 60)
        lines.append("Execute this plan? (yes/no/edit)")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _format_compact_preview(self, preview_data: PreviewData) -> str:
        """Format compact preview"""
        lines = []
        
        lines.append(f"[{preview_data.intent}] {preview_data.description}")
        lines.append(f"Complexity: {preview_data.complexity} | Duration: {preview_data.estimated_duration}")
        
        if preview_data.missing_requirements:
            lines.append(f"Missing: {', '.join(preview_data.missing_requirements)}")
        
        lines.append(f"Steps: {preview_data.step_count}")
        
        for i, step in enumerate(preview_data.steps):
            lines.append(f"  {i+1}. {step['action']} - {step['description']}")
        
        return "\n".join(lines)
    
    def _format_step_by_step_preview(self, preview_data: PreviewData) -> str:
        """Format step-by-step preview"""
        lines = []
        
        lines.append("=" * 60)
        lines.append(f"TASK: {preview_data.intent}")
        lines.append("=" * 60)
        lines.append("")
        
        for i, step in enumerate(preview_data.steps):
            lines.append(f"Step {i+1}: {step['action']}")
            lines.append(f"  {step['description']}")
            
            if step.get('required_apps'):
                lines.append(f"  Requires: {', '.join(step['required_apps'])}")
            
            if step.get('dependencies'):
                lines.append(f"  After: {', '.join(step['dependencies'])}")
            
            lines.append("")
            
            # Ask for confirmation
            lines.append(f"  Continue to step {i+1}? (yes/no/skip)")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_interactive_preview(self, preview_data: PreviewData) -> str:
        """Format interactive preview"""
        lines = []
        
        lines.append("=" * 60)
        lines.append("INTERACTIVE PREVIEW")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Task: {preview_data.intent}")
        lines.append(f"Description: {preview_data.description}")
        lines.append("")
        
        # Show steps with numbers for selection
        for i, step in enumerate(preview_data.steps):
            lines.append(f"[{i+1}] {step['action']}: {step['description']}")
        
        lines.append("")
        lines.append("Options:")
        lines.append("  [E] Edit a step")
        lines.append("  [A] Add a step")
        lines.append("  [R] Remove a step")
        lines.append("  [M] Modify parameters")
        lines.append("  [X] Execute")
        lines.append("  [C] Cancel")
        lines.append("")
        lines.append("Enter choice: ")
        
        return "\n".join(lines)
    
    async def edit_plan(self, plan: TaskPlan, edit_request: EditRequest) -> EditResult:
        """
        Edit a task plan
        
        Args:
            plan: The task plan to edit
            edit_request: The edit request
            
        Returns:
            EditResult object
        """
        start_time = time.time()
        
        self.logger.debug(f"Editing plan: {plan.id}, action: {edit_request.action.name}")
        
        try:
            # Create a copy of the plan
            edited_plan = self._deep_copy_plan(plan)
            
            # Apply the edit
            changes = []
            success = False
            message = ""
            
            if edit_request.action == EditAction.ADD_STEP:
                success, message, changes = self._add_step(edited_plan, edit_request)
            elif edit_request.action == EditAction.REMOVE_STEP:
                success, message, changes = self._remove_step(edited_plan, edit_request)
            elif edit_request.action == EditAction.MODIFY_STEP:
                success, message, changes = self._modify_step(edited_plan, edit_request)
            elif edit_request.action == EditAction.REORDER_STEPS:
                success, message, changes = self._reorder_steps(edited_plan, edit_request)
            elif edit_request.action == EditAction.CHANGE_PARAMETERS:
                success, message, changes = self._change_parameters(edited_plan, edit_request)
            elif edit_request.action == EditAction.CHANGE_PRIORITY:
                success, message, changes = self._change_priority(edited_plan, edit_request)
            
            if success:
                # Record edit in history
                self._edit_history.append(edit_request)
                if len(self._edit_history) > self._max_history:
                    self._edit_history = self._edit_history[-self._max_history:]
                
                # Notify callbacks
                for callback in self._on_edit_applied:
                    try:
                        callback(edited_plan, edit_request)
                    except Exception as e:
                        self.error_handler.handle_error(e, "edit_applied_callback")
            
            self.logger.debug(f"Edit completed in {time.time() - start_time:.4f}s")
            
            return EditResult(
                success=success,
                plan=edited_plan if success else None,
                message=message,
                changes=changes
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, f"edit_plan_{plan.id}")
            return EditResult(
                success=False,
                message=str(e)
            )
    
    def _deep_copy_plan(self, plan: TaskPlan) -> TaskPlan:
        """Create a deep copy of a plan"""
        # Create new steps
        new_steps = []
        for step in plan.steps:
            new_step = TaskStep(
                id=step.id,
                action=step.action,
                description=step.description,
                required_apps=list(step.required_apps),
                required_resources=dict(step.required_resources),
                dependencies=list(step.dependencies),
                parameters=dict(step.parameters),
                timeout=step.timeout,
                retry_count=step.retry_count,
                valid=step.valid,
                status=step.status,
                error=step.error,
                result=step.result
            )
            new_steps.append(new_step)
        
        # Create new plan
        new_plan = TaskPlan(
            id=plan.id,
            intent=plan.intent,
            description=plan.description,
            steps=new_steps,
            required_apps=list(plan.required_apps),
            required_resources=dict(plan.required_resources),
            missing_requirements=list(plan.missing_requirements),
            complexity=plan.complexity,
            estimated_duration=plan.estimated_duration,
            priority=plan.priority,
            created_at=plan.created_at
        )
        
        return new_plan
    
    def _add_step(self, plan: TaskPlan, edit_request: EditRequest) -> Tuple[bool, str, List[Dict]]:
        """Add a step to the plan"""
        # Parse step data from value
        step_data = edit_request.value
        
        if not isinstance(step_data, dict):
            return False, "Invalid step data", []
        
        # Create new step
        step_id = f"step_{len(plan.steps) + 1}_{int(time.time())}"
        
        new_step = TaskStep(
            id=step_id,
            action=step_data.get("action", "unknown"),
            description=step_data.get("description", ""),
            required_apps=step_data.get("required_apps", []),
            required_resources=step_data.get("required_resources", {}),
            dependencies=step_data.get("dependencies", []),
            parameters=step_data.get("parameters", {}),
            timeout=step_data.get("timeout", 30),
            retry_count=step_data.get("retry_count", 3)
        )
        
        # Insert at position
        position = edit_request.position if edit_request.position >= 0 else len(plan.steps)
        plan.steps.insert(position, new_step)
        
        # Update dependencies
        self._update_dependencies_after_add(plan, position)
        
        return True, f"Added step {step_id}", [
            {"action": "add_step", "step_id": step_id, "position": position}
        ]
    
    def _remove_step(self, plan: TaskPlan, edit_request: EditRequest) -> Tuple[bool, str, List[Dict]]:
        """Remove a step from the plan"""
        step_id = edit_request.target
        
        # Find step
        step_index = -1
        for i, step in enumerate(plan.steps):
            if step.id == step_id:
                step_index = i
                break
        
        if step_index < 0:
            return False, f"Step {step_id} not found", []
        
        # Remove step
        removed_step = plan.steps[step_index]
        del plan.steps[step_index]
        
        # Update dependencies
        self._update_dependencies_after_remove(plan, step_index, removed_step)
        
        return True, f"Removed step {step_id}", [
            {"action": "remove_step", "step_id": step_id, "position": step_index}
        ]
    
    def _modify_step(self, plan: TaskPlan, edit_request: EditRequest) -> Tuple[bool, str, List[Dict]]:
        """Modify a step in the plan"""
        step_id = edit_request.target
        new_data = edit_request.value
        
        if not isinstance(new_data, dict):
            return False, "Invalid modification data", []
        
        # Find step
        step = None
        for s in plan.steps:
            if s.id == step_id:
                step = s
                break
        
        if not step:
            return False, f"Step {step_id} not found", []
        
        # Apply modifications
        changes = []
        old_values = {}
        
        if "action" in new_data:
            old_values["action"] = step.action
            step.action = new_data["action"]
            changes.append({"field": "action", "old": old_values["action"], "new": step.action})
        
        if "description" in new_data:
            old_values["description"] = step.description
            step.description = new_data["description"]
            changes.append({"field": "description", "old": old_values["description"], "new": step.description})
        
        if "required_apps" in new_data:
            old_values["required_apps"] = list(step.required_apps)
            step.required_apps = new_data["required_apps"]
            changes.append({"field": "required_apps", "old": old_values["required_apps"], "new": step.required_apps})
        
        if "parameters" in new_data:
            old_values["parameters"] = dict(step.parameters)
            step.parameters.update(new_data["parameters"])
            changes.append({"field": "parameters", "old": old_values["parameters"], "new": step.parameters})
        
        if "timeout" in new_data:
            old_values["timeout"] = step.timeout
            step.timeout = new_data["timeout"]
            changes.append({"field": "timeout", "old": old_values["timeout"], "new": step.timeout})
        
        return True, f"Modified step {step_id}", [
            {"action": "modify_step", "step_id": step_id, "changes": changes}
        ]
    
    def _reorder_steps(self, plan: TaskPlan, edit_request: EditRequest) -> Tuple[bool, str, List[Dict]]:
        """Reorder steps in the plan"""
        step_id = edit_request.target
        new_position = edit_request.position
        
        # Find step
        old_position = -1
        for i, step in enumerate(plan.steps):
            if step.id == step_id:
                old_position = i
                break
        
        if old_position < 0:
            return False, f"Step {step_id} not found", []
        
        if new_position < 0 or new_position >= len(plan.steps):
            return False, "Invalid position", []
        
        # Move step
        step = plan.steps[old_position]
        del plan.steps[old_position]
        plan.steps.insert(new_position, step)
        
        # Update dependencies
        self._update_dependencies_after_reorder(plan)
        
        return True, f"Moved step {step_id} from {old_position} to {new_position}", [
            {"action": "reorder_step", "step_id": step_id, "old_position": old_position, "new_position": new_position}
        ]
    
    def _change_parameters(self, plan: TaskPlan, edit_request: EditRequest) -> Tuple[bool, str, List[Dict]]:
        """Change plan parameters"""
        param_name = edit_request.target
        param_value = edit_request.value
        
        # Update plan-level parameters
        if hasattr(plan, param_name):
            old_value = getattr(plan, param_name)
            setattr(plan, param_name, param_value)
            
            return True, f"Changed {param_name} from {old_value} to {param_value}", [
                {"action": "change_parameter", "parameter": param_name, "old": old_value, "new": param_value}
            ]
        
        return False, f"Parameter {param_name} not found", []
    
    def _change_priority(self, plan: TaskPlan, edit_request: EditRequest) -> Tuple[bool, str, List[Dict]]:
        """Change plan priority"""
        try:
            new_priority = TaskPriority[edit_request.value]
            old_priority = plan.priority
            plan.priority = new_priority
            
            return True, f"Changed priority from {old_priority.name} to {new_priority.name}", [
                {"action": "change_priority", "old": old_priority.name, "new": new_priority.name}
            ]
        except KeyError:
            return False, f"Invalid priority: {edit_request.value}", []
    
    def _update_dependencies_after_add(self, plan: TaskPlan, position: int):
        """Validate the added step's dependencies against the real plan."""
        if position < 0 or position >= len(plan.steps):
            return
        
        new_step = plan.steps[position]
        valid_ids = {
            s.id for i, s in enumerate(plan.steps) if i != position
        }
        
        invalid = [d for d in new_step.dependencies if d not in valid_ids]
        if invalid:
            new_step.dependencies = [
                d for d in new_step.dependencies if d in valid_ids
            ]
            self.logger.warning(
                f"Removed invalid dependencies from added step "
                f"{new_step.id}: {', '.join(invalid)}"
            )
    
    def _update_dependencies_after_remove(self, plan: TaskPlan, removed_index: int, removed_step: TaskStep):
        """Update dependencies after removing a step"""
        # Remove dependencies on the deleted step
        for step in plan.steps:
            if removed_step.id in step.dependencies:
                step.dependencies.remove(removed_step.id)
        
        # Re-index dependencies
        for step in plan.steps:
            new_deps = []
            for dep in step.dependencies:
                # Find if dependency still exists
                if any(s.id == dep for s in plan.steps):
                    new_deps.append(dep)
            step.dependencies = new_deps
    
    def _update_dependencies_after_reorder(self, plan: TaskPlan):
        """Check the real dependency order after a reorder and warn."""
        position_by_id = {step.id: i for i, step in enumerate(plan.steps)}
        
        for step in plan.steps:
            step_index = position_by_id.get(step.id, -1)
            for dep_id in step.dependencies:
                dep_index = position_by_id.get(dep_id, -1)
                if dep_index < 0:
                    self.logger.warning(
                        f"Step {step.id} depends on unknown step {dep_id}"
                    )
                elif dep_index > step_index:
                    self.logger.warning(
                        f"Step {step.id} now runs before its dependency "
                        f"{dep_id}; the executor will retry it until the "
                        f"dependency completes"
                    )
    
    async def validate_edit(self, plan: TaskPlan, edit_request: EditRequest) -> Tuple[bool, str]:
        """
        Validate an edit request before applying
        
        Args:
            plan: The task plan
            edit_request: The edit request
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if edit_request.action == EditAction.ADD_STEP:
            step_data = edit_request.value
            if not isinstance(step_data, dict):
                return False, "Invalid step data"
            if "action" not in step_data:
                return False, "Step must have an action"
            return True, ""
        
        elif edit_request.action == EditAction.REMOVE_STEP:
            # Check if step exists
            step_id = edit_request.target
            if not any(s.id == step_id for s in plan.steps):
                return False, f"Step {step_id} not found"
            
            # Check if step has dependencies
            step = next(s for s in plan.steps if s.id == step_id)
            if any(s.id == step_id for s in plan.steps if s != step):
                # Other steps depend on this step
                dependents = [s.id for s in plan.steps if step.id in s.dependencies]
                if dependents:
                    return False, f"Cannot remove step {step_id} - required by: {', '.join(dependents)}"
            
            return True, ""
        
        elif edit_request.action == EditAction.MODIFY_STEP:
            step_id = edit_request.target
            if not any(s.id == step_id for s in plan.steps):
                return False, f"Step {step_id} not found"
            return True, ""
        
        elif edit_request.action == EditAction.REORDER_STEPS:
            step_id = edit_request.target
            new_position = edit_request.position
            if not any(s.id == step_id for s in plan.steps):
                return False, f"Step {step_id} not found"
            if new_position < 0 or new_position >= len(plan.steps):
                return False, "Invalid position"
            return True, ""
        
        elif edit_request.action == EditAction.CHANGE_PARAMETERS:
            if not hasattr(plan, edit_request.target):
                return False, f"Parameter {edit_request.target} not found"
            return True, ""
        
        elif edit_request.action == EditAction.CHANGE_PRIORITY:
            try:
                TaskPriority[edit_request.value]
                return True, ""
            except KeyError:
                return False, f"Invalid priority: {edit_request.value}"
        
        return False, f"Unknown edit action: {edit_request.action}"
    
    # Callback Registration
    
    def on_preview_generated(self, callback: Callable):
        """Register preview generated callback"""
        self._on_preview_generated.append(callback)
    
    def on_edit_applied(self, callback: Callable):
        """Register edit applied callback"""
        self._on_edit_applied.append(callback)
    
    # Utility Methods
    
    async def get_edit_history(self, limit: int = 10) -> List[EditRequest]:
        """Get recent edit history"""
        return list(reversed(self._edit_history[-limit:]))
    
    async def clear_preview_cache(self):
        """Clear preview cache"""
        self._preview_cache.clear()
        self.logger.info("Preview cache cleared")
    
    async def get_cached_preview(self, plan_id: str) -> Optional[PreviewData]:
        """Get cached preview for a plan"""
        return self._preview_cache.get(plan_id)
