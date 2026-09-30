"""
Test Input Processor Module
"""

import unittest
import asyncio
import os
import tempfile
from pathlib import Path

from brain.modules.input_processor import InputProcessor, ProcessedInput
from configs.config import Config
from tests import TestConfig


class TestInputProcessor(unittest.TestCase):
    """Test cases for Input Processor"""
    
    def setUp(self):
        """Setup test fixtures"""
        self.config = TestConfig.get_config()
        self.logger = TestConfig.get_logger("InputProcessorTest")
        self.processor = InputProcessor(self.config, self.logger)
    
    def tearDown(self):
        """Cleanup after tests"""
        pass
    
    def test_initialization(self):
        """Test input processor initialization"""
        self.assertIsNotNone(self.processor)
        self.assertFalse(self.processor.is_listening())
        self.assertFalse(self.processor.is_recording())
    
    def test_process_text_input(self):
        """Test processing text input"""
        async def test_async():
            result = await self.processor.process("Hello, world!", "text")
            self.assertIsInstance(result, ProcessedInput)
            self.assertEqual(result.text, "Hello, world!")
            self.assertEqual(result.input_type, "text")
            self.assertEqual(result.confidence, 1.0)
        
        asyncio.run(test_async())
    
    def test_process_text_with_bytes(self):
        """Test processing text input as bytes"""
        async def test_async():
            result = await self.processor.process(b"Hello, world!", "text")
            self.assertIsInstance(result, ProcessedInput)
            self.assertEqual(result.text, "Hello, world!")
        
        asyncio.run(test_async())
    
    def test_process_text_with_path(self):
        """Test processing text input from file path"""
        async def test_async():
            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write("Hello from file!")
                temp_path = f.name
            
            try:
                result = await self.processor.process(Path(temp_path), "text")
                self.assertIsInstance(result, ProcessedInput)
                self.assertEqual(result.text, "Hello from file!")
            finally:
                os.unlink(temp_path)
        
        asyncio.run(test_async())
    
    def test_clean_text(self):
        """Test text cleaning"""
        # Test with extra spaces
        result = self.processor._clean_text("  Hello   world!  ")
        self.assertEqual(result, "Hello world!")
        
        # Test with special characters
        result = self.processor._clean_text("Hello, world! How are you?")
        self.assertEqual(result, "Hello, world! How are you?")
        
        # Test with newlines
        result = self.processor._clean_text("Hello\nworld!")
        self.assertEqual(result, "Hello world!")
    
    def test_detect_language(self):
        """Test language detection"""
        # English
        result = self.processor._detect_language("Hello world")
        self.assertEqual(result, "en")
        
        # Urdu/Hindi
        result = self.processor._detect_language("hai aur kya")
        self.assertEqual(result, "ur")
        
        # Default to English
        result = self.processor._detect_language("xyz abc")
        self.assertEqual(result, "en")
    
    def test_check_wake_word(self):
        """Test wake word checking"""
        async def test_async():
            # Test with wake word
            result = await self.processor.check_wake_word("jarvis hello")
            self.assertTrue(result)
            
            # Test without wake word
            result = await self.processor.check_wake_word("hello world")
            self.assertFalse(result)
            
            # Test case insensitive
            result = await self.processor.check_wake_word("JARVIS hello")
            self.assertTrue(result)
        
        asyncio.run(test_async())
    
    def test_set_language(self):
        """Test setting language"""
        result = self.processor.set_language("ur")
        self.assertTrue(result)
        self.assertEqual(self.processor.get_language(), "ur")
        
        # Test invalid language
        result = self.processor.set_language("invalid")
        self.assertFalse(result)
    
    def test_get_supported_languages(self):
        """Test getting supported languages"""
        languages = self.processor.get_supported_languages()
        self.assertIsInstance(languages, list)
        self.assertGreater(len(languages), 0)
        self.assertIn("en", languages)


class TestInputProcessorAsync(unittest.IsolatedAsyncioTestCase):
    """Async test cases for Input Processor"""
    
    async def asyncSetUp(self):
        """Async setup"""
        self.config = TestConfig.get_config()
        self.logger = TestConfig.get_logger("InputProcessorAsyncTest")
        self.processor = InputProcessor(self.config, self.logger)
    
    async def test_process_with_wake_word(self):
        """Test processing with wake word detection"""
        has_wake_word, result = await self.processor.process_with_wake_word("jarvis hello", "text")
        self.assertTrue(has_wake_word)
        self.assertIsInstance(result, ProcessedInput)
        
        has_wake_word, result = await self.processor.process_with_wake_word("hello world", "text")
        self.assertFalse(has_wake_word)
    
    async def test_start_stop_listening(self):
        """Test starting and stopping listening"""
        result = await self.processor.start_listening()
        self.assertTrue(result)
        self.assertTrue(self.processor.is_listening())
        
        result = await self.processor.stop_listening()
        self.assertTrue(result)
        self.assertFalse(self.processor.is_listening())


if __name__ == '__main__':
    unittest.main()
