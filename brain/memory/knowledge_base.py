"""
Knowledge Base Module
Manages structured knowledge storage and retrieval
"""

import asyncio
import json
import time
import os
import sqlite3
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from pathlib import Path
import hashlib

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler
from .cloud_memory import CloudMemory


@dataclass
class KnowledgeCategory:
    """Knowledge category"""
    name: str
    description: str = ""
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "parent": self.parent,
            "children": self.children
        }


@dataclass
class KnowledgeItem:
    """A single piece of knowledge"""
    id: str
    content: str
    category: str = "general"
    source: str = "unknown"
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
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
            "metadata": self.metadata
        }


class KnowledgeBase:
    """
    Manages structured knowledge storage and retrieval
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Configuration
        self._db_path = "/storage/emulated/0/Android/data/com.termux/files/home/JARVIS/memory/knowledge.db"
        
        # Knowledge storage
        self._knowledge: Dict[str, KnowledgeItem] = {}
        self._categories: Dict[str, KnowledgeCategory] = {}
        self._indexes: Dict[str, Dict] = {
            "category": {},
            "tag": {},
            "source": {}
        }
        
        # Cloud sync
        self._cloud_memory = None
        
        # State
        self._initialized = False
        
        # Callbacks
        self._on_knowledge_added: List[Callable[[KnowledgeItem], None]] = []
        self._on_knowledge_updated: List[Callable[[str, Dict], None]] = []
        self._on_knowledge_removed: List[Callable[[str], None]] = []
        
        # Ensure directory exists
        self._ensure_db_dir()
    
    def _ensure_db_dir(self):
        """Ensure database directory exists"""
        try:
            db_dir = os.path.dirname(self._db_path)
            os.makedirs(db_dir, exist_ok=True)
        except Exception as e:
            self.error_handler.handle_error(e, "ensure_db_dir")
    
    async def initialize(self):
        """Initialize the knowledge base"""
        try:
            # Initialize database
            await self._initialize_database()
            
            # Load existing knowledge
            await self._load_knowledge()
            
            # Initialize categories
            self._initialize_categories()
            
            self._initialized = True
            self.logger.info("Knowledge Base initialized")
            
        except Exception as e:
            self.error_handler.handle_error(e, "knowledge_base_initialize")
    
    async def _initialize_database(self):
        """Initialize the SQLite database"""
        try:
            # Connect to database
            self._connection = sqlite3.connect(self._db_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            
            # Create tables
            cursor = self._connection.cursor()
            
            # Knowledge items table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    tags TEXT NOT NULL,
                    references TEXT NOT NULL,
                    metadata TEXT NOT NULL
                )
            """)
            
            # Categories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    name TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    parent TEXT,
                    children TEXT NOT NULL
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_items(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_source ON knowledge_items(source)")
            
            self._connection.commit()
            
        except Exception as e:
            self.error_handler.handle_error(e, "initialize_database")
            connection = getattr(self, "_connection", None)
            if connection is not None:
                try:
                    connection.rollback()
                except Exception:
                    pass
    
    
    async def _load_knowledge(self):
        """Load knowledge from database"""
        try:
            cursor = self._connection.cursor()
            
            cursor.execute("""
                SELECT * FROM knowledge_items
            """)
            
            rows = cursor.fetchall()
            
            for row in rows:
                knowledge_item = KnowledgeItem(
                    id=row["id"],
                    content=row["content"],
                    category=row["category"],
                    source=row["source"],
                    confidence=row["confidence"],
                    timestamp=row["timestamp"],
                    tags=json.loads(row["tags"]),
                    references=json.loads(row["references"]),
                    metadata=json.loads(row["metadata"])
                )
                
                self._add_to_knowledge(knowledge_item, from_load=True)
            
            self.logger.info(f"Loaded {len(rows)} knowledge items")
            
        except Exception as e:
            self.error_handler.handle_error(e, "load_knowledge")
    
    def _initialize_categories(self):
        """Initialize default categories"""
        default_categories = [
            KnowledgeCategory(
                name="general",
                description="General knowledge"
            ),
            KnowledgeCategory(
                name="commands",
                description="User commands and patterns"
            ),
            KnowledgeCategory(
                name="preferences",
                description="User preferences"
            ),
            KnowledgeCategory(
                name="procedures",
                description="Task procedures and workflows"
            ),
            KnowledgeCategory(
                name="facts",
                description="Factual information"
            ),
            KnowledgeCategory(
                name="concepts",
                description="Concepts and explanations"
            ),
            KnowledgeCategory(
                name="apps",
                description="App capabilities and usage"
            ),
            KnowledgeCategory(
                name="files",
                description="File patterns and information"
            ),
            KnowledgeCategory(
                name="web",
                description="Web search patterns"
            )
        ]
        
        for category in default_categories:
            self._categories[category.name] = category
    
    # Knowledge Operations
    
    async def store(self, knowledge: Dict) -> str:
        """
        Store a piece of knowledge
        
        Args:
            knowledge: Knowledge dictionary to store
            
        Returns:
            Knowledge item ID
        """
        try:
            # Generate ID if not provided
            if "id" not in knowledge or not knowledge["id"]:
                content_hash = hashlib.md5(json.dumps(knowledge).encode()).hexdigest()
                knowledge["id"] = f"kn_{content_hash[:12]}_{int(time.time())}"
            
            # Create knowledge item
            knowledge_item = KnowledgeItem(
                id=knowledge["id"],
                content=knowledge.get("content", knowledge.get("_content", "")),
                category=knowledge.get("category", knowledge.get("_category", "general")),
                source=knowledge.get("source", knowledge.get("_source", "unknown")),
                confidence=knowledge.get("confidence", 0.8),
                timestamp=knowledge.get("timestamp", time.time()),
                tags=knowledge.get("tags", knowledge.get("_tags", [])),
                references=knowledge.get("references", knowledge.get("_references", [])),
                metadata=knowledge.get("metadata", knowledge.get("_metadata", {}))
            )
            
            # Add to knowledge base
            self._add_to_knowledge(knowledge_item)
            
            # Save to database
            await self._save_to_database(knowledge_item)
            
            self.logger.debug(f"Knowledge stored: {knowledge_item.id}")
            
            return knowledge_item.id
            
        except Exception as e:
            self.error_handler.handle_error(e, "store_knowledge")
            return ""
    
    async def retrieve(self, knowledge_id: str) -> Optional[KnowledgeItem]:
        """
        Retrieve a knowledge item
        
        Args:
            knowledge_id: ID of the knowledge item
            
        Returns:
            KnowledgeItem or None
        """
        return self._knowledge.get(knowledge_id)
    
    async def query(self, query: str, 
                  category: str = None,
                  limit: int = 10) -> List[Dict]:
        """
        Query knowledge
        
        Args:
            query: Search query
            category: Filter by category
            limit: Maximum number of results
            
        Returns:
            List of knowledge dictionaries
        """
        results = []
        
        try:
            # Get candidate IDs
            candidate_ids = self._get_candidate_ids(category)
            
            # Search content
            query_lower = query.lower()
            for knowledge_id in candidate_ids:
                if knowledge_id in self._knowledge:
                    item = self._knowledge[knowledge_id]
                    
                    # Check if query matches content
                    if query_lower in item.content.lower():
                        results.append(item.to_dict())
                        if len(results) >= limit:
                            break
            
            # Sort by confidence and timestamp
            results.sort(key=lambda x: (x.get("confidence", 0), -x.get("timestamp", 0)), reverse=True)
            
            return results
            
        except Exception as e:
            self.error_handler.handle_error(e, "query_knowledge")
            return results
    
    async def update(self, knowledge_id: str, updates: Dict) -> bool:
        """
        Update a knowledge item
        
        Args:
            knowledge_id: ID of the knowledge item
            updates: Dictionary of updates
            
        Returns:
            True if successful
        """
        try:
            if knowledge_id not in self._knowledge:
                return False
            
            item = self._knowledge[knowledge_id]
            
            # Remove from indexes
            self._remove_from_indexes(item)
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            
            # Add back to indexes
            self._add_to_indexes(item)
            
            # Update in database
            await self._update_in_database(item)
            
            # Notify update
            for callback in self._on_knowledge_updated:
                try:
                    callback(knowledge_id, updates)
                except Exception as e:
                    self.error_handler.handle_error(e, "knowledge_updated_callback")
            
            self.logger.debug(f"Knowledge updated: {knowledge_id}")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "update_knowledge")
            return False
    
    async def delete(self, knowledge_id: str) -> bool:
        """
        Delete a knowledge item
        
        Args:
            knowledge_id: ID of the knowledge item
            
        Returns:
            True if successful
        """
        try:
            if knowledge_id not in self._knowledge:
                return False
            
            item = self._knowledge[knowledge_id]
            
            # Remove from indexes
            self._remove_from_indexes(item)
            
            # Remove from knowledge base
            del self._knowledge[knowledge_id]
            
            # Delete from database
            await self._delete_from_database(knowledge_id)
            
            # Notify removal
            for callback in self._on_knowledge_removed:
                try:
                    callback(knowledge_id)
                except Exception as e:
                    self.error_handler.handle_error(e, "knowledge_removed_callback")
            
            self.logger.debug(f"Knowledge deleted: {knowledge_id}")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "delete_knowledge")
            return False
    
    # Category Operations
    
    def get_category(self, category_name: str) -> Optional[KnowledgeCategory]:
        """Get a category by name"""
        return self._categories.get(category_name)
    
    def get_all_categories(self) -> List[KnowledgeCategory]:
        """Get all categories"""
        return list(self._categories.values())
    
    def add_category(self, category: KnowledgeCategory) -> bool:
        """Add a new category"""
        if category.name in self._categories:
            return False
        
        self._categories[category.name] = category
        
        # Add to parent's children if parent exists
        if category.parent and category.parent in self._categories:
            parent = self._categories[category.parent]
            if category.name not in parent.children:
                parent.children.append(category.name)
        
        self.logger.info(f"Category added: {category.name}")
        return True
    
    def remove_category(self, category_name: str) -> bool:
        """Remove a category"""
        if category_name not in self._categories:
            return False
        
        category = self._categories[category_name]
        
        # Remove from parent's children
        if category.parent and category.parent in self._categories:
            parent = self._categories[category.parent]
            if category_name in parent.children:
                parent.children.remove(category_name)
        
        # Remove all knowledge in this category
        category_ids = self._indexes["category"].get(category_name, [])
        for knowledge_id in category_ids:
            if knowledge_id in self._knowledge:
                del self._knowledge[knowledge_id]
        
        # Remove from indexes
        if category_name in self._indexes["category"]:
            del self._indexes["category"][category_name]
        
        # Remove category
        del self._categories[category_name]
        
        self.logger.info(f"Category removed: {category_name}")
        return True
    
    # Cloud Sync
    
    async def sync_with_cloud(self) -> bool:
        """Sync knowledge with cloud storage (real: rclone via CloudMemory)"""
        try:
            if self._cloud_memory is None:
                self._cloud_memory = CloudMemory(self.config, self.logger)
                await self._cloud_memory.initialize()
            
            items = [item.to_dict() for item in self._knowledge.values()]
            success = await self._cloud_memory.sync_all(items)
            
            if success:
                self.logger.info(
                    f"Knowledge synced with cloud: {len(items)} item(s)"
                )
            else:
                self.logger.warning(
                    "Knowledge cloud sync did not complete; check the "
                    "rclone remote configuration"
                )
            return success
            
        except Exception as e:
            self.error_handler.handle_error(e, "sync_with_cloud")
            return False
    
    async def load_from_cloud(self) -> bool:
        """Load knowledge from cloud storage (real: rclone via CloudMemory)"""
        try:
            if self._cloud_memory is None:
                self._cloud_memory = CloudMemory(self.config, self.logger)
                await self._cloud_memory.initialize()
            
            downloaded = await self._cloud_memory.download_all()
            if not downloaded:
                self.logger.info("No knowledge items found in cloud storage")
                return True
            
            loaded = 0
            valid_fields = {
                "id", "content", "category", "source", "confidence",
                "timestamp", "tags", "references", "metadata"
            }
            for data in downloaded:
                if not isinstance(data, dict) or "id" not in data:
                    continue
                fields = {k: v for k, v in data.items() if k in valid_fields}
                if "content" not in fields:
                    continue
                item = KnowledgeItem(**fields)
                self._add_to_knowledge(item)
                await self._save_to_database(item)
                loaded += 1
            
            self.logger.info(f"Loaded {loaded} knowledge item(s) from cloud")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "load_from_cloud")
            return False
    
    # Statistics
    
    def get_statistics(self) -> Dict:
        """Get knowledge base statistics"""
        return {
            "total_items": len(self._knowledge),
            "total_categories": len(self._categories),
            "by_category": {cat: len(ids) for cat, ids in self._indexes["category"].items()},
            "by_source": {src: len(ids) for src, ids in self._indexes["source"].items()},
            "by_tag": {tag: len(ids) for tag, ids in self._indexes["tag"].items()}
        }
    
    # Internal Methods
    
    def _add_to_knowledge(self, item: KnowledgeItem, from_load: bool = False):
        """Add an item to knowledge base"""
        # Check if item already exists
        if item.id in self._knowledge:
            # Update existing item
            existing = self._knowledge[item.id]
            existing.content = item.content
            existing.category = item.category
            existing.source = item.source
            existing.confidence = item.confidence
            existing.timestamp = item.timestamp
            existing.tags = item.tags
            existing.references = item.references
            existing.metadata = item.metadata
        else:
            # Add new item
            self._knowledge[item.id] = item
        
        # Update indexes
        self._add_to_indexes(item)
        
        # Notify addition
        if not from_load:
            for callback in self._on_knowledge_added:
                try:
                    callback(item)
                except Exception as e:
                    self.error_handler.handle_error(e, "knowledge_added_callback")
    
    def _remove_from_indexes(self, item: KnowledgeItem):
        """Remove an item from indexes"""
        # Remove from category index
        if item.category in self._indexes["category"]:
            if item.id in self._indexes["category"][item.category]:
                self._indexes["category"][item.category].remove(item.id)
        
        # Remove from tag indexes
        for tag in item.tags:
            if tag in self._indexes["tag"]:
                if item.id in self._indexes["tag"][tag]:
                    self._indexes["tag"][tag].remove(item.id)
        
        # Remove from source index
        if item.source in self._indexes["source"]:
            if item.id in self._indexes["source"][item.source]:
                self._indexes["source"][item.source].remove(item.id)
    
    def _add_to_indexes(self, item: KnowledgeItem):
        """Add an item to indexes"""
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
        
        # Add to source index
        if item.source not in self._indexes["source"]:
            self._indexes["source"][item.source] = []
        if item.id not in self._indexes["source"][item.source]:
            self._indexes["source"][item.source].append(item.id)
    
    def _get_candidate_ids(self, category: str = None) -> List[str]:
        """Get candidate knowledge IDs based on filters"""
        if category:
            return self._indexes["category"].get(category, [])
        else:
            return list(self._knowledge.keys())
    
    async def _save_to_database(self, item: KnowledgeItem):
        """Save item to database"""
        try:
            cursor = self._connection.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO knowledge_items 
                (id, content, category, source, confidence, timestamp, 
                 tags, references, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.id,
                item.content,
                item.category,
                item.source,
                item.confidence,
                item.timestamp,
                json.dumps(item.tags),
                json.dumps(item.references),
                json.dumps(item.metadata)
            ))
            
            self._connection.commit()
            
        except Exception as e:
            self.error_handler.handle_error(e, "save_to_database")
            self._connection.rollback()
    
    async def _update_in_database(self, item: KnowledgeItem):
        """Update item in database"""
        await self._save_to_database(item)
    
    async def _delete_from_database(self, knowledge_id: str):
        """Delete item from database"""
        try:
            cursor = self._connection.cursor()
            
            cursor.execute("""
                DELETE FROM knowledge_items WHERE id = ?
            """, (knowledge_id,))
            
            self._connection.commit()
            
        except Exception as e:
            self.error_handler.handle_error(e, "delete_from_database")
            self._connection.rollback()
    
    # Callback Registration
    
    def on_knowledge_added(self, callback: Callable[[KnowledgeItem], None]):
        """Register knowledge added callback"""
        self._on_knowledge_added.append(callback)
    
    def on_knowledge_updated(self, callback: Callable[[str, Dict], None]):
        """Register knowledge updated callback"""
        self._on_knowledge_updated.append(callback)
    
    def on_knowledge_removed(self, callback: Callable[[str], None]):
        """Register knowledge removed callback"""
        self._on_knowledge_removed.append(callback)
    
    # Cleanup
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            # Close database connection
            if hasattr(self, '_connection') and self._connection:
                self._connection.close()
                self._connection = None
            
            # Clear knowledge
            self._knowledge = {}
            self._categories = {}
            self._indexes = {
                "category": {},
                "tag": {},
                "source": {}
            }
            
            self._initialized = False
            self.logger.info("Knowledge Base cleaned up")
            
        except Exception as e:
            self.error_handler.handle_error(e, "knowledge_base_cleanup")
