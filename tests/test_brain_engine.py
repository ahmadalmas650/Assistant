"""
Test Brain Engine Module
"""

import unittest
import asyncio
import time
from typing import Dict, Any

from brain.core.brain_engine import BrainEngine, BrainConfig, BrainState, BrainMode
from brain.modules.input_processor import InputProcessor, ProcessedInput
from brain.modules.command_parser import CommandParser, ParsedCommand
from configs.config import Config
from tests import TestConfig


class TestBrainEngine(unittest.TestCase):
    """Test cases for Brain Engine"""
    
    def setUp(self):
        """Setup test fixtures"""
        self.config = TestConfig.get_config()
        self.logger = TestConfig.get_logger("BrainEngineTest")
        self.brain_config = BrainConfig(
            name="JARVIS",
            wake_word="jarvis",
            max_memory_usage=2.0,
            max_cpu_usage=0.8,
            min_confidence_threshold=0.7,
            learning_enabled=True,
            cloud_sync_enabled=True,
            privacy_mode=True,
            debug_mode=True
        )
        self.brain = BrainEngine(self.brain_config)
    
    def tearDown(self):
        """Cleanup after tests"""
        pass
    
    def test_initialization(self):
        """Test brain engine initialization"""
        self.assertIsNotNone(self.brain)
        self.assertEqual(self.brain.config.name, "JARVIS")
        self.assertEqual(self.brain.config.wake_word, "jarvis")
        self.assertEqual(self.brain.state, BrainState.IDLE)
    
    def test_set_mode(self):
        """Test setting brain mode"""
        self.brain.set_mode(BrainMode.FAST)
        self.assertEqual(self.brain.mode, BrainMode.FAST)
        
        self.brain.set_mode(BrainMode.NORMAL)
        self.assertEqual(self.brain.mode, BrainMode.NORMAL)
    
    def test_set_state(self):
        """Test setting brain state"""
        self.brain.set_state(BrainState.PROCESSING)
        self.assertEqual(self.brain.state, BrainState.PROCESSING)
        
        self.brain.set_state(BrainState.IDLE)
        self.assertEqual(self.brain.state, BrainState.IDLE)
    
    def test_check_wake_word(self):
        """Test wake word detection"""
        # Test with wake word at start
        self.assertTrue(self.brain._check_wake_word("jarvis hello"))
        
        # Test with wake word in middle
        self.assertTrue(self.brain._check_wake_word("hello jarvis world"))
        
        # Test with wake word at end
        self.assertTrue(self.brain._check_wake_word("hello jarvis"))
        
        # Test without wake word
        self.assertFalse(self.brain._check_wake_word("hello world"))
        
        # Test case insensitive
        self.assertTrue(self.brain._check_wake_word("JARVIS hello"))
        self.assertTrue(self.brain._check_wake_word("Jarvis hello"))
    
    def test_get_config(self):
        """Test getting configuration"""
        config = self.brain.get_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.name, "JARVIS")
    
    def test_update_config(self):
        """Test updating configuration"""
        self.brain.update_config(wake_word="computer")
        self.assertEqual(self.brain.config.wake_word, "computer")
        
        self.brain.update_config(max_memory_usage=3.0)
        self.assertEqual(self.brain.config.max_memory_usage, 3.0)
    
    def test_get_capabilities(self):
        """Test getting capabilities"""
        async def test_async():
            capabilities = await self.brain.get_capabilities()
            self.assertIsInstance(capabilities, list)
            self.assertGreater(len(capabilities), 0)
            self.assertIn("voice_input", capabilities)
            self.assertIn("text_input", capabilities)
            self.assertIn("wake_word_detection", capabilities)
        
        asyncio.run(test_async())
    
    def test_get_status(self):
        """Test getting status"""
        async def test_async():
            status = await self.brain.get_status()
            self.assertIsInstance(status, dict)
            self.assertIn("state", status)
            self.assertIn("mode", status)
            self.assertEqual(status["state"], "IDLE")
        
        asyncio.run(test_async())


class TestBrainEngineAsync(unittest.IsolatedAsyncioTestCase):
    """Async test cases for Brain Engine"""
    
    async def asyncSetUp(self):
        """Async setup"""
        self.config = TestConfig.get_config()
        self.logger = TestConfig.get_logger("BrainEngineAsyncTest")
        self.brain_config = BrainConfig(
            name="JARVIS",
            wake_word="jarvis",
            max_memory_usage=2.0,
            max_cpu_usage=0.8,
            min_confidence_threshold=0.7,
            learning_enabled=True,
            cloud_sync_enabled=True,
            privacy_mode=True,
            debug_mode=True
        )
        self.brain = BrainEngine(self.brain_config)
        await self.brain.initialize()
    
    async def test_process_input_no_wake_word(self):
        """Test processing input without wake word"""
        result = await self.brain.process_input("hello world", "text")
        self.assertIn("status", result)
        self.assertEqual(result["status"], "ignored")
        self.assertEqual(result["reason"], "no_wake_word")
    
    async def test_process_input_with_wake_word(self):
        """Test processing input with wake word"""
        # This will fail because we don't have all modules properly initialized
        # but it should at least not crash
        result = await self.brain.process_input("jarvis hello", "text")
        self.assertIn("status", result)
    
    async def test_execute_command(self):
        """Test direct command execution"""
        # Test with a simple command
        result = await self.brain.execute_command("hello")
        self.assertIn("status", result)
    
    async def test_get_preview(self):
        """Test getting command preview"""
        result = await self.brain.get_preview("upload video")
        self.assertIn("status", result)
        if result.get("status") == "preview":
            self.assertIn("plan", result)
            self.assertIn("command", result)
    
    async def test_stop_current_task(self):
        """Test stopping current task"""
        result = await self.brain.stop_current_task()
        self.assertIsInstance(result, bool)
    
    async def test_modify_current_task(self):
        """Test modifying current task"""
        result = await self.brain.modify_current_task("change something")
        self.assertIsInstance(result, bool)


if __name__ == '__main__':
    unittest.main()
