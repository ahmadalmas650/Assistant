"""
Cloud Sync Module
Handles synchronization with cloud storage (Mega, Google Drive, etc.)
"""

import asyncio
import json
import time
import os
import shutil
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import hashlib

from .logger import Logger
from .error_handler import ErrorHandler


class SyncStatus(Enum):
    """Synchronization status"""
    IDLE = auto()
    SYNCING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CONFLICT = auto()


class SyncDirection(Enum):
    """Synchronization direction"""
    UPLOAD = auto()
    DOWNLOAD = auto()
    BIDIRECTIONAL = auto()


@dataclass
class SyncResult:
    """Result of a synchronization operation"""
    status: SyncStatus
    direction: SyncDirection
    items_transferred: int = 0
    items_failed: int = 0
    conflicts: List[Dict] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "status": self.status.name,
            "direction": self.direction.name,
            "items_transferred": self.items_transferred,
            "items_failed": self.items_failed,
            "conflicts": self.conflicts,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "metadata": self.metadata
        }


@dataclass
class SyncConflict:
    """Represents a synchronization conflict"""
    item_id: str
    local_version: Dict
    remote_version: Dict
    local_timestamp: float
    remote_timestamp: float
    resolution: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "item_id": self.item_id,
            "local_timestamp": self.local_timestamp,
            "remote_timestamp": self.remote_timestamp,
            "resolution": self.resolution
        }


