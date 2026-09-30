"""
Privacy Guard Module
Protects sensitive data and ensures privacy compliance
"""

import re
import json
import time
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Callable, Set
from dataclasses import dataclass, field
from enum import Enum, auto

from .logger import Logger
from .error_handler import ErrorHandler


class PrivacyLevel(Enum):
    """Privacy protection levels"""
    PUBLIC = auto()      # No protection
    LOW = auto()         # Basic protection
    MEDIUM = auto()      # Standard protection
    HIGH = auto()        # Strong protection
    CRITICAL = auto()    # Maximum protection


class DataType(Enum):
    """Types of sensitive data"""
    PERSONAL = auto()       # Names, addresses, etc.
    FINANCIAL = auto()      # Credit cards, bank info
    HEALTH = auto()         # Medical information
    AUTHENTICATION = auto() # Passwords, tokens
    LOCATION = auto()       # GPS coordinates, addresses
    CONTACT = auto()        # Phone numbers, emails
    IDENTIFICATION = auto() # ID numbers, SSN
    BIOMETRIC = auto()      # Fingerprints, face data
    COMMUNICATION = auto() # Messages, calls
    BEHAVIORAL = auto()     # Usage patterns, habits


@dataclass
class SensitiveData:
    """Represents sensitive data that needs protection"""
    value: str
    data_type: DataType
    privacy_level: PrivacyLevel
    detected_in: str = ""
    timestamp: float = field(default_factory=time.time)
    action_taken: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "value": self._mask_value(),
            "data_type": self.data_type.name,
            "privacy_level": self.privacy_level.name,
            "detected_in": self.detected_in,
            "timestamp": self.timestamp,
            "action_taken": self.action_taken
        }
    
    def _mask_value(self) -> str:
        """Mask the value for display"""
        if self.privacy_level == PrivacyLevel.CRITICAL:
            return "[REDACTED]"
        elif self.privacy_level == PrivacyLevel.HIGH:
            return f"[MASKED: {self.data_type.name}]"
        else:
            # Show first and last characters
            if len(self.value) > 4:
                return f"{self.value[0]}{'*' * (len(self.value) - 2)}{self.value[-1]}"
            return self.value


@dataclass
class PrivacyPolicy:
    """Privacy policy configuration"""
    default_level: PrivacyLevel = PrivacyLevel.MEDIUM
    enabled: bool = True
    log_sensitive_data: bool = False
    auto_encrypt: bool = True
    auto_anonymize: bool = True
    allowed_data_types: List[DataType] = field(default_factory=list)
    blocked_data_types: List[DataType] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "default_level": self.default_level.name,
            "enabled": self.enabled,
            "log_sensitive_data": self.log_sensitive_data,
            "auto_encrypt": self.auto_encrypt,
            "auto_anonymize": self.auto_anonymize,
            "allowed_data_types": [dt.name for dt in self.allowed_data_types],
            "blocked_data_types": [dt.name for dt in self.blocked_data_types]
        }


