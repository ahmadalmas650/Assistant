"""
Multi-Source Learner Module
Learns from multiple information sources
"""

import asyncio
import json
import time
import re
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import hashlib

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler
from ..modules.app_integrator import AppIntegrator, AppInfo, AppAction


class SourceType(Enum):
    """Types of information sources"""
    AI_ASSISTANT = auto()
    WEB_SEARCH = auto()
    DATABASE = auto()
    FILE = auto()
    USER_INPUT = auto()
    LIVE_SCREEN = auto()
    VOICE = auto()
    API = auto()
    UNKNOWN = auto()


@dataclass
class SourceInfo:
    """Information about a source"""
    id: str
    name: str
    source_type: SourceType
    capabilities: List[str] = field(default_factory=list)
    priority: int = 0
    reliability: float = 0.8
    last_used: float = 0.0
    usage_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "source_type": self.source_type.name,
            "capabilities": self.capabilities,
            "priority": self.priority,
            "reliability": self.reliability,
            "last_used": self.last_used,
            "usage_count": self.usage_count
        }


@dataclass
class LearningData:
    """Data learned from a source"""
    source_id: str
    content: str
    category: str = "general"
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "source_id": self.source_id,
            "content": self.content,
            "category": self.category,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "references": self.references,
            "metadata": self.metadata
        }


@dataclass
class SourceResult:
    """Result from a source"""
    source_id: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    confidence: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "source_id": self.source_id,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "processing_time": self.processing_time,
            "confidence": self.confidence
        }


