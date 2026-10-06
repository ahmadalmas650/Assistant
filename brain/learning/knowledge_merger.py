"""
Knowledge Merger Module
Merges knowledge from multiple sources intelligently
"""

import json
import time
import re
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import difflib

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler


class MergeStrategy(Enum):
    """Merging strategies"""
    CONCATENATION = auto()
    CONSENSUS = auto()
    WEIGHTED = auto()
    INTELLIGENT = auto()
    CUSTOM = auto()


class ConflictResolution(Enum):
    """Conflict resolution strategies"""
    KEEP_ALL = auto()
    KEEP_FIRST = auto()
    KEEP_LAST = auto()
    KEEP_MOST_RELIABLE = auto()
    KEEP_HIGHEST_CONFIDENCE = auto()
    MERGE = auto()


@dataclass
class MergeResult:
    """Result of a merge operation"""
    merged_content: str
    sources: List[str]
    strategy: MergeStrategy
    confidence: float = 0.0
    conflicts: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    processing_time: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "merged_content": self.merged_content,
            "sources": self.sources,
            "strategy": self.strategy.name,
            "confidence": self.confidence,
            "conflicts": self.conflicts,
            "metadata": self.metadata,
            "processing_time": self.processing_time
        }


@dataclass
class Conflict:
    """Represents a conflict between sources"""
    field: str
    values: Dict[str, Any]  # source_id -> value
    resolution: Optional[Any] = None
    resolution_source: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "field": self.field,
            "values": self.values,
            "resolution": self.resolution,
            "resolution_source": self.resolution_source
        }


