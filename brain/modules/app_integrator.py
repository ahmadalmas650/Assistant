"""
App Integrator Module
Integrates with installed Android apps for multi-source learning and execution
"""

import asyncio
import json
import time
import os
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler


class AppCategory(Enum):
    """App categories"""
    AI_ASSISTANT = auto()
    BROWSER = auto()
    SOCIAL_MEDIA = auto()
    MULTIMEDIA = auto()
    PRODUCTIVITY = auto()
    FILE_MANAGER = auto()
    COMMUNICATION = auto()
    UTILITY = auto()
    UNKNOWN = auto()


class AppAction(Enum):
    """App action types"""
    OPEN = auto()
    CLOSE = auto()
    SEARCH = auto()
    SEND = auto()
    RECEIVE = auto()
    EXECUTE = auto()
    QUERY = auto()
    LEARN = auto()
    READ = auto()
    WRITE = auto()
    EDIT = auto()
    UPLOAD = auto()
    DOWNLOAD = auto()


@dataclass
class AppInfo:
    """Information about an installed app"""
    package_name: str
    app_name: str
    category: AppCategory = AppCategory.UNKNOWN
    version: str = ""
    is_installed: bool = False
    is_enabled: bool = True
    permissions: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    icon_path: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "package_name": self.package_name,
            "app_name": self.app_name,
            "category": self.category.name,
            "version": self.version,
            "is_installed": self.is_installed,
            "is_enabled": self.is_enabled,
            "permissions": self.permissions,
            "capabilities": self.capabilities
        }


@dataclass
class AppResult:
    """Result from app interaction"""
    app: AppInfo
    action: AppAction
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "app": self.app.to_dict(),
            "action": self.action.name,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "processing_time": self.processing_time,
            "timestamp": self.timestamp
        }


@dataclass
class AppQuery:
    """Query for app interaction"""
    app: AppInfo
    action: AppAction
    parameters: Dict = field(default_factory=dict)
    timeout: int = 30  # seconds
    retry_count: int = 3
    
    def to_dict(self) -> Dict:
        return {
            "app": self.app.to_dict(),
            "action": self.action.name,
            "parameters": self.parameters,
            "timeout": self.timeout,
            "retry_count": self.retry_count
        }


