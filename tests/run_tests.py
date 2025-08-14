#!/usr/bin/env python3
"""
Test runner script for lrc-mcp.

This script provides convenient ways to run different test suites.
"""

import subprocess
import sys
from pathlib import Path


def run_unit_tests():
    """Run unit tests only."""
    print("Running unit tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit", "-v"])
    return result.returncode


def run_integration_tests():
    """Run integration tests only."""
    print("Running integration tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/integration", "-v"])
    return result.returncode


def run_functional_tests():
    """Run functional tests only."""
    print("Running functional tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/functional", "-v"])
    return result.returncode

def run_all_tests():
    """Run all tests (unit and integration only)."""
    print("Running all tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit", "tests/integration", "-v"])
    return result.returncode


def run_tests_with_coverage():
    """Run all tests with coverage report."""
    print("Running tests with coverage...")
    result = subprocess.run([
        sys.executable, "-m", "pytest", "tests", 
        "--cov=src/lrc_mcp", 
        "--cov-report=html", 
        "--cov-report=term"
    ])
    return result.returncode


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python run_tests.py [unit|integration|functional|all|coverage]")
        return 1
    
    command = sys.argv[1]
    
    if command == "unit":
        return run_unit_tests()
    elif command == "integration":
        return run_integration_tests()
    elif command == "functional":
        return run_functional_tests()
    elif command == "all":
        return run_all_tests()
    elif command == "coverage":
        return run_tests_with_coverage()
    else:
        print(f"Unknown command: {command}")
        print("Usage: python run_tests.py [unit|integration|functional|all|coverage]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
