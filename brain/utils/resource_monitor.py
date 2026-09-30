"""
Resource Monitor Module
Monitors system resources (CPU, memory, storage, etc.)
"""

import asyncio
import json
import time
import os
import psutil
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from .logger import Logger


class ResourceType(Enum):
    """Types of system resources"""
    CPU = auto()
    MEMORY = auto()
    STORAGE = auto()
    NETWORK = auto()
    BATTERY = auto()


@dataclass
class ResourceStatus:
    """Current status of system resources"""
    cpu_usage: float = 0.0  # Percentage
    memory_usage: float = 0.0  # GB
    memory_percent: float = 0.0  # Percentage
    storage_usage: float = 0.0  # GB
    storage_percent: float = 0.0  # Percentage
    network_usage: Dict[str, float] = field(default_factory=dict)  # sent/recv in bytes
    battery_level: float = 0.0  # Percentage
    battery_charging: bool = False
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "memory_percent": self.memory_percent,
            "storage_usage": self.storage_usage,
            "storage_percent": self.storage_percent,
            "network_usage": self.network_usage,
            "battery_level": self.battery_level,
            "battery_charging": self.battery_charging,
            "timestamp": self.timestamp
        }
    
    def get_summary(self) -> str:
        """Get a human-readable summary"""
        return (f"CPU: {self.cpu_usage:.1f}%, "
                f"Memory: {self.memory_usage:.2f}GB ({self.memory_percent:.1f}%), "
                f"Storage: {self.storage_usage:.2f}GB ({self.storage_percent:.1f}%), "
                f"Battery: {self.battery_level:.1f}% {'Charging' if self.battery_charging else 'Discharging'}")


@dataclass
class ResourceThreshold:
    """Threshold for resource monitoring"""
    resource_type: ResourceType
    warning_threshold: float = 0.0
    critical_threshold: float = 0.0
    action: str = ""  # Action to take when threshold is exceeded


