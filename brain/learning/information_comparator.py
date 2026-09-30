"""
Information Comparator Module
Compares information from different sources for accuracy and relevance
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


class ComparisonMetric(Enum):
    """Metrics for comparison"""
    SIMILARITY = auto()
    RELEVANCE = auto()
    ACCURACY = auto()
    COMPLETENESS = auto()
    CONTRADICTION = auto()
    NOVELTY = auto()


class ComparisonResult(Enum):
    """Result of comparison"""
    IDENTICAL = auto()
    SIMILAR = auto()
    DIFFERENT = auto()
    CONTRADICTORY = auto()
    COMPLEMENTARY = auto()


@dataclass
class Comparison:
    """Represents a comparison between two pieces of information"""
    item1: Any
    item2: Any
    source1: str
    source2: str
    metric: ComparisonMetric
    score: float = 0.0
    result: ComparisonResult = ComparisonResult.DIFFERENT
    details: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "source1": self.source1,
            "source2": self.source2,
            "metric": self.metric.name,
            "score": self.score,
            "result": self.result.name,
            "details": self.details
        }


@dataclass
class InformationQuality:
    """Quality assessment of a piece of information"""
    source: str
    content: str
    relevance: float = 0.0
    accuracy: float = 0.0
    completeness: float = 0.0
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "source": self.source,
            "relevance": self.relevance,
            "accuracy": self.accuracy,
            "completeness": self.completeness,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
    def get_overall_score(self) -> float:
        """Calculate overall quality score"""
        return (self.relevance * 0.4 + 
                self.accuracy * 0.3 + 
                self.completeness * 0.2 + 
                self.confidence * 0.1)


class InformationComparator:
    """
    Compares information from different sources
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Configuration
        self._similarity_threshold = 0.7
        self._relevance_threshold = 0.5
        self._contradiction_threshold = 0.3
        
        # Callbacks
        self._on_comparison_complete: List[Callable[[Comparison], None]] = []
    
    def set_similarity_threshold(self, threshold: float) -> bool:
        """Set similarity threshold"""
        if 0 <= threshold <= 1:
            self._similarity_threshold = threshold
            return True
        return False
    
    def set_relevance_threshold(self, threshold: float) -> bool:
        """Set relevance threshold"""
        if 0 <= threshold <= 1:
            self._relevance_threshold = threshold
            return True
        return False
    
    def set_contradiction_threshold(self, threshold: float) -> bool:
        """Set contradiction threshold"""
        if 0 <= threshold <= 1:
            self._contradiction_threshold = threshold
            return True
        return False
    
    async def compare_information(self, info1: Any, info2: Any,
                                source1: str, source2: str,
                                metric: ComparisonMetric = None) -> Comparison:
        """
        Compare two pieces of information
        
        Args:
            info1: First piece of information
            info2: Second piece of information
            source1: Source of first information
            source2: Source of second information
            metric: Comparison metric to use
            
        Returns:
            Comparison object
        """
        if metric is None:
            metric = ComparisonMetric.SIMILARITY
        
        try:
            if metric == ComparisonMetric.SIMILARITY:
                return self._compare_similarity(info1, info2, source1, source2)
            elif metric == ComparisonMetric.RELEVANCE:
                return self._compare_relevance(info1, info2, source1, source2)
            elif metric == ComparisonMetric.ACCURACY:
                return self._compare_accuracy(info1, info2, source1, source2)
            elif metric == ComparisonMetric.COMPLETENESS:
                return self._compare_completeness(info1, info2, source1, source2)
            elif metric == ComparisonMetric.CONTRADICTION:
                return self._compare_contradiction(info1, info2, source1, source2)
            elif metric == ComparisonMetric.NOVELTY:
                return self._compare_novelty(info1, info2, source1, source2)
            else:
                return self._compare_similarity(info1, info2, source1, source2)
                
        except Exception as e:
            self.error_handler.handle_error(e, "compare_information")
            return Comparison(
                item1=info1,
                item2=info2,
                source1=source1,
                source2=source2,
                metric=metric,
                score=0.0,
                result=ComparisonResult.DIFFERENT,
                details={"error": str(e)}
            )
    
    def _compare_similarity(self, info1: Any, info2: Any,
                           source1: str, source2: str) -> Comparison:
        """Compare by similarity"""
        # Convert to strings
        str1 = str(info1)
        str2 = str(info2)
        
        # Calculate similarity
        similarity = self._calculate_similarity(str1, str2)
        
        # Determine result
        if similarity >= 0.9:
            result = ComparisonResult.IDENTICAL
        elif similarity >= self._similarity_threshold:
            result = ComparisonResult.SIMILAR
        else:
            result = ComparisonResult.DIFFERENT
        
        return Comparison(
            item1=info1,
            item2=info2,
            source1=source1,
            source2=source2,
            metric=ComparisonMetric.SIMILARITY,
            score=similarity,
            result=result,
            details={"similarity": similarity}
        )
    
    def _compare_relevance(self, info1: Any, info2: Any,
                          source1: str, source2: str) -> Comparison:
        """Compare by relevance to each other"""
        # This is a simplified implementation
        # In a real system, we would have context about what we're comparing for
        
        str1 = str(info1)
        str2 = str(info2)
        
        # Calculate word overlap
        words1 = set(str1.lower().split())
        words2 = set(str2.lower().split())
        
        if not words1 or not words2:
            similarity = 0.0
        else:
            similarity = len(words1 & words2) / len(words1 | words2)
        
        # For relevance, higher similarity means more relevant to each other
        if similarity >= self._relevance_threshold:
            result = ComparisonResult.SIMILAR
        else:
            result = ComparisonResult.DIFFERENT
        
        return Comparison(
            item1=info1,
            item2=info2,
            source1=source1,
            source2=source2,
            metric=ComparisonMetric.RELEVANCE,
            score=similarity,
            result=result,
            details={"relevance_score": similarity}
        )
    
    def _compare_accuracy(self, info1: Any, info2: Any,
                         source1: str, source2: str) -> Comparison:
        """Compare by accuracy (requires reference data)"""
        # This is a placeholder - accuracy comparison would require
        # reference data or fact-checking against known sources
        
        # For now, return neutral comparison
        return Comparison(
            item1=info1,
            item2=info2,
            source1=source1,
            source2=source2,
            metric=ComparisonMetric.ACCURACY,
            score=0.5,
            result=ComparisonResult.DIFFERENT,
            details={"note": "Accuracy comparison requires reference data"}
        )
    
    def _compare_completeness(self, info1: Any, info2: Any,
                            source1: str, source2: str) -> Comparison:
        """Compare by completeness"""
        str1 = str(info1)
        str2 = str(info2)
        
        len1 = len(str1)
        len2 = len(str2)
        
        # Simple comparison: longer is more complete
        if len1 == 0 and len2 == 0:
            score = 0.0
        elif len1 == 0:
            score = 1.0  # info2 is more complete
        elif len2 == 0:
            score = -1.0  # info1 is more complete
        else:
            # Calculate ratio
            score = (len1 - len2) / max(len1, len2)
        
        # Map to comparison result
        if abs(score) < 0.2:
            result = ComparisonResult.SIMILAR
        elif score > 0:
            result = ComparisonResult.COMPLEMENTARY  # info1 is more complete
        else:
            result = ComparisonResult.COMPLEMENTARY  # info2 is more complete
        
        return Comparison(
            item1=info1,
            item2=info2,
            source1=source1,
            source2=source2,
            metric=ComparisonMetric.COMPLETENESS,
            score=abs(score),
            result=result,
            details={"length1": len1, "length2": len2}
        )
    
    def _compare_contradiction(self, info1: Any, info2: Any,
                             source1: str, source2: str) -> Comparison:
        """Compare for contradictions"""
        str1 = str(info1).lower()
        str2 = str(info2).lower()
        
        # Check for direct contradictions
        contradictions = [
            ("yes", "no"),
            ("true", "false"),
            ("correct", "incorrect"),
            ("right", "wrong"),
            ("good", "bad"),
            ("high", "low"),
            ("up", "down"),
            ("left", "right"),
            ("on", "off"),
            ("enable", "disable")
        ]
        
        is_contradiction = False
        for word1, word2 in contradictions:
            if (word1 in str1 and word2 in str2) or (word2 in str1 and word1 in str2):
                is_contradiction = True
                break
        
        # Calculate similarity
        similarity = self._calculate_similarity(str1, str2)
        
        if is_contradiction:
            result = ComparisonResult.CONTRADICTORY
            score = 1.0
        elif similarity < self._contradiction_threshold:
            result = ComparisonResult.CONTRADICTORY
            score = 1.0 - similarity
        else:
            result = ComparisonResult.DIFFERENT
            score = 1.0 - similarity
        
        return Comparison(
            item1=info1,
            item2=info2,
            source1=source1,
            source2=source2,
            metric=ComparisonMetric.CONTRADICTION,
            score=score,
            result=result,
            details={"is_contradiction": is_contradiction, "similarity": similarity}
        )
    
    def _compare_novelty(self, info1: Any, info2: Any,
                        source1: str, source2: str) -> Comparison:
        """Compare by novelty (how much new information each provides)"""
        str1 = str(info1)
        str2 = str(info2)
        
        # Calculate unique content
        words1 = set(str1.lower().split())
        words2 = set(str2.lower().split())
        
        if not words1 or not words2:
            return Comparison(
                item1=info1,
                item2=info2,
                source1=source1,
                source2=source2,
                metric=ComparisonMetric.NOVELTY,
                score=0.0,
                result=ComparisonResult.DIFFERENT
            )
        
        # Calculate novelty scores
        novelty1 = len(words1 - words2) / len(words1 | words2)
        novelty2 = len(words2 - words1) / len(words1 | words2)
        avg_novelty = (novelty1 + novelty2) / 2
        
        # Determine result
        if avg_novelty > 0.5:
            result = ComparisonResult.COMPLEMENTARY
        elif avg_novelty > 0.3:
            result = ComparisonResult.DIFFERENT
        else:
            result = ComparisonResult.SIMILAR
        
        return Comparison(
            item1=info1,
            item2=info2,
            source1=source1,
            source2=source2,
            metric=ComparisonMetric.NOVELTY,
            score=avg_novelty,
            result=result,
            details={"novelty1": novelty1, "novelty2": novelty2}
        )
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings (0-1)"""
        # Use sequence matching
        similarity = difflib.SequenceMatcher(None, str1, str2).ratio()
        
        # Also consider word overlap
        words1 = set(str1.lower().split())
        words2 = set(str2.lower().split())
        
        if words1 and words2:
            word_similarity = len(words1 & words2) / len(words1 | words2)
            # Weighted average
            similarity = (similarity * 0.7) + (word_similarity * 0.3)
        
        return min(similarity, 1.0)
    
    async def compare_multiple(self, information: Dict[str, Any],
                            metric: ComparisonMetric = None) -> Dict[str, Dict]:
        """
        Compare multiple pieces of information
        
        Args:
            information: Dictionary of source_id -> information
            metric: Comparison metric to use
            
        Returns:
            Dictionary of comparisons
        """
        comparisons = {}
        
        source_ids = list(information.keys())
        
        for i in range(len(source_ids)):
            for j in range(i + 1, len(source_ids)):
                source1 = source_ids[i]
                source2 = source_ids[j]
                
                comparison = await self.compare_information(
                    information[source1],
                    information[source2],
                    source1,
                    source2,
                    metric
                )
                
                key = f"{source1}_vs_{source2}"
                comparisons[key] = comparison.to_dict()
        
        return comparisons
    
    async def compare_results(self, results: Dict[str, Any]) -> Dict:
        """
        Compare results from multiple sources
        
        Args:
            results: Dictionary of source_id -> result
            
        Returns:
            Comparison analysis
        """
        analysis = {
            "sources": list(results.keys()),
            "pairwise_comparisons": {},
            "agreements": [],
            "disagreements": [],
            "complementary": [],
            "contradictions": [],
            "summary": {}
        }
        
        # Extract text from results
        texts = {}
        for source_id, result in results.items():
            if isinstance(result, dict):
                text = result.get("response", result.get("text", result.get("content", "")))
            else:
                text = str(result)
            
            if text:
                texts[source_id] = text
        
        # Perform pairwise comparisons
        source_ids = list(texts.keys())
        
        for i in range(len(source_ids)):
            for j in range(i + 1, len(source_ids)):
                source1 = source_ids[i]
                source2 = source_ids[j]
                
                # Compare using different metrics
                similarity = await self.compare_information(
                    texts[source1], texts[source2], source1, source2,
                    ComparisonMetric.SIMILARITY
                )
                contradiction = await self.compare_information(
                    texts[source1], texts[source2], source1, source2,
                    ComparisonMetric.CONTRADICTION
                )
                
                key = f"{source1}_vs_{source2}"
                analysis["pairwise_comparisons"][key] = {
                    "similarity": similarity.to_dict(),
                    "contradiction": contradiction.to_dict()
                }
                
                # Categorize
                if similarity.result == ComparisonResult.IDENTICAL:
                    analysis["agreements"].append(key)
                elif contradiction.result == ComparisonResult.CONTRADICTORY:
                    analysis["contradictions"].append(key)
                elif similarity.result == ComparisonResult.SIMILAR:
                    analysis["disagreements"].append(key)
                else:
                    analysis["complementary"].append(key)
        
        # Calculate summary statistics
        total_comparisons = len(analysis["pairwise_comparisons"])
        if total_comparisons > 0:
            analysis["summary"] = {
                "total_comparisons": total_comparisons,
                "agreement_count": len(analysis["agreements"]),
                "disagreement_count": len(analysis["disagreements"]),
                "complementary_count": len(analysis["complementary"]),
                "contradiction_count": len(analysis["contradictions"]),
                "agreement_rate": len(analysis["agreements"]) / total_comparisons,
                "contradiction_rate": len(analysis["contradictions"]) / total_comparisons
            }
        
        return analysis
    
    async def assess_quality(self, information: Dict[str, Any], 
                          query: str = "") -> Dict[str, InformationQuality]:
        """
        Assess the quality of information from multiple sources
        
        Args:
            information: Dictionary of source_id -> information
            query: The original query (for relevance assessment)
            
        Returns:
            Dictionary of source_id -> InformationQuality
        """
        qualities = {}
        
        for source_id, info in information.items():
            str_info = str(info)
            
            # Calculate relevance to query
            if query:
                relevance = self._calculate_relevance(str_info, query)
            else:
                relevance = 0.5
            
            # Calculate completeness
            completeness = self._calculate_completeness(str_info)
            
            # Calculate confidence (mock value - would be from source)
            confidence = 0.8
            
            # Calculate accuracy (placeholder)
            accuracy = 0.7
            
            qualities[source_id] = InformationQuality(
                source=source_id,
                content=str_info,
                relevance=relevance,
                accuracy=accuracy,
                completeness=completeness,
                confidence=confidence,
                metadata={"query": query}
            )
        
        return qualities
    
    def _calculate_relevance(self, text: str, query: str) -> float:
        """Calculate relevance of text to query"""
        text_lower = text.lower()
        query_lower = query.lower()
        
        # Check for exact matches
        query_words = set(query_lower.split())
        text_words = set(text_lower.split())
        
        if not query_words or not text_words:
            return 0.0
        
        # Calculate overlap
        overlap = len(query_words & text_words) / len(query_words)
        
        # Also check if query appears in text
        if query_lower in text_lower:
            overlap = max(overlap, 0.9)
        
        return min(overlap, 1.0)
    
    def _calculate_completeness(self, text: str) -> float:
        """Calculate completeness of text"""
        # Simple implementation: longer text is more complete
        length = len(text)
        
        if length == 0:
            return 0.0
        elif length < 50:
            return 0.3
        elif length < 100:
            return 0.6
        elif length < 500:
            return 0.8
        else:
            return 1.0
    
    async def find_consensus(self, information: Dict[str, Any]) -> Dict:
        """
        Find consensus among multiple sources
        
        Args:
            information: Dictionary of source_id -> information
            
        Returns:
            Consensus information
        """
        if not information:
            return {"consensus": None, "sources": []}
        
        # Extract text
        texts = {}
        for source_id, info in information.items():
            if isinstance(info, dict):
                text = info.get("response", info.get("text", ""))
            else:
                text = str(info)
            
            if text:
                texts[source_id] = text
        
        if not texts:
            return {"consensus": None, "sources": []}
        
        # Find most common text
        all_texts = list(texts.values())
        
        # Group similar texts
        groups = self._group_similar_texts(texts)
        
        # Find largest group
        largest_group = max(groups, key=len) if groups else []
        
        if len(largest_group) >= len(texts) / 2:
            # Consensus found
            consensus_text = max(largest_group, key=len)  # Take longest
            consensus_sources = [
                source for source, text in texts.items()
                if text in largest_group
            ]
            
            return {
                "consensus": consensus_text,
                "sources": consensus_sources,
                "confidence": len(consensus_sources) / len(texts),
                "type": "text"
            }
        else:
            # No clear consensus
            return {
                "consensus": None,
                "sources": [],
                "confidence": 0.0,
                "type": "none"
            }
    
    def _group_similar_texts(self, texts: Dict[str, str],
                           threshold: float = 0.7) -> List[List[str]]:
        """Group similar texts together"""
        if not texts:
            return []
        
        text_list = list(texts.values())
        
        groups = []
        used = set()
        
        for i, text1 in enumerate(text_list):
            if i in used:
                continue
            
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
    
    async def detect_contradictions(self, information: Dict[str, Any]) -> List[Dict]:
        """
        Detect contradictions between sources
        
        Args:
            information: Dictionary of source_id -> information
            
        Returns:
            List of contradictions
        """
        contradictions = []
        
        source_ids = list(information.keys())
        
        for i in range(len(source_ids)):
            for j in range(i + 1, len(source_ids)):
                source1 = source_ids[i]
                source2 = source_ids[j]
                
                comparison = await self.compare_information(
                    information[source1],
                    information[source2],
                    source1,
                    source2,
                    ComparisonMetric.CONTRADICTION
                )
                
                if comparison.result == ComparisonResult.CONTRADICTORY:
                    contradictions.append({
                        "source1": source1,
                        "source2": source2,
                        "info1": str(information[source1]),
                        "info2": str(information[source2]),
                        "confidence": comparison.score
                    })
        
        return contradictions
    
    # Callback Registration
    
    def on_comparison_complete(self, callback: Callable[[Comparison], None]):
        """Register comparison completion callback"""
        self._on_comparison_complete.append(callback)
    
    # Cleanup
    
    async def cleanup(self):
        """Clean up resources"""
        self._on_comparison_complete = []
        self.logger.info("Information Comparator cleaned up")
