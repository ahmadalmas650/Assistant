"""
Bridge Client

Real asyncio JSON-RPC 2.0 client that connects the Python brain (Termux)
to the Bridge APK's LocalJsonRpcServer on 127.0.0.1.

Wire format (one JSON object per line):
  request:  {"jsonrpc":"2.0","id":1,"method":"ping","params":{}}
  response: {"jsonrpc":"2.0","id":1,"result":{...}} or {"error":{...}}

Zero external dependencies. Auto-reconnects on the next call after a
connection loss, so a temporary bridge restart never crashes the brain.
Designed for a 3 GB RAM Android 15 device: one socket, tiny buffers.
"""

import asyncio
import itertools
import json
import time
from typing import Any, Dict, List, Optional

try:
    from brain.utils.logger import get_logger
    logger = get_logger("bridge_client")
except Exception:  # pragma: no cover - logger must never break the brain
    import logging
    logger = logging.getLogger("bridge_client")
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO)


class BridgeError(Exception):
    """Raised when the bridge returns an error or is unreachable."""

    def __init__(self, message: str, code: Optional[int] = None) -> None:
        super().__init__(message)
        self.code = code


class BridgeNotConnectedError(BridgeError):
    """Raised when the Bridge APK is not reachable on localhost."""


class BridgeClient:
    """
    JSON-RPC 2.0 client for the Bridge APK.

    Args:
        host: always 127.0.0.1 (the bridge never listens on the network).
        port: must match BridgeConstants.BRIDGE_PORT in the APK (default 8080).
        timeout: per-request timeout in seconds.
        connect_timeout: how long a single connect attempt may take.
        max_payload: safety cap for a single response line (bytes).
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        timeout: float = 10.0,
        connect_timeout: float = 5.0,
        max_payload: int = 8 * 1024 * 1024,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.timeout = float(timeout)
        self.connect_timeout = float(connect_timeout)
        self.max_payload = int(max_payload)
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._lock = asyncio.Lock()
        self._ids = itertools.count(1)
        self._last_error: Optional[str] = None
        self._last_success: float = 0.0

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def last_success_at(self) -> float:
        return self._last_success

    async def connect(self) -> None:
        """Open the socket if it is not already open."""
        async with self._lock:
            if self.connected:
                return
            await self._close_locked()
            try:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=self.connect_timeout,
                )
                self._last_error = None
                logger.info("connected to bridge at %s:%d", self.host, self.port)
            except (OSError, asyncio.TimeoutError) as exc:
                self._last_error = str(exc)
                raise BridgeNotConnectedError(
                    "bridge not reachable at %s:%d (%s). Is the Bridge APK "
                    "foreground service running?" % (self.host, self.port, exc)
                ) from exc

    async def close(self) -> None:
        """Close the socket (safe to call repeatedly)."""
        async with self._lock:
            await self._close_locked()

    async def _close_locked(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send one JSON-RPC request and return the result field."""
        request_id = next(self._ids)
        request = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            },
            ensure_ascii=False,
        )
        async with self._lock:
            if not self.connected:
                await self.connect()
            assert self._reader is not None and self._writer is not None
            try:
                self._writer.write((request + "\n").encode("utf-8"))
                await asyncio.wait_for(self._writer.drain(), timeout=self.timeout)
                line = await asyncio.wait_for(
                    self._read_response_line(), timeout=self.timeout
                )
            except (OSError, asyncio.TimeoutError, BridgeNotConnectedError) as exc:
                await self._close_locked()
                self._last_error = str(exc)
                raise BridgeNotConnectedError(
                    "bridge connection lost during %s: %s" % (method, exc)
                ) from exc
        self._last_success = time.time()
        return self._parse_response(method, request_id, line)

    async def _read_response_line(self) -> bytes:
        assert self._reader is not None
        while True:
            line = await self._reader.readline()
            if not line:
                raise BridgeNotConnectedError("bridge closed the connection")
            if len(line) > self.max_payload:
                raise BridgeError("bridge response too large", code=-32607)
            if line.strip():
                return line

    def _parse_response(self, method: str, request_id: int, raw: bytes) -> Any:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BridgeError("invalid JSON from bridge: %s" % exc) from exc
        if not isinstance(payload, dict):
            raise BridgeError("unexpected bridge payload: %r" % (payload,))
        if payload.get("id") != request_id:
            raise BridgeError(
                "bridge id mismatch: expected %s, got %r"
                % (request_id, payload.get("id"))
            )
        if "error" in payload and payload["error"] is not None:
            err = payload["error"]
            raise BridgeError(
                str(err.get("message", "bridge error")),
                code=err.get("code"),
            )
        return payload.get("result")

    # Convenience methods (mirror the bridge method surface)

    async def ping(self) -> bool:
        result = await self.call("ping")
        return bool(isinstance(result, dict) and result.get("ok"))

    async def get_screen_text(self) -> str:
        result = await self.call("get_screen_text")
        return str(result.get("text", "")) if isinstance(result, dict) else ""

    async def get_all_nodes(self) -> List[Dict[str, Any]]:
        result = await self.call("get_all_nodes")
        if isinstance(result, dict) and isinstance(result.get("nodes"), list):
            return result["nodes"]
        return []

    async def get_foreground_app(self) -> str:
        result = await self.call("get_foreground_app")
        return str(result.get("package", "")) if isinstance(result, dict) else ""

    async def click_text(self, text: str, exact: bool = False) -> Dict[str, Any]:
        return await self.call("click_node", {"text": text, "exact": bool(exact)})

    async def click_node_id(self, node_id: str) -> Dict[str, Any]:
        return await self.call("click_node", {"node_id": node_id})

    async def click_coordinates(self, x: int, y: int) -> Dict[str, Any]:
        return await self.call("click_node", {"x": int(x), "y": int(y)})

    async def input_text(self, text: str, node_text: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"text": text}
        if node_text:
            params["node_text"] = node_text
        return await self.call("input_text", params)

    async def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int,
                    duration_ms: int = 300) -> Dict[str, Any]:
        return await self.call("swipe", {
            "start_x": int(start_x), "start_y": int(start_y),
            "end_x": int(end_x), "end_y": int(end_y),
            "duration": int(duration_ms),
        })

    async def press_back(self) -> Dict[str, Any]:
        return await self.call("press_back")

    async def press_home(self) -> Dict[str, Any]:
        return await self.call("press_home")

    async def press_recents(self) -> Dict[str, Any]:
        return await self.call("press_recents")

    async def launch_app(self, package: str) -> Dict[str, Any]:
        return await self.call("launch_app", {"package": str(package)})

    async def notification_info(self) -> Dict[str, Any]:
        return await self.call("notification_info")

    async def speech_to_text(self, timeout_s: float = 10.0,
                             language: str = "en-US") -> Dict[str, Any]:
        """Recognize one utterance via the Bridge APK (SpeechRecognizer).

        Returns {"text": str, "confidence": float}. Recognition runs
        inside the APK; no audio is shipped to the Python side.
        """
        result = await self.call(
            "speech_to_text",
            {"timeout": float(timeout_s), "language": str(language)},
        )
        if isinstance(result, dict):
            return {
                "text": str(result.get("text", "")),
                "confidence": float(result.get("confidence", 0.0)),
            }
        return {"text": "", "confidence": 0.0}

    async def listen_wake_word(self, wake_word: str = "jarvis",
                               timeout_s: float = 30.0) -> Dict[str, Any]:
        """Listen for the wake word via the Bridge APK.

        Blocks for up to timeout_s seconds and returns
        {"detected": bool, "confidence": float}.
        """
        result = await self.call(
            "listen_wake_word",
            {"wake_word": str(wake_word), "timeout": float(timeout_s)},
        )
        if isinstance(result, dict):
            return {
                "detected": bool(result.get("detected")),
                "confidence": float(result.get("confidence", 0.0)),
            }
        return {"detected": False, "confidence": 0.0}

    async def cleanup(self) -> None:
        await self.close()


__all__ = ["BridgeClient", "BridgeError", "BridgeNotConnectedError"]
