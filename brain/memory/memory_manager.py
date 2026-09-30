"""
Memory Manager Module
Manages all memory and knowledge storage operations
"""

import asyncio
import json
import time
import os
import sqlite3
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum, auto
import hashlib

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler
from .local_memory import LocalMemory
from .cloud_memory import CloudMemory
from .knowledge_base import KnowledgeBase


class MemoryType(Enum):
    """Types of memory"""
    SHORT_TERM = auto()
    LONG_TERM = auto()
    WORKING = auto()
    EPISODIC = auto()
    SEMANTIC = auto()
    PROCEDURAL = auto()


class StorageLocation(Enum):
    """Storage locations"""
    LOCAL = auto()
    CLOUD = auto()
    BOTH = auto()


@dataclass
class MemoryItem:
    """A single memory item"""
    id: str
    content: Any
    memory_type: MemoryType = MemoryType.SHORT_TERM
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    expiration: float = 0.0  # 0 = no expiration
    priority: int = 0
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.name,
            "category": self.category,
            "tags": self.tags,
            "timestamp": self.timestamp,
            "expiration": self.expiration,
            "priority": self.priority,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "metadata": self.metadata
        }
    
    def is_expired(self) -> bool:
        """Check if memory item has expired"""
        if self.expiration == 0:
            return False
        return time.time() > self.expiration


@dataclass
class MemoryStats:
    """Memory statistics"""
    total_items: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    by_location: Dict[str, int] = field(default_factory=dict)
    total_size: int = 0  # bytes
    last_cleanup: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "total_items": self.total_items,
            "by_type": self.by_type,
            "by_category": self.by_category,
            "by_location": self.by_location,
            "total_size": self.total_size,
            "last_cleanup": self.last_cleanup
        }


