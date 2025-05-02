import pytest
from unittest.mock import patch, MagicMock, ANY
import logging

# Import the class under test
from src.handler.llm_interaction_manager import LLMInteractionManager

# Import pydantic_ai classes needed for type hints or mock spec verification if necessary
# from pydantic_ai import Agent as RealAgent # Example if needed for spec
# from pydantic_ai.models import AIResponse as RealAIResponse # Example if needed for spec

# Import Pydantic BaseModel for output_type_override testing
from pydantic import BaseModel


# Define a test Pydantic model for structured output testing
class TestOutputModel(BaseModel):
    result: str
    score: float


# --- Fixtures ---


@pytest.fixture
def mock_agent_instance():
    """Provides a mocked instance of the pydantic-ai Agent."""
    agent = MagicMock()  # spec=RealAgent could be added if RealAgent is imported
    # Configure the mock response object
    mock_response = MagicMock()  # spec=RealAIResponse could be added
    mock_response.output = "Default agent response"
    mock_response.tool_calls = []
    mock_response.usage = {"prompt_tokens": 10, "completion_tokens": 20}
    agent.run_sync.return_value = mock_response
    return agent


@pytest.fixture
def llm_manager_instance(mock_agent_instance):
    """Provides an instance of LLMInteractionManager with a mocked agent class during its init."""
    config = {
        "base_system_prompt": "Test Base Prompt",
        "pydantic_ai_agent_config": {"temperature": 0.5},
    }
    # Patch the Agent class specifically for the duration of this fixture's setup
    # Use new_callable=MagicMock to ensure the mock class itself is truthy
    with patch(
        "src.handler.llm_interaction_manager.Agent", new_callable=MagicMock
    ) as MockAgentClassForFixture:
        MockAgentClassForFixture.return_value = (
            mock_agent_instance  # Configure the mock instance returned
        )
        manager = LLMInteractionManager(
            default_model_identifier="test:model", config=config
        )
        # Verify Agent was called during init
        MockAgentClassForFixture.assert_called_once_with(
            model="test:model",
            system_prompt="Test Base Prompt",
            temperature=0.5,  # Check extra config was passed
        )
        # Store the class mock if tests need to assert calls on the class itself
        # manager._MockAgentClass = MockAgentClassForFixture # Optional
        # Ensure the instance uses the mock agent instance we configured
        # This might be redundant if MockAgentClassForFixture.return_value works as expected,
        # but explicitly setting it ensures the correct mock instance is used by execute_call tests.
        manager.agent = mock_agent_instance
        return manager


# --- Test Cases ---


def test_llm_manager_init_success(mock_agent_instance):
    """Test successful initialization of the manager and agent."""
    config = {"base_system_prompt": "Init Prompt"}
    # Patch Agent specifically for this test's instantiation
    # Use new_callable=MagicMock to ensure the mock class itself is truthy
    with patch(
        "src.handler.llm_interaction_manager.Agent", new_callable=MagicMock
    ) as MockAgentClassForTest:
        MockAgentClassForTest.return_value = mock_agent_instance
        manager = LLMInteractionManager(
            default_model_identifier="init:model", config=config
        )

        assert manager.agent is not None, "Agent should be initialized"
        assert manager.agent == mock_agent_instance, "Agent should be the mock instance"
        assert manager.default_model_identifier == "init:model"
        assert manager.base_system_prompt == "Init Prompt"
        MockAgentClassForTest.assert_called_once_with(
            model="init:model",
            system_prompt="Init Prompt",
            # No extra config passed here
        )


# No patch needed here as the code checks for model ID before attempting Agent init
def test_llm_manager_init_no_model_id():
    """Test initialization failure when no model ID is provided."""
    # Act
    manager = LLMInteractionManager(default_model_identifier=None, config={})

    # Assert
    assert manager.agent is None
    # Agent constructor should NOT have been called


@patch("src.handler.llm_interaction_manager.logger.error")
def test_llm_manager_init_agent_exception(mock_log_error):
    """Test initialization failure when Agent instantiation raises an error."""
    test_exception = ValueError("Agent init failed")
    # Patch Agent specifically for this test, setting side_effect
    # Use new_callable=MagicMock to ensure the mock class itself is truthy
    with patch(
        "src.handler.llm_interaction_manager.Agent", new_callable=MagicMock
    ) as MockAgentClassForTest:
        MockAgentClassForTest.side_effect = (
            test_exception  # Make Agent() raise an error
        )
        manager = LLMInteractionManager(
            default_model_identifier="fail:model", config={}
        )

        assert manager.agent is None, "Agent should be None after failed initialization"
        MockAgentClassForTest.assert_called_once()  # Verify instantiation was attempted

        # Check log call more robustly
        mock_log_error.assert_called_once()  # Verify it was called
        args, kwargs = mock_log_error.call_args
        # Check the main message content
        expected_msg_part = f"Failed to initialize pydantic-ai Agent for model 'fail:model': {test_exception}"
        assert expected_msg_part in args[0]
        # Check exc_info was passed
        assert kwargs.get("exc_info") is True


