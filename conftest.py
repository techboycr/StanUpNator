# conftest.py — pytest configuration
# Ensures the project root is always in sys.path when running tests
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