class MultiSourceLearner:
    """
    Learns from multiple information sources
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Source registry
        self._sources: Dict[str, SourceInfo] = {}
        self._source_map: Dict[SourceType, List[str]] = {}
        
        # App integrator for source access
        self.app_integrator = AppIntegrator(config, logger)
        
        # Learning state
        self._is_learning = False
        self._learning_queue: List[Tuple[str, str]] = []  # (source_id, query)
        self._processing = False
        
        # Callbacks
        self._on_source_result: List[Callable[[SourceResult], None]] = []
        self._on_learning_complete: List[Callable[[Dict], None]] = []
        
        # Initialize
        self._initialize()
    
    async def initialize(self):
        """Initialize the multi-source learner"""
        # Register known sources
        self._register_known_sources()
        
        # Initialize app integrator
        await self.app_integrator.initialize()
        
        self.logger.info("Multi-Source Learner initialized")
    
    def _register_known_sources(self):
        """Register known information sources"""
        # AI Assistants
        ai_sources = [
            SourceInfo(
                id="chatgpt",
                name="ChatGPT",
                source_type=SourceType.AI_ASSISTANT,
                capabilities=[
                    "text_generation",
                    "question_answering",
                    "information_retrieval",
                    "code_generation",
                    "summarization",
                    "explanation"
                ],
                priority=1,
                reliability=0.9
            ),
            SourceInfo(
                id="deepseek",
                name="DeepSeek",
                source_type=SourceType.AI_ASSISTANT,
                capabilities=[
                    "text_generation",
                    "reasoning",
                    "analysis",
                    "problem_solving"
                ],
                priority=2,
                reliability=0.9
            ),
            SourceInfo(
                id="grok",
                name="Grok",
                source_type=SourceType.AI_ASSISTANT,
                capabilities=[
                    "text_generation",
                    "question_answering",
                    "real_time_information"
                ],
                priority=3,
                reliability=0.85
            ),
        ]
        
        # Web Sources
        web_sources = [
            SourceInfo(
                id="chrome",
                name="Chrome",
                source_type=SourceType.WEB_SEARCH,
                capabilities=[
                    "web_search",
                    "web_browsing",
                    "web_scraping",
                    "information_retrieval"
                ],
                priority=4,
                reliability=0.85
            ),
            SourceInfo(
                id="youtube",
                name="YouTube",
                source_type=SourceType.WEB_SEARCH,
                capabilities=[
                    "video_search",
                    "video_information",
                    "tutorial_retrieval"
                ],
                priority=5,
                reliability=0.8
            ),
        ]
        
        # Combine all sources
        all_sources = ai_sources + web_sources
        
        for source in all_sources:
            self._sources[source.id] = source
            if source.source_type not in self._source_map:
                self._source_map[source.source_type] = []
            self._source_map[source.source_type].append(source.id)
    
    def register_source(self, source: SourceInfo) -> bool:
        """Register a new source"""
        if source.id in self._sources:
            return False
        
        self._sources[source.id] = source
        
        if source.source_type not in self._source_map:
            self._source_map[source.source_type] = []
        self._source_map[source.source_type].append(source.id)
        
        self.logger.info(f"Source registered: {source.name} ({source.id})")
        return True
    
    def unregister_source(self, source_id: str) -> bool:
        """Unregister a source"""
        if source_id not in self._sources:
            return False
        
        source = self._sources[source_id]
        
        # Remove from source map
        if source.source_type in self._source_map:
            if source_id in self._source_map[source.source_type]:
                self._source_map[source.source_type].remove(source_id)
        
        del self._sources[source_id]
        
        self.logger.info(f"Source unregistered: {source_id}")
        return True
    
    def get_source(self, source_id: str) -> Optional[SourceInfo]:
        """Get source information"""
        return self._sources.get(source_id)
    
    def get_sources_by_type(self, source_type: SourceType) -> List[SourceInfo]:
        """Get sources by type"""
        source_ids = self._source_map.get(source_type, [])
        return [self._sources[id] for id in source_ids if id in self._sources]
    
    def get_all_sources(self) -> List[SourceInfo]:
        """Get all registered sources"""
        return list(self._sources.values())
    
    def is_source_available(self, source_id: str) -> bool:
        """Check if a source is available"""
        source = self._sources.get(source_id)
        if not source:
            return False
        
        # Check if source is available via app integrator
        if source.source_type == SourceType.AI_ASSISTANT:
            package_map = {
                "chatgpt": "com.chatgpt",
                "deepseek": "com.deepseek.app",
                "grok": "com.grok"
            }
            package = package_map.get(source_id)
            if package:
                return self.app_integrator.is_app_installed(package)
        
        elif source.source_type == SourceType.WEB_SEARCH:
            package_map = {
                "chrome": "com.android.chrome",
                "youtube": "com.google.android.youtube"
            }
            package = package_map.get(source_id)
            if package:
                return self.app_integrator.is_app_installed(package)
        
        return True
    
    async def learn_from_source(self, source_id: str, query: str) -> Optional[Dict]:
        """
        Learn from a specific source
        
        Args:
            source_id: ID of the source
            query: The query to learn about
            
        Returns:
            Learning result or None
        """
        start_time = time.time()
        
        try:
            # Get source info
            source = self._sources.get(source_id)
            if not source:
                return {"error": f"Source not found: {source_id}"}
            
            # Check if source is available
            if not self.is_source_available(source_id):
                return {"error": f"Source not available: {source_id}"}
            
            # Process based on source type
            if source.source_type == SourceType.AI_ASSISTANT:
                result = await self._learn_from_ai(source_id, query)
            elif source.source_type == SourceType.WEB_SEARCH:
                result = await self._learn_from_web(source_id, query)
            else:
                result = await self._learn_from_generic(source_id, query)
            
            # Update source usage
            source.last_used = time.time()
            source.usage_count += 1
            
            # Add processing time
            if result and isinstance(result, dict):
                result["processing_time"] = time.time() - start_time
                result["source_id"] = source_id
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, f"learn_from_source_{source_id}")
            return {"error": str(e), "processing_time": time.time() - start_time}
    
    async def _learn_from_ai(self, source_id: str, query: str) -> Dict:
        """Learn from an AI assistant source"""
        # Map source IDs to package names
        package_map = {
            "chatgpt": "com.chatgpt",
            "deepseek": "com.deepseek.app",
            "grok": "com.grok"
        }
        
        package = package_map.get(source_id)
        if not package:
            return {"error": f"Unknown AI source: {source_id}"}
        
        # Use app integrator to query the AI
        result = await self.app_integrator.execute_action(
            package,
            AppAction.QUERY,
            query=query
        )
        
        if result and result.success and result.data:
            return {
                "success": True,
                "response": result.data.get("response", result.data),
                "confidence": result.data.get("confidence", 0.9),
                "source": source_id
            }
        else:
            return {
                "success": False,
                "error": result.error if result else "No response",
                "source": source_id
            }
    
    async def _learn_from_web(self, source_id: str, query: str) -> Dict:
        """Learn from a web source"""
        # Map source IDs to package names
        package_map = {
            "chrome": "com.android.chrome",
            "youtube": "com.google.android.youtube"
        }
        
        package = package_map.get(source_id)
        if not package:
            return {"error": f"Unknown web source: {source_id}"}
        
        # Use app integrator to search
        result = await self.app_integrator.execute_action(
            package,
            AppAction.SEARCH,
            query=query
        )
        
        if result and result.success and result.data:
            return {
                "success": True,
                "results": result.data.get("results", result.data),
                "confidence": 0.85,
                "source": source_id
            }
        else:
            return {
                "success": False,
                "error": result.error if result else "No results",
                "source": source_id
            }
    
    async def _learn_from_generic(self, source_id: str, query: str) -> Dict:
        """
        Learn from a generic (non AI / non web) source.

        There is no automated flow for generic sources yet: the
        learner only knows how to drive AI assistant apps and web
        apps through the app integrator. Instead of inventing a
        response, fail honestly so the caller can pick a source
        that has a real flow.
        """
        return {
            "success": False,
            "error": (
                f"No automated learning flow exists for generic source "
                f"'{source_id}'; supported flows are AI assistant apps "
                f"and web apps"
            ),
            "source": source_id
        }

    async def learn_from_multiple_sources(self, query: str, 
                                           source_ids: List[str] = None) -> Dict[str, Dict]:
        """
        Learn from multiple sources
        
        Args:
            query: The query to learn about
            source_ids: List of source IDs (None for all available)
            
        Returns:
            Dictionary of source_id -> result
        """
        results = {}
        
        # Get sources to query
        if source_ids is None:
            sources = self.get_all_sources()
        else:
            sources = [self._sources.get(sid) for sid in source_ids if sid in self._sources]
        
        # Query all sources concurrently
        tasks = []
        for source in sources:
            if self.is_source_available(source.id):
                task = asyncio.create_task(
                    self.learn_from_source(source.id, query)
                )
                tasks.append((source.id, task))
        
        # Wait for all tasks
        for source_id, task in tasks:
            try:
                result = await task
                results[source_id] = result
                
                # Notify source result
                source_result = SourceResult(
                    source_id=source_id,
                    success=result.get("success", False),
                    data=result,
                    processing_time=result.get("processing_time", 0)
                )
                
                for callback in self._on_source_result:
                    try:
                        callback(source_result)
                    except Exception as e:
                        self.error_handler.handle_error(e, "source_result_callback")
                        
            except Exception as e:
                self.error_handler.handle_error(e, f"learn_from_source_{source_id}")
                results[source_id] = {"error": str(e)}
        
        # Notify learning complete
        for callback in self._on_learning_complete:
            try:
                callback(results)
            except Exception as e:
                self.error_handler.handle_error(e, "learning_complete_callback")
        
        return results
    
    async def learn_with_fallback(self, query: str, 
                                primary_sources: List[str],
                                fallback_sources: List[str]) -> Dict:
        """
        Learn with fallback sources if primary sources fail
        
        Args:
            query: The query to learn about
            primary_sources: List of primary source IDs
            fallback_sources: List of fallback source IDs
            
        Returns:
            Learning result with source information
        """
        # Try primary sources first
        primary_results = await self.learn_from_multiple_sources(query, primary_sources)
        
        # Check if we got good results from primary sources
        good_results = {k: v for k, v in primary_results.items() 
                       if v.get("success", False) and v.get("confidence", 0) > 0.7}
        
        if good_results:
            return {
                "query": query,
                "sources": primary_sources,
                "results": primary_results,
                "used_fallback": False
            }
        
        # Use fallback sources
        fallback_results = await self.learn_from_multiple_sources(query, fallback_sources)
        
        return {
            "query": query,
            "primary_sources": primary_sources,
            "fallback_sources": fallback_sources,
            "primary_results": primary_results,
            "fallback_results": fallback_results,
            "used_fallback": True
        }
    
    async def get_best_result(self, query: str, 
                             source_ids: List[str] = None) -> Optional[Dict]:
        """
        Get the best result from multiple sources
        
        Args:
            query: The query
            source_ids: List of source IDs to use
            
        Returns:
            Best result or None
        """
        results = await self.learn_from_multiple_sources(query, source_ids)
        
        # Find best result
        best_source = None
        best_result = None
        best_confidence = 0.0
        
        for source_id, result in results.items():
            if result.get("success", False):
                confidence = result.get("confidence", 0.0)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_source = source_id
                    best_result = result
        
        if best_result:
            best_result["best_source"] = best_source
            best_result["best_confidence"] = best_confidence
        
        return best_result
    
    async def extract_knowledge(self, query: str, 
                               sources: List[str] = None) -> List[LearningData]:
        """
        Extract structured knowledge from sources
        
        Args:
            query: The query
            sources: List of source IDs
            
        Returns:
            List of LearningData objects
        """
        results = await self.learn_from_multiple_sources(query, sources)
        
        knowledge_items = []
        
        for source_id, result in results.items():
            if result.get("success", False):
                content = result.get("response", result.get("results", ""))
                
                if isinstance(content, dict):
                    content = str(content)
                
                if content and len(content) > 20:
                    knowledge_item = LearningData(
                        source_id=source_id,
                        content=content,
                        category=self._determine_category(query),
                        confidence=result.get("confidence", 0.8),
                        tags=[query.lower(), source_id],
                        metadata={"query": query}
                    )
                    knowledge_items.append(knowledge_item)
        
        return knowledge_items
    
    def _determine_category(self, query: str) -> str:
        """Determine category from query"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["how to", "tutorial", "guide", "steps"]):
            return "procedure"
        elif any(word in query_lower for word in ["what is", "define", "explain", "meaning"]):
            return "definition"
        elif any(word in query_lower for word in ["why", "reason", "cause"]):
            return "explanation"
        elif any(word in query_lower for word in ["when", "date", "time", "year"]):
            return "temporal"
        elif any(word in query_lower for word in ["where", "location", "place"]):
            return "location"
        elif any(word in query_lower for word in ["who", "person", "name"]):
            return "person"
        else:
            return "general"
    
    async def compare_sources(self, query: str, 
                            source_ids: List[str]) -> Dict:
        """
        Compare results from different sources
        
        Args:
            query: The query
            source_ids: List of source IDs
            
        Returns:
            Comparison result
        """
        results = await self.learn_from_multiple_sources(query, source_ids)
        
        comparison = {
            "query": query,
            "sources": source_ids,
            "results": results,
            "agreements": [],
            "disagreements": [],
            "unique_information": {}
        }
        
        # Extract text from results
        texts = {}
        for source_id, result in results.items():
            if result.get("success", False):
                content = result.get("response", result.get("results", ""))
                if isinstance(content, dict):
                    content = str(content)
                texts[source_id] = content
        
        # Compare texts
        for i, (source1, text1) in enumerate(texts.items()):
            for j, (source2, text2) in enumerate(texts.items()):
                if i < j:
                    similarity = self._calculate_similarity(text1, text2)
                    
                    if similarity > 0.8:
                        comparison["agreements"].append({
                            "source1": source1,
                            "source2": source2,
                            "similarity": similarity
                        })
                    elif similarity < 0.3:
                        comparison["disagreements"].append({
                            "source1": source1,
                            "source2": source2,
                            "similarity": similarity
                        })
        
        # Find unique information
        for source_id, text in texts.items():
            unique_info = []
            for other_id, other_text in texts.items():
                if source_id != other_id:
                    similarity = self._calculate_similarity(text, other_text)
                    if similarity < 0.5:
                        # Extract unique parts
                        unique_info.append(f"Unique from {source_id}")
            
            if unique_info:
                comparison["unique_information"][source_id] = unique_info
        
        return comparison
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (0-1)"""
        # Simple implementation: Jaccard similarity on words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    # Queue Management
    
    async def queue_learning_task(self, source_id: str, query: str) -> str:
        """
        Queue a learning task
        
        Args:
            source_id: Source ID
            query: Query to learn about
            
        Returns:
            Task ID
        """
        task_id = f"task_{int(time.time())}_{len(self._learning_queue)}"
        self._learning_queue.append((source_id, query))
        
        self.logger.debug(f"Learning task queued: {task_id}")
        
        # Process queue if not already processing
        if not self._processing:
            asyncio.create_task(self._process_queue())
        
        return task_id
    
    async def _process_queue(self):
        """Process the learning queue"""
        if self._processing:
            return
        
        self._processing = True
        
        while self._learning_queue:
            source_id, query = self._learning_queue.pop(0)
            
            try:
                await self.learn_from_source(source_id, query)
            except Exception as e:
                self.error_handler.handle_error(e, f"queue_process_{source_id}")
        
        self._processing = False
    
    # Source Management
    
    def get_source_stats(self) -> Dict[str, Dict]:
        """Get statistics for all sources"""
        stats = {}
        
        for source_id, source in self._sources.items():
            stats[source_id] = {
                "name": source.name,
                "type": source.source_type.name,
                "priority": source.priority,
                "reliability": source.reliability,
                "usage_count": source.usage_count,
                "last_used": source.last_used,
                "available": self.is_source_available(source_id)
            }
        
        return stats
    
    def prioritize_source(self, source_id: str, priority: int) -> bool:
        """Set priority for a source"""
        if source_id not in self._sources:
            return False
        
        self._sources[source_id].priority = priority
        self.logger.info(f"Source priority set: {source_id} = {priority}")
        return True
    
    def set_source_reliability(self, source_id: str, reliability: float) -> bool:
        """Set reliability for a source"""
        if source_id not in self._sources or not (0 <= reliability <= 1):
            return False
        
        self._sources[source_id].reliability = reliability
        self.logger.info(f"Source reliability set: {source_id} = {reliability}")
        return True
    
    # Callback Registration
    
    def on_source_result(self, callback: Callable[[SourceResult], None]):
        """Register source result callback"""
        self._on_source_result.append(callback)
    
    def on_learning_complete(self, callback: Callable[[Dict], None]):
        """Register learning complete callback"""
        self._on_learning_complete.append(callback)
    
    # Cleanup
    
    async def cleanup(self):
        """Clean up resources"""
        self._learning_queue = []
        self._processing = False
        self.logger.info("Multi-Source Learner cleaned up")
