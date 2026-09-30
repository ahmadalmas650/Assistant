"""
Test Suite for JARVIS AI Assistant
Comprehensive testing framework for all components
"""

import unittest
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from brain.core.brain_engine import BrainEngine, BrainConfig, BrainState
from brain.modules.input_processor import InputProcessor
from brain.modules.command_parser import CommandParser
from brain.modules.wake_word_detector import WakeWordDetector
from brain.learning.multi_source_learner import MultiSourceLearner
from brain.learning.knowledge_merger import KnowledgeMerger
from brain.memory.memory_manager import MemoryManager
from brain.tasks.task_manager import TaskManager
from brain.tasks.preview_system import PreviewSystem
from configs.config import Config
from brain.utils.logger import Logger


class TestConfig:
    """Test configuration"""
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    
    @classmethod
    def get_logger(cls, name: str = "test"):
        """Get a logger for testing"""
        return Logger(name, debug=cls.DEBUG)
    
    @classmethod
    def get_config(cls):
        """Get a test configuration"""
        config = Config()
        config.brain.debug_mode = True
        config.logging.level = "DEBUG"
        return config


def run_async_tests(test_class):
    """Run async tests"""
    suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


# Import all test modules
from .test_brain_engine import *
from .test_input_processor import *
from .test_command_parser import *
from .test_wake_word_detector import *
from .test_task_manager import *
from .test_preview_system import *
from .test_memory_manager import *
from .test_learning_system import *
from .test_accessibility import *
from .test_app_integration import *
from .test_ocr_engine import *
from .test_screenshot_manager import *

__all__ = [
    'TestConfig',
    'run_async_tests',
    'TestBrainEngine',
    'TestInputProcessor',
    'TestCommandParser',
    'TestWakeWordDetector',
    'TestTaskManager',
    'TestPreviewSystem',
    'TestMemoryManager',
    'TestLearningSystem',
    'TestAccessibilityController',
    'TestAppIntegrator',
    'TestOCREngine',
    'TestScreenshotManager'
]
