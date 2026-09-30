"""
Configuration Module
Loads and manages all configuration
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


@dataclass
class DeviceConfig:
    """Device configuration"""
    target_platform: str = "Android"
    min_sdk_version: int = 21
    target_sdk_version: int = 34
    min_ram_gb: float = 3.0
    min_storage_gb: float = 10.0
    architecture: str = "ARM64"


@dataclass
class BrainConfig:
    """Brain configuration"""
    wake_word: str = "jarvis"
    max_memory_usage_gb: float = 2.0
    max_cpu_usage: float = 0.8
    min_confidence_threshold: float = 0.7
    learning_enabled: bool = True
    cloud_sync_enabled: bool = True
    privacy_mode: bool = True
    debug_mode: bool = False
    response_timeout_seconds: int = 30
    task_timeout_seconds: int = 300
    max_concurrent_tasks: int = 3


@dataclass
class InputConfig:
    """Input configuration"""
    voice_enabled: bool = True
    text_enabled: bool = True
    default_language: str = "en"
    supported_languages: list = field(default_factory=lambda: ["en", "ur", "hi", "es", "fr", "de"])
    voice_sample_rate: int = 16000
    voice_channels: int = 1
    voice_sample_width: int = 2


@dataclass
class AppConfig:
    """App configuration"""
    allowed_apps: list = field(default_factory=lambda: [
        "com.android.chrome",
        "com.google.android.youtube",
        "com.chatgpt",
        "com.deepseek.app",
        "com.grok",
        "com.kinemaster",
        "com.lexa.fakegapp",
        "org.telegram.messenger",
        "com.whatsapp",
        "com.google.android.gm",
        "com.android.email"
    ])
    dangerous_apps: list = field(default_factory=lambda: [
        "com.android.settings",
        "com.android.phone",
        "com.android.contacts"
    ])
    app_timeout_seconds: int = 60
    app_launch_delay_ms: int = 1000


@dataclass
class AccessibilityConfig:
    """Accessibility configuration"""
    enabled: bool = True
    screenshot_enabled: bool = True
    ocr_enabled: bool = True
    full_control: bool = True
    privacy_filter: bool = True


@dataclass
class LearningConfig:
    """Learning configuration"""
    sources: list = field(default_factory=lambda: [
        "chatgpt",
        "deepseek",
        "youtube",
        "grok",
        "chrome",
        "local_knowledge"
    ])
    merge_strategy: str = "intelligent"
    confidence_threshold: float = 0.6
    min_sources: int = 2
    max_learning_tasks: int = 5
    knowledge_retention_days: int = 30


@dataclass
class MemoryConfig:
    """Memory configuration"""
    local_storage_path: str = "/data/data/com.termux/files/home/Assistant/data/"
    cloud_provider: str = "mega"
    auto_sync: bool = True
    sync_interval_hours: int = 24
    temp_data_cleanup: bool = True
    temp_data_retention_hours: int = 1


@dataclass
class PrivacyConfig:
    """Privacy configuration"""
    sensitive_data_patterns: list = field(default_factory=lambda: [
        "password",
        "secret",
        "credit.*card",
        "bank.*account",
        "ssn",
        "social.*security",
        "api.*key",
        "token"
    ])
    encryption_enabled: bool = True
    data_masking: bool = True
    user_consent_required: bool = True


@dataclass
class NetworkConfig:
    """Network configuration"""
    timeout_seconds: int = 30
    retry_count: int = 3
    use_proxy: bool = False
    cache_enabled: bool = True
    cache_size_mb: int = 100


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file_enabled: bool = True
    console_enabled: bool = True
    max_file_size_mb: int = 10
    max_files: int = 5
    log_retention_days: int = 7


@dataclass
class FeaturesConfig:
    """Features configuration"""
    voice_input: bool = True
    text_input: bool = True
    wake_word_detection: bool = True
    command_preview: bool = True
    live_control: bool = True
    background_execution: bool = True
    multi_source_learning: bool = True
    screenshot: bool = True
    ocr: bool = True
    app_integration: bool = True
    accessibility_control: bool = True
    cloud_sync: bool = True
    privacy_protection: bool = True


@dataclass
class Config:
    """Main configuration class"""
    app_name: str = "JARVIS"
    version: str = "1.0.0"
    description: str = "Production-grade Android AI Assistant"
    author: str = "ahmadalmas650"
    
    device: DeviceConfig = field(default_factory=DeviceConfig)
    brain: BrainConfig = field(default_factory=BrainConfig)
    input: InputConfig = field(default_factory=InputConfig)
    apps: AppConfig = field(default_factory=AppConfig)
    accessibility: AccessibilityConfig = field(default_factory=AccessibilityConfig)
    learning: LearningConfig = field(default_factory=LearningConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    
    # Internal
    _config_path: Optional[str] = None
    
    def __post_init__(self):
        """Post initialization"""
        self._load_from_env()
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        import os
        
        # Brain settings
        if os.getenv("BRAIN_WAKE_WORD"):
            self.brain.wake_word = os.getenv("BRAIN_WAKE_WORD")
        if os.getenv("BRAIN_MAX_MEMORY_GB"):
            self.brain.max_memory_usage_gb = float(os.getenv("BRAIN_MAX_MEMORY_GB"))
        if os.getenv("BRAIN_MIN_CONFIDENCE"):
            self.brain.min_confidence_threshold = float(os.getenv("BRAIN_MIN_CONFIDENCE"))
        if os.getenv("BRAIN_LEARNING_ENABLED"):
            self.brain.learning_enabled = os.getenv("BRAIN_LEARNING_ENABLED").lower() == "true"
        if os.getenv("BRAIN_CLOUD_SYNC_ENABLED"):
            self.brain.cloud_sync_enabled = os.getenv("BRAIN_CLOUD_SYNC_ENABLED").lower() == "true"
        if os.getenv("BRAIN_PRIVACY_MODE"):
            self.brain.privacy_mode = os.getenv("BRAIN_PRIVACY_MODE").lower() == "true"
        if os.getenv("BRAIN_DEBUG_MODE"):
            self.brain.debug_mode = os.getenv("BRAIN_DEBUG_MODE").lower() == "true"
    
    @classmethod
    def load_from_file(cls, path: str = None) -> "Config":
        """Load configuration from JSON file"""
        if path is None:
            # Try default locations
            possible_paths = [
                "/data/data/com.termux/files/home/Assistant/configs/config.json",
                "configs/config.json",
                "config.json"
            ]
            
            for p in possible_paths:
                if os.path.exists(p):
                    path = p
                    break
        
        if path is None or not os.path.exists(path):
            # Return default config
            return cls()
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            config = cls()
            config._config_path = path
            config._load_from_dict(data)
            return config
            
        except Exception as e:
            print(f"Error loading config from {path}: {str(e)}")
            return cls()
    
    def _load_from_dict(self, data: Dict[str, Any]):
        """Load configuration from dictionary"""
        if not isinstance(data, dict):
            return
        
        # Basic info
        if "app_name" in data:
            self.app_name = data["app_name"]
        if "version" in data:
            self.version = data["version"]
        if "description" in data:
            self.description = data["description"]
        if "author" in data:
            self.author = data["author"]
        
        # Device
        if "device" in data and isinstance(data["device"], dict):
            device_data = data["device"]
            if "target_platform" in device_data:
                self.device.target_platform = device_data["target_platform"]
            if "min_sdk_version" in device_data:
                self.device.min_sdk_version = device_data["min_sdk_version"]
            if "target_sdk_version" in device_data:
                self.device.target_sdk_version = device_data["target_sdk_version"]
            if "min_ram" in device_data:
                self.device.min_ram_gb = float(device_data["min_ram"].replace("GB", ""))
            if "min_storage" in device_data:
                self.device.min_storage_gb = float(device_data["min_storage"].replace("GB", ""))
            if "architecture" in device_data:
                self.device.architecture = device_data["architecture"]
        
        # Brain
        if "brain" in data and isinstance(data["brain"], dict):
            brain_data = data["brain"]
            if "wake_word" in brain_data:
                self.brain.wake_word = brain_data["wake_word"]
            if "max_memory_usage_gb" in brain_data:
                self.brain.max_memory_usage_gb = brain_data["max_memory_usage_gb"]
            if "max_cpu_usage" in brain_data:
                self.brain.max_cpu_usage = brain_data["max_cpu_usage"]
            if "min_confidence_threshold" in brain_data:
                self.brain.min_confidence_threshold = brain_data["min_confidence_threshold"]
            if "learning_enabled" in brain_data:
                self.brain.learning_enabled = brain_data["learning_enabled"]
            if "cloud_sync_enabled" in brain_data:
                self.brain.cloud_sync_enabled = brain_data["cloud_sync_enabled"]
            if "privacy_mode" in brain_data:
                self.brain.privacy_mode = brain_data["privacy_mode"]
            if "debug_mode" in brain_data:
                self.brain.debug_mode = brain_data["debug_mode"]
            if "response_timeout_seconds" in brain_data:
                self.brain.response_timeout_seconds = brain_data["response_timeout_seconds"]
            if "task_timeout_seconds" in brain_data:
                self.brain.task_timeout_seconds = brain_data["task_timeout_seconds"]
            if "max_concurrent_tasks" in brain_data:
                self.brain.max_concurrent_tasks = brain_data["max_concurrent_tasks"]
        
        # Input
        if "input" in data and isinstance(data["input"], dict):
            input_data = data["input"]
            if "voice_enabled" in input_data:
                self.input.voice_enabled = input_data["voice_enabled"]
            if "text_enabled" in input_data:
                self.input.text_enabled = input_data["text_enabled"]
            if "default_language" in input_data:
                self.input.default_language = input_data["default_language"]
            if "supported_languages" in input_data:
                self.input.supported_languages = input_data["supported_languages"]
        
        # Apps
        if "apps" in data and isinstance(data["apps"], dict):
            app_data = data["apps"]
            if "allowed_apps" in app_data:
                self.apps.allowed_apps = app_data["allowed_apps"]
            if "dangerous_apps" in app_data:
                self.apps.dangerous_apps = app_data["dangerous_apps"]
        
        # Learning
        if "learning" in data and isinstance(data["learning"], dict):
            learning_data = data["learning"]
            if "sources" in learning_data:
                self.learning.sources = learning_data["sources"]
            if "merge_strategy" in learning_data:
                self.learning.merge_strategy = learning_data["merge_strategy"]
            if "confidence_threshold" in learning_data:
                self.learning.confidence_threshold = learning_data["confidence_threshold"]
        
        # Memory
        if "memory" in data and isinstance(data["memory"], dict):
            memory_data = data["memory"]
            if "local_storage_path" in memory_data:
                self.memory.local_storage_path = memory_data["local_storage_path"]
            if "cloud_provider" in memory_data:
                self.memory.cloud_provider = memory_data["cloud_provider"]
            if "auto_sync" in memory_data:
                self.memory.auto_sync = memory_data["auto_sync"]
        
        # Privacy
        if "privacy" in data and isinstance(data["privacy"], dict):
            privacy_data = data["privacy"]
            if "sensitive_data_patterns" in privacy_data:
                self.privacy.sensitive_data_patterns = privacy_data["sensitive_data_patterns"]
            if "encryption_enabled" in privacy_data:
                self.privacy.encryption_enabled = privacy_data["encryption_enabled"]
        
        # Network
        if "network" in data and isinstance(data["network"], dict):
            network_data = data["network"]
            if "timeout_seconds" in network_data:
                self.network.timeout_seconds = network_data["timeout_seconds"]
            if "retry_count" in network_data:
                self.network.retry_count = network_data["retry_count"]
        
        # Logging
        if "logging" in data and isinstance(data["logging"], dict):
            logging_data = data["logging"]
            if "level" in logging_data:
                self.logging.level = logging_data["level"]
            if "file_enabled" in logging_data:
                self.logging.file_enabled = logging_data["file_enabled"]
        
        # Features
        if "features" in data and isinstance(data["features"], dict):
            features_data = data["features"]
            for key, value in features_data.items():
                if hasattr(self.features, key):
                    setattr(self.features, key, value)
    
    def save_to_file(self, path: str = None):
        """Save configuration to JSON file"""
        if path is None:
            path = self._config_path
        
        if path is None:
            path = "configs/config.json"
        
        try:
            data = self.to_dict()
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving config to {path}: {str(e)}")
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "app_name": self.app_name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "device": {
                "target_platform": self.device.target_platform,
                "min_sdk_version": self.device.min_sdk_version,
                "target_sdk_version": self.device.target_sdk_version,
                "min_ram_gb": self.device.min_ram_gb,
                "min_storage_gb": self.device.min_storage_gb,
                "architecture": self.device.architecture
            },
            "brain": {
                "wake_word": self.brain.wake_word,
                "max_memory_usage_gb": self.brain.max_memory_usage_gb,
                "max_cpu_usage": self.brain.max_cpu_usage,
                "min_confidence_threshold": self.brain.min_confidence_threshold,
                "learning_enabled": self.brain.learning_enabled,
                "cloud_sync_enabled": self.brain.cloud_sync_enabled,
                "privacy_mode": self.brain.privacy_mode,
                "debug_mode": self.brain.debug_mode,
                "response_timeout_seconds": self.brain.response_timeout_seconds,
                "task_timeout_seconds": self.brain.task_timeout_seconds,
                "max_concurrent_tasks": self.brain.max_concurrent_tasks
            },
            "input": {
                "voice_enabled": self.input.voice_enabled,
                "text_enabled": self.input.text_enabled,
                "default_language": self.input.default_language,
                "supported_languages": self.input.supported_languages
            },
            "apps": {
                "allowed_apps": self.apps.allowed_apps,
                "dangerous_apps": self.apps.dangerous_apps,
                "app_timeout_seconds": self.apps.app_timeout_seconds,
                "app_launch_delay_ms": self.apps.app_launch_delay_ms
            },
            "accessibility": {
                "enabled": self.accessibility.enabled,
                "screenshot_enabled": self.accessibility.screenshot_enabled,
                "ocr_enabled": self.accessibility.ocr_enabled,
                "full_control": self.accessibility.full_control,
                "privacy_filter": self.accessibility.privacy_filter
            },
            "learning": {
                "sources": self.learning.sources,
                "merge_strategy": self.learning.merge_strategy,
                "confidence_threshold": self.learning.confidence_threshold,
                "min_sources": self.learning.min_sources,
                "max_learning_tasks": self.learning.max_learning_tasks,
                "knowledge_retention_days": self.learning.knowledge_retention_days
            },
            "memory": {
                "local_storage_path": self.memory.local_storage_path,
                "cloud_provider": self.memory.cloud_provider,
                "auto_sync": self.memory.auto_sync,
                "sync_interval_hours": self.memory.sync_interval_hours,
                "temp_data_cleanup": self.memory.temp_data_cleanup,
                "temp_data_retention_hours": self.memory.temp_data_retention_hours
            },
            "privacy": {
                "sensitive_data_patterns": self.privacy.sensitive_data_patterns,
                "encryption_enabled": self.privacy.encryption_enabled,
                "data_masking": self.privacy.data_masking,
                "user_consent_required": self.privacy.user_consent_required
            },
            "network": {
                "timeout_seconds": self.network.timeout_seconds,
                "retry_count": self.network.retry_count,
                "use_proxy": self.network.use_proxy,
                "cache_enabled": self.network.cache_enabled,
                "cache_size_mb": self.network.cache_size_mb
            },
            "logging": {
                "level": self.logging.level,
                "file_enabled": self.logging.file_enabled,
                "console_enabled": self.logging.console_enabled,
                "max_file_size_mb": self.logging.max_file_size_mb,
                "max_files": self.logging.max_files,
                "log_retention_days": self.logging.log_retention_days
            },
            "features": {
                "voice_input": self.features.voice_input,
                "text_input": self.features.text_input,
                "wake_word_detection": self.features.wake_word_detection,
                "command_preview": self.features.command_preview,
                "live_control": self.features.live_control,
                "background_execution": self.features.background_execution,
                "multi_source_learning": self.features.multi_source_learning,
                "screenshot": self.features.screenshot,
                "ocr": self.features.ocr,
                "app_integration": self.features.app_integration,
                "accessibility_control": self.features.accessibility_control,
                "cloud_sync": self.features.cloud_sync,
                "privacy_protection": self.features.privacy_protection
            }
        }
