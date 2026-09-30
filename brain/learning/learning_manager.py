"""
Learning Manager Module
Manages all learning-related operations and knowledge acquisition
"""

import asyncio
import json
import time
import os
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import hashlib

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler
from ..memory.memory_manager import MemoryManager
from .multi_source_learner import MultiSourceLearner
from .knowledge_merger import KnowledgeMerger
from .information_comparator import InformationComparator


class LearningMode(Enum):
    """Learning modes"""
    PASSIVE = auto()  # Learn from user interactions
    ACTIVE = auto()   # Actively seek new knowledge
    HYBRID = auto()   # Both passive and active
    OFF = auto()      # No learning


class LearningSource(Enum):
    """Sources of learning"""
    USER_INTERACTION = auto()
    APP_INTEGRATION = auto()
    WEB_SEARCH = auto()
    FILE_ANALYSIS = auto()
    SCREENSHOT = auto()
    VOICE_INPUT = auto()
    MANUAL_ENTRY = auto()
    IMPORT = auto()


@dataclass
class LearningEvent:
    """Represents a learning event"""
    event_id: str
    source: LearningSource
    data: Dict
    timestamp: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    confidence: float = 1.0
    processed: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "event_id": self.event_id,
            "source": self.source.name,
            "data": self.data,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "confidence": self.confidence,
            "processed": self.processed
        }


@dataclass
class LearningResult:
    """Result of a learning operation"""
    success: bool
    learned_items: List[str] = field(default_factory=list)
    new_knowledge: Dict = field(default_factory=dict)
    updated_knowledge: Dict = field(default_factory=dict)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    processing_time: float = 0.0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "learned_items": self.learned_items,
            "new_knowledge": self.new_knowledge,
            "updated_knowledge": self.updated_knowledge,
            "confidence_scores": self.confidence_scores,
            "processing_time": self.processing_time,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


@dataclass
class KnowledgeItem:
    """A single piece of knowledge"""
    id: str
    content: str
    category: str
    source: str
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    usage_count: int = 0
    last_used: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "source": self.source,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "references": self.references,
            "usage_count": self.usage_count,
            "last_used": self.last_used
        }
    
    def get_age(self) -> float:
        """Get age in seconds"""
        return time.time() - self.timestamp


