"""
Local Memory Module
Handles local storage of memory and data
"""

import asyncio
import json
import time
import os
import sqlite3
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler


@dataclass
class LocalMemoryConfig:
    """Configuration for local memory"""
    db_path: str = "/storage/emulated/0/Android/data/com.termux/files/home/JARVIS/memory/local.db"
    max_size: int = 50 * 1024 * 1024  # 50MB
    cleanup_interval: int = 3600  # 1 hour


class LocalMemory:
    """
    Manages local memory storage using SQLite
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Configuration
        self._db_path = getattr(config, 'db_path', LocalMemoryConfig().db_path)
        self._max_size = getattr(config, 'max_size', LocalMemoryConfig().max_size)
        
        # Database connection
        self._connection = None
        self._initialized = False
        
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
        """Initialize the local memory"""
        try:
            # Connect to database
            self._connection = sqlite3.connect(self._db_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            
            # Create tables
            await self._create_tables()
            
            self._initialized = True
            self.logger.info(f"Local memory initialized: {self._db_path}")
            
        except Exception as e:
            self.error_handler.handle_error(e, "local_memory_initialize")
    
    async def _create_tables(self):
        """Create database tables"""
        try:
            cursor = self._connection.cursor()
            
            # Memory items table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    expiration REAL NOT NULL,
                    priority INTEGER NOT NULL,
                    access_count INTEGER NOT NULL,
                    last_accessed REAL NOT NULL,
                    metadata TEXT NOT NULL
                )
            """)
            
            # Preferences table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            
            # Knowledge base table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    tags TEXT NOT NULL,
                    references TEXT NOT NULL,
                    usage_count INTEGER NOT NULL,
                    last_used REAL NOT NULL,
                    metadata TEXT NOT NULL
                )
            """)
            
            # Learning stats table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_stats (
                    key TEXT PRIMARY KEY,
                    value REAL NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_items(memory_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_items(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_expiration ON memory_items(expiration)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_base(category)")
            
            self._connection.commit()
            
        except Exception as e:
            self.error_handler.handle_error(e, "create_tables")
            self._connection.rollback()
    
    def _get_cursor(self):
        """Get a database cursor"""
        if not self._connection:
            raise Exception("Database not initialized")
        return self._connection.cursor()
    
    # Memory Item Operations
    
    async def save(self, item: Any) -> bool:
        """Save a memory item to local storage"""
        try:
            cursor = self._get_cursor()
            
            # Convert item to dictionary
            item_dict = item.to_dict() if hasattr(item, 'to_dict') else {
                "id": getattr(item, 'id', str(time.time())),
                "content": getattr(item, 'content', ''),
                "memory_type": getattr(item, 'memory_type', 'SHORT_TERM').name,
                "category": getattr(item, 'category', 'general'),
                "tags": json.dumps(getattr(item, 'tags', [])),
                "timestamp": getattr(item, 'timestamp', time.time()),
                "expiration": getattr(item, 'expiration', 0.0),
                "priority": getattr(item, 'priority', 0),
                "access_count": getattr(item, 'access_count', 0),
                "last_accessed": getattr(item, 'last_accessed', time.time()),
                "metadata": json.dumps(getattr(item, 'metadata', {}))
            }
            
            # Insert or replace
            cursor.execute("""
                INSERT OR REPLACE INTO memory_items 
                (id, content, memory_type, category, tags, timestamp, expiration, 
                 priority, access_count, last_accessed, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_dict["id"],
                item_dict["content"],
                item_dict["memory_type"],
                item_dict["category"],
                item_dict["tags"],
                item_dict["timestamp"],
                item_dict["expiration"],
                item_dict["priority"],
                item_dict["access_count"],
                item_dict["last_accessed"],
                item_dict["metadata"]
            ))
            
            self._connection.commit()
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "save_memory_item")
            self._connection.rollback()
            return False
    
    async def load(self, item_id: str) -> Optional[Dict]:
        """Load a memory item from local storage"""
        try:
            cursor = self._get_cursor()
            
            cursor.execute("""
                SELECT * FROM memory_items WHERE id = ?
            """, (item_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Convert to dictionary
            item_dict = {
                "id": row["id"],
                "content": row["content"],
                "memory_type": row["memory_type"],
                "category": row["category"],
                "tags": json.loads(row["tags"]),
                "timestamp": row["timestamp"],
                "expiration": row["expiration"],
                "priority": row["priority"],
                "access_count": row["access_count"],
                "last_accessed": row["last_accessed"],
                "metadata": json.loads(row["metadata"])
            }
            
            return item_dict
            
        except Exception as e:
            self.error_handler.handle_error(e, "load_memory_item")
            return None
    
    async def delete(self, item_id: str) -> bool:
        """Delete a memory item from local storage"""
        try:
            cursor = self._get_cursor()
            
            cursor.execute("""
                DELETE FROM memory_items WHERE id = ?
            """, (item_id,))
            
            self._connection.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            self.error_handler.handle_error(e, "delete_memory_item")
            self._connection.rollback()
            return False
    
    async def load_all(self) -> List[Dict]:
        """Load all memory items"""
        try:
            cursor = self._get_cursor()
            
            cursor.execute("""
                SELECT * FROM memory_items
            """)
            
            rows = cursor.fetchall()
            items = []
            
            for row in rows:
                item_dict = {
                    "id": row["id"],
                    "content": row["content"],
                    "memory_type": row["memory_type"],
                    "category": row["category"],
                    "tags": json.loads(row["tags"]),
                    "timestamp": row["timestamp"],
                    "expiration": row["expiration"],
                    "priority": row["priority"],
                    "access_count": row["access_count"],
                    "last_accessed": row["last_accessed"],
                    "metadata": json.loads(row["metadata"])
                }
                items.append(item_dict)
            
            return items
            
        except Exception as e:
            self.error_handler.handle_error(e, "load_all_memory_items")
            return []
    
    # Knowledge Base Operations
    
    async def save_knowledge(self, knowledge: List[Dict]) -> bool:
        """Save knowledge items"""
        try:
            cursor = self._get_cursor()
            
            for item in knowledge:
                cursor.execute("""
                    INSERT OR REPLACE INTO knowledge_base 
                    (id, content, category, source, confidence, timestamp, 
                     tags, references, usage_count, last_used, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.get("id", ""),
                    item.get("content", ""),
                    item.get("category", "general"),
                    item.get("source", "unknown"),
                    item.get("confidence", 0.0),
                    item.get("timestamp", time.time()),
                    json.dumps(item.get("tags", [])),
                    json.dumps(item.get("references", [])),
                    item.get("usage_count", 0),
                    item.get("last_used", time.time()),
                    json.dumps(item.get("metadata", {}))
                ))
            
            self._connection.commit()
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "save_knowledge")
            self._connection.rollback()
            return False
    
    async def load_knowledge(self) -> List[Dict]:
        """Load all knowledge items"""
        try:
            cursor = self._get_cursor()
            
            cursor.execute("""
                SELECT * FROM knowledge_base
            """)
            
            rows = cursor.fetchall()
            items = []
            
            for row in rows:
                item_dict = {
                    "id": row["id"],
                    "content": row["content"],
                    "category": row["category"],
                    "source": row["source"],
                    "confidence": row["confidence"],
                    "timestamp": row["timestamp"],
                    "tags": json.loads(row["tags"]),
                    "references": json.loads(row["references"]),
                    "usage_count": row["usage_count"],
                    "last_used": row["last_used"],
                    "metadata": json.loads(row["metadata"])
                }
                items.append(item_dict)
            
            return items
            
        except Exception as e:
            self.error_handler.handle_error(e, "load_knowledge")
            return []
    
    async def delete_knowledge(self, knowledge_id: str) -> bool:
        """Delete a knowledge item"""
        try:
            cursor = self._get_cursor()
            
            cursor.execute("""
                DELETE FROM knowledge_base WHERE id = ?
            """, (knowledge_id,))
            
            self._connection.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            self.error_handler.handle_error(e, "delete_knowledge")
            self._connection.rollback()
            return False
    
    # Preferences Operations
    
    async def store_preference(self, key: str, value: Any) -> bool:
        """Store a preference"""
        try:
            cursor = self._get_cursor()
            
            # Convert value to JSON string
            value_str = json.dumps(value) if not isinstance(value, str) else value
            
            cursor.execute("""
                INSERT OR REPLACE INTO preferences 
                (key, value, timestamp)
                VALUES (?, ?, ?)
            """, (key, value_str, time.time()))
            
            self._connection.commit()
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "store_preference")
            self._connection.rollback()
            return False
    
    async def get_preference(self, key: str) -> Optional[Any]:
        """Get a preference"""
        try:
            cursor = self._get_cursor()
            
            cursor.execute("""
                SELECT value FROM preferences WHERE key = ?
            """, (key,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Try to parse as JSON
            try:
                return json.loads(row["value"])
            except (ValueError, TypeError):
                return row["value"]
            
        except Exception as e:
            self.error_handler.handle_error(e, "get_preference")
            return None
    
    async def load_all_preferences(self) -> Dict:
        """Load all preferences"""
        try:
            cursor = self._get_cursor()
            
            cursor.execute("""
                SELECT key, value FROM preferences
            """)
            
            rows = cursor.fetchall()
            preferences = {}
            
            for row in rows:
                try:
                    preferences[row["key"]] = json.loads(row["value"])
                except (ValueError, TypeError):
                    preferences[row["key"]] = row["value"]
            
            return preferences
            
        except Exception as e:
            self.error_handler.handle_error(e, "load_all_preferences")
            return {}
    
    async def save_all_preferences(self, preferences: Dict) -> bool:
        """Save all preferences"""
        try:
            cursor = self._get_cursor()
            
            # Clear existing preferences
            cursor.execute("DELETE FROM preferences")
            
            # Insert new preferences
            for key, value in preferences.items():
                value_str = json.dumps(value) if not isinstance(value, str) else value
                cursor.execute("""
                    INSERT INTO preferences (key, value, timestamp)
                    VALUES (?, ?, ?)
                """, (key, value_str, time.time()))
            
            self._connection.commit()
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "save_all_preferences")
            self._connection.rollback()
            return False
    
    # Learning Stats Operations
    
    async def save_learning_stats(self, stats: Dict) -> bool:
        """Save learning statistics"""
        try:
            cursor = self._get_cursor()
            
            # Clear existing stats
            cursor.execute("DELETE FROM learning_stats")
            
            # Insert new stats
            for key, value in stats.items():
                cursor.execute("""
                    INSERT INTO learning_stats (key, value, timestamp)
                    VALUES (?, ?, ?)
                """, (key, value, time.time()))
            
            self._connection.commit()
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "save_learning_stats")
            self._connection.rollback()
            return False
    
    async def load_learning_stats(self) -> Dict:
        """Load learning statistics"""
        try:
            cursor = self._get_cursor()
            
            cursor.execute("""
                SELECT key, value FROM learning_stats
            """)
            
            rows = cursor.fetchall()
            stats = {}
            
            for row in rows:
                stats[row["key"]] = row["value"]
            
            return stats
            
        except Exception as e:
            self.error_handler.handle_error(e, "load_learning_stats")
            return {}
    
    # Cleanup
    
    async def cleanup_temp(self) -> int:
        """Clean up temporary data"""
        deleted_count = 0
        
        try:
            cursor = self._get_cursor()
            
            # Delete expired memory items
            cursor.execute("""
                DELETE FROM memory_items WHERE expiration > 0 AND expiration < ?
            """, (time.time(),))
            
            deleted_count += cursor.rowcount
            
            # Delete low-priority, old items if database is too large
            cursor.execute("SELECT COUNT(*) FROM memory_items")
            count = cursor.fetchone()[0]
            
            if count > 10000:  # Too many items
                # Delete old, low-priority items
                cursor.execute("""
                    DELETE FROM memory_items 
                    WHERE priority < 5 AND timestamp < ?
                    ORDER BY timestamp ASC
                    LIMIT 1000
                """, (time.time() - 86400,))  # 1 day old
                
                deleted_count += cursor.rowcount
            
            self._connection.commit()
            
        except Exception as e:
            self.error_handler.handle_error(e, "cleanup_temp")
            self._connection.rollback()
        
        return deleted_count
    
    async def cleanup_expired(self) -> int:
        """Clean up expired items"""
        deleted_count = 0
        
        try:
            cursor = self._get_cursor()
            
            cursor.execute("""
                DELETE FROM memory_items WHERE expiration > 0 AND expiration < ?
            """, (time.time(),))
            
            deleted_count = cursor.rowcount
            self._connection.commit()
            
        except Exception as e:
            self.error_handler.handle_error(e, "cleanup_expired")
            self._connection.rollback()
        
        return deleted_count
    
    async def cleanup(self):
        """Clean up all resources"""
        try:
            # Cleanup temporary data
            await self.cleanup_temp()
            
            # Close database connection
            if self._connection:
                self._connection.close()
                self._connection = None
            
            self._initialized = False
            self.logger.info("Local Memory cleaned up")
            
        except Exception as e:
            self.error_handler.handle_error(e, "local_memory_cleanup")
    
    # Statistics
    
    async def get_statistics(self) -> Dict:
        """Get database statistics"""
        stats = {
            "memory_items": 0,
            "knowledge_items": 0,
            "preferences": 0,
            "database_size": 0
        }
        
        try:
            cursor = self._get_cursor()
            
            # Count items
            cursor.execute("SELECT COUNT(*) FROM memory_items")
            stats["memory_items"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM knowledge_base")
            stats["knowledge_items"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM preferences")
            stats["preferences"] = cursor.fetchone()[0]
            
            # Get database size
            if os.path.exists(self._db_path):
                stats["database_size"] = os.path.getsize(self._db_path)
            
        except Exception as e:
            self.error_handler.handle_error(e, "get_statistics")
        
        return stats
