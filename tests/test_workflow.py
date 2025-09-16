"""
Tests for workflow execution and state management.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mobo.core.workflow import (
    create_bot_workflow,
    execute_workflow,
    validate_workflow_state,
    format_workflow_summary,
)
from mobo.core.state import (
    BotState,
    format_state_summary,
)


class TestBotState:
    """Test the BotState management."""

    def test_initial_state(self, sample_bot_state):
        """Test initial bot state."""
        assert sample_bot_state["model_calls"] == 0

    def test_format_state_summary(self, sample_bot_state):
        """Test formatting state summary."""
        summary = format_state_summary(sample_bot_state)

        assert isinstance(summary, str)
        assert sample_bot_state["user_message"] in summary
        assert sample_bot_state["user_id"] in summary


class TestWorkflowNodes:
    """Test individual workflow nodes."""


    def test_should_continue(self, sample_bot_state):
        """Test the should_continue conditional edge function."""
        from mobo.core.workflow import should_continue

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
                "final_response": "Hello! How can I help you?",
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
            "model_calls": 2,
        }
        mock_workflow.ainvoke.return_value = mock_final_state

        # Mock aget_state to return empty state
        mock_state = AsyncMock()
        mock_state.values = None
        mock_workflow.aget_state.return_value = mock_state

        final_state = await execute_workflow(
            workflow=mock_workflow,
            user_message="Hello bot!",
            user_id="123456789",
            channel_id="987654321",
        )

        assert "user_message" in final_state
        assert final_state["model_calls"] == 2

    @pytest.mark.asyncio
    async def test_execute_workflow_error(self, test_settings):
        """Test workflow execution with error."""
        # Create a workflow that raises an exception
        mock_workflow = AsyncMock()
        mock_workflow.ainvoke.side_effect = Exception("Workflow error")

        # Mock aget_state to return empty state
        mock_state = AsyncMock()
        mock_state.values = None
        mock_workflow.aget_state.return_value = mock_state

        final_state = await execute_workflow(
            workflow=mock_workflow,
            user_message="Hello bot!",
            user_id="123456789",
            channel_id="987654321",
        )

        assert "user_message" in final_state


class TestWorkflowFormatting:
    """Test workflow summary and formatting."""

    def test_format_workflow_summary(self, sample_bot_state):
        """Test formatting workflow summary."""
        # Add required data for summary
        sample_bot_state.update(
            {
                "personality": "You are helpful",
                "model_calls": 2,
                "final_response": "Hello! How can I help you?",
            }
        )

        summary = format_workflow_summary(sample_bot_state)

        assert isinstance(summary, str)
        assert "Workflow Execution Summary" in summary
        assert "Model Calls: 2" in summary
