"""
Tests for workflow execution and state management.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from bot.core.workflow import (
    create_bot_workflow,
    execute_workflow,
    validate_workflow_state,
    format_workflow_summary,
)
from bot.core.state import (
    BotState,
    create_initial_state,
    log_workflow_step,
    add_debug_info,
    format_state_summary,
)
from bot.core.response_extractor import response_extractor_node


class TestBotState:
    """Test the BotState management."""

    def test_create_initial_state(self):
        """Test creating initial bot state."""
        state = create_initial_state(
            user_message="Hello bot!", user_id="123456789", channel_id="987654321"
        )

        assert state["user_message"] == "Hello bot!"
        assert state["user_id"] == "123456789"
        assert state["channel_id"] == "987654321"
        assert state["workflow_path"] == []
        assert state["execution_time"] == 0.0
        assert state["model_calls"] == 0
        assert isinstance(state["debug_info"], dict)

    def test_log_workflow_step(self, sample_bot_state):
        """Test logging workflow steps."""
        initial_path = sample_bot_state["workflow_path"].copy()

        log_workflow_step(sample_bot_state, "test_step")

        assert len(sample_bot_state["workflow_path"]) == len(initial_path) + 1
        assert sample_bot_state["workflow_path"][-1] == "test_step"

    def test_add_debug_info(self, sample_bot_state):
        """Test adding debug information."""
        add_debug_info(sample_bot_state, "test_key", "test_value")

        assert "test_key" in sample_bot_state["debug_info"]
        assert sample_bot_state["debug_info"]["test_key"] == "test_value"

    def test_format_state_summary(self, sample_bot_state):
        """Test formatting state summary."""
        summary = format_state_summary(sample_bot_state)

        assert isinstance(summary, str)
        assert sample_bot_state["user_message"] in summary
        assert sample_bot_state["user_id"] in summary


class TestWorkflowNodes:
    """Test individual workflow nodes."""

    @pytest.mark.asyncio
    async def test_response_extractor_node(self, sample_bot_state):
        """Test the response extractor node."""
        # Add messages to state (simulating chatbot node output)
        from langchain_core.messages import HumanMessage

        mock_message = MagicMock()
        mock_message.content = "This is a test response"
        sample_bot_state["messages"] = [mock_message]

        result_state = await response_extractor_node(sample_bot_state)

        assert "final_response" in result_state
        assert result_state["final_response"] == "This is a test response"

    def test_should_continue(self, sample_bot_state):
        """Test the should_continue conditional edge function."""
        from bot.core.workflow import should_continue

        # Test case: no messages - should go to message generator
        result = should_continue(sample_bot_state)
        assert result == "message_generator"

        # Test case: message with no tool calls - should go to message generator
        mock_message = MagicMock()
        mock_message.tool_calls = []
        sample_bot_state["messages"] = [mock_message]
        result = should_continue(sample_bot_state)
        assert result == "message_generator"

        # Test case: message with tool calls - should go to tools
        mock_message.tool_calls = [{"name": "test_tool", "args": {}}]
        result = should_continue(sample_bot_state)
        assert result == "tools"


class TestWorkflowValidation:
    """Test workflow state validation."""

    def test_validate_workflow_state_valid(self, sample_bot_state):
        """Test validating a valid workflow state."""
        # Ensure all required fields are present
        sample_bot_state.update(
            {
                "personality": "You are helpful",
                "final_response": "Test response",
                "workflow_path": ["chatbot", "message_generator", "response_extractor"],
            }
        )

        errors = validate_workflow_state(sample_bot_state)
        assert len(errors) == 0

    def test_validate_workflow_state_missing_fields(self, sample_bot_state):
        """Test validation with missing required fields."""
        # Remove required field
        del sample_bot_state["user_message"]

        errors = validate_workflow_state(sample_bot_state)
        assert len(errors) > 0
        assert any("Missing required field" in error for error in errors)

    def test_validate_workflow_state_response_too_long(self, sample_bot_state):
        """Test validation with response too long."""
        sample_bot_state.update(
            {
                "personality": "You are helpful",
                "final_response": "x" * 2001,  # Over 2000 character limit
            }
        )

        errors = validate_workflow_state(sample_bot_state)
        assert any("Response too long" in error for error in errors)


class TestWorkflowExecution:
    """Test complete workflow execution."""

    @pytest.mark.asyncio
    async def test_execute_workflow_success(self, test_settings):
        """Test successful workflow execution."""
        # Create a minimal mock workflow
        mock_workflow = AsyncMock()
        mock_final_state = {
            "user_message": "Hello bot!",
            "user_id": "123456789",
            "channel_id": "987654321",
            "final_response": "Hello! How can I help you?",
            "workflow_path": ["chatbot", "message_generator", "response_extractor"],
            "execution_time": 1.5,
            "model_calls": 2,
        }
        mock_workflow.ainvoke.return_value = mock_final_state

        final_state = await execute_workflow(
            workflow=mock_workflow,
            user_message="Hello bot!",
            user_id="123456789",
            channel_id="987654321",
        )

        assert final_state["final_response"] == "Hello! How can I help you?"
        assert final_state["execution_time"] > 0
        assert len(final_state["workflow_path"]) > 0

    @pytest.mark.asyncio
    async def test_execute_workflow_error(self, test_settings):
        """Test workflow execution with error."""
        # Create a workflow that raises an exception
        mock_workflow = AsyncMock()
        mock_workflow.ainvoke.side_effect = Exception("Workflow error")

        final_state = await execute_workflow(
            workflow=mock_workflow,
            user_message="Hello bot!",
            user_id="123456789",
            channel_id="987654321",
        )

        assert final_state["final_response"] is None
        assert final_state["execution_time"] > 0
        assert "workflow_error" in final_state["debug_info"]


class TestWorkflowFormatting:
    """Test workflow summary and formatting."""

    def test_format_workflow_summary(self, sample_bot_state):
        """Test formatting workflow summary."""
        # Add required data for summary
        sample_bot_state.update(
            {
                "personality": "You are helpful",
                "final_response": "Test response",
                "workflow_path": ["chatbot", "message_generator", "response_extractor"],
                "execution_time": 2.5,
                "model_calls": 2,
            }
        )

        summary = format_workflow_summary(sample_bot_state)

        assert isinstance(summary, str)
        assert "Workflow Execution Summary" in summary
        assert "Total Execution Time: 2.50s" in summary
        assert "Model Calls: 2" in summary
        assert "message_generator → response_extractor" in summary
