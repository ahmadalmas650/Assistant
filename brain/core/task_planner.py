"""
Task Planner Module
Creates detailed execution plans for commands
"""

import json
import time
import re
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import asyncio

from ..utils.logger import Logger
from ..memory.knowledge_base import KnowledgeBase


class TaskComplexity(Enum):
    """Task complexity levels"""
    VERY_LOW = auto()
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    VERY_HIGH = auto()


class StepStatus(Enum):
    """Step execution status"""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass
class TaskStep:
    """A single step in a task plan"""
    id: str
    action: str
    description: str
    required_apps: List[str] = field(default_factory=list)
    required_resources: Dict[str, float] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    parameters: Dict = field(default_factory=dict)
    timeout: int = 30  # seconds
    retry_count: int = 3
    valid: bool = True
    status: StepStatus = StepStatus.PENDING
    error: Optional[str] = None
    result: Optional[Any] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "action": self.action,
            "description": self.description,
            "required_apps": self.required_apps,
            "required_resources": self.required_resources,
            "dependencies": self.dependencies,
            "parameters": self.parameters,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "valid": self.valid,
            "status": self.status.name,
            "error": self.error,
            "result": self.result
        }


@dataclass
class TaskPlan:
    """Complete task execution plan"""
    id: str
    intent: str
    description: str
    steps: List[TaskStep] = field(default_factory=list)
    required_apps: List[str] = field(default_factory=list)
    required_resources: Dict[str, float] = field(default_factory=dict)
    missing_requirements: List[str] = field(default_factory=list)
    complexity: TaskComplexity = TaskComplexity.LOW
    estimated_duration: float = 0.0  # seconds
    priority: int = 0  # 0-10 scale
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "intent": self.intent,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "required_apps": self.required_apps,
            "required_resources": self.required_resources,
            "missing_requirements": self.missing_requirements,
            "complexity": self.complexity.name,
            "estimated_duration": self.estimated_duration,
            "priority": self.priority,
            "created_at": self.created_at
        }


