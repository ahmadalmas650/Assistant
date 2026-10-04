"""
Cloud Memory Module
Handles cloud storage for memory and knowledge via rclone (Mega).

The user's long-term knowledge lives in a private Mega account
driven by the rclone binary installed in Termux
(`pkg install rclone`). Every operation below is a REAL rclone
subprocess call - nothing is faked. Google Drive and Dropbox
are not implemented and fail honestly if selected.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler


@dataclass
class CloudConfig:
    """Configuration for cloud storage"""
    provider: str = "mega"          # only "mega" is implemented
    enabled: bool = True
    remote_name: str = "mega"       # rclone remote name -> "mega:"
    root_path: str = "JARVIS"      # root folder inside the remote
    sync_interval: int = 3600      # 1 hour
    max_retries: int = 3


class CloudMemory:
    """
    Manages cloud storage for memory and knowledge.

    Supported provider: Mega, accessed through rclone. Storage
    layout: <remote>:JARVIS/memory/<item_id>.json
    """

    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)

        self._cloud_config = CloudConfig()

        # Optional overrides from the global config object
        for attr in ("provider", "enabled", "remote_name", "root_path"):
            value = getattr(config, "cloud_" + attr, None)
            if value is not None:
                setattr(self._cloud_config, attr, value)

        # State
        self._initialized = False
        self._is_syncing = False
        self._last_sync = 0.0

        # Callbacks
        self._on_sync_complete: List[callable] = []
        self._on_sync_error: List[callable] = []

    # ------------------------------------------------------------- rclone core

    @property
    def _remote(self) -> str:
        return f"{self._cloud_config.remote_name}:"

    def _memory_dir(self) -> str:
        return f"{self._remote}{self._cloud_config.root_path}/memory"

    @staticmethod
    def _safe_id(item_id: Any) -> str:
        return "".join(
            c if (c.isalnum() or c in "-_.") else "_"
            for c in str(item_id)
        )

    async def _rclone(self, *args: str, stdin_data: Optional[str] = None) -> str:
        """
        Run one rclone command and return stdout.

        Raises RuntimeError when rclone is missing or the command fails.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "rclone", *args,
                stdin=asyncio.subprocess.PIPE if stdin_data is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "rclone binary not found - install it in Termux with "
                "'pkg install rclone'"
            )

        if stdin_data is not None:
            stdout, stderr = await proc.communicate(stdin_data.encode("utf-8"))
        else:
            stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_text = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"rclone {' '.join(args)} failed: {err_text}")
        return stdout.decode("utf-8", errors="replace")

    # -------------------------------------------------------------- initialize

    async def initialize(self):
        """Initialize cloud memory (verify the rclone remote exists)."""
        if not self._cloud_config.enabled:
            self.logger.warning("Cloud storage is disabled")
            return

        if self._cloud_config.provider != "mega":
            self.error_handler.handle_error(
                RuntimeError(
                    f"Cloud provider '{self._cloud_config.provider}' is not "
                    f"implemented; only Mega via rclone is supported"
                ),
                "cloud_memory_initialize",
            )
            return

        try:
            remotes = await self._rclone("listremotes")
            remote_names = [r.strip() for r in remotes.splitlines() if r.strip()]
            expected = self._remote
            if expected not in remote_names:
                raise RuntimeError(
                    f"rclone remote '{expected}' is not configured - run "
                    f"'rclone config' in Termux and create a remote named "
                    f"'{self._cloud_config.remote_name}'"
                )
            # Ensure the memory directory exists (rclone mkdir is idempotent)
            await self._rclone("mkdir", self._memory_dir())
            self._initialized = True
            self.logger.info(
                f"Cloud memory initialized with Mega remote '{expected}'"
            )
        except Exception as e:
            self.error_handler.handle_error(e, "cloud_memory_initialize")

    async def _initialize_mega(self):
        """Backwards-compatible alias for the Mega initialization path."""
        await self.initialize()

    # ------------------------------------------------------------------- save

    async def save(self, item: Any) -> bool:
        """
        Save an item to cloud storage.

        Args:
            item: Memory item or knowledge item to save

        Returns:
            True if successful
        """
        if not self._cloud_config.enabled or not self._initialized:
            return False

        try:
            if hasattr(item, "to_dict"):
                item_dict = item.to_dict()
            else:
                item_dict = {
                    "id": getattr(item, "id", str(time.time())),
                    "content": getattr(item, "content", ""),
                    "type": type(item).__name__
                }

            item_id = self._safe_id(item_dict.get("id", str(time.time())))
            payload = json.dumps(item_dict, ensure_ascii=False)
            path = f"{self._memory_dir()}/{item_id}.json"
            await self._rclone("rcat", path, stdin_data=payload)
            self.logger.debug(f"Saved to Mega: {path}")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, "cloud_save")
            return False

    # ------------------------------------------------------------------- load

    async def load(self, item_id: str) -> Optional[Dict]:
        """
        Load an item from cloud storage.

        Args:
            item_id: ID of the item to load

        Returns:
            Item dictionary or None
        """
        if not self._cloud_config.enabled or not self._initialized:
            return None

        try:
            path = f"{self._memory_dir()}/{self._safe_id(item_id)}.json"
            content = await self._rclone("cat", path)
            return json.loads(content)
        except json.JSONDecodeError as e:
            self.error_handler.handle_error(e, "cloud_load_json")
            return None
        except Exception as e:
            self.error_handler.handle_error(e, "cloud_load")
            return None

    async def load_all(self) -> List[Dict]:
        """Load all items from cloud storage"""
        if not self._cloud_config.enabled or not self._initialized:
            return []

        try:
            listing = await self._rclone("lsf", self._memory_dir())
            items: List[Dict] = []
            for name in [n.strip() for n in listing.splitlines() if n.strip()]:
                if not name.endswith(".json"):
                    continue
                content = await self._rclone("cat", f"{self._memory_dir()}/{name}")
                try:
                    items.append(json.loads(content))
                except json.JSONDecodeError:
                    self.logger.warning(f"Skipping corrupt cloud item: {name}")
            return items

        except Exception as e:
            self.error_handler.handle_error(e, "cloud_load_all")
            return []

    # ----------------------------------------------------------------- delete

    async def delete(self, item_id: str) -> bool:
        """
        Delete an item from cloud storage.

        Args:
            item_id: ID of the item to delete

        Returns:
            True if successful
        """
        if not self._cloud_config.enabled or not self._initialized:
            return False

        try:
            path = f"{self._memory_dir()}/{self._safe_id(item_id)}.json"
            await self._rclone("deletefile", path)
            self.logger.debug(f"Deleted from Mega: {path}")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, "cloud_delete")
            return False

    # ---------------------------------------------------------- sync operations

    async def sync(self, items: List[Any]) -> bool:
        """
        Sync multiple items to cloud.

        Args:
            items: List of items to sync

        Returns:
            True if successful
        """
        if not self._cloud_config.enabled or not self._initialized:
            return False

        if self._is_syncing:
            return False

        self._is_syncing = True

        try:
            success = True

            for item in items:
                if not await self.save(item):
                    success = False
                    break

            self._last_sync = time.time()

            if success:
                for callback in self._on_sync_complete:
                    try:
                        callback(len(items))
                    except Exception as e:
                        self.error_handler.handle_error(e, "sync_complete_callback")
            else:
                for callback in self._on_sync_error:
                    try:
                        callback("Sync failed")
                    except Exception as e:
                        self.error_handler.handle_error(e, "sync_error_callback")

            return success

        except Exception as e:
            self.error_handler.handle_error(e, "cloud_sync")
            return False
        finally:
            self._is_syncing = False

    async def sync_all(self, items: List[Any]) -> bool:
        """Sync all items to cloud"""
        return await self.sync(items)

    async def download_all(self) -> List[Dict]:
        """Download all items from cloud"""
        return await self.load_all()

    # ------------------------------------------------------------ configuration

    def set_provider(self, provider: str) -> bool:
        """Set cloud provider (only 'mega' is implemented)."""
        if provider == "mega":
            self._cloud_config.provider = provider
            self.logger.info("Cloud provider set to: mega")
            return True
        self.logger.warning(
            f"Cloud provider '{provider}' is not implemented; only Mega "
            f"via rclone is supported"
        )
        return False

    def enable(self) -> bool:
        """Enable cloud storage"""
        self._cloud_config.enabled = True
        self.logger.info("Cloud storage enabled")
        return True

    def disable(self) -> bool:
        """Disable cloud storage"""
        self._cloud_config.enabled = False
        self.logger.info("Cloud storage disabled")
        return True

    def is_enabled(self) -> bool:
        """Check if cloud storage is enabled"""
        return self._cloud_config.enabled and self._initialized

    def get_provider(self) -> str:
        """Get current cloud provider"""
        return self._cloud_config.provider

    def get_last_sync(self) -> float:
        """Get timestamp of last sync"""
        return self._last_sync

    # ---------------------------------------------------------------- callbacks

    def on_sync_complete(self, callback: callable):
        """Register sync completion callback"""
        self._on_sync_complete.append(callback)

    def on_sync_error(self, callback: callable):
        """Register sync error callback"""
        self._on_sync_error.append(callback)

    # ------------------------------------------------------------------ cleanup

    async def cleanup(self):
        """Clean up resources"""
        try:
            self._on_sync_complete = []
            self._on_sync_error = []
            self._initialized = False
            self._is_syncing = False
            self.logger.info("Cloud Memory cleaned up")

        except Exception as e:
            self.error_handler.handle_error(e, "cloud_memory_cleanup")
