#!/usr/bin/env python3
"""
JARVIS Test Runner
Runs all tests for the JARVIS AI Assistant
"""

import unittest
import asyncio
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import test modules
from tests.test_brain_engine import TestBrainEngine, TestBrainEngineAsync
from tests.test_input_processor import TestInputProcessor, TestInputProcessorAsync
from tests.test_command_parser import TestCommandParser, TestCommandParserAsync


def discover_tests() -> List:
    """Discover all test modules"""
    test_loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()
    
    # Add all test modules
    test_modules = [
        TestBrainEngine,
        TestBrainEngineAsync,
        TestInputProcessor,
        TestInputProcessorAsync,
        TestCommandParser,
        TestCommandParserAsync
    ]
    
    for module in test_modules:
        test_suite.addTests(test_loader.loadTestsFromTestCase(module))
    
    return test_suite


def run_all_tests() -> Dict[str, Any]:
    """Run all tests and return results"""
    test_suite = discover_tests()
    
    # Create a test runner
    stream = sys.stdout
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    
    # Run tests
    result = runner.run(test_suite)
    
    # Return results
    return {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "success": result.wasSuccessful(),
        "details": {
            "failures": result.failures,
            "errors": result.errors
        }
    }


def run_specific_test(test_class_name: str):
    """Run a specific test class"""
    test_loader = unittest.TestLoader()
    
    # Find the test class
    test_classes = {
        "TestBrainEngine": TestBrainEngine,
        "TestBrainEngineAsync": TestBrainEngineAsync,
        "TestInputProcessor": TestInputProcessor,
        "TestInputProcessorAsync": TestInputProcessorAsync,
        "TestCommandParser": TestCommandParser,
        "TestCommandParserAsync": TestCommandParserAsync
    }
    
    if test_class_name not in test_classes:
        print(f"Test class '{test_class_name}' not found")
        print(f"Available test classes: {', '.join(test_classes.keys())}")
        return None
    
    test_class = test_classes[test_class_name]
    test_suite = test_loader.loadTestsFromTestCase(test_class)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "success": result.wasSuccessful()
    }


def run_test_method(test_class_name: str, method_name: str):
    """Run a specific test method"""
    test_loader = unittest.TestLoader()
    
    # Find the test class
    test_classes = {
        "TestBrainEngine": TestBrainEngine,
        "TestBrainEngineAsync": TestBrainEngineAsync,
        "TestInputProcessor": TestInputProcessor,
        "TestInputProcessorAsync": TestInputProcessorAsync,
        "TestCommandParser": TestCommandParser,
        "TestCommandParserAsync": TestCommandParserAsync
    }
    
    if test_class_name not in test_classes:
        print(f"Test class '{test_class_name}' not found")
        return None
    
    test_class = test_classes[test_class_name]
    
    # Create test suite with specific method
    test_suite = unittest.TestSuite()
    test_case = test_class(method_name)
    test_suite.addTest(test_case)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "success": result.wasSuccessful()
    }


def list_all_tests():
    """List all available tests"""
    test_classes = {
        "TestBrainEngine": TestBrainEngine,
        "TestBrainEngineAsync": TestBrainEngineAsync,
        "TestInputProcessor": TestInputProcessor,
        "TestInputProcessorAsync": TestInputProcessorAsync,
        "TestCommandParser": TestCommandParser,
        "TestCommandParserAsync": TestCommandParserAsync
    }
    
    print("\nAvailable Test Classes:")
    for name in test_classes.keys():
        print(f"  - {name}")
    
    print("\nTo run all tests:")
    print("  python tests/run_tests.py")
    
    print("\nTo run a specific test class:")
    print("  python tests/run_tests.py TestBrainEngine")
    
    print("\nTo run a specific test method:")
    print("  python tests/run_tests.py TestBrainEngine test_initialization")


def print_results(results: Dict[str, Any]):
    """Print test results"""
    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    print(f"Tests run: {results['tests_run']}")
    print(f"Failures: {results['failures']}")
    print(f"Errors: {results['errors']}")
    print(f"Success: {'YES' if results['success'] else 'NO'}")
    print("=" * 60)
    
    if not results['success']:
        if results['failures'] > 0:
            print("\nFailures:")
            for test, traceback in results['details']['failures']:
                print(f"  - {test}")
        
        if results['errors'] > 0:
            print("\nErrors:")
            for test, traceback in results['details']['errors']:
                print(f"  - {test}")


def main():
    """Main entry point"""
    print("\n" + "=" * 60)
    print("JARVIS Test Runner")
    print("=" * 60 + "\n")
    
    # Check command line arguments
    if len(sys.argv) == 1:
        # Run all tests
        print("Running all tests...\n")
        results = run_all_tests()
        print_results(results)
        
        # Exit with appropriate code
        sys.exit(0 if results['success'] else 1)
    
    elif len(sys.argv) == 2:
        # Run specific test class or list tests
        arg = sys.argv[1]
        
        if arg.lower() in ['help', '--help', '-h']:
            list_all_tests()
        elif arg.lower() in ['list', '--list', '-l']:
            list_all_tests()
        else:
            # Run specific test class
            results = run_specific_test(arg)
            if results:
                print_results(results)
                sys.exit(0 if results['success'] else 1)
            else:
                sys.exit(1)
    
    elif len(sys.argv) == 3:
        # Run specific test method
        test_class = sys.argv[1]
        method_name = sys.argv[2]
        
        results = run_test_method(test_class, method_name)
        if results:
            print_results(results)
            sys.exit(0 if results['success'] else 1)
        else:
            sys.exit(1)
    
    else:
        print("Usage:")
        print("  python tests/run_tests.py              # Run all tests")
        print("  python tests/run_tests.py TestClass    # Run specific test class")
        print("  python tests/run_tests.py TestClass method  # Run specific test method")
        print("  python tests/run_tests.py --list       # List all tests")
        print("  python tests/run_tests.py --help       # Show this help")
        sys.exit(1)


if __name__ == "__main__":
    main()