class AppIntegrator:
    """
    Integrates with installed Android apps
    
    Provides unified interface for:
    - AI assistants (ChatGPT, DeepSeek, Grok)
    - Browsers (Chrome)
    - Social media (YouTube, etc.)
    - Productivity apps
    - File managers
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # App registry
        self._app_registry: Dict[str, AppInfo] = {}
        self._category_map: Dict[AppCategory, List[str]] = {}
        
        # Action handlers
        self._action_handlers: Dict[Tuple[str, AppAction], Callable] = {}
        
        # State
        self._active_queries: Dict[str, AppQuery] = {}
        self._query_counter = 0
        
        # Callbacks
        self._on_app_action_complete: List[Callable[[AppResult], None]] = []
        self._on_app_discovered: List[Callable[[AppInfo], None]] = []
        
        # Initialize
        self._initialize()
    
    def _initialize(self):
        """Initialize the app integrator"""
        # Register known apps
        self._register_known_apps()
        
        # Register default handlers
        self._register_default_handlers()
        
        # Discover installed apps
        self._discover_installed_apps()
        
        self.logger.info("App Integrator initialized")
    
    def _register_known_apps(self):
        """Register known apps"""
        known_apps = [
            # AI Assistants
            AppInfo(
                package_name="com.chatgpt",
                app_name="ChatGPT",
                category=AppCategory.AI_ASSISTANT,
                capabilities=[
                    "text_generation",
                    "question_answering",
                    "information_retrieval",
                    "code_generation",
                    "summarization"
                ]
            ),
            AppInfo(
                package_name="com.deepseek",
                app_name="DeepSeek",
                category=AppCategory.AI_ASSISTANT,
                capabilities=[
                    "text_generation",
                    "question_answering",
                    "reasoning",
                    "analysis"
                ]
            ),
            AppInfo(
                package_name="com.grok",
                app_name="Grok",
                category=AppCategory.AI_ASSISTANT,
                capabilities=[
                    "text_generation",
                    "question_answering",
                    "real_time_information"
                ]
            ),
            
            # Browsers
            AppInfo(
                package_name="com.android.chrome",
                app_name="Chrome",
                category=AppCategory.BROWSER,
                capabilities=[
                    "web_browsing",
                    "search",
                    "web_scraping",
                    "download"
                ]
            ),
            
            # Social Media
            AppInfo(
                package_name="com.google.android.youtube",
                app_name="YouTube",
                category=AppCategory.SOCIAL_MEDIA,
                capabilities=[
                    "video_playback",
                    "video_upload",
                    "search",
                    "comments",
                    "subscriptions"
                ]
            ),
            AppInfo(
                package_name="com.whatsapp",
                app_name="WhatsApp",
                category=AppCategory.COMMUNICATION,
                capabilities=[
                    "messaging",
                    "file_sharing",
                    "voice_call",
                    "video_call"
                ]
            ),
            AppInfo(
                package_name="org.telegram.messenger",
                app_name="Telegram",
                category=AppCategory.COMMUNICATION,
                capabilities=[
                    "messaging",
                    "file_sharing",
                    "channels",
                    "bots"
                ]
            ),
            
            # Multimedia
            AppInfo(
                package_name="com.kinemaster",
                app_name="Kinemaster",
                category=AppCategory.MULTIMEDIA,
                capabilities=[
                    "video_editing",
                    "audio_editing",
                    "effects",
                    "export"
                ]
            ),
            
            # File Managers
            AppInfo(
                package_name="com.google.android.apps.nbu.files",
                app_name="Files",
                category=AppCategory.FILE_MANAGER,
                capabilities=[
                    "file_browsing",
                    "file_operations",
                    "file_sharing"
                ]
            ),
        ]
        
        for app in known_apps:
            self._app_registry[app.package_name] = app
            if app.category not in self._category_map:
                self._category_map[app.category] = []
            self._category_map[app.category].append(app.package_name)
    
    def _register_default_handlers(self):
        """Register default action handlers"""
        # Register handlers for known apps
        for package_name in self._app_registry:
            for action in AppAction:
                self.register_handler(package_name, action, self._default_handler)
    
    def _discover_installed_apps(self):
        """Discover installed apps on the device"""
        # In a real implementation, this would use:
        # - Android PackageManager via Shizuku
        # - Termux package list
        # - AccessibilityService
        
        # For now, mark known apps as installed
        for package_name, app in self._app_registry.items():
            if package_name in self.config.allowed_apps:
                app.is_installed = True
                self.logger.info(f"App discovered: {app.app_name} ({package_name})")
                
                # Notify discovery
                for callback in self._on_app_discovered:
                    try:
                        callback(app)
                    except Exception as e:
                        self.error_handler.handle_error(e, "app_discovered_callback")
    
    def register_app(self, app: AppInfo) -> bool:
        """Register a new app"""
        if app.package_name in self._app_registry:
            return False
        
        self._app_registry[app.package_name] = app
        
        if app.category not in self._category_map:
            self._category_map[app.category] = []
        self._category_map[app.category].append(app.package_name)
        
        self.logger.info(f"App registered: {app.app_name} ({app.package_name})")
        return True
    
    def unregister_app(self, package_name: str) -> bool:
        """Unregister an app"""
        if package_name not in self._app_registry:
            return False
        
        app = self._app_registry[package_name]
        
        # Remove from category map
        if app.category in self._category_map:
            if package_name in self._category_map[app.category]:
                self._category_map[app.category].remove(package_name)
        
        del self._app_registry[package_name]
        
        self.logger.info(f"App unregistered: {package_name}")
        return True
    
    def register_handler(self, package_name: str, action: AppAction, 
                        handler: Callable):
        """Register a custom handler for an app action"""
        self._action_handlers[(package_name, action)] = handler
        self.logger.debug(f"Handler registered for {package_name}.{action.name}")
    
    def get_app(self, package_name: str) -> Optional[AppInfo]:
        """Get app information"""
        return self._app_registry.get(package_name)
    
    def get_apps_by_category(self, category: AppCategory) -> List[AppInfo]:
        """Get apps by category"""
        package_names = self._category_map.get(category, [])
        return [self._app_registry[pn] for pn in package_names if pn in self._app_registry]
    
    def get_installed_apps(self) -> List[AppInfo]:
        """Get all installed apps"""
        return [app for app in self._app_registry.values() if app.is_installed]
    
    def get_apps_with_capability(self, capability: str) -> List[AppInfo]:
        """Get apps with specific capability"""
        return [
            app for app in self._app_registry.values()
            if capability in app.capabilities and app.is_installed
        ]
    
    def is_app_installed(self, package_name: str) -> bool:
        """Check if an app is installed"""
        app = self._app_registry.get(package_name)
        return app is not None and app.is_installed
    
    async def execute_action(self, package_name: str, action: AppAction,
                           **kwargs) -> Optional[AppResult]:
        """
        Execute an action on an app
        
        Args:
            package_name: Package name of the app
            action: Action to perform
            **kwargs: Additional parameters
            
        Returns:
            AppResult or None if failed
        """
        start_time = time.time()
        
        try:
            # Get app info
            app = self._app_registry.get(package_name)
            if not app or not app.is_installed:
                return AppResult(
                    app=AppInfo(package_name=package_name, app_name="Unknown"),
                    action=action,
                    success=False,
                    error=f"App not installed: {package_name}"
                )
            
            # Create query
            query = AppQuery(
                app=app,
                action=action,
                parameters=kwargs,
                timeout=kwargs.get("timeout", 30),
                retry_count=kwargs.get("retry_count", 3)
            )
            
            # Generate query ID
            query_id = f"query_{int(time.time())}_{self._query_counter}"
            self._query_counter += 1
            self._active_queries[query_id] = query
            
            # Get handler
            handler = self._action_handlers.get((package_name, action))
            
            if handler:
                # Use custom handler
                result = await self._call_handler(handler, query)
            else:
                # Use default handler
                result = await self._default_handler(query)
            
            # Calculate processing time
            result.processing_time = time.time() - start_time
            
            # Remove from active queries
            if query_id in self._active_queries:
                del self._active_queries[query_id]
            
            # Notify callbacks
            for callback in self._on_app_action_complete:
                try:
                    callback(result)
                except Exception as e:
                    self.error_handler.handle_error(e, "app_action_complete_callback")
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, f"execute_action_{package_name}_{action.name}")
            return None
    
    async def _call_handler(self, handler: Callable, query: AppQuery) -> AppResult:
        """Call an action handler"""
        # Check if handler is async
        if asyncio.iscoroutinefunction(handler):
            return await handler(query)
        else:
            return handler(query)
    
    async def _default_handler(self, query: AppQuery) -> AppResult:
        """Default handler for app actions"""
        start_time = time.time()
        
        try:
            # Simulate app interaction based on app and action
            app = query.app
            action = query.action
            parameters = query.parameters
            
            # Generate mock result
            result_data = self._generate_mock_result(app, action, parameters)
            
            return AppResult(
                app=app,
                action=action,
                success=True,
                data=result_data,
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            return AppResult(
                app=query.app,
                action=query.action,
                success=False,
                error=str(e),
                processing_time=time.time() - start_time
            )
    
    def _generate_mock_result(self, app: AppInfo, action: AppAction, 
                            parameters: Dict) -> Any:
        """Generate mock result for testing"""
        if app.category == AppCategory.AI_ASSISTANT:
            if action == AppAction.QUERY:
                query = parameters.get("query", "")
                return {
                    "response": f"This is a mock response to: {query}",
                    "confidence": 0.95,
                    "sources": ["mock_database"]
                }
            elif action == AppAction.LEARN:
                topic = parameters.get("topic", "")
                return {
                    "status": "learned",
                    "topic": topic,
                    "new_knowledge": ["fact1", "fact2", "fact3"]
                }
            elif action == AppAction.SEARCH:
                query = parameters.get("query", "")
                return {
                    "results": [
                        {"title": f"Result 1 for {query}", "url": "https://example.com/1"},
                        {"title": f"Result 2 for {query}", "url": "https://example.com/2"}
                    ]
                }
        
        elif app.category == AppCategory.BROWSER:
            if action == AppAction.SEARCH:
                query = parameters.get("query", "")
                return {
                    "url": f"https://www.google.com/search?q={query}",
                    "results": [
                        {"title": f"Google Search: {query}", "url": f"https://www.google.com/search?q={query}"}
                    ]
                }
            elif action == AppAction.OPEN:
                url = parameters.get("url", "https://www.google.com")
                return {
                    "status": "opened",
                    "url": url
                }
        
        elif app.category == AppCategory.SOCIAL_MEDIA:
            if app.package_name == "com.google.android.youtube":
                if action == AppAction.SEARCH:
                    query = parameters.get("query", "")
                    return {
                        "videos": [
                            {
                                "title": f"Video about {query}",
                                "url": f"https://youtube.com/watch?v={hash(query) % 1000000}",
                                "duration": "10:30",
                                "views": 10000
                            }
                        ]
                    }
                elif action == AppAction.UPLOAD:
                    video_path = parameters.get("video_path", "")
                    return {
                        "status": "uploaded",
                        "video_id": f"video_{int(time.time())}",
                        "url": f"https://youtube.com/watch?v={int(time.time()) % 1000000}"
                    }
        
        elif app.category == AppCategory.MULTIMEDIA:
            if app.package_name == "com.kinemaster":
                if action == AppAction.EDIT:
                    video_path = parameters.get("video_path", "")
                    return {
                        "status": "editing",
                        "project_id": f"project_{int(time.time())}",
                        "video_path": video_path
                    }
                elif action == AppAction.EXECUTE:
                    command = parameters.get("command", "")
                    return {
                        "status": "executed",
                        "command": command
                    }
        
        elif app.category == AppCategory.FILE_MANAGER:
            if action == AppAction.OPEN:
                file_path = parameters.get("file_path", "")
                return {
                    "status": "opened",
                    "file_path": file_path
                }
            elif action == AppAction.READ:
                file_path = parameters.get("file_path", "")
                return {
                    "status": "read",
                    "file_path": file_path,
                    "content": "Mock file content"
                }
        
        # Default mock response
        return {
            "status": "executed",
            "app": app.app_name,
            "action": action.name,
            "parameters": parameters
        }
    
    # Convenience Methods
    
    async def query_ai(self, query: str, apps: List[str] = None) -> Dict[str, Any]:
        """
        Query multiple AI apps and merge results
        
        Args:
            query: The query to ask
            apps: List of AI app package names to query
            
        Returns:
            Dictionary of app -> result
        """
        if apps is None:
            apps = [
                "com.chatgpt",
                "com.deepseek",
                "com.grok"
            ]
        
        results = {}
        
        for app_pkg in apps:
            if self.is_app_installed(app_pkg):
                result = await self.execute_action(
                    app_pkg,
                    AppAction.QUERY,
                    query=query
                )
                if result and result.success:
                    results[app_pkg] = result.data
        
        return results
    
    async def search_web(self, query: str, browser: str = "com.android.chrome") -> Optional[Any]:
        """Search the web using a browser"""
        if not self.is_app_installed(browser):
            return None
        
        result = await self.execute_action(
            browser,
            AppAction.SEARCH,
            query=query
        )
        
        return result.data if result and result.success else None
    
    async def search_youtube(self, query: str) -> Optional[Any]:
        """Search YouTube"""
        if not self.is_app_installed("com.google.android.youtube"):
            return None
        
        result = await self.execute_action(
            "com.google.android.youtube",
            AppAction.SEARCH,
            query=query
        )
        
        return result.data if result and result.success else None
    
    async def upload_video(self, video_path: str, platform: str = "com.google.android.youtube") -> Optional[Any]:
        """Upload a video to a platform"""
        if not self.is_app_installed(platform):
            return None
        
        result = await self.execute_action(
            platform,
            AppAction.UPLOAD,
            video_path=video_path
        )
        
        return result.data if result and result.success else None
    
    async def edit_video(self, video_path: str, app: str = "com.kinemaster") -> Optional[Any]:
        """Edit a video using an app"""
        if not self.is_app_installed(app):
            return None
        
        result = await self.execute_action(
            app,
            AppAction.EDIT,
            video_path=video_path
        )
        
        return result.data if result and result.success else None
    
    async def send_message(self, recipient: str, message: str, 
                          app: str = "com.whatsapp") -> Optional[Any]:
        """Send a message using an app"""
        if not self.is_app_installed(app):
            return None
        
        result = await self.execute_action(
            app,
            AppAction.SEND,
            recipient=recipient,
            message=message
        )
        
        return result.data if result and result.success else None
    
    async def learn_from_sources(self, topic: str, 
                               sources: List[str] = None) -> Dict[str, Any]:
        """
        Learn about a topic from multiple sources
        
        Args:
            topic: The topic to learn about
            sources: List of app package names to use as sources
            
        Returns:
            Dictionary of source -> learned information
        """
        if sources is None:
            sources = [
                "com.chatgpt",
                "com.deepseek",
                "com.grok",
                "com.android.chrome"
            ]
        
        results = {}
        
        for source_pkg in sources:
            if self.is_app_installed(source_pkg):
                app = self._app_registry[source_pkg]
                
                if app.category == AppCategory.AI_ASSISTANT:
                    result = await self.execute_action(
                        source_pkg,
                        AppAction.LEARN,
                        topic=topic
                    )
                    if result and result.success:
                        results[source_pkg] = result.data
                elif app.category == AppCategory.BROWSER:
                    result = await self.execute_action(
                        source_pkg,
                        AppAction.SEARCH,
                        query=topic
                    )
                    if result and result.success:
                        results[source_pkg] = result.data
        
        return results
    
    async def merge_results(self, results: Dict[str, Any], 
                           query: str = "") -> Dict:
        """
        Merge results from multiple sources
        
        Args:
            results: Dictionary of source -> result data
            query: The original query
            
        Returns:
            Merged result with confidence scores
        """
        merged = {
            "query": query,
            "sources": list(results.keys()),
            "merged_text": "",
            "confidence": 0.0,
            "source_confidences": {},
            "metadata": {
                "timestamp": time.time(),
                "source_count": len(results)
            }
        }
        
        # Simple merging strategy: concatenate all text responses
        text_parts = []
        total_confidence = 0.0
        
        for source, data in results.items():
            if isinstance(data, dict):
                text = data.get("response", data.get("text", ""))
                confidence = data.get("confidence", 0.8)
            else:
                text = str(data)
                confidence = 0.8
            
            if text:
                text_parts.append(f"[From {source}]: {text}")
                total_confidence += confidence
                merged["source_confidences"][source] = confidence
        
        merged["merged_text"] = "\n\n".join(text_parts)
        merged["confidence"] = total_confidence / len(results) if results else 0.0
        
        return merged
    
    async def compare_information(self, query: str, 
                                  apps: List[str] = None) -> Dict:
        """
        Compare information from multiple sources
        
        Args:
            query: The query to compare
            apps: List of apps to query
            
        Returns:
            Comparison result
        """
        if apps is None:
            apps = [
                "com.chatgpt",
                "com.deepseek",
                "com.grok"
            ]
        
        # Query all sources
        results = await self.query_ai(query, apps)
        
        # Merge results
        merged = await self.merge_results(results, query)
        
        # Add comparison data
        merged["comparison"] = {
            "query": query,
            "source_count": len(results),
            "agreement_score": self._calculate_agreement(results)
        }
        
        return merged
    
    def _calculate_agreement(self, results: Dict[str, Any]) -> float:
        """Calculate agreement score between sources"""
        if len(results) < 2:
            return 1.0
        
        # Simple implementation: compare text similarity
        texts = []
        for data in results.values():
            if isinstance(data, dict):
                text = data.get("response", data.get("text", ""))
            else:
                text = str(data)
            texts.append(text.lower())
        
        # Calculate pairwise similarity
        similarities = []
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                sim = self._text_similarity(texts[i], texts[j])
                similarities.append(sim)
        
        if not similarities:
            return 0.0
        
        return sum(similarities) / len(similarities)
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity (0-1)"""
        # Simple implementation: Jaccard similarity on words
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    # Multi-source Learning
    
    async def learn_from_all_sources(self, topic: str) -> Dict:
        """
        Learn about a topic from all available sources
        
        Args:
            topic: The topic to learn
            
        Returns:
            Comprehensive learning result
        """
        # Get all AI apps
        ai_apps = self.get_apps_by_category(AppCategory.AI_ASSISTANT)
        ai_app_packages = [app.package_name for app in ai_apps if app.is_installed]
        
        # Get browser
        browsers = self.get_apps_by_category(AppCategory.BROWSER)
        browser_packages = [app.package_name for app in browsers if app.is_installed]
        
        # Combine all sources
        all_sources = ai_app_packages + browser_packages
        
        # Learn from all sources
        results = await self.learn_from_sources(topic, all_sources)
        
        # Merge and analyze
        merged = await self.merge_results(results, topic)
        
        # Add learning metadata
        merged["learning"] = {
            "topic": topic,
            "sources_used": all_sources,
            "knowledge_gained": len(merged["merged_text"]),
            "timestamp": time.time()
        }
        
        return merged
    
    # Callback Registration
    
    def on_app_action_complete(self, callback: Callable[[AppResult], None]):
        """Register app action completion callback"""
        self._on_app_action_complete.append(callback)
    
    def on_app_discovered(self, callback: Callable[[AppInfo], None]):
        """Register app discovery callback"""
        self._on_app_discovered.append(callback)
    
    # Utility Methods
    
    def get_all_apps(self) -> List[AppInfo]:
        """Get all registered apps"""
        return list(self._app_registry.values())
    
    def get_categories(self) -> List[AppCategory]:
        """Get all app categories"""
        return list(self._category_map.keys())
    
    def get_capabilities(self) -> List[str]:
        """Get all unique capabilities"""
        capabilities = set()
        for app in self._app_registry.values():
            capabilities.update(app.capabilities)
        return list(capabilities)
    
    def get_active_queries(self) -> List[AppQuery]:
        """Get list of active queries"""
        return list(self._active_queries.values())
    
    async def cancel_query(self, query_id: str) -> bool:
        """Cancel an active query"""
        if query_id in self._active_queries:
            del self._active_queries[query_id]
            self.logger.info(f"Query cancelled: {query_id}")
            return True
        return False
    
    # Cleanup
    
    async def cleanup(self):
        """Clean up resources"""
        self._active_queries = {}
        self._query_counter = 0
        self.logger.info("App Integrator cleaned up")