class KnowledgeMerger:
    """
    Merges knowledge from multiple sources
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Configuration
        self._default_strategy = MergeStrategy.INTELLIGENT
        self._default_resolution = ConflictResolution.KEEP_HIGHEST_CONFIDENCE
        
        # Source reliability
        self._source_reliability: Dict[str, float] = {}
        
        # Callbacks
        self._on_merge_complete: List[Callable[[MergeResult], None]] = []
    
    def set_default_strategy(self, strategy: MergeStrategy) -> bool:
        """Set default merge strategy"""
        self._default_strategy = strategy
        self.logger.info(f"Default merge strategy set to: {strategy.name}")
        return True
    
    def get_default_strategy(self) -> MergeStrategy:
        """Get default merge strategy"""
        return self._default_strategy
    
    def set_default_resolution(self, resolution: ConflictResolution) -> bool:
        """Set default conflict resolution strategy"""
        self._default_resolution = resolution
        self.logger.info(f"Default conflict resolution set to: {resolution.name}")
        return True
    
    def get_default_resolution(self) -> ConflictResolution:
        """Get default conflict resolution strategy"""
        return self._default_resolution
    
    def set_source_reliability(self, source_id: str, reliability: float) -> bool:
        """Set reliability score for a source"""
        if not (0 <= reliability <= 1):
            return False
        
        self._source_reliability[source_id] = reliability
        self.logger.debug(f"Source reliability set: {source_id} = {reliability}")
        return True
    
    def get_source_reliability(self, source_id: str) -> float:
        """Get reliability score for a source"""
        return self._source_reliability.get(source_id, 0.8)
    
    async def merge_texts(self, texts: Dict[str, str], 
                       strategy: MergeStrategy = None,
                       resolution: ConflictResolution = None) -> str:
        """
        Merge multiple texts into a single coherent text
        
        Args:
            texts: Dictionary of source_id -> text
            strategy: Merge strategy to use
            resolution: Conflict resolution strategy
            
        Returns:
            Merged text
        """
        start_time = time.time()
        
        if strategy is None:
            strategy = self._default_strategy
        if resolution is None:
            resolution = self._default_resolution
        
        try:
            if strategy == MergeStrategy.CONCATENATION:
                merged = self._merge_by_concatenation(texts)
            elif strategy == MergeStrategy.CONSENSUS:
                merged = self._merge_by_consensus(texts)
            elif strategy == MergeStrategy.WEIGHTED:
                merged = self._merge_by_weighted(texts)
            elif strategy == MergeStrategy.INTELLIGENT:
                merged = self._merge_intelligently(texts, resolution)
            else:
                merged = self._merge_by_concatenation(texts)
            
            # Create merge result for callbacks
            result = MergeResult(
                merged_content=merged,
                sources=list(texts.keys()),
                strategy=strategy,
                processing_time=time.time() - start_time
            )
            
            # Notify callbacks
            for callback in self._on_merge_complete:
                try:
                    callback(result)
                except Exception as e:
                    self.error_handler.handle_error(e, "merge_complete_callback")
            
            return merged
            
        except Exception as e:
            self.error_handler.handle_error(e, "merge_texts")
            return ""
    
    async def merge_knowledge(self, knowledge: Dict[str, Dict],
                           strategy: MergeStrategy = None,
                           resolution: ConflictResolution = None) -> Dict:
        """
        Merge knowledge from multiple sources
        
        Args:
            knowledge: Dictionary of source_id -> knowledge dict
            strategy: Merge strategy to use
            resolution: Conflict resolution strategy
            
        Returns:
            Merged knowledge dictionary
        """
        start_time = time.time()
        
        if strategy is None:
            strategy = self._default_strategy
        if resolution is None:
            resolution = self._default_resolution
        
        try:
            if strategy == MergeStrategy.CONCATENATION:
                merged = self._merge_knowledge_concatenation(knowledge)
            elif strategy == MergeStrategy.CONSENSUS:
                merged = self._merge_knowledge_consensus(knowledge)
            elif strategy == MergeStrategy.WEIGHTED:
                merged = self._merge_knowledge_weighted(knowledge)
            elif strategy == MergeStrategy.INTELLIGENT:
                merged = self._merge_knowledge_intelligently(knowledge, resolution)
            else:
                merged = self._merge_knowledge_concatenation(knowledge)
            
            # Create merge result for callbacks
            result = MergeResult(
                merged_content=str(merged),
                sources=list(knowledge.keys()),
                strategy=strategy,
                processing_time=time.time() - start_time
            )
            
            # Notify callbacks
            for callback in self._on_merge_complete:
                try:
                    callback(result)
                except Exception as e:
                    self.error_handler.handle_error(e, "merge_complete_callback")
            
            return merged
            
        except Exception as e:
            self.error_handler.handle_error(e, "merge_knowledge")
            return {}
    
    def _merge_by_concatenation(self, texts: Dict[str, str]) -> str:
        """Merge by simple concatenation"""
        merged = []
        
        for source_id, text in texts.items():
            reliability = self.get_source_reliability(source_id)
            header = f"[Source: {source_id} (Reliability: {reliability:.1f})]"
            merged.append(f"{header}\n{text}\n\n")
        
        return "\n".join(merged).strip()
    
    def _merge_by_consensus(self, texts: Dict[str, str]) -> str:
        """Merge by finding consensus between sources"""
        if not texts:
            return ""
        
        # Find common sentences
        sentences = {}
        for source_id, text in texts.items():
            # Split into sentences
            source_sentences = re.split(r'[.!?]', text)
            for sentence in source_sentences:
                sentence = sentence.strip()
                if sentence:
                    if sentence not in sentences:
                        sentences[sentence] = []
                    sentences[sentence].append(source_id)
        
        # Sort by number of sources
        sorted_sentences = sorted(
            sentences.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )
        
        # Take sentences that appear in at least 2 sources
        consensus = []
        for sentence, sources in sorted_sentences:
            if len(sources) >= 2:
                consensus.append(sentence)
        
        if not consensus:
            # Fallback to concatenation
            return self._merge_by_concatenation(texts)
        
        return " ".join(consensus)
    
    def _merge_by_weighted(self, texts: Dict[str, str]) -> str:
        """Merge by weighted average based on source reliability"""
        if not texts:
            return ""
        
        # Calculate weights
        total_weight = 0
        weighted_texts = []
        
        for source_id, text in texts.items():
            weight = self.get_source_reliability(source_id)
            total_weight += weight
            weighted_texts.append((text, weight))
        
        if total_weight == 0:
            return self._merge_by_concatenation(texts)
        
        # Normalize weights
        normalized_texts = []
        for text, weight in weighted_texts:
            normalized_weight = weight / total_weight
            # Keep only the dominant source(s): texts holding more than
            # half of the total reliability weight
            if normalized_weight > 0.5:
                normalized_texts.append(text)
        
        if not normalized_texts:
            return self._merge_by_concatenation(texts)
        
        return "\n\n".join(normalized_texts)
    
    def _merge_intelligently(self, texts: Dict[str, str], 
                           resolution: ConflictResolution) -> str:
        """Intelligent merge with conflict detection"""
        if len(texts) <= 1:
            return list(texts.values())[0] if texts else ""
        
        # Step 1: Identify similar and different content
        similar_groups = self._group_similar_texts(texts)
        
        # Step 2: Merge similar groups
        merged_groups = []
        for group in similar_groups:
            if len(group) == 1:
                # Single source, add as-is
                merged_groups.append(group[0])
            else:
                # Multiple sources with similar content
                # Take the longest version (usually most complete)
                merged = max(group, key=len)
                merged_groups.append(merged)
        
        # Step 3: Combine all merged groups
        return "\n\n".join(merged_groups)
    
    def _group_similar_texts(self, texts: Dict[str, str], 
                           threshold: float = 0.7) -> List[List[str]]:
        """Group similar texts together"""
        if not texts:
            return []
        
        # Convert to list
        text_list = list(texts.values())
        
        # Create groups
        groups = []
        used = set()
        
        for i, text1 in enumerate(text_list):
            if i in used:
                continue
            
            # Find similar texts
            group = [text1]
            used.add(i)
            
            for j, text2 in enumerate(text_list):
                if j in used:
                    continue
                
                similarity = self._calculate_similarity(text1, text2)
                if similarity >= threshold:
                    group.append(text2)
                    used.add(j)
            
            groups.append(group)
        
        return groups
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (0-1)"""
        # Use sequence matching for better similarity
        similarity = difflib.SequenceMatcher(None, text1, text2).ratio()
        
        # Also consider word overlap
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if words1 and words2:
            word_similarity = len(words1 & words2) / len(words1 | words2)
            # Weighted average
            similarity = (similarity * 0.7) + (word_similarity * 0.3)
        
        return min(similarity, 1.0)
    
    def _merge_knowledge_concatenation(self, knowledge: Dict[str, Dict]) -> Dict:
        """Merge knowledge by concatenation"""
        merged = {}
        
        for source_id, data in knowledge.items():
            for key, value in data.items():
                if key not in merged:
                    merged[key] = []
                
                reliability = self.get_source_reliability(source_id)
                merged[key].append({
                    "value": value,
                    "source": source_id,
                    "reliability": reliability
                })
        
        return merged
    
    def _merge_knowledge_consensus(self, knowledge: Dict[str, Dict]) -> Dict:
        """Merge knowledge by consensus"""
        merged = {}
        
        for key in set(k for data in knowledge.values() for k in data.keys()):
            # Collect all values for this key
            values = []
            for source_id, data in knowledge.items():
                if key in data:
                    values.append((data[key], source_id))
            
            if values:
                # Find most common value
                value_counts = {}
                for value, source_id in values:
                    if value not in value_counts:
                        value_counts[value] = []
                    value_counts[value].append(source_id)
                
                # Get value with most sources
                best_value = max(value_counts.items(), key=lambda x: len(x[1]))[0]
                merged[key] = {
                    "value": best_value,
                    "sources": value_counts[best_value],
                    "consensus": len(value_counts[best_value]) / len(values)
                }
        
        return merged
    
    def _merge_knowledge_weighted(self, knowledge: Dict[str, Dict]) -> Dict:
        """Merge knowledge by weighted average"""
        merged = {}
        
        for key in set(k for data in knowledge.values() for k in data.keys()):
            # Collect all values with weights
            weighted_values = []
            total_weight = 0
            
            for source_id, data in knowledge.items():
                if key in data:
                    weight = self.get_source_reliability(source_id)
                    weighted_values.append((data[key], weight))
                    total_weight += weight
            
            if weighted_values and total_weight > 0:
                # Calculate weighted average for numeric values
                if all(isinstance(v, (int, float)) for v, _ in weighted_values):
                    weighted_sum = sum(v * w for v, w in weighted_values)
                    merged[key] = weighted_sum / total_weight
                else:
                    # For non-numeric, take the value from most reliable source
                    best = max(weighted_values, key=lambda x: x[1])
                    merged[key] = best[0]
        
        return merged
    
    def _merge_knowledge_intelligently(self, knowledge: Dict[str, Dict],
                                     resolution: ConflictResolution) -> Dict:
        """Intelligent merge with conflict resolution"""
        merged = {}
        conflicts = []
        
        for key in set(k for data in knowledge.values() for k in data.keys()):
            # Collect all values for this key
            values = {}
            for source_id, data in knowledge.items():
                if key in data:
                    values[source_id] = data[key]
            
            if not values:
                continue
            
            # Check if all values are the same
            unique_values = set(str(v) for v in values.values())
            
            if len(unique_values) == 1:
                # No conflict
                merged[key] = list(unique_values)[0]
            else:
                # Conflict - apply resolution strategy
                resolved_value = self._resolve_conflict(key, values, resolution)
                merged[key] = resolved_value
                
                conflicts.append({
                    "field": key,
                    "values": values,
                    "resolved_value": resolved_value
                })
        
        # Add conflict information to metadata
        if conflicts:
            merged["_conflicts"] = conflicts
        
        return merged
    
    def _resolve_conflict(self, field: str, values: Dict[str, Any],
                         resolution: ConflictResolution) -> Any:
        """Resolve a conflict based on strategy"""
        if resolution == ConflictResolution.KEEP_FIRST:
            return list(values.values())[0]
        
        elif resolution == ConflictResolution.KEEP_LAST:
            return list(values.values())[-1]
        
        elif resolution == ConflictResolution.KEEP_MOST_RELIABLE:
            best_source = max(values.keys(), key=lambda s: self.get_source_reliability(s))
            return values[best_source]
        
        elif resolution == ConflictResolution.KEEP_HIGHEST_CONFIDENCE:
            # Confidence data is not attached to values in this merger,
            # so the honest fallback is the most reliable source
            return self._resolve_conflict(field, values, ConflictResolution.KEEP_MOST_RELIABLE)
        
        elif resolution == ConflictResolution.MERGE:
            # Try to merge values
            if all(isinstance(v, str) for v in values.values()):
                return " | ".join(str(v) for v in values.values())
            else:
                return list(values.values())
        
        else:
            # Default: keep most reliable
            return self._resolve_conflict(field, values, ConflictResolution.KEEP_MOST_RELIABLE)
    
    async def merge_with_context(self, texts: Dict[str, str], 
                               context: Dict = None) -> str:
        """
        Merge texts with additional context
        
        Args:
            texts: Dictionary of source_id -> text
            context: Additional context for merging
            
        Returns:
            Merged text with context
        """
        merged = await self.merge_texts(texts)
        
        if context:
            # Add context header
            context_header = "**Context:**\n"
            for key, value in context.items():
                context_header += f"- {key}: {value}\n"
            
            merged = f"{context_header}\n\n{merged}"
        
        return merged
    
    async def merge_and_validate(self, texts: Dict[str, str],
                                validator: callable = None) -> Tuple[str, List[Dict]]:
        """
        Merge texts and validate the result
        
        Args:
            texts: Dictionary of source_id -> text
            validator: Function to validate merged result
            
        Returns:
            Tuple of (merged_text, list_of_issues)
        """
        merged = await self.merge_texts(texts)
        
        issues = []
        
        if validator:
            try:
                validation_result = validator(merged)
                if validation_result is not True:
                    if isinstance(validation_result, str):
                        issues.append({"type": "validation", "message": validation_result})
                    elif isinstance(validation_result, list):
                        issues.extend(validation_result)
                    elif isinstance(validation_result, dict):
                        issues.append(validation_result)
            except Exception as e:
                issues.append({"type": "validation_error", "message": str(e)})
        
        return merged, issues
    
    # Callback Registration
    
    def on_merge_complete(self, callback: Callable[[MergeResult], None]):
        """Register merge completion callback"""
        self._on_merge_complete.append(callback)
    
    # Cleanup
    
    async def cleanup(self):
        """Clean up resources"""
        self._source_reliability = {}
        self._on_merge_complete = []
        self.logger.info("Knowledge Merger cleaned up")
