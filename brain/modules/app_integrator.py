"""
App Integrator Module
Integrates with installed Android apps for multi-source learning and execution.

All actions run for real through the Bridge APK (JSON-RPC over localhost).
There are no simulated results: every success means a real app launch, text
input, or live screen read happened on the device, and every failure carries
the real technical reason.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler
from .bridge_client import BridgeClient, BridgeError, BridgeNotConnectedError


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
    timeout: int = 30
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
    Integrates with installed Android apps through the Bridge APK.

    Supported real actions (via accessibility automation):
      OPEN   - launch the app
      SEARCH - launch, type the query, wait, read the live screen
      QUERY  - launch, type the query, wait, read the live screen
      LEARN  - same as QUERY (learning-oriented alias)
      READ   - read live screen text if the app is in the foreground

    Every other action fails honestly with the technical reason instead of
    returning invented data. Complex in-app flows (uploading, editing,
    messaging) belong to the task planner + accessibility controller, which
    can drive individual UI nodes.
    """

    LAUNCH_SETTLE_SECONDS = 2.0
    RESPONSE_WAIT_SECONDS = 6.0

    def __init__(self, config, logger: Logger, bridge: Optional[BridgeClient] = None):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)

        self._owns_bridge = bridge is None
        self.bridge = bridge if bridge is not None else BridgeClient(
            host="127.0.0.1",
            port=getattr(getattr(config, "bridge", None), "port", 8080),
        )

        self._app_registry: Dict[str, AppInfo] = {}
        self._category_map: Dict[AppCategory, List[str]] = {}
        self._action_handlers: Dict[Tuple[str, AppAction], Callable] = {}
        self._active_queries: Dict[str, AppQuery] = {}
        self._query_counter = 0

        self._on_app_action_complete: List[Callable[[AppResult], None]] = []
        self._on_app_discovered: List[Callable[[AppInfo], None]] = []

        self._register_known_apps()
        self.logger.info("App Integrator initialized")

    async def initialize(self):
        """
        Connect to the bridge and check which registered apps are actually
        installed on the device. If the Bridge APK is not running, the real
        reason is logged and no app is treated as installed until the bridge
        is reachable; nothing is ever guessed.
        """
        try:
            await self.bridge.connect()
            reachable = await self.bridge.ping()
        except (BridgeError, OSError) as exc:
            self.logger.warning(
                "Bridge APK not reachable during initialize: %s. Installation "
                "checks skipped." % exc
            )
            return False

        if not reachable:
            self.logger.warning("Bridge APK did not answer ping; apps unverified.")
            return False

        allowed = getattr(getattr(self.config, "apps", None), "allowed_apps", []) or []
        for package_name in allowed:
            if package_name not in self._app_registry:
                continue
            installed = False
            try:
                installed = await self.bridge.is_app_installed(package_name)
            except BridgeError as exc:
                self.logger.warning(
                    "Installation check failed for %s: %s" % (package_name, exc)
                )
            app = self._app_registry[package_name]
            app.is_installed = installed
            if installed:
                self.logger.info(
                    "App discovered on device: %s (%s)" % (app.app_name, package_name)
                )
                for callback in self._on_app_discovered:
                    try:
                        callback(app)
                    except Exception as e:
                        self.error_handler.handle_error(e, "app_discovered_callback")

        self.logger.info("App Integrator initialized with live bridge")
        return True

    def _register_known_apps(self):
        """Register known apps (installation is verified against the device)"""
        known_apps = [
            AppInfo(
                package_name="com.openai.chatgpt",
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
                package_name="com.deepseek.app",
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
                package_name="ai.x.grok",
                app_name="Grok",
                category=AppCategory.AI_ASSISTANT,
                capabilities=[
                    "text_generation",
                    "question_answering",
                    "real_time_information"
                ]
            ),
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
                capabilities=["messaging", "file_sharing", "channels", "bots"]
            ),
            AppInfo(
                package_name="com.nexstreaming.app.kinemasterfree",
                app_name="Kinemaster",
                category=AppCategory.MULTIMEDIA,
                capabilities=["video_editing", "audio_editing", "effects", "export"]
            ),
            AppInfo(
                package_name="com.google.android.apps.nbu.files",
                app_name="Files",
                category=AppCategory.FILE_MANAGER,
                capabilities=["file_browsing", "file_operations", "file_sharing"]
            ),
        ]

        for app in known_apps:
            self._app_registry[app.package_name] = app
            if app.category not in self._category_map:
                self._category_map[app.category] = []
            self._category_map[app.category].append(app.package_name)

    def register_app(self, app: AppInfo) -> bool:
        """Register a new app"""
        if app.package_name in self._app_registry:
            return False

        self._app_registry[app.package_name] = app

        if app.category not in self._category_map:
            self._category_map[app.category] = []
        self._category_map[app.category].append(app.package_name)

        self.logger.info("App registered: %s (%s)" % (app.app_name, app.package_name))
        return True

    def unregister_app(self, package_name: str) -> bool:
        """Unregister an app"""
        if package_name not in self._app_registry:
            return False

        app = self._app_registry[package_name]

        if app.category in self._category_map:
            if package_name in self._category_map[app.category]:
                self._category_map[app.category].remove(package_name)

        del self._app_registry[package_name]
        self.logger.info("App unregistered: %s" % package_name)
        return True

    def register_handler(self, package_name: str, action: AppAction,
                        handler: Callable):
        """Register a custom handler for an app action"""
        self._action_handlers[(package_name, action)] = handler
        self.logger.debug("Handler registered for %s.%s" % (package_name, action.name))

    def get_app(self, package_name: str) -> Optional[AppInfo]:
        """Get app information"""
        return self._app_registry.get(package_name)

    def get_apps_by_category(self, category: AppCategory) -> List[AppInfo]:
        """Get apps by category"""
        package_names = self._category_map.get(category, [])
        return [self._app_registry[pn] for pn in package_names if pn in self._app_registry]

    def get_installed_apps(self) -> List[AppInfo]:
        """Get all apps confirmed installed on the device"""
        return [app for app in self._app_registry.values() if app.is_installed]

    def get_apps_with_capability(self, capability: str) -> List[AppInfo]:
        """Get apps with specific capability"""
        return [
            app for app in self._app_registry.values()
            if capability in app.capabilities and app.is_installed
        ]

    def is_app_installed(self, package_name: str) -> bool:
        """
        Whether the device confirmed this app is installed. True only after a
        real PackageManager check through the bridge succeeded; never guessed.
        """
        app = self._app_registry.get(package_name)
        return app is not None and app.is_installed

    async def execute_action(self, package_name: str, action: AppAction,
                           **kwargs) -> Optional[AppResult]:
        """
        Execute an action on an app for real via the Bridge APK.

        Args:
            package_name: Package name of the app
            action: Action to perform
            **kwargs: Additional parameters

        Returns:
            AppResult, or None only on an unexpected internal failure
        """
        start_time = time.time()

        try:
            app = self._app_registry.get(package_name)
            if not app:
                return AppResult(
                    app=AppInfo(package_name=package_name, app_name="Unknown"),
                    action=action,
                    success=False,
                    error="App not registered: %s" % package_name
                )
            if not app.is_installed:
                return AppResult(
                    app=app,
                    action=action,
                    success=False,
                    error=(
                        "App not confirmed installed on device: %s. Run "
                        "initialize() with the Bridge APK running to verify "
                        "installation." % package_name
                    )
                )

            query = AppQuery(
                app=app,
                action=action,
                parameters=kwargs,
                timeout=kwargs.get("timeout", 30),
                retry_count=kwargs.get("retry_count", 3)
            )

            query_id = "query_%d_%d" % (int(time.time()), self._query_counter)
            self._query_counter += 1
            self._active_queries[query_id] = query

            handler = self._action_handlers.get((package_name, action))

            if handler:
                result = await self._call_handler(handler, query)
            else:
                result = await self._default_handler(query)

            result.processing_time = time.time() - start_time

            if query_id in self._active_queries:
                del self._active_queries[query_id]

            for callback in self._on_app_action_complete:
                try:
                    callback(result)
                except Exception as e:
                    self.error_handler.handle_error(e, "app_action_complete_callback")

            return result

        except Exception as e:
            self.error_handler.handle_error(e, "execute_action_%s_%s" % (package_name, action.name))
            return None

    async def _call_handler(self, handler: Callable, query: AppQuery) -> AppResult:
        """Call an action handler"""
        if asyncio.iscoroutinefunction(handler):
            return await handler(query)
        return handler(query)

    async def _default_handler(self, query: AppQuery) -> AppResult:
        """
        Default handler: performs the action for real through the Bridge APK
        and returns the actual live screen content. Unsupported actions fail
        honestly instead of fabricating results.
        """
        start_time = time.time()
        app = query.app
        action = query.action
        parameters = query.parameters

        try:
            if action == AppAction.OPEN:
                return await self._action_open(app, start_time)

            if action in (AppAction.SEARCH, AppAction.QUERY, AppAction.LEARN):
                text = parameters.get("query") or parameters.get("topic") or ""
                if not text:
                    return AppResult(
                        app=app, action=action, success=False,
                        error="No query text provided for %s" % action.name,
                        processing_time=time.time() - start_time
                    )
                return await self._action_query(app, action, text, start_time)

            if action == AppAction.READ:
                return await self._action_read(app, start_time)

            return AppResult(
                app=app,
                action=action,
                success=False,
                error=(
                    "Action %s is not supported by AppIntegrator directly. It "
                    "requires in-app UI automation performed by the task "
                    "planner and the accessibility controller." % action.name
                ),
                processing_time=time.time() - start_time
            )

        except BridgeNotConnectedError as e:
            return AppResult(
                app=app, action=action, success=False,
                error="Bridge APK not reachable: %s" % e,
                processing_time=time.time() - start_time
            )
        except BridgeError as e:
            return AppResult(
                app=app, action=action, success=False,
                error="Bridge refused the operation: %s" % e,
                processing_time=time.time() - start_time
            )
        except Exception as e:
            return AppResult(
                app=app, action=action, success=False,
                error=str(e),
                processing_time=time.time() - start_time
            )

    async def _action_open(self, app: AppInfo, start_time: float) -> AppResult:
        """Launch the app the way a human does (launcher search) and
        confirm the launch from the bridge's foreground check."""
        result = await self.bridge.launch_app_by_name(app.app_name)
        ok = bool(isinstance(result, dict) and result.get("ok"))
        if not ok:
            reason = result.get("error", "launch_app_by_name returned failure") if isinstance(result, dict) else "unexpected bridge reply"
            return AppResult(
                app=app, action=AppAction.OPEN, success=False,
                error="Could not launch %s: %s" % (app.app_name, reason),
                processing_time=time.time() - start_time
            )
        launched_package = result.get("package") if isinstance(result, dict) else None
        return AppResult(
            app=app,
            action=AppAction.OPEN,
            success=True,
            data={
                "status": "opened",
                "launched_package": launched_package,
                "launch_method": "launcher_search"
            },
            processing_time=time.time() - start_time
        )

    async def _action_query(self, app: AppInfo, action: AppAction,
                           text: str, start_time: float) -> AppResult:
        """
        Launch the app through the launcher search, type the query, wait for
        the response to render, and return the actual live screen text.
        Confidence is a heuristic based on how much on-screen text was
        captured.
        """
        launch = await self.bridge.launch_app_by_name(app.app_name)
        if not (isinstance(launch, dict) and launch.get("ok")):
            reason = launch.get("error", "launch failed") if isinstance(launch, dict) else "unexpected bridge reply"
            return AppResult(
                app=app, action=action, success=False,
                error="Could not launch %s: %s" % (app.app_name, reason),
                processing_time=time.time() - start_time
            )

        await asyncio.sleep(self.LAUNCH_SETTLE_SECONDS)

        typed = await self.bridge.input_text(text)
        if not (isinstance(typed, dict) and typed.get("ok", True)):
            reason = typed.get("error", "input_text failed") if isinstance(typed, dict) else "unexpected bridge reply"
            return AppResult(
                app=app, action=action, success=False,
                error="Could not type the query into %s: %s" % (app.app_name, reason),
                processing_time=time.time() - start_time
            )

        await asyncio.sleep(self.RESPONSE_WAIT_SECONDS)

        screen_text = (await self.bridge.get_screen_text() or "").strip()

        if not screen_text:
            return AppResult(
                app=app, action=action, success=False,
                error=(
                    "Query was typed but no readable text was found on the "
                    "screen of %s. The app may not expose text nodes, or the "
                    "accessibility service may not be enabled." % app.app_name
                ),
                processing_time=time.time() - start_time
            )

        confidence = min(0.9, 0.3 + min(len(screen_text), 2000) / 4000.0)
        data = {
            "response": screen_text,
            "screen_text": screen_text,
            "source_app": app.package_name,
            "confidence": round(confidence, 3),
            "captured_chars": len(screen_text)
        }
        if action == AppAction.SEARCH:
            data["results"] = screen_text.split("\n")
        return AppResult(
            app=app, action=action, success=True, data=data,
            processing_time=time.time() - start_time
        )

    async def _action_read(self, app: AppInfo, start_time: float) -> AppResult:
        """Read the live screen text, but only if the app is in the foreground."""
        foreground = await self.bridge.get_foreground_app()
        if foreground != app.package_name:
            return AppResult(
                app=app, action=AppAction.READ, success=False,
                error=(
                    "%s is not in the foreground (current: %s). Open the app "
                    "first." % (app.app_name, foreground or "unknown")
                ),
                processing_time=time.time() - start_time
            )
        screen_text = (await self.bridge.get_screen_text() or "").strip()
        if not screen_text:
            return AppResult(
                app=app, action=AppAction.READ, success=False,
                error="No readable text nodes on the current screen of %s." % app.app_name,
                processing_time=time.time() - start_time
            )
        return AppResult(
            app=app, action=AppAction.READ, success=True,
            data={"screen_text": screen_text, "captured_chars": len(screen_text)},
            processing_time=time.time() - start_time
        )

    # Convenience Methods

    async def query_ai(self, query: str, apps: List[str] = None) -> Dict[str, Any]:
        """
        Query multiple AI apps and merge results.

        Args:
            query: The query to ask
            apps: List of AI app package names to query

        Returns:
            Dictionary of app -> result data (only real, successful reads)
        """
        if apps is None:
            apps = [
                "com.openai.chatgpt",
                "com.deepseek.app",
                "ai.x.grok"
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
        """Search the web using a browser and return the real screen content"""
        if not self.is_app_installed(browser):
            return None

        result = await self.execute_action(
            browser,
            AppAction.SEARCH,
            query=query
        )

        return result.data if result and result.success else None

    async def search_youtube(self, query: str) -> Optional[Any]:
        """Search YouTube and return the real screen content"""
        if not self.is_app_installed("com.google.android.youtube"):
            return None

        result = await self.execute_action(
            "com.google.android.youtube",
            AppAction.SEARCH,
            query=query
        )

        return result.data if result and result.success else None

    async def read_app_screen(self, package_name: str) -> Optional[Any]:
        """Read the current on-screen text of a foreground app"""
        if not self.is_app_installed(package_name):
            return None

        result = await self.execute_action(
            package_name,
            AppAction.READ
        )

        return result.data if result and result.success else None

    async def learn_from_sources(self, topic: str,
                               sources: List[str] = None) -> Dict[str, Any]:
        """
        Learn about a topic from multiple sources.

        Args:
            topic: The topic to learn about
            sources: List of app package names to use as sources

        Returns:
            Dictionary of source -> real screen content captured from that app
        """
        if sources is None:
            sources = [
                "com.openai.chatgpt",
                "com.deepseek.app",
                "ai.x.grok",
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
        Merge real results from multiple sources.

        Args:
            results: Dictionary of source -> result data
            query: The original query

        Returns:
            Merged result with confidence scores derived from the data
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

        text_parts = []
        total_confidence = 0.0

        for source, data in results.items():
            if isinstance(data, dict):
                text = data.get("response", data.get("text", data.get("screen_text", "")))
                confidence = float(data.get("confidence", 0.0))
            else:
                text = str(data)
                confidence = 0.0

            if text:
                text_parts.append("[From %s]: %s" % (source, text))
                total_confidence += confidence
                merged["source_confidences"][source] = confidence

        merged["merged_text"] = "\n\n".join(text_parts)
        merged["confidence"] = total_confidence / len(results) if results else 0.0

        return merged

    async def compare_information(self, query: str,
                                  apps: List[str] = None) -> Dict:
        """
        Compare information from multiple sources.

        Args:
            query: The query to compare
            apps: List of apps to query

        Returns:
            Comparison result
        """
        if apps is None:
            apps = [
                "com.openai.chatgpt",
                "com.deepseek.app",
                "ai.x.grok"
            ]

        results = await self.query_ai(query, apps)
        merged = await self.merge_results(results, query)

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

        texts = []
        for data in results.values():
            if isinstance(data, dict):
                text = data.get("response", data.get("text", data.get("screen_text", "")))
            else:
                text = str(data)
            texts.append(text.lower())

        similarities = []
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                sim = self._text_similarity(texts[i], texts[j])
                similarities.append(sim)

        if not similarities:
            return 0.0

        return sum(similarities) / len(similarities)

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity (0-1) using Jaccard similarity on words"""
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
        Learn about a topic from all installed, verified sources.

        Args:
            topic: The topic to learn

        Returns:
            Comprehensive learning result built from real screen reads
        """
        ai_apps = self.get_apps_by_category(AppCategory.AI_ASSISTANT)
        ai_app_packages = [app.package_name for app in ai_apps if app.is_installed]

        browsers = self.get_apps_by_category(AppCategory.BROWSER)
        browser_packages = [app.package_name for app in browsers if app.is_installed]

        all_sources = ai_app_packages + browser_packages

        results = await self.learn_from_sources(topic, all_sources)
        merged = await self.merge_results(results, topic)

        merged["learning"] = {
            "topic": topic,
            "sources_used": list(results.keys()),
            "sources_available": all_sources,
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
            self.logger.info("Query cancelled: %s" % query_id)
            return True
        return False

    # Cleanup

    async def cleanup(self):
        """Clean up resources"""
        self._active_queries = {}
        self._query_counter = 0
        if self._owns_bridge:
            await self.bridge.cleanup()
        self.logger.info("App Integrator cleaned up")
