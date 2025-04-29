import pytest
from unittest.mock import patch, MagicMock, ANY
import logging

# Mock pydantic-ai classes before importing the manager
# This prevents ImportError if pydantic-ai isn't installed in the test environment
# and allows us to control the mock behavior.
MockAgentClass = MagicMock()
MockAIResponse = MagicMock()

# Patch the pydantic_ai imports *before* importing the class under test
patcher_agent = patch('src.handler.llm_interaction_manager.Agent', MockAgentClass)
patcher_response = patch('src.handler.llm_interaction_manager.AIResponse', MockAIResponse)

patcher_agent.start()
patcher_response.start()

# Now import the class under test
from src.handler.llm_interaction_manager import LLMInteractionManager

# Stop patching after import if desired, or keep it running for all tests
# patcher_agent.stop()
# patcher_response.stop()


# --- Fixtures ---

@pytest.fixture
def mock_agent_instance():
    """Provides a mocked instance of the pydantic-ai Agent."""
    agent = MagicMock()
    # Configure the mock response object
    mock_response = MagicMock()
    mock_response.output = "Default agent response"
    mock_response.tool_calls = []
    mock_response.usage = {"prompt_tokens": 10, "completion_tokens": 20}
    agent.run_sync.return_value = mock_response
    return agent

@pytest.fixture
def llm_manager_instance(mock_agent_instance):
    """Provides an instance of LLMInteractionManager with a mocked agent."""
    # Reset the class mock to ensure clean state for instance creation mock
    MockAgentClass.reset_mock()
    MockAgentClass.return_value = mock_agent_instance # Make Agent() return our mock instance

    config = {
        "base_system_prompt": "Test Base Prompt",
        "pydantic_ai_agent_config": {"temperature": 0.5} # Example extra config
    }
    manager = LLMInteractionManager(default_model_identifier="test:model", config=config)
    # Ensure the manager uses the provided mock instance
    # This might be redundant if the constructor patch works, but good for clarity
    manager.agent = mock_agent_instance
    return manager

# --- Test Cases ---

def test_llm_manager_init_success(mock_agent_instance):
    """Test successful initialization of the manager and agent."""
    MockAgentClass.reset_mock()
    MockAgentClass.return_value = mock_agent_instance
    config = {"base_system_prompt": "Init Prompt"}
    manager = LLMInteractionManager(default_model_identifier="init:model", config=config)

    assert manager.agent is not None
    assert manager.agent == mock_agent_instance
    assert manager.default_model_identifier == "init:model"
    assert manager.base_system_prompt == "Init Prompt"
    # Check if Agent was called with expected args during init
    MockAgentClass.assert_called_once_with(
        model="init:model",
        system_prompt="Init Prompt"
        # Add checks for other config args if passed during init
    )

def test_llm_manager_init_no_model_id():
    """Test initialization failure when no model ID is provided."""
    MockAgentClass.reset_mock()
    manager = LLMInteractionManager(default_model_identifier=None, config={})
    assert manager.agent is None
    MockAgentClass.assert_not_called() # Agent shouldn't be instantiated

@patch('logging.error') # Mock logging to check error messages
def test_llm_manager_init_agent_exception(mock_log_error):
    """Test initialization failure when Agent instantiation raises an error."""
    MockAgentClass.reset_mock()
    test_exception = ValueError("Agent init failed")
    MockAgentClass.side_effect = test_exception # Make Agent() raise an error

    manager = LLMInteractionManager(default_model_identifier="fail:model", config={})

    assert manager.agent is None
    MockAgentClass.assert_called_once()
    mock_log_error.assert_called_with(
        f"Failed to initialize pydantic-ai Agent: {test_exception}", exc_info=True
    )

def test_llm_manager_set_debug_mode(llm_manager_instance):
    """Test setting the debug mode."""
    assert llm_manager_instance.debug_mode is False
    llm_manager_instance.set_debug_mode(True)
    assert llm_manager_instance.debug_mode is True
    llm_manager_instance.set_debug_mode(False)
    assert llm_manager_instance.debug_mode is False

def test_manager_execute_call_success(llm_manager_instance, mock_agent_instance):
    """Test a successful agent call via execute_call."""
    # Arrange
    prompt = "User query"
    history = [{"role": "user", "content": "Previous query"}]
    expected_response_content = "Agent response content"
    mock_response = MagicMock()
    mock_response.output = expected_response_content
    mock_response.tool_calls = []
    mock_response.usage = {"prompt": 1, "completion": 2}
    mock_agent_instance.run_sync.return_value = mock_response

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
    expected_messages = history + [{"role": "user", "content": prompt}]
    assert call_kwargs['messages'] == expected_messages
    assert call_kwargs['system_prompt'] == llm_manager_instance.base_system_prompt # Default
    assert 'tools' not in call_kwargs
    assert 'output_type' not in call_kwargs

def test_manager_execute_call_with_overrides(llm_manager_instance, mock_agent_instance):
    """Test execute_call with system prompt, tools, and output type overrides."""
    # Arrange
    prompt = "Query with overrides"
    history = []
    system_override = "Override System Prompt"
    tools_override = [lambda x: x] # Example tool function
    class OutputModel: pass # Example output type
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
        output_type_override=output_override
    )

    # Assert
    assert result["success"] is True
    assert result["content"] == "Override response"
    assert result["tool_calls"] == [{"name": "tool1"}]

    # Verify agent call arguments
    mock_agent_instance.run_sync.assert_called_once()
    call_args, call_kwargs = mock_agent_instance.run_sync.call_args
    assert call_kwargs['messages'][-1]['content'] == prompt
    assert call_kwargs['system_prompt'] == system_override # Override used
    assert call_kwargs['tools'] == tools_override
    assert call_kwargs['output_type'] == output_override

def test_manager_execute_call_agent_failure(llm_manager_instance, mock_agent_instance):
    """Test execute_call when the agent's run_sync raises an exception."""
    # Arrange
    prompt = "This will fail"
    history = []
    test_exception = ConnectionError("API unavailable")
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

def test_manager_execute_call_no_agent(llm_manager_instance):
    """Test execute_call when the agent is not initialized."""
    # Arrange
    llm_manager_instance.agent = None # Simulate agent initialization failure

    # Act
    result = llm_manager_instance.execute_call("Test", [])

    # Assert
    assert result["success"] is False
    assert "LLM Agent not initialized" in result["error"]

def test_manager_execute_call_structured_output_stringification(llm_manager_instance, mock_agent_instance):
    """Test that structured output (like Pydantic models) is stringified."""
    # Arrange
    class MyOutputModel:
        def __init__(self, value):
            self.value = value
        def model_dump_json(self): # Simulate Pydantic method
            import json
            return json.dumps({"value": self.value})

    structured_output = MyOutputModel("structured data")
    mock_response = MagicMock()
    mock_response.output = structured_output # Agent returns the model instance
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

# Stop patchers if they were started globally
patcher_agent.stop()
patcher_response.stop()
