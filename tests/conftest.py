"""Pytest configuration and fixtures for Safe-CLI-Agent tests."""

import pytest
import os
import sys

# Add project root to Python path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Fixture to set up mock environment variables."""
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-api-key")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://test.api.com/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")


@pytest.fixture
def sample_message():
    """Fixture providing a sample message dict."""
    return {
        "role": "user",
        "content": "Hello, test message",
        "timestamp": "2024-01-01T00:00:00",
        "type": "text",
    }