class LearningManager:
    """
    Manages all learning operations and knowledge acquisition
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Learning state
        self._mode = LearningMode.HYBRID
        self._is_learning = True
        self._learning_enabled = True
        
        # Components
        self.memory_manager = MemoryManager(config, logger)
        self.multi_source_learner = MultiSourceLearner(config, logger)
        self.knowledge_merger = KnowledgeMerger(config, logger)
        self.information_comparator = InformationComparator(config, logger)
        
        # Learning queue
        self._learning_queue: List[LearningEvent] = []
        self._processing = False
        self._event_counter = 0
        
        # Knowledge base
        self._knowledge_base: Dict[str, KnowledgeItem] = {}
        self._category_index: Dict[str, List[str]] = {}
        self._tag_index: Dict[str, List[str]] = {}
        
        # Statistics
        self._stats = {
            "total_events": 0,
            "processed_events": 0,
            "learned_items": 0,
            "knowledge_count": 0,
            "last_learning_time": 0.0
        }
        
        # Callbacks
        self._on_learning_complete: List[Callable[[LearningResult], None]] = []
        self._on_new_knowledge: List[Callable[[KnowledgeItem], None]] = []
        self._on_learning_event: List[Callable[[LearningEvent], None]] = []
    
    async def initialize(self):
        """Initialize the learning manager"""
        start_time = time.time()
        
        try:
            # Initialize memory
            await self.memory_manager.initialize()
            
            # Load existing knowledge
            await self._load_knowledge_base()
            
            # Initialize components
            await self.multi_source_learner.initialize()
            await self.knowledge_merger.initialize()
            await self.information_comparator.initialize()
            
            self._stats["last_learning_time"] = time.time()
            
            self.logger.info(f"Learning Manager initialized in {time.time() - start_time:.2f}s")
            
        except Exception as e:
            self.error_handler.handle_error(e, "learning_manager_initialize")
    
    async def _load_knowledge_base(self):
        """Load knowledge base from memory"""
        try:
            knowledge_data = await self.memory_manager.load_knowledge()
            
            for item_data in knowledge_data:
                knowledge_item = KnowledgeItem(
                    id=item_data.get("id", ""),
                    content=item_data.get("content", ""),
                    category=item_data.get("category", "general"),
                    source=item_data.get("source", "unknown"),
                    confidence=item_data.get("confidence", 0.0),
                    timestamp=item_data.get("timestamp", time.time()),
                    tags=item_data.get("tags", []),
                    references=item_data.get("references", []),
                    usage_count=item_data.get("usage_count", 0),
                    last_used=item_data.get("last_used", time.time())
                )
                
                self._add_to_knowledge_base(knowledge_item)
            
            self._stats["knowledge_count"] = len(self._knowledge_base)
            self.logger.info(f"Loaded {len(self._knowledge_base)} knowledge items")
            
        except Exception as e:
            self.error_handler.handle_error(e, "load_knowledge_base")
    
    async def save_state(self):
        """Save learning state"""
        try:
            # Save knowledge base
            knowledge_data = [item.to_dict() for item in self._knowledge_base.values()]
            await self.memory_manager.save_knowledge(knowledge_data)
            
            # Save statistics
            await self.memory_manager.save_learning_stats(self._stats)
            
            self.logger.info("Learning state saved")
            
        except Exception as e:
            self.error_handler.handle_error(e, "save_learning_state")
    
    # Learning Mode Control
    
    def set_mode(self, mode: LearningMode) -> bool:
        """Set learning mode"""
        self._mode = mode
        self.logger.info(f"Learning mode set to: {mode.name}")
        return True
    
    def get_mode(self) -> LearningMode:
        """Get current learning mode"""
        return self._mode
    
    def enable_learning(self) -> bool:
        """Enable learning"""
        self._learning_enabled = True
        self.logger.info("Learning enabled")
        return True
    
    def disable_learning(self) -> bool:
        """Disable learning"""
        self._learning_enabled = False
        self.logger.info("Learning disabled")
        return True
    
    def is_learning_enabled(self) -> bool:
        """Check if learning is enabled"""
        return self._learning_enabled and self._mode != LearningMode.OFF
    
    # Learning Event Methods
    
    async def add_learning_event(self, source: LearningSource, 
                               data: Dict, 
                               tags: List[str] = None,
                               confidence: float = 1.0) -> str:
        """
        Add a learning event to the queue
        
        Args:
            source: Source of the learning event
            data: Data to learn from
            tags: Tags for categorization
            confidence: Confidence in the data
            
        Returns:
            Event ID
        """
        if not self._learning_enabled:
            return ""
        
        event_id = f"event_{int(time.time())}_{self._event_counter}"
        self._event_counter += 1
        
        event = LearningEvent(
            event_id=event_id,
            source=source,
            data=data,
            tags=tags or [],
            confidence=confidence
        )
        
        self._learning_queue.append(event)
        self._stats["total_events"] += 1
        
        # Notify event
        for callback in self._on_learning_event:
            try:
                callback(event)
            except Exception as e:
                self.error_handler.handle_error(e, "learning_event_callback")
        
        self.logger.debug(f"Learning event added: {event_id} from {source.name}")
        
        # Process queue if not already processing
        if not self._processing:
            asyncio.create_task(self._process_queue())
        
        return event_id
    
    async def _process_queue(self):
        """Process the learning queue"""
        if self._processing:
            return
        
        self._processing = True
        
        while self._learning_queue:
            event = self._learning_queue.pop(0)
            
            try:
                # Process the event
                result = await self._process_event(event)
                
                if result:
                    self._stats["processed_events"] += 1
                    
                    # Notify completion
                    for callback in self._on_learning_complete:
                        try:
                            callback(result)
                        except Exception as e:
                            self.error_handler.handle_error(e, "learning_complete_callback")
                
            except Exception as e:
                self.error_handler.handle_error(e, f"process_event_{event.event_id}")
        
        self._processing = False
    
    async def _process_event(self, event: LearningEvent) -> Optional[LearningResult]:
        """Process a single learning event"""
        start_time = time.time()
        
        try:
            # Mark as processed
            event.processed = True
            
            # Extract knowledge from the event
            extracted_knowledge = await self._extract_knowledge_from_event(event)
            
            if not extracted_knowledge:
                self.logger.debug(f"No knowledge extracted from event: {event.event_id}")
                return None
            
            # Add to knowledge base
            new_items = []
            for category, items in extracted_knowledge.items():
                for item_data in items:
                    knowledge_item = await self._create_knowledge_item(
                        item_data,
                        category,
                        event.source
                    )
                    
                    if knowledge_item:
                        self._add_to_knowledge_base(knowledge_item)
                        new_items.append(knowledge_item)
                        self._stats["learned_items"] += 1
                        self._stats["knowledge_count"] = len(self._knowledge_base)
            
            # Create result
            result = LearningResult(
                success=True,
                learned_items=[item.id for item in new_items],
                new_knowledge={cat: len(items) for cat, items in extracted_knowledge.items()},
                processing_time=time.time() - start_time,
                metadata={
                    "event_id": event.event_id,
                    "source": event.source.name,
                    "tags": event.tags
                }
            )
            
            self._stats["last_learning_time"] = time.time()
            
            # Notify new knowledge
            for item in new_items:
                for callback in self._on_new_knowledge:
                    try:
                        callback(item)
                    except Exception as e:
                        self.error_handler.handle_error(e, "new_knowledge_callback")
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, f"process_event_{event.event_id}")
            return LearningResult(
                success=False,
                processing_time=time.time() - start_time,
                metadata={"event_id": event.event_id, "error": str(e)}
            )
    
    async def _extract_knowledge_from_event(self, event: LearningEvent) -> Dict[str, List[Dict]]:
        """Extract knowledge from a learning event"""
        extracted = {}
        
        try:
            # Route to appropriate extractor based on source
            if event.source == LearningSource.USER_INTERACTION:
                extracted = await self._extract_from_user_interaction(event.data)
            elif event.source == LearningSource.APP_INTEGRATION:
                extracted = await self._extract_from_app_integration(event.data)
            elif event.source == LearningSource.WEB_SEARCH:
                extracted = await self._extract_from_web_search(event.data)
            elif event.source == LearningSource.FILE_ANALYSIS:
                extracted = await self._extract_from_file_analysis(event.data)
            elif event.source == LearningSource.SCREENSHOT:
                extracted = await self._extract_from_screenshot(event.data)
            elif event.source == LearningSource.VOICE_INPUT:
                extracted = await self._extract_from_voice_input(event.data)
            elif event.source == LearningSource.MANUAL_ENTRY:
                extracted = await self._extract_from_manual_entry(event.data)
            
            return extracted
            
        except Exception as e:
            self.error_handler.handle_error(e, f"extract_knowledge_{event.event_id}")
            return extracted
    
    async def _extract_from_user_interaction(self, data: Dict) -> Dict[str, List[Dict]]:
        """Extract knowledge from user interaction"""
        extracted = {}
        
        # Extract command patterns
        if "command" in data:
            command = data["command"]
            intent = data.get("intent", "")
            
            extracted.setdefault("commands", []).append({
                "command": command,
                "intent": intent,
                "timestamp": time.time(),
                "confidence": data.get("confidence", 1.0)
            })
        
        # Extract preferences
        if "preference" in data:
            extracted.setdefault("preferences", []).append({
                "preference": data["preference"],
                "value": data.get("value", True),
                "timestamp": time.time()
            })
        
        # Extract corrections
        if "correction" in data:
            extracted.setdefault("corrections", []).append({
                "original": data.get("original", ""),
                "corrected": data["correction"],
                "timestamp": time.time()
            })
        
        return extracted
    
    async def _extract_from_app_integration(self, data: Dict) -> Dict[str, List[Dict]]:
        """Extract knowledge from app integration"""
        extracted = {}
        
        app = data.get("app", "unknown")
        action = data.get("action", "")
        result = data.get("result", {})
        
        # Extract app capabilities
        extracted.setdefault("app_capabilities", []).append({
            "app": app,
            "action": action,
            "success": data.get("success", False),
            "timestamp": time.time()
        })
        
        # Extract information from results
        if isinstance(result, dict):
            for key, value in result.items():
                if isinstance(value, str) and len(value) > 20:
                    extracted.setdefault("app_responses", []).append({
                        "app": app,
                        "key": key,
                        "value": value,
                        "timestamp": time.time()
                    })
        
        return extracted
    
    async def _extract_from_web_search(self, data: Dict) -> Dict[str, List[Dict]]:
        """Extract knowledge from web search"""
        extracted = {}
        
        query = data.get("query", "")
        results = data.get("results", [])
        source = data.get("source", "unknown")
        
        # Extract search patterns
        extracted.setdefault("search_patterns", []).append({
            "query": query,
            "source": source,
            "timestamp": time.time()
        })
        
        # Extract information from results
        for result in results:
            if isinstance(result, dict):
                title = result.get("title", "")
                url = result.get("url", "")
                snippet = result.get("snippet", "")
                
                if title:
                    extracted.setdefault("web_knowledge", []).append({
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "source": source,
                        "query": query,
                        "timestamp": time.time()
                    })
        
        return extracted
    
    async def _extract_from_file_analysis(self, data: Dict) -> Dict[str, List[Dict]]:
        """Extract knowledge from file analysis"""
        extracted = {}
        
        file_path = data.get("file_path", "")
        file_type = data.get("file_type", "unknown")
        content = data.get("content", "")
        
        # Extract file patterns
        extracted.setdefault("file_patterns", []).append({
            "file_path": file_path,
            "file_type": file_type,
            "timestamp": time.time()
        })
        
        # Extract content-based knowledge
        if content and len(content) > 50:
            extracted.setdefault("file_content", []).append({
                "file_path": file_path,
                "file_type": file_type,
                "content": content[:500],  # Store first 500 chars
                "timestamp": time.time()
            })
        
        return extracted
    
    async def _extract_from_screenshot(self, data: Dict) -> Dict[str, List[Dict]]:
        """Extract knowledge from screenshot"""
        extracted = {}
        
        image_path = data.get("image_path", "")
        ocr_text = data.get("ocr_text", "")
        
        # Extract screenshot patterns
        extracted.setdefault("screenshot_patterns", []).append({
            "image_path": image_path,
            "timestamp": time.time()
        })
        
        # Extract text from OCR
        if ocr_text and len(ocr_text) > 10:
            extracted.setdefault("screenshot_text", []).append({
                "image_path": image_path,
                "text": ocr_text[:500],  # Store first 500 chars
                "timestamp": time.time()
            })
        
        return extracted
    
    async def _extract_from_voice_input(self, data: Dict) -> Dict[str, List[Dict]]:
        """Extract knowledge from voice input"""
        extracted = {}
        
        text = data.get("text", "")
        confidence = data.get("confidence", 0.0)
        
        # Extract voice patterns
        extracted.setdefault("voice_patterns", []).append({
            "text": text,
            "confidence": confidence,
            "timestamp": time.time()
        })
        
        return extracted
    
    async def _extract_from_manual_entry(self, data: Dict) -> Dict[str, List[Dict]]:
        """Extract knowledge from manual entry"""
        extracted = {}
        
        category = data.get("category", "general")
        content = data.get("content", "")
        
        if content:
            extracted.setdefault(category, []).append({
                "content": content,
                "source": "manual",
                "timestamp": time.time()
            })
        
        return extracted
    
    async def _create_knowledge_item(self, data: Dict, category: str, 
                                     source: LearningSource) -> Optional[KnowledgeItem]:
        """Create a knowledge item from extracted data"""
        try:
            # Generate ID
            content = str(data)
            content_hash = hashlib.md5(content.encode()).hexdigest()
            item_id = f"knowledge_{content_hash[:12]}_{int(time.time())}"
            
            # Create knowledge item
            item = KnowledgeItem(
                id=item_id,
                content=content,
                category=category,
                source=source.name,
                confidence=data.get("confidence", 0.8),
                timestamp=time.time(),
                tags=data.get("tags", []),
                references=data.get("references", [])
            )
            
            return item
            
        except Exception as e:
            self.error_handler.handle_error(e, "create_knowledge_item")
            return None
    
    def _add_to_knowledge_base(self, item: KnowledgeItem):
        """Add a knowledge item to the knowledge base"""
        # Check if item already exists
        if item.id in self._knowledge_base:
            # Update existing item
            existing = self._knowledge_base[item.id]
            existing.content = item.content
            existing.category = item.category
            existing.confidence = max(existing.confidence, item.confidence)
            existing.timestamp = time.time()
            existing.tags = list(set(existing.tags + item.tags))
            existing.references = list(set(existing.references + item.references))
            existing.usage_count += 1
            existing.last_used = time.time()
            
            self.logger.debug(f"Updated knowledge item: {item.id}")
        else:
            # Add new item
            self._knowledge_base[item.id] = item
            
            # Update indexes
            if item.category not in self._category_index:
                self._category_index[item.category] = []
            self._category_index[item.category].append(item.id)
            
            for tag in item.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = []
                self._tag_index[tag].append(item.id)
            
            self.logger.debug(f"Added knowledge item: {item.id} ({item.category})")
            
            # Notify new knowledge
            for callback in self._on_new_knowledge:
                try:
                    callback(item)
                except Exception as e:
                    self.error_handler.handle_error(e, "new_knowledge_callback")
    
    # Learning from Execution
    
    async def learn_from_execution(self, command_data: Dict, 
                                   task_plan: Dict, 
                                   execution_result: Dict) -> Optional[LearningResult]:
        """
        Learn from a task execution
        
        Args:
            command_data: The parsed command data
            task_plan: The task plan that was executed
            execution_result: The result of the execution
            
        Returns:
            LearningResult or None
        """
        if not self._learning_enabled:
            return None
        
        try:
            # Create learning event
            event_data = {
                "command": command_data.get("text", ""),
                "intent": command_data.get("intent", ""),
                "plan": task_plan,
                "result": execution_result,
                "success": execution_result.get("status") == "success"
            }
            
            tags = [
                "execution",
                command_data.get("intent", "unknown").lower()
            ]
            
            confidence = execution_result.get("confidence", 0.8)
            
            event_id = await self.add_learning_event(
                LearningSource.USER_INTERACTION,
                event_data,
                tags,
                confidence
            )
            
            # Return a basic result (detailed result will come from event processing)
            return LearningResult(
                success=True,
                processing_time=0.0,
                metadata={"event_id": event_id}
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "learn_from_execution")
            return LearningResult(
                success=False,
                processing_time=0.0,
                metadata={"error": str(e)}
            )
    
    async def learn_from_feedback(self, feedback: Dict) -> Optional[LearningResult]:
        """
        Learn from user feedback
        
        Args:
            feedback: Feedback data from user
            
        Returns:
            LearningResult or None
        """
        if not self._learning_enabled:
            return None
        
        try:
            # Create learning event
            event_data = {
                "feedback": feedback,
                "timestamp": time.time()
            }
            
            tags = ["feedback", "user_input"]
            
            event_id = await self.add_learning_event(
                LearningSource.MANUAL_ENTRY,
                event_data,
                tags,
                1.0
            )
            
            return LearningResult(
                success=True,
                processing_time=0.0,
                metadata={"event_id": event_id}
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "learn_from_feedback")
            return LearningResult(
                success=False,
                processing_time=0.0,
                metadata={"error": str(e)}
            )
    
    # Knowledge Query Methods
    
    async def query_knowledge(self, query: str, 
                           category: str = None,
                           tags: List[str] = None,
                           limit: int = 10) -> List[KnowledgeItem]:
        """
        Query the knowledge base
        
        Args:
            query: Search query
            category: Filter by category
            tags: Filter by tags
            limit: Maximum number of results
            
        Returns:
            List of matching knowledge items
        """
        results = []
        
        try:
            # Search by category
            if category and category in self._category_index:
                candidate_ids = self._category_index[category]
            else:
                candidate_ids = list(self._knowledge_base.keys())
            
            # Filter by tags
            if tags:
                tag_set = set(tags)
                candidate_ids = [
                    id for id in candidate_ids
                    if id in self._knowledge_base and
                    tag_set.intersection(set(self._knowledge_base[id].tags))
                ]
            
            # Search content
            query_lower = query.lower()
            for id in candidate_ids:
                if id in self._knowledge_base:
                    item = self._knowledge_base[id]
                    if query_lower in item.content.lower():
                        results.append(item)
                        if len(results) >= limit:
                            break
            
            # Sort by confidence and usage
            results.sort(key=lambda x: (x.confidence * 0.7 + x.usage_count * 0.3), reverse=True)
            
            return results[:limit]
            
        except Exception as e:
            self.error_handler.handle_error(e, "query_knowledge")
            return results
    
    async def get_knowledge_by_category(self, category: str, 
                                        limit: int = 20) -> List[KnowledgeItem]:
        """Get knowledge items by category"""
        if category not in self._category_index:
            return []
        
        item_ids = self._category_index[category]
        items = [self._knowledge_base[id] for id in item_ids if id in self._knowledge_base]
        
        # Sort by confidence and usage
        items.sort(key=lambda x: (x.confidence * 0.7 + x.usage_count * 0.3), reverse=True)
        
        return items[:limit]
    
    async def get_knowledge_by_tag(self, tag: str, 
                                  limit: int = 20) -> List[KnowledgeItem]:
        """Get knowledge items by tag"""
        if tag not in self._tag_index:
            return []
        
        item_ids = self._tag_index[tag]
        items = [self._knowledge_base[id] for id in item_ids if id in self._knowledge_base]
        
        # Sort by confidence and usage
        items.sort(key=lambda x: (x.confidence * 0.7 + x.usage_count * 0.3), reverse=True)
        
        return items[:limit]
    
    # Knowledge Management
    
    async def add_knowledge(self, content: str, category: str, 
                          source: str = "manual",
                          tags: List[str] = None,
                          confidence: float = 0.8) -> Optional[str]:
        """
        Add knowledge manually
        
        Args:
            content: Knowledge content
            category: Knowledge category
            source: Source of knowledge
            tags: Tags for categorization
            confidence: Confidence in the knowledge
            
        Returns:
            Knowledge item ID or None
        """
        try:
            # Create knowledge item
            item = KnowledgeItem(
                id=f"manual_{int(time.time())}_{len(self._knowledge_base)}",
                content=content,
                category=category,
                source=source,
                confidence=confidence,
                tags=tags or [],
                timestamp=time.time()
            )
            
            # Add to knowledge base
            self._add_to_knowledge_base(item)
            
            # Save to memory
            await self.memory_manager.save_knowledge([item.to_dict()])
            
            return item.id
            
        except Exception as e:
            self.error_handler.handle_error(e, "add_knowledge")
            return None
    
    async def update_knowledge(self, item_id: str, 
                            updates: Dict) -> bool:
        """
        Update a knowledge item
        
        Args:
            item_id: ID of the knowledge item
            updates: Dictionary of updates
            
        Returns:
            True if successful
        """
        try:
            if item_id not in self._knowledge_base:
                return False
            
            item = self._knowledge_base[item_id]
            
            for key, value in updates.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            
            # Update timestamp
            item.last_used = time.time()
            
            # Save to memory
            await self.memory_manager.save_knowledge([item.to_dict()])
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "update_knowledge")
            return False
    
    async def remove_knowledge(self, item_id: str) -> bool:
        """
        Remove a knowledge item
        
        Args:
            item_id: ID of the knowledge item
            
        Returns:
            True if successful
        """
        try:
            if item_id not in self._knowledge_base:
                return False
            
            item = self._knowledge_base[item_id]
            
            # Remove from indexes
            if item.category in self._category_index:
                if item_id in self._category_index[item.category]:
                    self._category_index[item.category].remove(item_id)
            
            for tag in item.tags:
                if tag in self._tag_index:
                    if item_id in self._tag_index[tag]:
                        self._tag_index[tag].remove(item_id)
            
            # Remove from knowledge base
            del self._knowledge_base[item_id]
            
            # Delete from memory
            await self.memory_manager.delete_knowledge(item_id)
            
            self._stats["knowledge_count"] = len(self._knowledge_base)
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "remove_knowledge")
            return False
    
    # Multi-source Learning
    
    async def learn_from_multiple_sources(self, query: str, 
                                        sources: List[str]) -> Dict:
        """
        Learn from multiple sources simultaneously
        
        Args:
            query: The query to learn about
            sources: List of source identifiers
            
        Returns:
            Dictionary of source -> learning result
        """
        results = {}
        
        for source in sources:
            try:
                # Use multi-source learner
                result = await self.multi_source_learner.learn_from_source(
                    source, query
                )
                
                if result:
                    results[source] = result
                    
                    # Create learning event
                    await self.add_learning_event(
                        LearningSource.APP_INTEGRATION,
                        {"source": source, "query": query, "result": result},
                        ["multi_source", query.lower()],
                        result.get("confidence", 0.8)
                    )
                
            except Exception as e:
                self.error_handler.handle_error(e, f"learn_from_source_{source}")
                results[source] = {"error": str(e)}
        
        return results
    
    async def merge_knowledge_from_sources(self, query: str, 
                                           sources: List[str]) -> Dict:
        """
        Merge knowledge from multiple sources
        
        Args:
            query: The query
            sources: List of sources
            
        Returns:
            Merged knowledge result
        """
        # Learn from all sources
        results = await self.learn_from_multiple_sources(query, sources)
        
        # Extract text from results
        texts = {}
        for source, result in results.items():
            if isinstance(result, dict):
                if "text" in result:
                    texts[source] = result["text"]
                elif "response" in result:
                    texts[source] = result["response"]
                elif "content" in result:
                    texts[source] = result["content"]
        
        # Merge texts
        merged = self.knowledge_merger.merge_texts(texts)
        
        return {
            "query": query,
            "sources": sources,
            "merged_text": merged,
            "individual_results": results
        }
    
    async def compare_information_from_sources(self, query: str, 
                                              sources: List[str]) -> Dict:
        """
        Compare information from multiple sources
        
        Args:
            query: The query
            sources: List of sources
            
        Returns:
            Comparison result
        """
        # Learn from all sources
        results = await self.learn_from_multiple_sources(query, sources)
        
        # Compare results
        comparison = self.information_comparator.compare_results(results)
        
        return {
            "query": query,
            "sources": sources,
            "comparison": comparison,
            "results": results
        }
    
    # Statistics and Analytics
    
    def get_statistics(self) -> Dict:
        """Get learning statistics"""
        return {
            "total_events": self._stats["total_events"],
            "processed_events": self._stats["processed_events"],
            "learned_items": self._stats["learned_items"],
            "knowledge_count": self._stats["knowledge_count"],
            "last_learning_time": self._stats["last_learning_time"],
            "mode": self._mode.name,
            "learning_enabled": self._learning_enabled,
            "categories": {cat: len(ids) for cat, ids in self._category_index.items()},
            "tags": {tag: len(ids) for tag, ids in self._tag_index.items()}
        }
    
    def get_category_stats(self) -> Dict[str, Dict]:
        """Get statistics by category"""
        stats = {}
        
        for category, item_ids in self._category_index.items():
            items = [self._knowledge_base[id] for id in item_ids if id in self._knowledge_base]
            
            if items:
                avg_confidence = sum(item.confidence for item in items) / len(items)
                avg_usage = sum(item.usage_count for item in items) / len(items)
                
                stats[category] = {
                    "count": len(items),
                    "avg_confidence": avg_confidence,
                    "avg_usage": avg_usage,
                    "total_usage": sum(item.usage_count for item in items)
                }
        
        return stats
    
    # Callback Registration
    
    def on_learning_complete(self, callback: Callable[[LearningResult], None]):
        """Register learning completion callback"""
        self._on_learning_complete.append(callback)
    
    def on_new_knowledge(self, callback: Callable[[KnowledgeItem], None]):
        """Register new knowledge callback"""
        self._on_new_knowledge.append(callback)
    
    def on_learning_event(self, callback: Callable[[LearningEvent], None]):
        """Register learning event callback"""
        self._on_learning_event.append(callback)
    
    # Cleanup
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            # Save state
            await self.save_state()
            
            # Clear queues
            self._learning_queue = []
            self._processing = False
            self._event_counter = 0
            
            self.logger.info("Learning Manager cleaned up")
            
        except Exception as e:
            self.error_handler.handle_error(e, "learning_manager_cleanup")
