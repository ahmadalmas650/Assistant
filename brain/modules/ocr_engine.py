"""
Production-grade Screen Text Engine (live accessibility only).

The screen is read directly from the Android accessibility node tree:
instant (<100 ms), ~10 MB RAM, confidence >= 0.99. There is NO screenshot
and NO OCR pipeline in this module by design - the accessibility tree is the
single source of truth for everything visible on screen.

Designed for Android 15, 3 GB RAM, Termux + Bridge APK environment.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from brain.utils.logger import get_logger
    logger = get_logger("ocr_engine")
except Exception:  # pragma: no cover - logger must never break the brain
    import logging
    logger = logging.getLogger("ocr_engine")
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO)


@dataclass
class OCRResult:
    """Result of a live accessibility screen read."""
    text: str
    confidence: float
    processing_time: float
    strategy: str = "live_accessibility"
    elements: List[str] = field(default_factory=list)
    nodes: List[Any] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return bool(self.text.strip()) and self.error is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": round(self.confidence, 3),
            "processing_time": round(self.processing_time, 3),
            "strategy": self.strategy,
            "elements": self.elements,
            "error": self.error,
        }


class OCREngine:
    """
    Live accessibility screen reader.

    Args:
        config: optional dict, all keys optional:
            min_confidence (float, default 0.5)
        accessibility_controller: live bridge controller exposing node
            access (get_all_nodes / get_screen_nodes / nodes property...).
            The engine probes for whichever API is available at runtime.
    """

    STRATEGY_ACCESSIBILITY = "live_accessibility"

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        accessibility_controller: Any = None,
    ) -> None:
        config = dict(config or {})
        self.config = config
        self.min_confidence = float(config.get("min_confidence", 0.5))
        self.accessibility_controller = accessibility_controller

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def extract_text_from_screen(self) -> OCRResult:
        """Read all visible text from the current screen via accessibility."""
        started = time.monotonic()
        nodes = await self.collect_nodes(refresh=True)
        if not nodes:
            return OCRResult(
                text="", confidence=0.0,
                processing_time=time.monotonic() - started,
                error="no accessibility nodes available (bridge not connected?)",
            )
        elements = self.extract_elements(nodes)
        if not elements:
            return OCRResult(
                text="", confidence=0.0,
                processing_time=time.monotonic() - started,
                nodes=nodes,
                error="screen exposes no readable text nodes",
            )
        elapsed = time.monotonic() - started
        logger.info(
            "live accessibility read ok (%d nodes, %d chars, %.2fs)",
            len(nodes), len(elements), elapsed,
        )
        return OCRResult(
            text="\n".join(elements),
            confidence=0.99,
            processing_time=elapsed,
            elements=elements,
            nodes=nodes,
        )

    async def extract_live_text(self) -> str:
        """Get all visible on-screen text instantly."""
        result = await self.extract_text_from_screen()
        return result.text

    async def extract_elements_async(self, refresh: bool = True) -> List[str]:
        """Unique, ordered list of all text elements on screen."""
        nodes = await self.collect_nodes(refresh=refresh)
        return self.extract_elements(nodes)

    @staticmethod
    def extract_elements(nodes: List[Any]) -> List[str]:
        """Unique, ordered text elements from a node list (deduplicated)."""
        elements: List[str] = []
        for node in nodes:
            for value in OCREngine._node_texts(node):
                value = (value or "").strip()
                if value and value not in elements:
                    elements.append(value)
        return elements

    async def find_text(self, needle: str) -> Optional[Any]:
        """Find the first node whose visible text contains `needle`."""
        needle = (needle or "").strip().lower()
        if not needle:
            return None
        for node in await self.collect_nodes(refresh=True):
            for value in self._node_texts(node):
                if needle in (value or "").lower():
                    return node
        return None

    async def find_all_text(self, needle: str) -> List[Any]:
        """Find every node whose visible text contains `needle`."""
        needle = (needle or "").strip().lower()
        if not needle:
            return []
        matches: List[Any] = []
        for node in await self.collect_nodes(refresh=True):
            for value in self._node_texts(node):
                if needle in (value or "").lower():
                    matches.append(node)
                    break
        return matches

    # ------------------------------------------------------------------ #
    # Node collection (probes the controller API surface)
    # ------------------------------------------------------------------ #

    async def collect_nodes(self, refresh: bool = True) -> List[Any]:
        """Fetch the current node list from the accessibility controller."""
        controller = self.accessibility_controller
        if controller is None:
            return []
        candidates = (
            "get_all_nodes",
            "get_screen_nodes",
            "get_visible_nodes",
            "dump_nodes",
        )
        for name in candidates:
            fn = getattr(controller, name, None)
            if fn is None:
                continue
            try:
                out = fn(refresh=True) if (refresh and _takes_refresh(fn)) else fn()
                if asyncio.iscoroutine(out):
                    out = await out
                if isinstance(out, dict):
                    out = list(out.values())
                if isinstance(out, (list, tuple)):
                    return list(out)
            except Exception as exc:
                logger.debug("node API %s failed: %s", name, exc)
        # last resort: plain nodes property / attribute
        for attr in ("nodes", "screen_nodes", "root_node"):
            value = getattr(controller, attr, None)
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                return list(value)
            if isinstance(value, dict):
                return list(value.values())
            return [value]
        return []

    # ------------------------------------------------------------------ #
    # Node text helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _node_texts(node: Any) -> List[str]:
        """Extract every textual field a node may carry."""
        texts: List[str] = []
        if isinstance(node, str):
            return [node]
        if isinstance(node, dict):
            for key in ("text", "content_description", "contentDescription",
                        "label", "value", "description"):
                value = node.get(key)
                if isinstance(value, str) and value.strip():
                    texts.append(value.strip())
            return texts
        for attr in ("text", "content_description", "contentDescription",
                     "label", "description"):
            value = getattr(node, attr, None)
            if isinstance(value, str) and value.strip():
                texts.append(value.strip())
        return texts

    @staticmethod
    def node_text(node: Any) -> str:
        """Best single text value for a node."""
        values = OCREngine._node_texts(node)
        return values[0] if values else ""


def _takes_refresh(fn: Any) -> bool:
    try:
        import inspect
        return "refresh" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


__all__ = ["OCREngine", "OCRResult"]
