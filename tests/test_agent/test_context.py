"""Tests for ContextManager."""

import pytest
from src.agent.context import ContextManager
from src.agent.types import ContextPolicy


class TestContextManager:
    """Test suite for ContextManager."""

    def test_initial_state(self):
        """Test ContextManager initialization."""
        cm = ContextManager()
        assert cm.current_step == 0
        assert len(cm.messages) == 0
        assert len(cm.summaries) == 0
        assert cm.summary_index == 0

    def test_add_message(self):
        """Test adding a message to context."""
        cm = ContextManager()
        cm.add_message(
            role="user",
            content="Test message",
            sender="TestAgent",
        )
        assert len(cm.messages) == 1
        assert cm.messages[0].content == "Test message"
        assert cm.messages[0].role == "user"

    def test_add_user_message(self):
        """Test adding a user message with critical importance."""
        cm = ContextManager()
        cm.add_user_message("TestAgent", "Important message")
        assert len(cm.messages) == 1
        assert cm.messages[0].importance == "critical"

    def test_should_compress(self):
        """Test compression trigger logic."""
        policy = ContextPolicy(
            summary_enabled=True,
            summary_interval=6,
        )
        cm = ContextManager(policy=policy)

        # Add some messages
        for i in range(10):
            cm.add_message(role="user", content=f"Message {i}", sender="TestAgent")
            cm.current_step = i + 1

        # Step 6 should trigger compression
        cm.current_step = 6
        assert cm.should_compress() is True

        # Step 7 should not
        cm.current_step = 7
        assert cm.should_compress() is False

    def test_inject_summary(self):
        """Test summary injection."""
        cm = ContextManager()
        cm.add_message(role="user", content="Message 1", sender="TestAgent")
        cm.add_message(role="user", content="Message 2", sender="TestAgent")

        cm.inject_summary("Summary of messages 1 and 2")

        assert len(cm.summaries) == 1
        # Note: summary_index is set BEFORE appending summary message
        # so it equals len(messages) before append = 2
        assert cm.summary_index == 2
        assert cm.messages[-1].role == "summary"
        assert cm.messages[-1].content == "Summary of messages 1 and 2"

    def test_get_unsummarized_messages(self):
        """Test getting unsummarized messages."""
        cm = ContextManager()
        cm.add_message(role="user", content="Message 1", sender="TestAgent")
        cm.add_message(role="user", content="Message 2", sender="TestAgent")

        # All messages are unsummarized
        unsummarized = cm.get_unsummarized_messages()
        assert len(unsummarized) == 2

        # After summary, the summary message itself is unsummarized
        # because summary_index is set before append
        cm.inject_summary("Summary")
        unsummarized = cm.get_unsummarized_messages()
        assert len(unsummarized) == 1  # Only the summary message
        assert unsummarized[0].role == "summary"

    def test_clear(self):
        """Test clearing context."""
        cm = ContextManager()
        cm.add_message(role="user", content="Test", sender="TestAgent")
        cm.inject_summary("Summary")

        cm.clear()

        assert len(cm.messages) == 0
        assert len(cm.summaries) == 0
        assert cm.current_step == 0
        assert cm.summary_index == 0