class TaskPlanner:
    """
    Creates detailed execution plans for commands
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        
        # Task templates
        self._templates = self._load_templates()
        
        # Knowledge base for task planning
        self.knowledge_base = KnowledgeBase(config, logger)
        
        # Step counter
        self._step_counter = 0
    
    def _load_templates(self) -> Dict:
        """Load task templates"""
        return {
            "upload_video": {
                "intent": "upload_video",
                "description": "Upload video to YouTube or other platform",
                "steps": [
                    {
                        "action": "select_file",
                        "description": "Select video file",
                        "required_apps": ["file_manager"],
                        "parameters": {"file_type": "video"}
                    },
                    {
                        "action": "check_metadata",
                        "description": "Check video metadata",
                        "required_apps": [],
                        "parameters": {"check": ["title", "description", "thumbnail"]}
                    },
                    {
                        "action": "edit_if_needed",
                        "description": "Edit video if required",
                        "required_apps": ["com.kinemaster"],
                        "dependencies": ["check_metadata"],
                        "parameters": {"auto_edit": True}
                    },
                    {
                        "action": "create_thumbnail",
                        "description": "Create thumbnail if missing",
                        "required_apps": ["thumbnail_maker"],
                        "dependencies": ["check_metadata"],
                        "parameters": {"auto_generate": True}
                    },
                    {
                        "action": "upload",
                        "description": "Upload video to platform",
                        "required_apps": ["com.google.android.youtube"],
                        "dependencies": ["select_file", "check_metadata"],
                        "parameters": {"platform": "youtube"}
                    },
                    {
                        "action": "verify_upload",
                        "description": "Verify upload success",
                        "required_apps": ["com.google.android.youtube"],
                        "dependencies": ["upload"]
                    }
                ],
                "required_apps": [
                    "com.google.android.youtube",
                    "com.kinemaster"
                ],
                "complexity": TaskComplexity.HIGH,
                "estimated_duration": 300.0
            },
            
            "edit_photo": {
                "intent": "edit_photo",
                "description": "Edit a photo using installed apps",
                "steps": [
                    {
                        "action": "select_file",
                        "description": "Select photo file",
                        "required_apps": ["file_manager"],
                        "parameters": {"file_type": "image"}
                    },
                    {
                        "action": "open_editor",
                        "description": "Open photo in editor",
                        "required_apps": ["com.kinemaster", "photo_editor"],
                        "dependencies": ["select_file"],
                        "parameters": {"auto_edit": False}
                    },
                    {
                        "action": "apply_edits",
                        "description": "Apply requested edits",
                        "required_apps": ["photo_editor"],
                        "dependencies": ["open_editor"]
                    },
                    {
                        "action": "save_file",
                        "description": "Save edited photo",
                        "required_apps": ["photo_editor"],
                        "dependencies": ["apply_edits"]
                    }
                ],
                "required_apps": ["photo_editor"],
                "complexity": TaskComplexity.MEDIUM,
                "estimated_duration": 120.0
            },
            
            "search_information": {
                "intent": "search",
                "description": "Search for information across multiple sources",
                "steps": [
                    {
                        "action": "extract_query",
                        "description": "Extract search query",
                        "required_apps": []
                    },
                    {
                        "action": "search_chatgpt",
                        "description": "Search in ChatGPT",
                        "required_apps": ["com.chatgpt"],
                        "dependencies": ["extract_query"]
                    },
                    {
                        "action": "search_deepseek",
                        "description": "Search in DeepSeek",
                        "required_apps": ["com.deepseek"],
                        "dependencies": ["extract_query"]
                    },
                    {
                        "action": "search_youtube",
                        "description": "Search in YouTube",
                        "required_apps": ["com.google.android.youtube"],
                        "dependencies": ["extract_query"]
                    },
                    {
                        "action": "search_grok",
                        "description": "Search in Grok",
                        "required_apps": ["com.grok"],
                        "dependencies": ["extract_query"]
                    },
                    {
                        "action": "merge_results",
                        "description": "Merge results from all sources",
                        "required_apps": [],
                        "dependencies": [
                            "search_chatgpt",
                            "search_deepseek", 
                            "search_youtube",
                            "search_grok"
                        ]
                    },
                    {
                        "action": "present_results",
                        "description": "Present merged results",
                        "required_apps": [],
                        "dependencies": ["merge_results"]
                    }
                ],
                "required_apps": [
                    "com.chatgpt",
                    "com.deepseek",
                    "com.google.android.youtube",
                    "com.grok"
                ],
                "complexity": TaskComplexity.MEDIUM,
                "estimated_duration": 60.0
            },
            
            "take_screenshot": {
                "intent": "screenshot",
                "description": "Take a screenshot",
                "steps": [
                    {
                        "action": "capture_screen",
                        "description": "Capture the screen",
                        "required_apps": [],
                        "required_resources": {"accessibility": 1.0}
                    },
                    {
                        "action": "save_screenshot",
                        "description": "Save screenshot to storage",
                        "required_apps": [],
                        "dependencies": ["capture_screen"]
                    }
                ],
                "required_apps": [],
                "required_resources": {"accessibility": 1.0},
                "complexity": TaskComplexity.LOW,
                "estimated_duration": 5.0
            },
            
            "extract_text": {
                "intent": "ocr",
                "description": "Extract text from image using OCR",
                "steps": [
                    {
                        "action": "select_image",
                        "description": "Select image for OCR",
                        "required_apps": ["file_manager"],
                        "parameters": {"file_type": "image"}
                    },
                    {
                        "action": "run_ocr",
                        "description": "Run OCR on image",
                        "required_apps": [],
                        "dependencies": ["select_image"],
                        "required_resources": {"memory": 0.5}
                    },
                    {
                        "action": "return_text",
                        "description": "Return extracted text",
                        "required_apps": [],
                        "dependencies": ["run_ocr"]
                    }
                ],
                "required_apps": [],
                "required_resources": {"memory": 0.5},
                "complexity": TaskComplexity.LOW,
                "estimated_duration": 10.0
            }
        }
    
    async def plan(self, command_data: Dict) -> TaskPlan:
        """
        Create a task plan for a command
        
        Args:
            command_data: Parsed command data
            
        Returns:
            TaskPlan object
        """
        start_time = time.time()
        
        intent = command_data.get("intent", "")
        entities = command_data.get("entities", {})
        text = command_data.get("text", "")
        
        self.logger.info(f"Planning task for intent: {intent}")
        
        # Check for exact template match
        if intent in self._templates:
            template = self._templates[intent]
            plan = self._create_plan_from_template(template, command_data)
            self.logger.info(f"Used template for {intent}")
            return plan
        
        # Try to match with variations
        matched_template = self._find_matching_template(intent, text)
        if matched_template:
            plan = self._create_plan_from_template(matched_template, command_data)
            self.logger.info(f"Matched template for {intent}")
            return plan
        
        # Create custom plan based on intent and entities
        plan = await self._create_custom_plan(command_data)
        self.logger.info(f"Created custom plan for {intent}")
        return plan
    
    def _find_matching_template(self, intent: str, text: str) -> Optional[Dict]:
        """Find matching template with variations"""
        # Check for partial matches
        for template_name, template in self._templates.items():
            if intent in template_name or template_name in intent:
                return template
            
            # Check if any step actions match
            for step in template.get("steps", []):
                if step.get("action") == intent:
                    return template
        
        # Check text for keywords
        text_lower = text.lower()
        for template_name, template in self._templates.items():
            if template_name in text_lower:
                return template
        
        return None
    
    def _create_plan_from_template(self, template: Dict, command_data: Dict) -> TaskPlan:
        """Create plan from template"""
        intent = command_data.get("intent", "")
        entities = command_data.get("entities", {})
        
        # Generate unique ID
        plan_id = f"plan_{int(time.time())}_{self._step_counter}"
        self._step_counter += 1
        
        # Create steps
        steps = []
        step_map = {}  # For dependency resolution
        
        for step_data in template.get("steps", []):
            step = self._create_step_from_template(step_data, command_data, step_map)
            steps.append(step)
            step_map[step.id] = step
        
        # Resolve dependencies
        self._resolve_dependencies(steps, step_map)
        
        # Calculate required apps and resources
        required_apps = list(set(template.get("required_apps", [])))
        required_resources = template.get("required_resources", {})
        
        # Check for missing requirements
        missing_requirements = self._check_missing_requirements(
            steps, required_apps, required_resources, command_data
        )
        
        # Determine complexity
        complexity = self._get_complexity(
            template.get("complexity", TaskComplexity.MEDIUM),
            len(steps),
            missing_requirements
        )
        
        # Calculate estimated duration
        estimated_duration = template.get("estimated_duration", 0)
        if estimated_duration == 0:
            estimated_duration = sum(s.timeout for s in steps)
        
        plan = TaskPlan(
            id=plan_id,
            intent=intent,
            description=template.get("description", intent),
            steps=steps,
            required_apps=required_apps,
            required_resources=required_resources,
            missing_requirements=missing_requirements,
            complexity=complexity,
            estimated_duration=estimated_duration
        )
        
        return plan
    
    def _create_step_from_template(self, step_data: Dict, command_data: Dict, 
                                   step_map: Dict) -> TaskStep:
        """Create a step from template data"""
        step_id = f"step_{self._step_counter}_{step_data.get('action', 'unknown')}"
        self._step_counter += 1
        
        # Resolve dependencies
        dependencies = []
        for dep in step_data.get("dependencies", []):
            if dep in step_map:
                dependencies.append(step_map[dep].id)
            else:
                dependencies.append(dep)
        
        # Create step
        step = TaskStep(
            id=step_id,
            action=step_data.get("action", "unknown"),
            description=step_data.get("description", step_data.get("action", "")),
            required_apps=step_data.get("required_apps", []),
            required_resources=step_data.get("required_resources", {}),
            dependencies=dependencies,
            parameters=self._resolve_parameters(step_data.get("parameters", {}), command_data),
            timeout=step_data.get("timeout", 30),
            retry_count=step_data.get("retry_count", 3)
        )
        
        return step
    
    def _resolve_parameters(self, template_params: Dict, command_data: Dict) -> Dict:
        """Resolve template parameters with command data"""
        resolved = {}
        entities = command_data.get("entities", {})
        
        for key, value in template_params.items():
            if isinstance(value, str) and value.startswith("entity:"):
                # Reference to entity
                entity_type = value[7:]
                if entity_type in entities:
                    resolved[key] = entities[entity_type]
                else:
                    resolved[key] = None
            elif isinstance(value, str) and value.startswith("intent:"):
                # Reference to intent
                resolved[key] = command_data.get("intent", "")
            else:
                resolved[key] = value
        
        return resolved
    
    def _resolve_dependencies(self, steps: List[TaskStep], step_map: Dict):
        """Resolve step dependencies"""
        # This is a placeholder - in a real implementation, we'd do topological sorting
        pass
    
    def _check_missing_requirements(self, steps: List[TaskStep], 
                                   required_apps: List[str], 
                                   required_resources: Dict[str, float],
                                   command_data: Dict) -> List[str]:
        """Check for missing requirements"""
        missing = []
        
        # Check required apps
        available_apps = self.config.allowed_apps
        for app in required_apps:
            if app not in available_apps:
                missing.append(f"app:{app}")
        
        # Check required resources
        available_resources = self._get_available_resources()
        for resource, amount in required_resources.items():
            available = available_resources.get(resource, 0)
            if available < amount:
                missing.append(f"resource:{resource}")
        
        # Check step requirements
        for step in steps:
            for app in step.required_apps:
                if app not in available_apps and app not in required_apps:
                    missing.append(f"app:{app}")
            
            for resource, amount in step.required_resources.items():
                available = available_resources.get(resource, 0)
                if available < amount and resource not in required_resources:
                    missing.append(f"resource:{resource}")
        
        # Check entities
        entities = command_data.get("entities", {})
        intent = command_data.get("intent", "")
        
        if intent == "upload_video":
            if "file" not in entities:
                missing.append("entity:file")
            if "platform" not in entities:
                missing.append("entity:platform")
        
        elif intent == "edit_photo":
            if "file" not in entities:
                missing.append("entity:file")
        
        elif intent == "send_message":
            if "recipient" not in entities:
                missing.append("entity:recipient")
            if "content" not in entities:
                missing.append("entity:content")
        
        return list(set(missing))
    
    def _get_complexity(self, template_complexity: TaskComplexity, 
                       step_count: int, missing_requirements: List[str]) -> TaskComplexity:
        """Determine overall complexity"""
        # Start with template complexity
        complexity = template_complexity
        
        # Adjust based on step count
        if step_count > 10:
            complexity = TaskComplexity.VERY_HIGH
        elif step_count > 7:
            complexity = TaskComplexity.HIGH
        elif step_count > 4:
            if complexity.value < TaskComplexity.MEDIUM.value:
                complexity = TaskComplexity.MEDIUM
        
        # Adjust for missing requirements
        if len(missing_requirements) > 3:
            complexity = TaskComplexity.VERY_HIGH
        elif len(missing_requirements) > 1:
            if complexity.value < TaskComplexity.HIGH.value:
                complexity = TaskComplexity.HIGH
        
        return complexity
    
    def _get_available_resources(self) -> Dict[str, float]:
        """Get available system resources"""
        return {
            "memory": 2.0,
            "cpu": 0.8,
            "storage": 10.0,
            "network": 1.0,
            "accessibility": 1.0
        }
    
    async def _create_custom_plan(self, command_data: Dict) -> TaskPlan:
        """Create a custom plan based on intent and entities"""
        intent = command_data.get("intent", "")
        entities = command_data.get("entities", {})
        text = command_data.get("text", "")
        
        plan_id = f"custom_plan_{int(time.time())}_{self._step_counter}"
        self._step_counter += 1
        
        # Create basic steps based on intent
        steps = []
        required_apps = []
        
        # Intent-based step generation
        if intent in ["upload", "post", "share"]:
            steps.extend([
                TaskStep(
                    id=f"step_{self._step_counter}",
                    action="select_content",
                    description="Select content to upload",
                    parameters={"content_type": entities.get("content_type", "file")}
                ),
                TaskStep(
                    id=f"step_{self._step_counter + 1}",
                    action="upload",
                    description="Upload content",
                    dependencies=[steps[-1].id],
                    parameters={"platform": entities.get("platform", "default")}
                )
            ])
            self._step_counter += 2
            
        elif intent in ["edit", "modify", "change"]:
            steps.extend([
                TaskStep(
                    id=f"step_{self._step_counter}",
                    action="select_file",
                    description="Select file to edit",
                    parameters={"file_type": entities.get("file_type", "unknown")}
                ),
                TaskStep(
                    id=f"step_{self._step_counter + 1}",
                    action="open_editor",
                    description="Open in editor",
                    dependencies=[steps[-1].id],
                    required_apps=["editor"]
                ),
                TaskStep(
                    id=f"step_{self._step_counter + 2}",
                    action="apply_edits",
                    description="Apply edits",
                    dependencies=[steps[-1].id]
                )
            ])
            self._step_counter += 3
            required_apps = ["editor"]
            
        elif intent in ["search", "find", "look_up"]:
            steps.extend([
                TaskStep(
                    id=f"step_{self._step_counter}",
                    action="extract_query",
                    description="Extract search query"
                ),
                TaskStep(
                    id=f"step_{self._step_counter + 1}",
                    action="search",
                    description="Search for information",
                    dependencies=[steps[-1].id],
                    parameters={"sources": ["chatgpt", "deepseek", "youtube", "grok"]}
                ),
                TaskStep(
                    id=f"step_{self._step_counter + 2}",
                    action="present_results",
                    description="Present search results",
                    dependencies=[steps[-1].id]
                )
            ])
            self._step_counter += 3
            required_apps = ["com.chatgpt", "com.deepseek", "com.google.android.youtube", "com.grok"]
            
        elif intent in ["screenshot", "capture"]:
            steps.extend([
                TaskStep(
                    id=f"step_{self._step_counter}",
                    action="capture_screen",
                    description="Capture screenshot",
                    required_resources={"accessibility": 1.0}
                ),
                TaskStep(
                    id=f"step_{self._step_counter + 1}",
                    action="save_screenshot",
                    description="Save screenshot",
                    dependencies=[steps[-1].id]
                )
            ])
            self._step_counter += 2
            
        elif intent in ["ocr", "extract_text"]:
            steps.extend([
                TaskStep(
                    id=f"step_{self._step_counter}",
                    action="select_image",
                    description="Select image for OCR",
                    parameters={"file_type": "image"}
                ),
                TaskStep(
                    id=f"step_{self._step_counter + 1}",
                    action="run_ocr",
                    description="Run OCR",
                    dependencies=[steps[-1].id],
                    required_resources={"memory": 0.5}
                ),
                TaskStep(
                    id=f"step_{self._step_counter + 2}",
                    action="return_text",
                    description="Return extracted text",
                    dependencies=[steps[-1].id]
                )
            ])
            self._step_counter += 3
        else:
            # Generic task
            steps.append(TaskStep(
                id=f"step_{self._step_counter}",
                action="execute_intent",
                description=f"Execute {intent}",
                parameters={"intent": intent, "entities": entities}
            ))
            self._step_counter += 1
        
        # Check for missing requirements
        missing_requirements = self._check_missing_requirements(
            steps, required_apps, {}, command_data
        )
        
        # Determine complexity
        complexity = self._get_complexity(
            TaskComplexity.MEDIUM, len(steps), missing_requirements
        )
        
        # Calculate estimated duration
        estimated_duration = sum(s.timeout for s in steps)
        
        plan = TaskPlan(
            id=plan_id,
            intent=intent,
            description=text,
            steps=steps,
            required_apps=required_apps,
            required_resources={},
            missing_requirements=missing_requirements,
            complexity=complexity,
            estimated_duration=estimated_duration
        )
        
        return plan
    
    async def optimize_plan(self, plan: TaskPlan) -> TaskPlan:
        """
        Optimize a task plan based on available resources and knowledge
        
        Args:
            plan: The task plan to optimize
            
        Returns:
            Optimized task plan
        """
        # This would integrate with knowledge base and resource monitor
        # For now, just return the original plan
        return plan
    
    async def validate_plan(self, plan: TaskPlan) -> Tuple[bool, List[str]]:
        """
        Validate a task plan
        
        Args:
            plan: The task plan to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check for circular dependencies
        if self._has_circular_dependencies(plan.steps):
            errors.append("Circular dependencies detected")
        
        # Check for missing dependencies
        step_ids = {s.id for s in plan.steps}
        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    errors.append(f"Step {step.id} has missing dependency: {dep}")
        
        # Check resource requirements
        available_resources = self._get_available_resources()
        for resource, amount in plan.required_resources.items():
            available = available_resources.get(resource, 0)
            if available < amount:
                errors.append(f"Insufficient resource: {resource}")
        
        # Check app requirements
        available_apps = self.config.allowed_apps
        for app in plan.required_apps:
            if app not in available_apps:
                errors.append(f"Missing app: {app}")
        
        return len(errors) == 0, errors
    
    def _has_circular_dependencies(self, steps: List[TaskStep]) -> bool:
        """Check for circular dependencies in steps"""
        # This is a simplified check - a full implementation would use graph algorithms
        for step in steps:
            visited = set()
            if self._check_circular(step.id, step.dependencies, steps, visited):
                return True
        return False
    
    def _check_circular(self, step_id: str, dependencies: List[str], 
                       steps: List[TaskStep], visited: Set[str]) -> bool:
        """Recursive check for circular dependencies"""
        if step_id in visited:
            return True
        
        visited.add(step_id)
        
        # Find step by ID
        step_map = {s.id: s for s in steps}
        
        for dep in dependencies:
            if dep in step_map:
                if self._check_circular(dep, step_map[dep].dependencies, steps, visited.copy()):
                    return True
        
        return False
    
    async def get_plan_preview(self, plan: TaskPlan) -> Dict:
        """
        Get a human-readable preview of a task plan
        
        Args:
            plan: The task plan
            
        Returns:
            Dictionary with preview information
        """
        return {
            "id": plan.id,
            "intent": plan.intent,
            "description": plan.description,
            "complexity": plan.complexity.name.replace("_", " ").title(),
            "estimated_duration": f"{plan.estimated_duration:.1f} seconds",
            "step_count": len(plan.steps),
            "required_apps": plan.required_apps,
            "missing_requirements": plan.missing_requirements,
            "steps": [
                {
                    "id": s.id,
                    "action": s.action,
                    "description": s.description,
                    "dependencies": s.dependencies,
                    "required_apps": s.required_apps
                }
                for s in plan.steps
            ]
        }
