"""
Decision Maker Module
Makes intelligent decisions based on available information and confidence levels
"""

import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum, auto
import random

from ..utils.logger import Logger
from .confidence_engine import ConfidenceEngine


class DecisionType(Enum):
    """Types of decisions"""
    EXECUTE = auto()      # Execute the task
    ASK_USER = auto()     # Ask user for clarification
    REJECT = auto()       # Reject the command
    DEFER = auto()        # Defer to later
    LEARN = auto()        # Need to learn first
    MERGE = auto()        # Merge with existing knowledge


class DecisionLevel(Enum):
    """Decision confidence levels"""
    CRITICAL = auto()     # Must execute
    HIGH = auto()         # High confidence
    MEDIUM = auto()       # Medium confidence
    LOW = auto()          # Low confidence
    UNKNOWN = auto()      # Unknown


@dataclass
class Decision:
    """Decision data structure"""
    action: DecisionType
    level: DecisionLevel
    confidence: float
    reason: str
    alternatives: List[str] = None
    required_info: List[str] = None
    metadata: Dict = None
    
    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []
        if self.required_info is None:
            self.required_info = []
        if self.metadata is None:
            self.metadata = {}


class DecisionMaker:
    """
    Makes decisions based on command analysis, confidence, and context
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.confidence_engine = ConfidenceEngine(config, logger)
        
        # Decision rules and thresholds
        self._rules = self._load_decision_rules()
        
        # Context tracking
        self._context_history = []
        self._max_history = 100
    
    def _load_decision_rules(self) -> Dict:
        """Load decision rules"""
        return {
            "min_confidence_execute": 0.7,
            "min_confidence_ask": 0.4,
            "min_confidence_reject": 0.2,
            "critical_commands": [
                "emergency",
                "stop",
                "cancel",
                "shutdown",
                "reboot"
            ],
            "dangerous_commands": [
                "delete",
                "format",
                "factory reset",
                "uninstall",
                "root",
                "hack"
            ],
            "sensitive_actions": [
                "send money",
                "transfer",
                "payment",
                "purchase",
                "buy"
            ],
            "learning_required": [
                "learn",
                "teach",
                "remember",
                "new task"
            ]
        }
    
    def make_decision(self, command_data: Dict, task_plan: Dict, 
                     confidence: Optional[float] = None) -> Decision:
        """
        Make a decision based on command and task plan
        
        Args:
            command_data: Parsed command data
            task_plan: Planned task execution
            confidence: Pre-calculated confidence (optional)
            
        Returns:
            Decision object
        """
        start_time = time.time()
        
        # Calculate confidence if not provided
        if confidence is None:
            confidence = self.confidence_engine.calculate_confidence(command_data, task_plan)
        
        self.logger.debug(f"Making decision for command: {command_data.get('intent', 'unknown')}")
        self.logger.debug(f"Confidence: {confidence:.2f}")
        
        # Check for critical commands (always execute)
        command_text = command_data.get("text", "").lower()
        if self._is_critical_command(command_text):
            decision = Decision(
                action=DecisionType.EXECUTE,
                level=DecisionLevel.CRITICAL,
                confidence=1.0,
                reason="Critical command detected"
            )
            self.logger.info("Critical command - immediate execution")
            return decision
        
        # Check for dangerous commands
        if self._is_dangerous_command(command_text):
            decision = Decision(
                action=DecisionType.REJECT,
                level=DecisionLevel.HIGH,
                confidence=confidence,
                reason="Dangerous command detected",
                alternatives=["Please rephrase your request safely"]
            )
            self.logger.warning("Dangerous command rejected")
            return decision
        
        # Check for sensitive actions
        if self._is_sensitive_action(command_text):
            decision = Decision(
                action=DecisionType.ASK_USER,
                level=DecisionLevel.MEDIUM,
                confidence=confidence,
                reason="Sensitive action requires confirmation",
                required_info=["Please confirm you want to proceed"]
            )
            self.logger.info("Sensitive action - user confirmation required")
            return decision
        
        # Check for learning required
        if self._is_learning_required(command_text):
            decision = Decision(
                action=DecisionType.LEARN,
                level=DecisionLevel.MEDIUM,
                confidence=confidence,
                reason="Learning required for this task",
                required_info=["What should I learn about this?"]
            )
            self.logger.info("Learning required for this command")
            return decision
        
        # Make decision based on confidence
        if confidence >= self._rules["min_confidence_execute"]:
            decision = Decision(
                action=DecisionType.EXECUTE,
                level=self._get_decision_level(confidence),
                confidence=confidence,
                reason=f"High confidence ({confidence:.2f}) in task execution"
            )
            self.logger.info(f"High confidence - executing task")
            
        elif confidence >= self._rules["min_confidence_ask"]:
            # Need more information
            missing_info = self._identify_missing_info(command_data, task_plan)
            decision = Decision(
                action=DecisionType.ASK_USER,
                level=self._get_decision_level(confidence),
                confidence=confidence,
                reason=f"Medium confidence ({confidence:.2f}) - needs clarification",
                required_info=missing_info
            )
            self.logger.info(f"Medium confidence - asking for clarification")
            
        else:
            # Low confidence - reject or defer
            if confidence >= self._rules["min_confidence_reject"]:
                decision = Decision(
                    action=DecisionType.DEFER,
                    level=DecisionLevel.LOW,
                    confidence=confidence,
                    reason=f"Low confidence ({confidence:.2f}) - deferring task",
                    alternatives=["Please provide more details"]
                )
            else:
                decision = Decision(
                    action=DecisionType.REJECT,
                    level=DecisionLevel.UNKNOWN,
                    confidence=confidence,
                    reason=f"Very low confidence ({confidence:.2f}) - cannot execute"
                )
            self.logger.warning(f"Low confidence - task deferred/rejected")
        
        # Add alternatives based on task type
        decision.alternatives = self._get_alternatives(command_data, task_plan, confidence)
        
        # Add metadata
        decision.metadata = {
            "decision_time": time.time() - start_time,
            "command_type": command_data.get("intent", "unknown"),
            "task_complexity": task_plan.get("complexity", "low"),
            "context": self._get_context_summary()
        }
        
        return decision
    
    def _is_critical_command(self, command_text: str) -> bool:
        """Check if command is critical"""
        for critical in self._rules["critical_commands"]:
            if critical in command_text:
                return True
        return False
    
    def _is_dangerous_command(self, command_text: str) -> bool:
        """Check if command is dangerous"""
        for dangerous in self._rules["dangerous_commands"]:
            if dangerous in command_text:
                return True
        return False
    
    def _is_sensitive_action(self, command_text: str) -> bool:
        """Check if command involves sensitive actions"""
        for sensitive in self._rules["sensitive_actions"]:
            if sensitive in command_text:
                return True
        return False
    
    def _is_learning_required(self, command_text: str) -> bool:
        """Check if command requires learning"""
        for learn in self._rules["learning_required"]:
            if learn in command_text:
                return True
        return False
    
    def _get_decision_level(self, confidence: float) -> DecisionLevel:
        """Get decision level based on confidence"""
        if confidence >= 0.9:
            return DecisionLevel.CRITICAL
        elif confidence >= 0.7:
            return DecisionLevel.HIGH
        elif confidence >= 0.5:
            return DecisionLevel.MEDIUM
        elif confidence >= 0.3:
            return DecisionLevel.LOW
        else:
            return DecisionLevel.UNKNOWN
    
    def _identify_missing_info(self, command_data: Dict, task_plan: Dict) -> List[str]:
        """Identify what information is missing"""
        missing = []
        
        # Check command intent
        intent = command_data.get("intent", "")
        entities = command_data.get("entities", {})
        
        # Common missing information patterns
        if intent in ["upload_video", "post_content"]:
            if "file" not in entities:
                missing.append("Which file should I upload/post?")
            if "platform" not in entities:
                missing.append("Where should I upload/post this?")
            if intent == "upload_video":
                if "title" not in entities:
                    missing.append("What title should I use?")
                if "description" not in entities:
                    missing.append("What description should I use?")
        
        elif intent in ["edit_video", "edit_photo"]:
            if "file" not in entities:
                missing.append("Which file should I edit?")
            if "app" not in entities:
                missing.append("Which app should I use for editing?")
        
        elif intent in ["send_message", "email"]:
            if "recipient" not in entities:
                missing.append("Who should I send this to?")
            if "content" not in entities:
                missing.append("What message should I send?")
        
        elif intent == "search":
            if "query" not in entities:
                missing.append("What should I search for?")
        
        # Check task plan for missing steps
        if task_plan.get("missing_requirements"):
            for req in task_plan["missing_requirements"]:
                missing.append(f"Missing: {req}")
        
        # Remove duplicates
        return list(set(missing))
    
    def _get_alternatives(self, command_data: Dict, task_plan: Dict, 
                         confidence: float) -> List[str]:
        """Get alternative actions or suggestions"""
        alternatives = []
        intent = command_data.get("intent", "")
        
        # Common alternatives
        if intent == "upload_video":
            alternatives.extend([
                "I can help you edit the video first",
                "Would you like me to create a thumbnail?",
                "Should I optimize the video for YouTube?"
            ])
        
        elif intent == "edit_photo":
            alternatives.extend([
                "I can use Kinemaster for advanced editing",
                "Would you like me to apply filters?",
                "Should I crop or resize the image?"
            ])
        
        elif intent == "search":
            alternatives.extend([
                "I can search multiple sources for better results",
                "Would you like me to summarize the results?",
                "Should I compare information from different apps?"
            ])
        
        # Add confidence-based alternatives
        if confidence < 0.6:
            alternatives.append("Please provide more specific instructions")
        
        return alternatives
    
    def _get_context_summary(self) -> Dict:
        """Get summary of recent context"""
        # Return last few context items
        return {
            "recent_actions": self._context_history[-5:] if self._context_history else []
        }
    
    def add_context(self, context_data: Dict):
        """Add to context history"""
        self._context_history.append(context_data)
        if len(self._context_history) > self._max_history:
            self._context_history = self._context_history[-self._max_history:]
    
    def clear_context(self):
        """Clear context history"""
        self._context_history = []
    
    async def make_async_decision(self, command_data: Dict, task_plan: Dict) -> Decision:
        """
        Async version of make_decision (for future use)
        """
        # Currently same as sync version, but can be extended
        return self.make_decision(command_data, task_plan)
    
    def evaluate_risk(self, command_data: Dict) -> float:
        """
        Evaluate risk level of a command (0-1 scale)
        """
        risk_score = 0.0
        command_text = command_data.get("text", "").lower()
        
        # Check for dangerous patterns
        for dangerous in self._rules["dangerous_commands"]:
            if dangerous in command_text:
                risk_score += 0.5
        
        for sensitive in self._rules["sensitive_actions"]:
            if sensitive in command_text:
                risk_score += 0.3
        
        # Check entities
        entities = command_data.get("entities", {})
        if "password" in entities or "credit_card" in entities:
            risk_score += 0.4
        
        # Normalize
        return min(risk_score, 1.0)
    
    def get_decision_explanation(self, decision: Decision) -> str:
        """
        Get human-readable explanation of a decision
        """
        explanations = {
            DecisionType.EXECUTE: f"I will execute this task with {decision.confidence*100:.1f}% confidence.",
            DecisionType.ASK_USER: f"I need more information to proceed ({decision.confidence*100:.1f}% confidence).",
            DecisionType.REJECT: f"I cannot execute this task ({decision.confidence*100:.1f}% confidence).",
            DecisionType.DEFER: f"I will defer this task for now ({decision.confidence*100:.1f}% confidence).",
            DecisionType.LEARN: f"I need to learn about this first ({decision.confidence*100:.1f}% confidence).",
            DecisionType.MERGE: f"I will merge this with existing knowledge ({decision.confidence*100:.1f}% confidence)."
        }
        
        base = explanations.get(decision.action, "Unknown decision type")
        
        if decision.reason:
            base += f" Reason: {decision.reason}"
        
        if decision.required_info:
            base += f" Required info: {', '.join(decision.required_info)}"
        
        return base