class ResourceMonitor:
    """
    Monitors system resources and provides alerts
    """
    
    def __init__(self, max_memory: float = 2.0, max_cpu: float = 0.8):
        """
        Initialize the resource monitor
        
        Args:
            max_memory: Maximum memory usage in GB before alerts
            max_cpu: Maximum CPU usage percentage before alerts
        """
        self._max_memory = max_memory
        self._max_cpu = max_cpu
        
        # Thresholds
        self._thresholds: List[ResourceThreshold] = [
            ResourceThreshold(
                resource_type=ResourceType.CPU,
                warning_threshold=0.7,
                critical_threshold=0.9,
                action="reduce_processing"
            ),
            ResourceThreshold(
                resource_type=ResourceType.MEMORY,
                warning_threshold=1.5,
                critical_threshold=1.8,
                action="cleanup_memory"
            ),
            ResourceThreshold(
                resource_type=ResourceType.STORAGE,
                warning_threshold=30.0,
                critical_threshold=35.0,
                action="cleanup_storage"
            ),
            ResourceThreshold(
                resource_type=ResourceType.BATTERY,
                warning_threshold=20.0,
                critical_threshold=10.0,
                action="conserve_power"
            )
        ]
        
        # State
        self._last_status: Optional[ResourceStatus] = None
        self._last_check: float = 0.0
        self._check_interval: float = 5.0  # seconds
        
        # Alert state
        self._alerts: Dict[ResourceType, str] = {}
        
        # Callbacks
        self._on_resource_alert: List[Callable[[ResourceType, str, float], None]] = []
        self._on_resource_update: List[Callable[[ResourceStatus], None]] = []
        
        # Initialize psutil if available
        self._psutil_available = True
        try:
            import psutil
        except ImportError:
            self._psutil_available = False
    
    def get_status(self) -> ResourceStatus:
        """
        Get current resource status
        
        Returns:
            ResourceStatus object
        """
        status = ResourceStatus()
        
        try:
            if self._psutil_available:
                # Get CPU usage
                status.cpu_usage = psutil.cpu_percent(interval=1)
                
                # Get memory usage
                memory = psutil.virtual_memory()
                status.memory_usage = memory.used / (1024 ** 3)  # Convert to GB
                status.memory_percent = memory.percent
                
                # Get storage usage
                storage = psutil.disk_usage('/')
                status.storage_usage = storage.used / (1024 ** 3)  # Convert to GB
                status.storage_percent = storage.percent
                
                # Get network usage
                net_io = psutil.net_io_counters()
                status.network_usage = {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv
                }
                
                # Get battery status (if available)
                try:
                    battery = psutil.sensors_battery()
                    if battery:
                        status.battery_level = battery.percent
                        status.battery_charging = battery.power_plugged
                except:
                    pass
            else:
                # Fallback to mock values if psutil not available
                status.cpu_usage = 10.0
                status.memory_usage = 0.5
                status.memory_percent = 25.0
                status.storage_usage = 5.0
                status.storage_percent = 50.0
                status.battery_level = 80.0
                status.battery_charging = True
        
        except Exception as e:
            # Return last known status if error
            if self._last_status:
                return self._last_status
            
            # Otherwise return default status
            status = ResourceStatus()
        
        self._last_status = status
        self._last_check = time.time()
        
        return status
    
    async def start_monitoring(self):
        """Start continuous resource monitoring"""
        asyncio.create_task(self._monitor_loop())
    
    async def _monitor_loop(self):
        """Monitoring loop"""
        while True:
            try:
                # Get current status
                status = self.get_status()
                
                # Check thresholds
                self._check_thresholds(status)
                
                # Notify updates
                for callback in self._on_resource_update:
                    try:
                        callback(status)
                    except:
                        pass
                
                # Wait for next check
                await asyncio.sleep(self._check_interval)
                
            except Exception as e:
                # Wait before retrying
                await asyncio.sleep(5)
    
    def _check_thresholds(self, status: ResourceStatus):
        """Check if any thresholds are exceeded"""
        for threshold in self._thresholds:
            value = self._get_resource_value(status, threshold.resource_type)
            
            if value is None:
                continue
            
            # Check if we're above warning threshold
            if value > threshold.warning_threshold:
                alert_level = "warning"
            elif value > threshold.critical_threshold:
                alert_level = "critical"
            else:
                # Below warning threshold, clear alert
                if threshold.resource_type in self._alerts:
                    del self._alerts[threshold.resource_type]
                continue
            
            # Check if this is a new alert
            if (threshold.resource_type not in self._alerts or
                self._alerts[threshold.resource_type] != alert_level):
                
                self._alerts[threshold.resource_type] = alert_level
                
                # Notify callbacks
                for callback in self._on_resource_alert:
                    try:
                        callback(threshold.resource_type, alert_level, value)
                    except:
                        pass
    
    def _get_resource_value(self, status: ResourceStatus, 
                            resource_type: ResourceType) -> Optional[float]:
        """Get the value for a specific resource type"""
        if resource_type == ResourceType.CPU:
            return status.cpu_usage / 100  # Convert percentage to 0-1
        elif resource_type == ResourceType.MEMORY:
            return status.memory_usage
        elif resource_type == ResourceType.STORAGE:
            return status.storage_usage
        elif resource_type == ResourceType.BATTERY:
            return status.battery_level
        else:
            return None
    
    def get_alerts(self) -> Dict[ResourceType, str]:
        """Get current alerts"""
        return self._alerts.copy()
    
    def has_alert(self, resource_type: ResourceType) -> bool:
        """Check if there's an alert for a specific resource"""
        return resource_type in self._alerts
    
    def get_alert_level(self, resource_type: ResourceType) -> Optional[str]:
        """Get the alert level for a specific resource"""
        return self._alerts.get(resource_type)
    
    def check_resource(self, resource_type: ResourceType) -> Tuple[float, str]:
        """
        Check a specific resource
        
        Args:
            resource_type: The resource type to check
            
        Returns:
            Tuple of (value, alert_level or empty string)
        """
        status = self.get_status()
        value = self._get_resource_value(status, resource_type)
        
        if value is None:
            return 0.0, ""
        
        alert_level = self.get_alert_level(resource_type)
        return value, alert_level or ""
    
    def is_low_memory(self) -> bool:
        """Check if system is low on memory"""
        status = self.get_status()
        return status.memory_usage > self._max_memory * 0.9
    
    def is_high_cpu(self) -> bool:
        """Check if CPU usage is high"""
        status = self.get_status()
        return status.cpu_usage > self._max_cpu * 100 * 0.9
    
    def is_low_battery(self) -> bool:
        """Check if battery is low"""
        status = self.get_status()
        return status.battery_level < 20.0
    
    def is_charging(self) -> bool:
        """Check if device is charging"""
        status = self.get_status()
        return status.battery_charging
    
    def get_available_memory(self) -> float:
        """Get available memory in GB"""
        status = self.get_status()
        return self._max_memory - status.memory_usage
    
    def get_available_storage(self) -> float:
        """Get available storage in GB"""
        status = self.get_status()
        # This is a simplified calculation
        return 40.0 - status.storage_usage  # Assuming 40GB total
    
    # Configuration
    
    def set_check_interval(self, interval: float):
        """Set the monitoring interval in seconds"""
        self._check_interval = interval
    
    def add_threshold(self, threshold: ResourceThreshold):
        """Add a custom threshold"""
        self._thresholds.append(threshold)
    
    def remove_threshold(self, resource_type: ResourceType):
        """Remove thresholds for a resource type"""
        self._thresholds = [
            t for t in self._thresholds
            if t.resource_type != resource_type
        ]
    
    # Callbacks
    
    def on_resource_alert(self, callback: Callable[[ResourceType, str, float], None]):
        """
        Register callback for resource alerts
        
        Args:
            callback: Function to call when alert is triggered
                   Parameters: (resource_type, alert_level, value)
        """
        self._on_resource_alert.append(callback)
    
    def on_resource_update(self, callback: Callable[[ResourceStatus], None]):
        """
        Register callback for resource updates
        
        Args:
            callback: Function to call when resource status is updated
                   Parameters: (ResourceStatus)
        """
        self._on_resource_update.append(callback)
    
    # Utility methods
    
    def get_resource_usage(self) -> Dict:
        """Get detailed resource usage information"""
        status = self.get_status()
        
        return {
            "cpu": {
                "usage_percent": status.cpu_usage,
                "cores": os.cpu_count() if hasattr(os, 'cpu_count') else 1
            },
            "memory": {
                "used_gb": status.memory_usage,
                "used_percent": status.memory_percent,
                "max_gb": self._max_memory
            },
            "storage": {
                "used_gb": status.storage_usage,
                "used_percent": status.storage_percent
            },
            "network": status.network_usage,
            "battery": {
                "level_percent": status.battery_level,
                "charging": status.battery_charging
            }
        }
    
    def get_performance_score(self) -> float:
        """
        Calculate an overall performance score (0-1)
        
        Returns:
            Performance score where 1 is optimal
        """
        status = self.get_status()
        
        # Normalize values to 0-1
        cpu_score = 1.0 - (status.cpu_usage / 100)
        memory_score = 1.0 - (status.memory_usage / self._max_memory)
        storage_score = 1.0 - (status.storage_usage / 40.0)  # Assuming 40GB total
        battery_score = status.battery_level / 100
        
        # Weighted average
        performance = (cpu_score * 0.3 + 
                     memory_score * 0.3 + 
                     storage_score * 0.2 + 
                     battery_score * 0.2)
        
        return max(0.0, min(1.0, performance))
    
    # Cleanup
    
    def cleanup(self):
        """Clean up resources"""
        self._on_resource_alert = []
        self._on_resource_update = []
        self._alerts = {}