class CloudSync:
    """
    Handles synchronization with cloud storage
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Configuration
        self._provider = "mega"  # Default to Mega
        self._sync_interval = 3600  # 1 hour
        self._enabled = True
        
        # State
        self._status = SyncStatus.IDLE
        self._last_sync = 0.0
        self._is_syncing = False
        
        # Callbacks
        self._on_sync_start: List[Callable[[SyncDirection], None]] = []
        self._on_sync_complete: List[Callable[[SyncResult], None]] = []
        self._on_sync_progress: List[Callable[[int, int], None]] = []
        self._on_conflict: List[Callable[[SyncConflict], None]] = []
        
        # Conflict resolution
        self._conflict_resolution = "keep_both"  # keep_both, keep_local, keep_remote, newest
        
        # Real rclone backend detection (honest: sync only works when
        # rclone is installed and a remote is configured in Termux)
        self._rclone_path = shutil.which("rclone")
        sync_cfg = getattr(config, "cloud_sync", None)
        self._remote_name = str(getattr(sync_cfg, "remote_name", "assistant"))
        self._remote_dir = str(getattr(sync_cfg, "remote_dir", "assistant-backup"))
        self._local_dir = str(getattr(sync_cfg, "local_dir", "~/assistant-data"))
        
        if self._rclone_path is None:
            self.logger.warning(
                "rclone is not installed in Termux; cloud sync will report "
                "honest failures until 'pkg install rclone' and a remote "
                "are configured"
            )
    
    def _rclone_available(self) -> bool:
        """Check whether a real rclone binary is available."""
        return self._rclone_path is not None
    
    async def _run_rclone(self, args: List[str]) -> Tuple[int, str, str]:
        """Run a real rclone command and return (code, stdout, stderr)."""
        proc = await asyncio.create_subprocess_exec(
            self._rclone_path, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace")
        )
    
    async def _rclone_remote_exists(self) -> bool:
        """Check (really, via rclone listremotes) that the remote exists."""
        code, out, _ = await self._run_rclone(["listremotes"])
        if code != 0:
            return False
        remotes = [line.strip() for line in out.splitlines() if line.strip()]
        return f"{self._remote_name}:" in remotes
    
    # Configuration
    
    def set_provider(self, provider: str) -> bool:
        """Set cloud provider (maps to a real configured rclone remote)."""
        valid_providers = ["mega", "google_drive", "dropbox"]
        if provider in valid_providers:
            self._provider = provider
            self._remote_name = provider
            self.logger.info(
                f"Cloud provider set to: {provider} (rclone remote "
                f"'{provider}' must exist; run 'rclone config' if not)"
            )
            return True
        return False
    
    def get_provider(self) -> str:
        """Get current cloud provider"""
        return self._provider
    
    def set_sync_interval(self, interval: int) -> bool:
        """Set synchronization interval in seconds"""
        if interval > 0:
            self._sync_interval = interval
            self.logger.info(f"Sync interval set to: {interval}s")
            return True
        return False
    
    def get_sync_interval(self) -> int:
        """Get synchronization interval"""
        return self._sync_interval
    
    def enable(self):
        """Enable cloud synchronization"""
        self._enabled = True
        self.logger.info("Cloud synchronization enabled")
    
    def disable(self):
        """Disable cloud synchronization"""
        self._enabled = False
        self.logger.info("Cloud synchronization disabled")
    
    def is_enabled(self) -> bool:
        """Check if synchronization is enabled"""
        return self._enabled
    
    def set_conflict_resolution(self, resolution: str) -> bool:
        """Set conflict resolution strategy"""
        valid_resolutions = ["keep_both", "keep_local", "keep_remote", "newest"]
        if resolution in valid_resolutions:
            self._conflict_resolution = resolution
            self.logger.info(f"Conflict resolution set to: {resolution}")
            return True
        return False
    
    # Synchronization
    
    async def sync(self, direction: SyncDirection = SyncDirection.BIDIRECTIONAL,
                  items: List[Dict] = None) -> SyncResult:
        """
        Perform synchronization
        
        Args:
            direction: Direction of synchronization
            items: Specific items to sync (None for all)
            
        Returns:
            SyncResult
        """
        if not self._enabled:
            return SyncResult(
                status=SyncStatus.FAILED,
                direction=direction,
                metadata={"error": "Sync disabled"}
            )
        
        if self._is_syncing:
            return SyncResult(
                status=SyncStatus.FAILED,
                direction=direction,
                metadata={"error": "Sync already in progress"}
            )
        
        self._is_syncing = True
        self._status = SyncStatus.SYNCING
        
        start_time = time.time()
        
        # Notify start
        for callback in self._on_sync_start:
            try:
                callback(direction)
            except Exception as e:
                self.error_handler.handle_error(e, "sync_start_callback")
        
        try:
            if direction == SyncDirection.UPLOAD:
                result = await self._upload_sync(items)
            elif direction == SyncDirection.DOWNLOAD:
                result = await self._download_sync()
            else:
                result = await self._bidirectional_sync(items)
            
            # Update last sync time
            self._last_sync = time.time()
            self._status = result.status
            
            # Notify completion
            for callback in self._on_sync_complete:
                try:
                    callback(result)
                except Exception as e:
                    self.error_handler.handle_error(e, "sync_complete_callback")
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, "sync")
            result = SyncResult(
                status=SyncStatus.FAILED,
                direction=direction,
                start_time=start_time,
                end_time=time.time(),
                metadata={"error": str(e)}
            )
            
            # Notify completion (with failure)
            for callback in self._on_sync_complete:
                try:
                    callback(result)
                except Exception as e:
                    self.error_handler.handle_error(e, "sync_complete_callback")
            
            self._status = SyncStatus.FAILED
            self._is_syncing = False
            return result
        finally:
            self._is_syncing = False
    
    async def _upload_sync(self, items: List[Dict] = None) -> SyncResult:
        """Upload synchronization"""
        start_time = time.time()
        
        try:
            items_transferred = 0
            items_failed = 0
            conflicts = []
            
            # Get items to upload
            if items is None:
                # In a real implementation, get all items that need syncing
                items = []
            
            total_items = len(items)
            
            for i, item in enumerate(items):
                try:
                    # Upload item
                    success = await self._upload_item(item)
                    
                    if success:
                        items_transferred += 1
                    else:
                        items_failed += 1
                    
                    # Update progress
                    for callback in self._on_sync_progress:
                        try:
                            callback(i + 1, total_items)
                        except Exception as e:
                            self.error_handler.handle_error(e, "sync_progress_callback")
                        
                except Exception as e:
                    self.error_handler.handle_error(e, f"upload_item_{item.get('id', 'unknown')}")
                    items_failed += 1
            
            return SyncResult(
                status=SyncStatus.COMPLETED,
                direction=SyncDirection.UPLOAD,
                items_transferred=items_transferred,
                items_failed=items_failed,
                conflicts=conflicts,
                start_time=start_time,
                end_time=time.time(),
                duration=time.time() - start_time
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "upload_sync")
            return SyncResult(
                status=SyncStatus.FAILED,
                direction=SyncDirection.UPLOAD,
                start_time=start_time,
                end_time=time.time(),
                metadata={"error": str(e)}
            )
    
    async def _download_sync(self) -> SyncResult:
        """Download synchronization (real: rclone copy from the remote)."""
        start_time = time.time()
        
        try:
            if not self._rclone_available():
                return SyncResult(
                    status=SyncStatus.FAILED,
                    direction=SyncDirection.DOWNLOAD,
                    start_time=start_time,
                    end_time=time.time(),
                    metadata={
                        "error": "rclone is not installed; run 'pkg install "
                                 "rclone' in Termux and configure a remote"
                    }
                )
            
            if not await self._rclone_remote_exists():
                return SyncResult(
                    status=SyncStatus.FAILED,
                    direction=SyncDirection.DOWNLOAD,
                    start_time=start_time,
                    end_time=time.time(),
                    metadata={
                        "error": f"rclone remote '{self._remote_name}' is not "
                                 f"configured; run 'rclone config'"
                    }
                )
            
            local_dir = os.path.expanduser(self._local_dir)
            os.makedirs(local_dir, exist_ok=True)
            remote_path = f"{self._remote_name}:{self._remote_dir}"
            
            code, out, err = await self._run_rclone([
                "copy", remote_path, local_dir,
                "--stats", "1", "--stats-one-line"
            ])
            
            if code != 0:
                self.logger.error(f"rclone download failed: {err.strip()}")
                return SyncResult(
                    status=SyncStatus.FAILED,
                    direction=SyncDirection.DOWNLOAD,
                    start_time=start_time,
                    end_time=time.time(),
                    metadata={"error": err.strip()[:500]}
                )
            
            transferred = self._parse_rclone_transferred(out + "\n" + err)
            self.logger.info(
                f"rclone download complete: {transferred} file(s) copied"
            )
            
            for callback in self._on_sync_progress:
                try:
                    callback(transferred, transferred)
                except Exception as e:
                    self.error_handler.handle_error(e, "sync_progress_callback")
            
            return SyncResult(
                status=SyncStatus.COMPLETED,
                direction=SyncDirection.DOWNLOAD,
                items_transferred=transferred,
                items_failed=0,
                conflicts=[],
                start_time=start_time,
                end_time=time.time(),
                duration=time.time() - start_time
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "download_sync")
            return SyncResult(
                status=SyncStatus.FAILED,
                direction=SyncDirection.DOWNLOAD,
                start_time=start_time,
                end_time=time.time(),
                metadata={"error": str(e)}
            )
    
    def _parse_rclone_transferred(self, output: str) -> int:
        """Parse the real 'Transferred:' count from rclone stats output."""
        for line in output.splitlines():
            if "Transferred:" in line:
                parts = line.split(": ", 1)
                if len(parts) == 2:
                    head = parts[1].split(" ", 1)[0]
                    try:
                        return int(head)
                    except ValueError:
                        continue
        return 0
    
    async def _bidirectional_sync(self, items: List[Dict] = None) -> SyncResult:
        """Bidirectional synchronization"""
        start_time = time.time()
        
        try:
            # First, download from cloud
            download_result = await self._download_sync()
            
            if download_result.status != SyncStatus.COMPLETED:
                return download_result
            
            # Then, upload local changes
            upload_result = await self._upload_sync(items)
            
            # Combine results
            return SyncResult(
                status=SyncStatus.COMPLETED,
                direction=SyncDirection.BIDIRECTIONAL,
                items_transferred=download_result.items_transferred + upload_result.items_transferred,
                items_failed=download_result.items_failed + upload_result.items_failed,
                conflicts=download_result.conflicts + upload_result.conflicts,
                start_time=start_time,
                end_time=time.time(),
                duration=time.time() - start_time
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "bidirectional_sync")
            return SyncResult(
                status=SyncStatus.FAILED,
                direction=SyncDirection.BIDIRECTIONAL,
                start_time=start_time,
                end_time=time.time(),
                metadata={"error": str(e)}
            )
    
    async def _upload_item(self, item: Dict) -> bool:
        """Upload a single item to cloud (real: rclone copy to the remote)."""
        try:
            if not self._rclone_available():
                self.logger.error(
                    "Upload skipped: rclone is not installed in Termux"
                )
                return False
            
            if not await self._rclone_remote_exists():
                self.logger.error(
                    f"Upload skipped: rclone remote '{self._remote_name}' "
                    f"is not configured"
                )
                return False
            
            local_path = item.get("local_path") or item.get("file_path") or item.get("path")
            if not local_path or not os.path.exists(str(local_path)):
                self.logger.error(
                    f"Upload skipped: local path not found: {local_path}"
                )
                return False
            
            local_path = str(local_path)
            remote_path = f"{self._remote_name}:{self._remote_dir}"
            
            if os.path.isdir(local_path):
                code, _, err = await self._run_rclone([
                    "copy", local_path, remote_path,
                    "--stats", "1", "--stats-one-line"
                ])
            else:
                code, _, err = await self._run_rclone([
                    "copyto", local_path,
                    f"{remote_path}/{os.path.basename(local_path)}",
                    "--stats", "1", "--stats-one-line"
                ])
            
            if code != 0:
                self.logger.error(
                    f"rclone upload failed for {local_path}: {err.strip()[:300]}"
                )
                return False
            
            self.logger.info(f"rclone upload complete: {local_path}")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, f"upload_item_{item.get('id', 'unknown')}")
            return False
    
    async def _upload_to_mega(self, item: Dict) -> bool:
        """Upload to the configured Mega remote (real rclone remote)."""
        return await self._upload_item(item)
    
    async def _upload_to_google_drive(self, item: Dict) -> bool:
        """Upload to the configured Google Drive remote (real rclone remote)."""
        return await self._upload_item(item)
    
    async def _upload_to_dropbox(self, item: Dict) -> bool:
        """Upload to the configured Dropbox remote (real rclone remote)."""
        return await self._upload_item(item)
    
    # Conflict Handling
    
    async def handle_conflict(self, conflict: SyncConflict) -> SyncConflict:
        """
        Handle a synchronization conflict
        
        Args:
            conflict: The conflict to resolve
            
        Returns:
            Resolved conflict
        """
        try:
            # Apply conflict resolution strategy
            if self._conflict_resolution == "keep_local":
                conflict.resolution = "keep_local"
            elif self._conflict_resolution == "keep_remote":
                conflict.resolution = "keep_remote"
            elif self._conflict_resolution == "newest":
                if conflict.local_timestamp > conflict.remote_timestamp:
                    conflict.resolution = "keep_local"
                else:
                    conflict.resolution = "keep_remote"
            else:  # keep_both
                conflict.resolution = "keep_both"
            
            # Notify conflict
            for callback in self._on_conflict:
                try:
                    callback(conflict)
                except Exception as e:
                    self.error_handler.handle_error(e, "conflict_callback")
            
            return conflict
            
        except Exception as e:
            self.error_handler.handle_error(e, "handle_conflict")
            conflict.resolution = "failed"
            return conflict
    
    # Status
    
    def get_status(self) -> SyncStatus:
        """Get current synchronization status"""
        return self._status
    
    def get_last_sync(self) -> float:
        """Get timestamp of last synchronization"""
        return self._last_sync
    
    def is_syncing(self) -> bool:
        """Check if synchronization is in progress"""
        return self._is_syncing
    
    # Callbacks
    
    def on_sync_start(self, callback: Callable[[SyncDirection], None]):
        """Register sync start callback"""
        self._on_sync_start.append(callback)
    
    def on_sync_complete(self, callback: Callable[[SyncResult], None]):
        """Register sync completion callback"""
        self._on_sync_complete.append(callback)
    
    def on_sync_progress(self, callback: Callable[[int, int], None]):
        """Register sync progress callback"""
        self._on_sync_progress.append(callback)
    
    def on_conflict(self, callback: Callable[[SyncConflict], None]):
        """Register conflict callback"""
        self._on_conflict.append(callback)
    
    # Utility Methods
    
    def generate_sync_id(self) -> str:
        """Generate a unique synchronization ID"""
        import uuid
        return f"sync_{uuid.uuid4().hex[:12]}_{int(time.time())}"
    
    def calculate_checksum(self, data: Any) -> str:
        """Calculate checksum for data"""
        data_str = json.dumps(data) if not isinstance(data, str) else data
        return hashlib.md5(data_str.encode()).hexdigest()
    
    # Cleanup
    
    def cleanup(self):
        """Clean up resources"""
        self._on_sync_start = []
        self._on_sync_complete = []
        self._on_sync_progress = []
        self._on_conflict = []
        self._status = SyncStatus.IDLE
        self._is_syncing = False
        self.logger.info("Cloud Sync cleaned up")
