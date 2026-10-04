"""
Test Command Parser Module
"""

import unittest
import asyncio

from brain.modules.command_parser import CommandParser, ParsedCommand, IntentType, EntityType
from configs import Config
from tests import TestConfig


class TestCommandParser(unittest.TestCase):
    """Test cases for Command Parser"""
    
    def setUp(self):
        """Setup test fixtures"""
        self.config = TestConfig.get_config()
        self.logger = TestConfig.get_logger("CommandParserTest")
        self.parser = CommandParser(self.config, self.logger)
    
    def tearDown(self):
        """Cleanup after tests"""
        pass
    
    def test_initialization(self):
        """Test command parser initialization"""
        self.assertIsNotNone(self.parser)
    
    def test_parse_simple_command(self):
        """Test parsing a simple command"""
        async def test_async():
            result = await self.parser.parse("upload video")
            self.assertIsInstance(result, ParsedCommand)
            self.assertTrue(result.valid)
            self.assertEqual(result.text, "upload video")
            self.assertEqual(result.intent, IntentType.UPLOAD)
        
        asyncio.run(test_async())
    
    def test_parse_command_with_entities(self):
        """Test parsing command with entities"""
        async def test_async():
            result = await self.parser.parse("upload video to YouTube")
            self.assertTrue(result.valid)
            self.assertEqual(result.intent, IntentType.UPLOAD)
            self.assertGreater(len(result.entities), 0)
        
        asyncio.run(test_async())
    
    def test_parse_edit_command(self):
        """Test parsing edit command"""
        async def test_async():
            result = await self.parser.parse("edit this photo")
            self.assertTrue(result.valid)
            self.assertEqual(result.intent, IntentType.EDIT)
        
        asyncio.run(test_async())
    
    def test_parse_search_command(self):
        """Test parsing search command"""
        async def test_async():
            result = await self.parser.parse("search for AI news")
            self.assertTrue(result.valid)
            self.assertEqual(result.intent, IntentType.SEARCH)
        
        asyncio.run(test_async())
    
    def test_parse_screenshot_command(self):
        """Test parsing screenshot command"""
        async def test_async():
            result = await self.parser.parse("take a screenshot")
            self.assertTrue(result.valid)
            self.assertEqual(result.intent, IntentType.CAPTURE)
        
        asyncio.run(test_async())
    
    def test_parse_ocr_command(self):
        """Test parsing OCR command"""
        async def test_async():
            result = await self.parser.parse("extract text from image")
            self.assertTrue(result.valid)
            self.assertEqual(result.intent, IntentType.EXTRACT)
        
        asyncio.run(test_async())
    
    def test_parse_invalid_command(self):
        """Test parsing invalid command"""
        async def test_async():
            result = await self.parser.parse("")
            self.assertIsInstance(result, ParsedCommand)
            self.assertFalse(result.valid)
        
        asyncio.run(test_async())
    
    def test_parse_unknown_command(self):
        """Test parsing unknown command"""
        async def test_async():
            result = await self.parser.parse("xyz abc def")
            self.assertTrue(result.valid)
            self.assertEqual(result.intent, IntentType.UNKNOWN)
        
        asyncio.run(test_async())
    
    def test_entity_extraction(self):
        """Test entity extraction"""
        async def test_async():
            # Test file entity
            result = await self.parser.parse("upload my_video.mp4")
            self.assertTrue(any(e.entity_type == EntityType.FILE for e in result.entities))
            
            # Test app entity
            result = await self.parser.parse("open YouTube")
            self.assertTrue(any(e.entity_type == EntityType.APP for e in result.entities))
        
        asyncio.run(test_async())


class TestCommandParserAsync(unittest.IsolatedAsyncioTestCase):
    """Async test cases for Command Parser"""
    
    async def asyncSetUp(self):
        """Async setup"""
        self.config = TestConfig.get_config()
        self.logger = TestConfig.get_logger("CommandParserAsyncTest")
        self.parser = CommandParser(self.config, self.logger)
    
    async def test_parse_multiple_commands(self):
        """Test parsing multiple commands"""
        commands = [
            "upload video",
            "edit photo",
            "search for news",
            "take screenshot",
            "extract text"
        ]
        
        for cmd in commands:
            result = await self.parser.parse(cmd)
            self.assertTrue(result.valid, f"Failed to parse: {cmd}")
            self.assertIsNotNone(result.intent)


if __name__ == '__main__':
    unittest.main()