class PrivacyGuard:
    """
    Protects sensitive data and ensures privacy compliance
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Privacy configuration
        self._policy = PrivacyPolicy()
        
        # Sensitive data patterns
        self._patterns = self._load_patterns()
        
        # Detected sensitive data
        self._detected_data: List[SensitiveData] = []
        self._max_history = 1000
        
        # Encryption key (in production, use secure key management)
        self._encryption_key = None
        
        # Callbacks
        self._on_sensitive_data_detected: List[Callable[[SensitiveData], None]] = []
        self._on_privacy_violation: List[Callable[[Dict], None]] = []
    
    def _load_patterns(self) -> Dict[DataType, List[Tuple[str, PrivacyLevel]]]:
        """Load patterns for detecting sensitive data"""
        return {
            DataType.PERSONAL: [
                (r'\b(?:Mr|Mrs|Ms|Dr|Prof)\s+\w+\s+\w+\b', PrivacyLevel.MEDIUM),
                (r'\b\w+\s+Street\b', PrivacyLevel.MEDIUM),
                (r'\b\w+\s+Avenue\b', PrivacyLevel.MEDIUM),
                (r'\b\w+\s+Road\b', PrivacyLevel.MEDIUM),
                (r'\b\w+\s+Lane\b', PrivacyLevel.MEDIUM)
            ],
            DataType.FINANCIAL: [
                (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', PrivacyLevel.CRITICAL),  # Credit card
                (r'\b\d{3,4}\b', PrivacyLevel.MEDIUM),  # CVV
                (r'\b(?:VISA|MasterCard|Amex|Discover)\b', PrivacyLevel.HIGH),
                (r'\b\d{8,12}\b', PrivacyLevel.MEDIUM),  # Account numbers
                (r'\b(?:Routing|Account|Bank)\s+(?:Number|#|No)\b', PrivacyLevel.HIGH)
            ],
            DataType.AUTHENTICATION: [
                (r'\bpassword\b', PrivacyLevel.CRITICAL),
                (r'\bpasswd\b', PrivacyLevel.CRITICAL),
                (r'\btoken\b', PrivacyLevel.HIGH),
                (r'\bapi[_-]?key\b', PrivacyLevel.HIGH),
                (r'\bsecret\b', PrivacyLevel.HIGH),
                (r'\bauth(?:entication)?\b', PrivacyLevel.MEDIUM)
            ],
            DataType.CONTACT: [
                (r'\b\w+@\w+\.\w+\b', PrivacyLevel.MEDIUM),  # Email
                (r'\b\+?\d{10,15}\b', PrivacyLevel.MEDIUM),  # Phone
                (r'\b\d{3}[\s-]?\d{3}[\s-]?\d{4}\b', PrivacyLevel.MEDIUM),  # Phone
                (r'\b(?:Phone|Mobile|Cell)\s+(?:Number|#|No)\b', PrivacyLevel.MEDIUM)
            ],
            DataType.IDENTIFICATION: [
                (r'\b\d{3}-\d{2}-\d{4}\b', PrivacyLevel.CRITICAL),  # SSN
                (r'\b\d{9,11}\b', PrivacyLevel.HIGH),  # ID numbers
                (r'\b(?:SSN|Social\s+Security)\b', PrivacyLevel.CRITICAL),
                (r'\b(?:ID|Identification)\s+(?:Number|#|No)\b', PrivacyLevel.HIGH)
            ],
            DataType.LOCATION: [
                (r'\b\d{1,3}\.\d{1,6},\s*\-?\d{1,3}\.\d{1,6}\b', PrivacyLevel.MEDIUM),  # GPS coordinates
                (r'\b(?:Latitude|Longitude|GPS)\b', PrivacyLevel.MEDIUM),
                (r'\b\d{5}(?:-\d{4})?\b', PrivacyLevel.LOW)  # ZIP codes
            ],
            DataType.HEALTH: [
                (r'\b(?:Medical|Health|Patient)\s+(?:Record|History|ID)\b', PrivacyLevel.HIGH),
                (r'\b(?:Diagnosis|Treatment|Prescription)\b', PrivacyLevel.HIGH),
                (r'\b\w+\s+(?:Hospital|Clinic|Doctor)\b', PrivacyLevel.MEDIUM)
            ],
            DataType.COMMUNICATION: [
                (r'\b(?:Message|Text|SMS|Email)\s+(?:Content|Body)\b', PrivacyLevel.MEDIUM),
                (r'\b(?:Call|Phone)\s+(?:Log|History|Record)\b', PrivacyLevel.MEDIUM)
            ]
        }
    
    # Configuration
    
    def set_policy(self, policy: PrivacyPolicy):
        """Set the privacy policy"""
        self._policy = policy
        self.logger.info("Privacy policy updated")
    
    def get_policy(self) -> PrivacyPolicy:
        """Get the current privacy policy"""
        return self._policy
    
    def enable(self):
        """Enable privacy protection"""
        self._policy.enabled = True
        self.logger.info("Privacy protection enabled")
    
    def disable(self):
        """Disable privacy protection"""
        self._policy.enabled = False
        self.logger.warning("Privacy protection disabled")
    
    def is_enabled(self) -> bool:
        """Check if privacy protection is enabled"""
        return self._policy.enabled
    
    def set_default_level(self, level: PrivacyLevel):
        """Set the default privacy level"""
        self._policy.default_level = level
        self.logger.info(f"Default privacy level set to: {level.name}")
    
    # Data Scanning
    
    def scan_text(self, text: str, context: str = "") -> List[SensitiveData]:
        """
        Scan text for sensitive data
        
        Args:
            text: Text to scan
            context: Context for the scan
            
        Returns:
            List of detected sensitive data
        """
        if not self._policy.enabled:
            return []
        
        detected = []
        
        try:
            for data_type, patterns in self._patterns.items():
                for pattern, level in patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        # Check if this data type is blocked
                        if data_type in self._policy.blocked_data_types:
                            # Create sensitive data record
                            sensitive_data = SensitiveData(
                                value=match.group(),
                                data_type=data_type,
                                privacy_level=level,
                                detected_in=context,
                                action_taken="blocked"
                            )
                            detected.append(sensitive_data)
                            
                            # Notify detection
                            for callback in self._on_sensitive_data_detected:
                                try:
                                    callback(sensitive_data)
                                except Exception as e:
                                    self.error_handler.handle_error(e, "sensitive_data_callback")
                        
                        # Check if this data type is allowed
                        elif data_type in self._policy.allowed_data_types:
                            # Allow but log
                            sensitive_data = SensitiveData(
                                value=match.group(),
                                data_type=data_type,
                                privacy_level=level,
                                detected_in=context,
                                action_taken="allowed"
                            )
                            detected.append(sensitive_data)
                        
                        # If policy is to auto-anonymize
                        if self._policy.auto_anonymize:
                            # Replace with placeholder
                            replacement = self._get_placeholder(data_type, level)
                            text = text[:match.start()] + replacement + text[match.end():]
            
            # Add to history
            self._add_to_history(detected)
            
        except Exception as e:
            self.error_handler.handle_error(e, "scan_text")
        
        return detected
    
    def scan_dict(self, data: Dict, context: str = "") -> List[SensitiveData]:
        """
        Scan a dictionary for sensitive data
        
        Args:
            data: Dictionary to scan
            context: Context for the scan
            
        Returns:
            List of detected sensitive data
        """
        detected = []
        
        for key, value in data.items():
            if isinstance(value, str):
                # Scan string values
                found = self.scan_text(value, f"{context}.{key}")
                detected.extend(found)
            elif isinstance(value, dict):
                # Recursively scan nested dictionaries
                found = self.scan_dict(value, f"{context}.{key}")
                detected.extend(found)
            elif isinstance(value, list):
                # Scan list items
                for i, item in enumerate(value):
                    if isinstance(item, str):
                        found = self.scan_text(item, f"{context}.{key}[{i}]")
                        detected.extend(found)
                    elif isinstance(item, dict):
                        found = self.scan_dict(item, f"{context}.{key}[{i}]")
                        detected.extend(found)
        
        return detected
    
    def scan_list(self, items: List, context: str = "") -> List[SensitiveData]:
        """
        Scan a list for sensitive data
        
        Args:
            items: List to scan
            context: Context for the scan
            
        Returns:
            List of detected sensitive data
        """
        detected = []
        
        for i, item in enumerate(items):
            if isinstance(item, str):
                found = self.scan_text(item, f"{context}[{i}]")
                detected.extend(found)
            elif isinstance(item, dict):
                found = self.scan_dict(item, f"{context}[{i}]")
                detected.extend(found)
        
        return detected
    
    def _get_placeholder(self, data_type: DataType, level: PrivacyLevel) -> str:
        """Get a placeholder for sensitive data"""
        placeholders = {
            DataType.PERSONAL: {
                PrivacyLevel.LOW: "[NAME]",
                PrivacyLevel.MEDIUM: "[PERSONAL]",
                PrivacyLevel.HIGH: "[REDACTED]",
                PrivacyLevel.CRITICAL: "[REDACTED]"
            },
            DataType.FINANCIAL: {
                PrivacyLevel.LOW: "[CARD]",
                PrivacyLevel.MEDIUM: "[FINANCIAL]",
                PrivacyLevel.HIGH: "[REDACTED]",
                PrivacyLevel.CRITICAL: "[REDACTED]"
            },
            DataType.AUTHENTICATION: {
                PrivacyLevel.LOW: "[PASSWORD]",
                PrivacyLevel.MEDIUM: "[AUTH]",
                PrivacyLevel.HIGH: "[REDACTED]",
                PrivacyLevel.CRITICAL: "[REDACTED]"
            },
            DataType.CONTACT: {
                PrivacyLevel.LOW: "[CONTACT]",
                PrivacyLevel.MEDIUM: "[CONTACT]",
                PrivacyLevel.HIGH: "[REDACTED]",
                PrivacyLevel.CRITICAL: "[REDACTED]"
            },
            DataType.IDENTIFICATION: {
                PrivacyLevel.LOW: "[ID]",
                PrivacyLevel.MEDIUM: "[ID]",
                PrivacyLevel.HIGH: "[REDACTED]",
                PrivacyLevel.CRITICAL: "[REDACTED]"
            },
            DataType.LOCATION: {
                PrivacyLevel.LOW: "[LOCATION]",
                PrivacyLevel.MEDIUM: "[LOCATION]",
                PrivacyLevel.HIGH: "[REDACTED]",
                PrivacyLevel.CRITICAL: "[REDACTED]"
            },
            DataType.HEALTH: {
                PrivacyLevel.LOW: "[HEALTH]",
                PrivacyLevel.MEDIUM: "[HEALTH]",
                PrivacyLevel.HIGH: "[REDACTED]",
                PrivacyLevel.CRITICAL: "[REDACTED]"
            },
            DataType.COMMUNICATION: {
                PrivacyLevel.LOW: "[MESSAGE]",
                PrivacyLevel.MEDIUM: "[MESSAGE]",
                PrivacyLevel.HIGH: "[REDACTED]",
                PrivacyLevel.CRITICAL: "[REDACTED]"
            }
        }
        
        return placeholders.get(data_type, {}).get(level, "[REDACTED]")
    
    # Anonymization
    
    def anonymize_text(self, text: str, context: str = "") -> str:
        """
        Anonymize sensitive data in text
        
        Args:
            text: Text to anonymize
            context: Context for the operation
            
        Returns:
            Anonymized text
        """
        if not self._policy.enabled or not self._policy.auto_anonymize:
            return text
        
        try:
            # Scan and replace sensitive data
            for data_type, patterns in self._patterns.items():
                for pattern, level in patterns:
                    if data_type in self._policy.blocked_data_types:
                        matches = re.finditer(pattern, text, re.IGNORECASE)
                        for match in matches:
                            replacement = self._get_placeholder(data_type, level)
                            text = text[:match.start()] + replacement + text[match.end():]
            
            return text
            
        except Exception as e:
            self.error_handler.handle_error(e, "anonymize_text")
            return text
    
    def anonymize_dict(self, data: Dict, context: str = "") -> Dict:
        """
        Anonymize sensitive data in a dictionary
        
        Args:
            data: Dictionary to anonymize
            context: Context for the operation
            
        Returns:
            Anonymized dictionary
        """
        if not self._policy.enabled or not self._policy.auto_anonymize:
            return data
        
        try:
            # Create a copy to avoid modifying original
            anonymized = {}
            
            for key, value in data.items():
                if isinstance(value, str):
                    anonymized[key] = self.anonymize_text(value, f"{context}.{key}")
                elif isinstance(value, dict):
                    anonymized[key] = self.anonymize_dict(value, f"{context}.{key}")
                elif isinstance(value, list):
                    anonymized[key] = self.anonymize_list(value, f"{context}.{key}")
                else:
                    anonymized[key] = value
            
            return anonymized
            
        except Exception as e:
            self.error_handler.handle_error(e, "anonymize_dict")
            return data
    
    def anonymize_list(self, items: List, context: str = "") -> List:
        """
        Anonymize sensitive data in a list
        
        Args:
            items: List to anonymize
            context: Context for the operation
            
        Returns:
            Anonymized list
        """
        if not self._policy.enabled or not self._policy.auto_anonymize:
            return items
        
        try:
            anonymized = []
            
            for i, item in enumerate(items):
                if isinstance(item, str):
                    anonymized.append(self.anonymize_text(item, f"{context}[{i}]"))
                elif isinstance(item, dict):
                    anonymized.append(self.anonymize_dict(item, f"{context}[{i}]"))
                elif isinstance(item, list):
                    anonymized.append(self.anonymize_list(item, f"{context}[{i}]"))
                else:
                    anonymized.append(item)
            
            return anonymized
            
        except Exception as e:
            self.error_handler.handle_error(e, "anonymize_list")
            return items
    
    # Input/Output Checking
    
    def check_input(self, data: Any, context: str = "") -> Dict:
        """
        Check input for privacy violations
        
        Args:
            data: Data to check
            context: Context for the check
            
        Returns:
            Dictionary with check results
        """
        result = {
            "blocked": False,
            "sensitive_data": [],
            "anonymized_data": None,
            "recommendations": []
        }
        
        if not self._policy.enabled:
            return result
        
        try:
            # Scan for sensitive data
            if isinstance(data, str):
                sensitive_data = self.scan_text(data, context)
            elif isinstance(data, dict):
                sensitive_data = self.scan_dict(data, context)
            elif isinstance(data, list):
                sensitive_data = self.scan_list(data, context)
            else:
                sensitive_data = []
            
            result["sensitive_data"] = [sd.to_dict() for sd in sensitive_data]
            
            # Check if any blocked data was found
            blocked_data = [sd for sd in sensitive_data if sd.action_taken == "blocked"]
            if blocked_data:
                result["blocked"] = True
                result["recommendations"].append("Remove or anonymize sensitive data")
            
            # Anonymize if requested
            if self._policy.auto_anonymize and sensitive_data:
                if isinstance(data, str):
                    result["anonymized_data"] = self.anonymize_text(data, context)
                elif isinstance(data, dict):
                    result["anonymized_data"] = self.anonymize_dict(data, context)
                elif isinstance(data, list):
                    result["anonymized_data"] = self.anonymize_list(data, context)
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, "check_input")
            return result
    
    def check_output(self, data: Any, context: str = "") -> Dict:
        """
        Check output for privacy violations
        
        Args:
            data: Data to check
            context: Context for the check
            
        Returns:
            Dictionary with check results
        """
        # Same as input check but with different context
        return self.check_input(data, f"output.{context}")
    
    # Encryption
    
    def set_encryption_key(self, key: str):
        """Set the encryption key"""
        # In production, use proper key management
        self._encryption_key = key
    
    def encrypt_data(self, data: Any) -> Optional[str]:
        """
        Encrypt sensitive data
        
        Args:
            data: Data to encrypt
            
        Returns:
            Encrypted string or None
        """
        if not self._policy.auto_encrypt or not self._encryption_key:
            return None
        
        try:
            # Convert data to JSON string
            data_str = json.dumps(data) if not isinstance(data, str) else data
            
            # Simple encryption (in production, use proper encryption)
            import base64
            from cryptography.fernet import Fernet
            
            # Generate key if not set
            if not self._encryption_key:
                self._encryption_key = Fernet.generate_key().decode()
            
            # Encrypt
            fernet = Fernet(self._encryption_key.encode())
            encrypted = fernet.encrypt(data_str.encode())
            
            return base64.b64encode(encrypted).decode()
            
        except ImportError:
            # Fallback if cryptography not available
            self.logger.warning("Encryption not available - cryptography module not installed")
            return None
        except Exception as e:
            self.error_handler.handle_error(e, "encrypt_data")
            return None
    
    def decrypt_data(self, encrypted_data: str) -> Optional[Any]:
        """
        Decrypt encrypted data
        
        Args:
            encrypted_data: Encrypted string
            
        Returns:
            Decrypted data or None
        """
        if not self._encryption_key:
            return None
        
        try:
            import base64
            from cryptography.fernet import Fernet
            
            # Decrypt
            fernet = Fernet(self._encryption_key.encode())
            decoded = base64.b64decode(encrypted_data.encode())
            decrypted = fernet.decrypt(decoded)
            
            # Try to parse as JSON
            try:
                return json.loads(decrypted.decode())
            except:
                return decrypted.decode()
            
        except ImportError:
            self.logger.warning("Decryption not available - cryptography module not installed")
            return None
        except Exception as e:
            self.error_handler.handle_error(e, "decrypt_data")
            return None
    
    # Privacy Violation Handling
    
    def report_violation(self, violation_type: str, details: Dict) -> str:
        """
        Report a privacy violation
        
        Args:
            violation_type: Type of violation
            details: Details about the violation
            
        Returns:
            Violation ID
        """
        violation_id = f"violation_{int(time.time())}"
        
        # Log the violation
        self.logger.error(f"Privacy violation: {violation_type}", details)
        
        # Notify callbacks
        violation_data = {
            "violation_id": violation_id,
            "violation_type": violation_type,
            "details": details,
            "timestamp": time.time()
        }
        
        for callback in self._on_privacy_violation:
            try:
                callback(violation_data)
            except Exception as e:
                self.error_handler.handle_error(e, "privacy_violation_callback")
        
        return violation_id
    
    # History
    
    def _add_to_history(self, sensitive_data: List[SensitiveData]):
        """Add to detection history"""
        self._detected_data.extend(sensitive_data)
        if len(self._detected_data) > self._max_history:
            self._detected_data = self._detected_data[-self._max_history:]
    
    def get_detection_history(self, count: int = 100) -> List[SensitiveData]:
        """Get recent detection history"""
        return self._detected_data[-count:]
    
    def get_detection_stats(self) -> Dict:
        """Get detection statistics"""
        stats = {
            "total_detections": len(self._detected_data),
            "by_type": {},
            "by_level": {},
            "by_context": {}
        }
        
        for data in self._detected_data:
            # Count by type
            type_name = data.data_type.name
            stats["by_type"][type_name] = stats["by_type"].get(type_name, 0) + 1
            
            # Count by level
            level_name = data.privacy_level.name
            stats["by_level"][level_name] = stats["by_level"].get(level_name, 0) + 1
            
            # Count by context
            stats["by_context"][data.detected_in] = stats["by_context"].get(data.detected_in, 0) + 1
        
        return stats
    
    def clear_history(self):
        """Clear detection history"""
        self._detected_data = []
    
    # Callbacks
    
    def on_sensitive_data_detected(self, callback: Callable[[SensitiveData], None]):
        """Register callback for sensitive data detection"""
        self._on_sensitive_data_detected.append(callback)
    
    def on_privacy_violation(self, callback: Callable[[Dict], None]):
        """Register callback for privacy violations"""
        self._on_privacy_violation.append(callback)
    
    # Cleanup
    
    def cleanup(self):
        """Clean up resources"""
        self._detected_data = []
        self._on_sensitive_data_detected = []
        self._on_privacy_violation = []
        self._encryption_key = None
        self.logger.info("Privacy Guard cleaned up")
