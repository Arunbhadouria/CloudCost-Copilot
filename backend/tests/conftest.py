"""Pytest configuration and global fixtures for backend tests."""
import os
import pytest

# Ensure all tests run in mock LLM mode with no external network calls
os.environ["LLM_MODE"] = "mock"
from app.config import settings
settings.LLM_MODE = "mock"