# No patch needed here as we are testing the manager's internal state
def test_llm_manager_set_debug_mode(llm_manager_instance):
    """Test setting the debug mode."""
    # Arrange: llm_manager_instance fixture already provides a manager
    assert llm_manager_instance.debug_mode is False

    # Act & Assert
    llm_manager_instance.set_debug_mode(True)
    assert llm_manager_instance.debug_mode is True
    llm_manager_instance.set_debug_mode(False)
    assert llm_manager_instance.debug_mode is False


# No patch needed here as the fixture provides a manager with a *mocked* agent instance
def test_manager_execute_call_success(llm_manager_instance, mock_agent_instance):
    """Test a successful agent call via execute_call."""
    # Arrange
    prompt = "User query"
    history = [{"role": "user", "content": "Previous query"}]
    expected_response_content = "Agent response content"
    # Configure the mock agent's response (already done in mock_agent_instance fixture,
    # but can be overridden here if needed for specific test)
    mock_response = MagicMock()
    mock_response.output = expected_response_content
    mock_response.tool_calls = []
    mock_response.usage = {"prompt": 1, "completion": 2}
    mock_agent_instance.run_sync.return_value = (
        mock_response  # Ensure mock agent returns this
    )

    # Act
    result = llm_manager_instance.execute_call(prompt, history)

    # Assert
    assert result["success"] is True
    assert result["content"] == expected_response_content
    assert result["tool_calls"] == []
    assert result["usage"] == {"prompt": 1, "completion": 2}
    assert result["error"] is None

    # Verify agent call arguments
    mock_agent_instance.run_sync.assert_called_once()
    call_args, call_kwargs = mock_agent_instance.run_sync.call_args
    assert call_args[0] == prompt  # Check positional arg
    assert call_kwargs.get("message_history") == history  # Check kwarg
    assert (
        call_kwargs.get("system_prompt") == llm_manager_instance.base_system_prompt
    )  # Default
    assert "tools" not in call_kwargs
    assert "output_type" not in call_kwargs


# No patch needed here
def test_manager_execute_call_with_overrides(llm_manager_instance, mock_agent_instance):
    """Test execute_call with system prompt, tools, and output type overrides."""
    # Arrange
    prompt = "Query with overrides"
    history = []
    system_override = "Override System Prompt"
    tools_override = [lambda x: x]  # Example tool function

    class OutputModel:
        pass  # Example output type

    output_override = OutputModel

    mock_response = MagicMock()
    mock_response.output = "Override response"
    mock_response.tool_calls = [{"name": "tool1"}]
    mock_response.usage = {}
    mock_agent_instance.run_sync.return_value = mock_response

    # Act
    result = llm_manager_instance.execute_call(
        prompt,
        history,
        system_prompt_override=system_override,
        tools_override=tools_override,
        output_type_override=output_override,
    )

    # Assert
    assert result["success"] is True
    assert result["content"] == "Override response"
    assert result["tool_calls"] == [{"name": "tool1"}]

    # Verify agent call arguments
    mock_agent_instance.run_sync.assert_called_once()
    call_args, call_kwargs = mock_agent_instance.run_sync.call_args
    assert call_args[0] == prompt  # Check positional arg
    assert call_kwargs.get("message_history") == history
    assert call_kwargs.get("system_prompt") == system_override  # Override used
    assert call_kwargs.get("tools") == tools_override
    assert call_kwargs.get("output_type") == output_override


# No patch needed here
def test_manager_execute_call_agent_failure(llm_manager_instance, mock_agent_instance):
    """Test execute_call when the agent's run_sync raises an exception."""
    # Arrange
    prompt = "This will fail"
    history = []
    test_exception = ConnectionError("API unavailable")
    # Configure the mock agent instance to raise an error
    mock_agent_instance.run_sync.side_effect = test_exception

    # Act
    result = llm_manager_instance.execute_call(prompt, history)

    # Assert
    assert result["success"] is False
    assert result["content"] is None
    assert result["tool_calls"] is None
    assert result["usage"] is None
    assert "Agent execution failed" in result["error"]
    assert str(test_exception) in result["error"]
    mock_agent_instance.run_sync.assert_called_once()


