"""
Confidence Engine Module
Calculates confidence levels for decisions and actions
"""

import json
import time
import math
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from collections import defaultdict

from ..utils.logger import Logger


@dataclass
class ConfidenceScore:
    """Confidence score for a specific aspect"""
    aspect: str
    score: float  # 0-1 scale
    weight: float = 1.0
    explanation: str = ""


@dataclass
class ConfidenceResult:
    """Complete confidence calculation result"""
    overall_score: float
    scores: List[ConfidenceScore]
    explanation: str
    factors: Dict[str, Any]


class ConfidenceEngine:
    """
    Calculates confidence levels for various operations
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        
        # Weight configurations
        self._weights = {
            "intent_recognition": 0.3,
            "entity_extraction": 0.2,
            "task_feasibility": 0.25,
            "knowledge_availability": 0.15,
            "resource_availability": 0.1,
            "historical_success": 0.1,
            "user_preference": 0.05,
            "app_availability": 0.2,
            "privacy_compliance": 0.15
        }
        
        # Historical data
        self._success_rates = defaultdict(lambda: {"success": 0, "total": 0})
        self._knowledge_coverage = defaultdict(float)
        
        # Real recorded user preferences per intent
        self._user_preferences = defaultdict(
            lambda: {"preferred": 0, "total": 0}
        )
    
    def calculate_confidence(self, command_data: Dict, task_plan: Dict) -> float:
        """
        Calculate overall confidence score for a command and task plan
        
        Args:
            command_data: Parsed command data
            task_plan: Planned task execution
            
        Returns:
            Confidence score (0-1)
        """
        result = self.calculate_confidence_detailed(command_data, task_plan)
        return result.overall_score
    
    def calculate_confidence_detailed(self, command_data: Dict, task_plan: Dict) -> ConfidenceResult:
        """
        Calculate detailed confidence with breakdown
        
        Args:
            command_data: Parsed command data
            task_plan: Planned task execution
            
        Returns:
            ConfidenceResult with detailed breakdown
        """
        scores = []
        factors = {}
        
        start_time = time.time()
        
        # 1. Intent Recognition Confidence
        intent_score = self._calculate_intent_confidence(command_data)
        scores.append(intent_score)
        factors["intent"] = intent_score.score
        
        # 2. Entity Extraction Confidence
        entity_score = self._calculate_entity_confidence(command_data)
        scores.append(entity_score)
        factors["entities"] = entity_score.score
        
        # 3. Task Feasibility Confidence
        feasibility_score = self._calculate_feasibility_confidence(task_plan)
        scores.append(feasibility_score)
        factors["feasibility"] = feasibility_score.score
        
        # 4. Knowledge Availability Confidence
        knowledge_score = self._calculate_knowledge_confidence(command_data)
        scores.append(knowledge_score)
        factors["knowledge"] = knowledge_score.score
        
        # 5. Resource Availability Confidence
        resource_score = self._calculate_resource_confidence(task_plan)
        scores.append(resource_score)
        factors["resources"] = resource_score.score
        
        # 6. Historical Success Confidence
        historical_score = self._calculate_historical_confidence(command_data)
        scores.append(historical_score)
        factors["historical"] = historical_score.score
        
        # 7. User Preference Confidence
        preference_score = self._calculate_preference_confidence(command_data)
        scores.append(preference_score)
        factors["preferences"] = preference_score.score
        
        # 8. App Availability Confidence
        app_score = self._calculate_app_confidence(task_plan)
        scores.append(app_score)
        factors["apps"] = app_score.score
        
        # 9. Privacy Compliance Confidence
        privacy_score = self._calculate_privacy_confidence(command_data, task_plan)
        scores.append(privacy_score)
        factors["privacy"] = privacy_score.score
        
        # Calculate weighted average
        total_weight = sum(s.weight for s in scores)
        if total_weight > 0:
            overall_score = sum(s.score * s.weight for s in scores) / total_weight
        else:
            overall_score = 0.5  # Default if no scores
        
        # Generate explanation
        explanation = self._generate_explanation(scores, overall_score)
        
        calc_time = time.time() - start_time
        self.logger.debug(f"Confidence calculated in {calc_time:.4f}s: {overall_score:.2f}")
        
        return ConfidenceResult(
            overall_score=overall_score,
            scores=scores,
            explanation=explanation,
            factors=factors
        )
    
    def _calculate_intent_confidence(self, command_data: Dict) -> ConfidenceScore:
        """Calculate confidence in intent recognition"""
        intent = command_data.get("intent", "")
        intent_confidence = command_data.get("intent_confidence", 0.8)
        
        # Base score from intent recognition
        score = intent_confidence
        
        # Adjust based on intent clarity
        if not intent:
            score = 0.0
            explanation = "No intent detected"
        elif intent in ["unknown", "other"]:
            score *= 0.5
            explanation = "Unclear intent"
        else:
            explanation = f"Intent '{intent}' recognized with {intent_confidence*100:.1f}% confidence"
        
        return ConfidenceScore(
            aspect="intent_recognition",
            score=score,
            weight=self._weights["intent_recognition"],
            explanation=explanation
        )
    
    def _calculate_entity_confidence(self, command_data: Dict) -> ConfidenceScore:
        """Calculate confidence in entity extraction"""
        entities = command_data.get("entities", {})
        
        if not entities:
            return ConfidenceScore(
                aspect="entity_extraction",
                score=0.5,
                weight=self._weights["entity_extraction"],
                explanation="No entities extracted"
            )
        
        # Calculate based on entity types and confidence
        total_confidence = 0
        entity_count = 0
        
        for entity_type, entity_data in entities.items():
            if isinstance(entity_data, dict):
                conf = entity_data.get("confidence", 0.8)
                total_confidence += conf
                entity_count += 1
            elif isinstance(entity_data, list):
                for item in entity_data:
                    if isinstance(item, dict):
                        conf = item.get("confidence", 0.8)
                        total_confidence += conf
                        entity_count += 1
        
        if entity_count > 0:
            score = total_confidence / entity_count
            explanation = f"{entity_count} entities extracted with avg {score*100:.1f}% confidence"
        else:
            score = 0.5
            explanation = "Entities present but no confidence data"
        
        return ConfidenceScore(
            aspect="entity_extraction",
            score=score,
            weight=self._weights["entity_extraction"],
            explanation=explanation
        )
    
    def _calculate_feasibility_confidence(self, task_plan: Dict) -> ConfidenceScore:
        """Calculate confidence in task feasibility"""
        if not task_plan:
            return ConfidenceScore(
                aspect="task_feasibility",
                score=0.0,
                weight=self._weights["task_feasibility"],
                explanation="No task plan provided"
            )
        
        # Check if task plan has all required steps
        steps = task_plan.get("steps", [])
        missing = task_plan.get("missing_requirements", [])
        complexity = task_plan.get("complexity", "low")
        
        # Base score
        score = 1.0
        explanation = "Task plan complete"
        
        # Reduce score for missing requirements
        if missing:
            score *= (1 - len(missing) * 0.1)
            explanation = f"Task plan has {len(missing)} missing requirements"
        
        # Adjust based on complexity
        complexity_factor = {
            "very_low": 1.0,
            "low": 0.95,
            "medium": 0.9,
            "high": 0.8,
            "very_high": 0.6
        }
        score *= complexity_factor.get(complexity, 0.8)
        
        # Check if steps are valid
        if steps:
            valid_steps = sum(1 for s in steps if s.get("valid", True))
            step_confidence = valid_steps / len(steps)
            score *= step_confidence
            explanation += f", {step_confidence*100:.1f}% of steps are valid"
        
        return ConfidenceScore(
            aspect="task_feasibility",
            score=max(score, 0.1),  # Minimum 10%
            weight=self._weights["task_feasibility"],
            explanation=explanation
        )
    
    def _calculate_knowledge_confidence(self, command_data: Dict) -> ConfidenceScore:
        """Calculate confidence based on available knowledge"""
        intent = command_data.get("intent", "")
        entities = command_data.get("entities", {})
        
        # Check if we have knowledge about this intent
        intent_knowledge = self._knowledge_coverage.get(intent, 0.5)
        
        # Check entities
        entity_knowledge = 0.5
        if entities:
            entity_scores = []
            for entity_type in entities.keys():
                entity_scores.append(self._knowledge_coverage.get(entity_type, 0.5))
            if entity_scores:
                entity_knowledge = sum(entity_scores) / len(entity_scores)
        
        # Combined score
        score = (intent_knowledge * 0.7 + entity_knowledge * 0.3)
        
        explanation = f"Knowledge coverage: intent={intent_knowledge:.2f}, entities={entity_knowledge:.2f}"
        
        return ConfidenceScore(
            aspect="knowledge_availability",
            score=score,
            weight=self._weights["knowledge_availability"],
            explanation=explanation
        )
    
    def _calculate_resource_confidence(self, task_plan: Dict) -> ConfidenceScore:
        """Calculate confidence based on resource availability"""
        required_resources = task_plan.get("required_resources", {})
        available_resources = self._get_available_resources()
        
        if not required_resources:
            return ConfidenceScore(
                aspect="resource_availability",
                score=1.0,
                weight=self._weights["resource_availability"],
                explanation="No special resources required"
            )
        
        # Check each required resource
        total_score = 0
        resource_count = 0
        missing_resources = []
        
        for resource, required_amount in required_resources.items():
            available = available_resources.get(resource, 0)
            if available >= required_amount:
                total_score += 1.0
            else:
                ratio = available / required_amount if required_amount > 0 else 0
                total_score += ratio
                missing_resources.append(resource)
            resource_count += 1
        
        if resource_count > 0:
            score = total_score / resource_count
        else:
            score = 1.0
        
        if missing_resources:
            explanation = f"Missing resources: {', '.join(missing_resources)}"
        else:
            explanation = "All required resources available"
        
        return ConfidenceScore(
            aspect="resource_availability",
            score=score,
            weight=self._weights["resource_availability"],
            explanation=explanation
        )
    
    def _calculate_historical_confidence(self, command_data: Dict) -> ConfidenceScore:
        """Calculate confidence based on historical success rates"""
        intent = command_data.get("intent", "")
        
        # Get success rate for this intent (real recorded stats only;
        # unknown intents honestly report no data)
        stats = self._success_rates.get(intent, {"success": 0, "total": 0})
        
        if stats["total"] > 0:
            success_rate = stats["success"] / stats["total"]
            score = success_rate
            explanation = f"Historical success rate: {success_rate*100:.1f}% ({stats['success']}/{stats['total']})"
        else:
            score = 0.5
            explanation = "No historical data"
        
        return ConfidenceScore(
            aspect="historical_success",
            score=score,
            weight=self._weights["historical_success"],
            explanation=explanation
        )
    
    def _calculate_preference_confidence(self, command_data: Dict) -> ConfidenceScore:
        """Calculate confidence from recorded user preferences (real data only)."""
        preference_data = self._user_preferences.get(
            command_data.get("intent", "")
        )
        
        if not preference_data or preference_data.get("total", 0) <= 0:
            return ConfidenceScore(
                aspect="user_preference",
                score=0.5,
                weight=self._weights["user_preference"],
                explanation="No user preference data recorded yet for this intent"
            )
        
        total = preference_data["total"]
        preferred = preference_data.get("preferred", 0)
        ratio = preferred / total
        return ConfidenceScore(
            aspect="user_preference",
            score=ratio,
            weight=self._weights["user_preference"],
            explanation=(
                f"User preferred this intent's handling in {preferred}/{total} "
                f"recorded interactions"
            )
        )
    
    def _calculate_app_confidence(self, task_plan: Dict) -> ConfidenceScore:
        """Calculate confidence based on app availability"""
        required_apps = task_plan.get("required_apps", [])
        available_apps = self.config.allowed_apps
        
        if not required_apps:
            return ConfidenceScore(
                aspect="app_availability",
                score=1.0,
                weight=self._weights["app_availability"],
                explanation="No specific apps required"
            )
        
        # Check app availability
        available_count = sum(1 for app in required_apps if app in available_apps)
        score = available_count / len(required_apps)
        
        missing_apps = [app for app in required_apps if app not in available_apps]
        
        if missing_apps:
            explanation = f"Missing apps: {', '.join(missing_apps)}"
        else:
            explanation = "All required apps available"
        
        return ConfidenceScore(
            aspect="app_availability",
            score=score,
            weight=self._weights["app_availability"],
            explanation=explanation
        )
    
    def _calculate_privacy_confidence(self, command_data: Dict, task_plan: Dict) -> ConfidenceScore:
        """Calculate confidence in privacy compliance"""
        # Check for sensitive data
        entities = command_data.get("entities", {})
        
        sensitive_types = ["password", "credit_card", "ssn", "phone", "email", "address"]
        
        has_sensitive = any(st in entities for st in sensitive_types)
        
        if has_sensitive:
            # Lower confidence if sensitive data is involved
            score = 0.5
            explanation = "Sensitive data detected - privacy checks required"
        else:
            score = 0.9
            explanation = "No sensitive data detected"
        
        return ConfidenceScore(
            aspect="privacy_compliance",
            score=score,
            weight=self._weights["privacy_compliance"],
            explanation=explanation
        )
    
    def _get_available_resources(self) -> Dict[str, float]:
        """Get real available system resources from the device.
        
        Memory comes from /proc/meminfo, storage from statvfs of the home
        directory, and CPU from /proc/loadavg (relative to the CPU count).
        Values that cannot be measured honestly are omitted so callers
        never see fabricated numbers.
        """
        available: Dict[str, float] = {}
        
        # Real memory reading (GB available)
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        available["memory"] = float(line.split()[1]) / (1024 * 1024)
                        break
        except (OSError, ValueError, IndexError):
            pass
        
        # Real storage reading (GB available on the data partition)
        try:
            stats = os.statvfs(os.path.expanduser("~"))
            available["storage"] = (stats.f_bavail * stats.f_frsize) / (1024 ** 3)
        except (OSError, AttributeError):
            pass
        
        # Real CPU availability (1 - load per core, clamped to [0, 1])
        try:
            with open("/proc/loadavg", "r") as f:
                load1 = float(f.read().split()[0])
            cpu_count = os.cpu_count() or 1
            available["cpu"] = max(0.0, 1.0 - (load1 / cpu_count))
        except (OSError, ValueError, IndexError):
            pass
        
        return available
    
    def _generate_explanation(self, scores: List[ConfidenceScore], overall_score: float) -> str:
        """Generate human-readable explanation"""
        if not scores:
            return "No confidence factors available"
        
        # Get lowest scoring aspects
        sorted_scores = sorted(scores, key=lambda x: x.score)
        low_scores = [s for s in sorted_scores if s.score < 0.6]
        
        if low_scores:
            low_aspects = [s.aspect.replace("_", " ").title() for s in low_scores]
            return f"Confidence: {overall_score*100:.1f}%. Low scores in: {', '.join(low_aspects)}"
        else:
            return f"Confidence: {overall_score*100:.1f}%. All factors scoring well."
    
    def update_success_rate(self, intent: str, success: bool):
        """Update success rate for an intent"""
        stats = self._success_rates[intent]
        stats["total"] += 1
        if success:
            stats["success"] += 1
        
        self.logger.debug(f"Updated success rate for {intent}: {stats['success']}/{stats['total']}")
    
    def update_knowledge_coverage(self, aspect: str, coverage: float):
        """Update knowledge coverage for an aspect"""
        self._knowledge_coverage[aspect] = coverage
        self.logger.debug(f"Updated knowledge coverage for {aspect}: {coverage:.2f}")
    
    def record_preference(self, intent: str, preferred: bool):
        """Record a real user preference signal for an intent."""
        prefs = self._user_preferences[intent]
        prefs["total"] += 1
        if preferred:
            prefs["preferred"] += 1
        self.logger.debug(
            f"Updated preference for {intent}: {prefs['preferred']}/{prefs['total']}"
        )
    
    def get_confidence_breakdown(self, command_data: Dict, task_plan: Dict) -> Dict:
        """Get detailed confidence breakdown"""
        result = self.calculate_confidence_detailed(command_data, task_plan)
        
        return {
            "overall": result.overall_score,
            "scores": [
                {
                    "aspect": s.aspect,
                    "score": s.score,
                    "weight": s.weight,
                    "weighted_score": s.score * s.weight,
                    "explanation": s.explanation
                }
                for s in result.scores
            ],
            "explanation": result.explanation,
            "factors": result.factors
        }
    
    def is_high_confidence(self, confidence: float) -> bool:
        """Check if confidence is high enough for automatic execution"""
        return confidence >= self.config.min_confidence_threshold
    
    def get_recommendation(self, confidence: float) -> str:
        """Get recommendation based on confidence level"""
        if confidence >= 0.9:
            return "STRONGLY_RECOMMEND"
        elif confidence >= 0.7:
            return "RECOMMEND"
        elif confidence >= 0.5:
            return "CAUTIOUS"
        elif confidence >= 0.3:
            return "NEEDS_REVIEW"
        else:
            return "NOT_RECOMMENDED"