class MemoryManager:
    """
    Manages all memory operations
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Memory components
        self.local_memory = LocalMemory(config, logger)
        self.cloud_memory = CloudMemory(config, logger)
        self.knowledge_base = KnowledgeBase(config, logger)
        
        # Configuration
        self._memory_dir = "/storage/emulated/0/Android/data/com.termux/files/home/JARVIS/memory"
        self._max_memory_items = 10000
        self._max_memory_size = 100 * 1024 * 1024  # 100MB
        self._cleanup_interval = 3600  # 1 hour
        
        # State
        self._memory: Dict[str, MemoryItem] = {}
        self._indexes: Dict[str, Dict] = {
            "type": {},
            "category": {},
            "tag": {}
        }
        self._stats = MemoryStats()
        self._last_cleanup = 0.0
        
        # Callbacks
        self._on_memory_change: List[Callable[[str, MemoryItem], None]] = []
        self._on_cleanup: List[Callable[[int], None]] = []
        
        # Ensure memory directory exists
        self._ensure_memory_dir()
    
    def _ensure_memory_dir(self):
        """Ensure memory directory exists"""
        try:
            os.makedirs(self._memory_dir, exist_ok=True)
            self.logger.info(f"Memory directory: {self._memory_dir}")
        except Exception as e:
            self.error_handler.handle_error(e, "ensure_memory_dir")
    
    async def initialize(self):
        """Initialize the memory manager"""
        start_time = time.time()
        
        try:
            # Initialize components
            await self.local_memory.initialize()
            await self.cloud_memory.initialize()
            await self.knowledge_base.initialize()
            
            # Load existing memory
            await self._load_memory()
            
            # Start cleanup timer
            self._start_cleanup_timer()
            
            self.logger.info(f"Memory Manager initialized in {time.time() - start_time:.2f}s")
            
        except Exception as e:
            self.error_handler.handle_error(e, "memory_manager_initialize")
    
    async def _load_memory(self):
        """Load memory from storage"""
        try:
            # Load from local memory
            local_items = await self.local_memory.load_all()
            
            for item_data in local_items:
                self._add_to_memory(MemoryItem(**item_data), from_load=True)
            
            self.logger.info(f"Loaded {len(local_items)} memory items from local storage")
            
        except Exception as e:
            self.error_handler.handle_error(e, "load_memory")
    
    def _start_cleanup_timer(self):
        """Start periodic cleanup timer"""
        asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """Periodic cleanup loop"""
        while True:
            await asyncio.sleep(self._cleanup_interval)
            
            try:
                deleted = await self.cleanup_expired()
                if deleted > 0:
                    self.logger.info(f"Cleaned up {deleted} expired memory items")
                    
                    for callback in self._on_cleanup:
                        try:
                            callback(deleted)
                        except Exception as e:
                            self.error_handler.handle_error(e, "cleanup_callback")
            except Exception as e:
                self.error_handler.handle_error(e, "cleanup_loop")
    
    # Memory Operations
    
    async def store(self, content: Any, 
                   memory_type: MemoryType = MemoryType.SHORT_TERM,
                   category: str = "general",
                   tags: List[str] = None,
                   expiration: float = 0.0,
                   priority: int = 0,
                   metadata: Dict = None) -> str:
        """
        Store a memory item
        
        Args:
            content: Content to store
            memory_type: Type of memory
            category: Category for organization
            tags: Tags for indexing
            expiration: Expiration timestamp (0 = no expiration)
            priority: Priority level
            metadata: Additional metadata
            
        Returns:
            Memory item ID
        """
        try:
            # Generate ID
            content_str = str(content)
            content_hash = hashlib.md5(content_str.encode()).hexdigest()
            item_id = f"mem_{content_hash[:12]}_{int(time.time())}"
            
            # Create memory item
            item = MemoryItem(
                id=item_id,
                content=content,
                memory_type=memory_type,
                category=category,
                tags=tags or [],
                timestamp=time.time(),
                expiration=expiration,
                priority=priority,
                metadata=metadata or {}
            )
            
            # Add to memory
            self._add_to_memory(item)
            
            # Save to storage based on type
            if memory_type in [MemoryType.LONG_TERM, MemoryType.SEMANTIC, MemoryType.PROCEDURAL]:
                await self._save_to_long_term(item)
            else:
                await self._save_to_short_term(item)
            
            self.logger.debug(f"Memory stored: {item_id} ({memory_type.name})")
            
            return item_id
            
        except Exception as e:
            self.error_handler.handle_error(e, "store_memory")
            return ""
    
    async def retrieve(self, item_id: str) -> Optional[MemoryItem]:
        """
        Retrieve a memory item
        
        Args:
            item_id: ID of the memory item
            
        Returns:
            MemoryItem or None if not found
        """
        try:
            item = self._memory.get(item_id)
            if item:
                # Update access stats
                item.access_count += 1
                item.last_accessed = time.time()
                
                # Update in storage if modified
                await self._update_in_storage(item)
                
                self.logger.debug(f"Memory retrieved: {item_id}")
            
            return item
            
        except Exception as e:
            self.error_handler.handle_error(e, "retrieve_memory")
            return None
    
    async def delete(self, item_id: str) -> bool:
        """
        Delete a memory item
        
        Args:
            item_id: ID of the memory item
            
        Returns:
            True if successful
        """
        try:
            if item_id not in self._memory:
                return False
            
            item = self._memory[item_id]
            
            # Remove from indexes
            self._remove_from_indexes(item)
            
            # Remove from memory
            del self._memory[item_id]
            
            # Delete from storage
            await self._delete_from_storage(item)
            
            self.logger.debug(f"Memory deleted: {item_id}")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "delete_memory")
            return False
    
    async def update(self, item_id: str, 
                    updates: Dict) -> bool:
        """
        Update a memory item
        
        Args:
            item_id: ID of the memory item
            updates: Dictionary of updates
            
        Returns:
            True if successful
        """
        try:
            if item_id not in self._memory:
                return False
            
            item = self._memory[item_id]
            
            # Remove from indexes
            self._remove_from_indexes(item)
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            
            # Add back to indexes
            self._add_to_indexes(item)
            
            # Update in storage
            await self._update_in_storage(item)
            
            self.logger.debug(f"Memory updated: {item_id}")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "update_memory")
            return False
    
    # Query Methods
    
    async def query(self, query: str, 
                   memory_type: MemoryType = None,
                   category: str = None,
                   tags: List[str] = None,
                   limit: int = 20) -> List[MemoryItem]:
        """
        Query memory items
        
        Args:
            query: Search query
            memory_type: Filter by memory type
            category: Filter by category
            tags: Filter by tags
            limit: Maximum number of results
            
        Returns:
            List of matching memory items
        """
        results = []
        
        try:
            # Get candidate items
            candidate_ids = self._get_candidate_ids(memory_type, category, tags)
            
            # Search content
            query_lower = query.lower()
            for item_id in candidate_ids:
                if item_id in self._memory:
                    item = self._memory[item_id]
                    
                    # Check content
                    content_str = str(item.content)
                    if query_lower in content_str.lower():
                        results.append(item)
                        if len(results) >= limit:
                            break
            
            # Sort by priority and recency
            results.sort(key=lambda x: (x.priority, -x.timestamp), reverse=True)
            
            return results[:limit]
            
        except Exception as e:
            self.error_handler.handle_error(e, "query_memory")
            return results
    
    async def query_by_type(self, memory_type: MemoryType,
                           limit: int = 20) -> List[MemoryItem]:
        """Query memory items by type"""
        type_index = self._indexes["type"].get(memory_type.name, [])
        items = [self._memory[id] for id in type_index if id in self._memory]
        
        # Sort by priority and recency
        items.sort(key=lambda x: (x.priority, -x.timestamp), reverse=True)
        
        return items[:limit]
    
    async def query_by_category(self, category: str,
                                limit: int = 20) -> List[MemoryItem]:
        """Query memory items by category"""
        category_index = self._indexes["category"].get(category, [])
        items = [self._memory[id] for id in category_index if id in self._memory]
        
        # Sort by priority and recency
        items.sort(key=lambda x: (x.priority, -x.timestamp), reverse=True)
        
        return items[:limit]
    
    async def query_by_tag(self, tag: str,
                         limit: int = 20) -> List[MemoryItem]:
        """Query memory items by tag"""
        tag_index = self._indexes["tag"].get(tag, [])
        items = [self._memory[id] for id in tag_index if id in self._memory]
        
        # Sort by priority and recency
        items.sort(key=lambda x: (x.priority, -x.timestamp), reverse=True)
        
        return items[:limit]
    
    def _get_candidate_ids(self, memory_type: MemoryType = None,
                          category: str = None,
                          tags: List[str] = None) -> List[str]:
        """Get candidate item IDs based on filters"""
        candidate_ids = set(self._memory.keys())
        
        # Filter by type
        if memory_type:
            type_index = self._indexes["type"].get(memory_type.name, [])
            candidate_ids.intersection_update(type_index)
        
        # Filter by category
        if category:
            category_index = self._indexes["category"].get(category, [])
            candidate_ids.intersection_update(category_index)
        
        # Filter by tags
        if tags:
            for tag in tags:
                tag_index = self._indexes["tag"].get(tag, [])
                candidate_ids.intersection_update(tag_index)
        
        return list(candidate_ids)
    
    # Knowledge Management
    
    async def store_knowledge(self, knowledge: Dict, 
                            category: str = "general",
                            source: str = "unknown",
                            tags: List[str] = None) -> str:
        """
        Store structured knowledge
        
        Args:
            knowledge: Knowledge to store
            category: Category for organization
            source: Source of knowledge
            tags: Tags for indexing
            
        Returns:
            Knowledge ID
        """
        try:
            # Add metadata
            knowledge["_category"] = category
            knowledge["_source"] = source
            knowledge["_timestamp"] = time.time()
            
            # Store in knowledge base
            knowledge_id = await self.knowledge_base.store(knowledge)
            
            # Also store in memory for quick access
            await self.store(
                knowledge,
                MemoryType.SEMANTIC,
                category,
                tags,
                0,  # No expiration for knowledge
                10,  # High priority
                {"knowledge_id": knowledge_id, "source": source}
            )
            
            return knowledge_id
            
        except Exception as e:
            self.error_handler.handle_error(e, "store_knowledge")
            return ""
    
    async def query_knowledge(self, query: str, 
                             category: str = None,
                             limit: int = 10) -> List[Dict]:
        """
        Query the knowledge base
        
        Args:
            query: Search query
            category: Filter by category
            limit: Maximum number of results
            
        Returns:
            List of knowledge items
        """
        return await self.knowledge_base.query(query, category, limit)
    
    async def update_knowledge(self, knowledge_id: str,
                              updates: Dict) -> bool:
        """Update knowledge"""
        return await self.knowledge_base.update(knowledge_id, updates)
    
    async def delete_knowledge(self, knowledge_id: str) -> bool:
        """Delete knowledge"""
        return await self.knowledge_base.delete(knowledge_id)
    
    # Preferences Management
    
    async def store_preference(self, key: str, value: Any) -> bool:
        """Store a user preference"""
        try:
            # Store in local memory
            await self.local_memory.store_preference(key, value)
            
            # Also store in memory
            await self.store(
                {"key": key, "value": value},
                MemoryType.LONG_TERM,
                "preferences",
                ["preference", key],
                0,  # No expiration
                5,   # Medium priority
                {"type": "preference"}
            )
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "store_preference")
            return False
    
    async def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference"""
        try:
            # Try to get from local memory first
            value = await self.local_memory.get_preference(key)
            if value is not None:
                return value
            
            # Fallback to default
            return default
            
        except Exception as e:
            self.error_handler.handle_error(e, "get_preference")
            return default
    
    async def load_preferences(self) -> Dict:
        """Load all preferences"""
        try:
            return await self.local_memory.load_all_preferences()
        except Exception as e:
            self.error_handler.handle_error(e, "load_preferences")
            return {}
    
    async def save_preferences(self, preferences: Dict) -> bool:
        """Save all preferences"""
        try:
            await self.local_memory.save_all_preferences(preferences)
            return True
        except Exception as e:
            self.error_handler.handle_error(e, "save_preferences")
            return False
    
    # Cloud Sync
    
    async def sync_with_cloud(self) -> bool:
        """Sync memory with cloud storage"""
        try:
            # Sync knowledge base
            await self.knowledge_base.sync_with_cloud()
            
            # Sync long-term memory
            long_term_items = [
                item for item in self._memory.values()
                if item.memory_type in [MemoryType.LONG_TERM, MemoryType.SEMANTIC, MemoryType.PROCEDURAL]
            ]
            
            for item in long_term_items:
                await self.cloud_memory.save(item)
            
            self.logger.info("Memory synced with cloud")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "sync_with_cloud")
            return False
    
    async def load_from_cloud(self) -> bool:
        """Load memory from cloud storage"""
        try:
            # Load knowledge from cloud
            await self.knowledge_base.load_from_cloud()
            
            # Load long-term memory from cloud
            cloud_items = await self.cloud_memory.load_all()
            
            for item_data in cloud_items:
                item = MemoryItem(**item_data)
                self._add_to_memory(item, from_load=True)
            
            self.logger.info(f"Loaded {len(cloud_items)} memory items from cloud")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "load_from_cloud")
            return False
    
    # Cleanup
    
    async def cleanup_expired(self) -> int:
        """Clean up expired memory items"""
        deleted_count = 0
        
        try:
            current_time = time.time()
            expired_ids = [
                id for id, item in self._memory.items()
                if item.is_expired()
            ]
            
            for item_id in expired_ids:
                if await self.delete(item_id):
                    deleted_count += 1
            
            self._last_cleanup = current_time
            self._stats.last_cleanup = current_time
            
            return deleted_count
            
        except Exception as e:
            self.error_handler.handle_error(e, "cleanup_expired")
            return deleted_count
    
    async def cleanup_temp_data(self) -> int:
        """Clean up temporary data"""
        deleted_count = 0
        
        try:
            # Delete short-term memory items
            short_term_ids = [
                id for id, item in self._memory.items()
                if item.memory_type == MemoryType.SHORT_TERM and
                item.access_count < 3  # Low access count
            ]
            
            for item_id in short_term_ids:
                if await self.delete(item_id):
                    deleted_count += 1
            
            # Also cleanup local memory
            deleted_count += await self.local_memory.cleanup_temp()
            
            return deleted_count
            
        except Exception as e:
            self.error_handler.handle_error(e, "cleanup_temp_data")
            return deleted_count
    
    async def optimize_memory(self) -> int:
        """Optimize memory usage"""
        optimized_count = 0
        
        try:
            # Check memory size
            current_size = self._calculate_memory_size()
            
            if current_size > self._max_memory_size:
                # Find low-priority, old items
                candidates = [
                    item for item in self._memory.values()
                    if item.priority < 5 and item.memory_type != MemoryType.LONG_TERM
                ]
                
                # Sort by priority and access count
                candidates.sort(key=lambda x: (x.priority, x.access_count, x.timestamp))
                
                # Delete until under limit
                for item in candidates:
                    if self._calculate_memory_size() <= self._max_memory_size:
                        break
                    
                    if await self.delete(item.id):
                        optimized_count += 1
            
            return optimized_count
            
        except Exception as e:
            self.error_handler.handle_error(e, "optimize_memory")
            return optimized_count
    
    def _calculate_memory_size(self) -> int:
        """Calculate current memory size in bytes"""
        total_size = 0
        
        for item in self._memory.values():
            # Estimate size
            content_size = len(str(item.content)) * 4  # Approximate
            metadata_size = len(json.dumps(item.metadata)) if item.metadata else 0
            total_size += content_size + metadata_size + 100  # Overhead
        
        return total_size
    
    # Statistics
    
    def get_statistics(self) -> MemoryStats:
        """Get memory statistics"""
        self._stats.total_items = len(self._memory)
        
        # Update by type
        self._stats.by_type = {}
        for memory_type in MemoryType:
            count = len(self._indexes["type"].get(memory_type.name, []))
            self._stats.by_type[memory_type.name] = count
        
        # Update by category
        self._stats.by_category = {}
        for category, ids in self._indexes["category"].items():
            self._stats.by_category[category] = len(ids)
        
        # Update by location
        self._stats.by_location = {
            "local": len(self._memory),
            "cloud": 0  # Would be updated from cloud
        }
        
        # Update total size
        self._stats.total_size = self._calculate_memory_size()
        
        return self._stats
    
    # Internal Methods
    
    def _add_to_memory(self, item: MemoryItem, from_load: bool = False):
        """Add an item to memory"""
        # Check if item already exists
        if item.id in self._memory:
            # Update existing item
            existing = self._memory[item.id]
            existing.content = item.content
            existing.memory_type = item.memory_type
            existing.category = item.category
            existing.tags = item.tags
            existing.expiration = item.expiration
            existing.priority = item.priority
            existing.metadata = item.metadata
            existing.timestamp = item.timestamp
        else:
            # Add new item
            self._memory[item.id] = item
        
        # Update indexes
        self._add_to_indexes(item)
        
        # Update statistics
        self._stats.total_items = len(self._memory)
        
        # Notify change
        if not from_load:
            for callback in self._on_memory_change:
                try:
                    callback(item.id, item)
                except Exception as e:
                    self.error_handler.handle_error(e, "memory_change_callback")
    
    def _remove_from_indexes(self, item: MemoryItem):
        """Remove an item from indexes"""
        # Remove from type index
        type_index = self._indexes["type"]
        if item.memory_type.name in type_index:
            if item.id in type_index[item.memory_type.name]:
                type_index[item.memory_type.name].remove(item.id)
        
        # Remove from category index
        category_index = self._indexes["category"]
        if item.category in category_index:
            if item.id in category_index[item.category]:
                category_index[item.category].remove(item.id)
        
        # Remove from tag indexes
        tag_index = self._indexes["tag"]
        for tag in item.tags:
            if tag in tag_index:
                if item.id in tag_index[tag]:
                    tag_index[tag].remove(item.id)
    
    def _add_to_indexes(self, item: MemoryItem):
        """Add an item to indexes"""
        # Add to type index
        if item.memory_type.name not in self._indexes["type"]:
            self._indexes["type"][item.memory_type.name] = []
        if item.id not in self._indexes["type"][item.memory_type.name]:
            self._indexes["type"][item.memory_type.name].append(item.id)
        
        # Add to category index
        if item.category not in self._indexes["category"]:
            self._indexes["category"][item.category] = []
        if item.id not in self._indexes["category"][item.category]:
            self._indexes["category"][item.category].append(item.id)
        
        # Add to tag indexes
        for tag in item.tags:
            if tag not in self._indexes["tag"]:
                self._indexes["tag"][tag] = []
            if item.id not in self._indexes["tag"][tag]:
                self._indexes["tag"][tag].append(item.id)
    
    async def _save_to_long_term(self, item: MemoryItem):
        """Save item to long-term storage"""
        await self.local_memory.save(item)
    
    async def _save_to_short_term(self, item: MemoryItem):
        """Save item to short-term storage"""
        await self.local_memory.save(item)
    
    async def _delete_from_storage(self, item: MemoryItem):
        """Delete item from storage"""
        await self.local_memory.delete(item.id)
    
    async def _update_in_storage(self, item: MemoryItem):
        """Update item in storage"""
        await self.local_memory.save(item)
    
    # Callback Registration
    
    def on_memory_change(self, callback: Callable[[str, MemoryItem], None]):
        """Register memory change callback"""
        self._on_memory_change.append(callback)
    
    def on_cleanup(self, callback: Callable[[int], None]):
        """Register cleanup callback"""
        self._on_cleanup.append(callback)
    
    # Cleanup
    
    async def cleanup(self):
        """Clean up all resources"""
        try:
            # Cleanup expired items
            await self.cleanup_expired()
            
            # Cleanup temporary data
            await self.cleanup_temp_data()
            
            # Cleanup components
            await self.local_memory.cleanup()
            await self.cloud_memory.cleanup()
            await self.knowledge_base.cleanup()
            
            # Clear memory
            self._memory = {}
            self._indexes = {
                "type": {},
                "category": {},
                "tag": {}
            }
            self._stats = MemoryStats()
            
            self.logger.info("Memory Manager cleaned up")
            
        except Exception as e:
            self.error_handler.handle_error(e, "memory_manager_cleanup")