# No patch needed here
def test_manager_execute_call_no_agent(llm_manager_instance):
    """Test execute_call when the agent is not initialized."""
    # Arrange
    # Force the agent to None *after* initialization via fixture
    llm_manager_instance.agent = None

    # Act
    result = llm_manager_instance.execute_call("Test", [])

    # Assert
    assert result["success"] is False
    assert "LLM Agent not initialized" in result["error"]


# No patch needed here
def test_manager_execute_call_structured_output_stringification(
    llm_manager_instance, mock_agent_instance
):
    """Test that structured output (like Pydantic models) is stringified."""

    # Arrange
    class MyOutputModel:
        def __init__(self, value):
            self.value = value

        def model_dump_json(self):  # Simulate Pydantic method
            import json

            return json.dumps({"value": self.value})

    structured_output = MyOutputModel("structured data")
    mock_response = MagicMock()
    mock_response.output = structured_output  # Agent returns the model instance
    mock_response.tool_calls = []
    mock_response.usage = {}
    mock_agent_instance.run_sync.return_value = mock_response

    # Act
    result = llm_manager_instance.execute_call("Get structured data", [])

    # Assert
    assert result["success"] is True
    # Verify content is the JSON string representation
    assert result["content"] == '{"value": "structured data"}'
    mock_agent_instance.run_sync.assert_called_once()


def test_execute_call_with_output_type_override(
    llm_manager_instance, mock_agent_instance
):
    """Test that output_type_override is correctly passed to the agent.run_sync call."""
    # Arrange
    prompt = "Get structured data"
    history = []

    # Act
    result = llm_manager_instance.execute_call(
        prompt, history, output_type_override=TestOutputModel
    )

    # Assert
    assert result["success"] is True
    # Verify that agent.run_sync was called with output_type=TestOutputModel
    mock_agent_instance.run_sync.assert_called_once()
    _, kwargs = mock_agent_instance.run_sync.call_args
    assert kwargs.get("output_type") == TestOutputModel


def test_execute_call_with_pydantic_model_result(
    llm_manager_instance, mock_agent_instance
):
    """Test that Pydantic model in agent response is included in parsed_content."""
    # Arrange
    # Create an instance of our TestOutputModel to simulate agent response
    model_instance = TestOutputModel(result="test result", score=0.95)

    # Mock the agent response to return our model instance
    mock_response = MagicMock()
    mock_response.output = model_instance  # This is what pydantic-ai would return
    mock_response.tool_calls = []
    mock_agent_instance.run_sync.return_value = mock_response

    # Act
    result = llm_manager_instance.execute_call("Get structured data", [])

    # Assert
    assert result["success"] is True
    # Check that the result contains the actual model instance
    assert result["parsed_content"] == model_instance
    # Content should still be a string representation
    assert "test result" in result["content"]
    assert "0.95" in result["content"]


def test_execute_call_with_validation_error(llm_manager_instance, mock_agent_instance):
    """Test error handling when agent.run_sync raises a validation error."""
    # Arrange
    validation_error = ValueError("Validation failed for field 'score': expected float")
    mock_agent_instance.run_sync.side_effect = validation_error

    # Act
    result = llm_manager_instance.execute_call("Get structured data", [])

    # Assert
    assert result["success"] is False
    assert result["error"] is not None
    assert "Validation failed" in result["error"]
    # Error should contain the specific validation error message
    assert str(validation_error) in result["error"]


def test_get_provider_identifier_returns_model_id(
    llm_manager_instance, mock_agent_instance
):
    """Test that get_provider_identifier returns the model identifier when agent is available."""
    # Arrange - llm_manager_instance has default_model_identifier="test:model" from fixture

    # Act
    result = llm_manager_instance.get_provider_identifier()

    # Assert
    assert result == "test:model"


def test_get_provider_identifier_returns_none_when_no_agent(llm_manager_instance):
    """Test that get_provider_identifier returns None when agent is not available."""
    # Arrange
    llm_manager_instance.agent = None

    # Act
    with patch("logging.warning") as mock_warning:
        result = llm_manager_instance.get_provider_identifier()

    # Assert
    assert result is None
    mock_warning.assert_called_once()
    assert "Cannot get provider identifier" in mock_warning.call_args[0][0]
