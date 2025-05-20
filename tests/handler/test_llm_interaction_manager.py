from unittest.mock import MagicMock, patch, call, AsyncMock

import pytest

# Import pydantic_ai classes needed for type hints or mock spec verification if necessary
# from pydantic_ai import Agent as RealAgent # Example if needed for spec
# from pydantic_ai.models import AIResponse as RealAIResponse # Example if needed for spec
# Import Pydantic BaseModel for output_type_override testing
from pydantic import BaseModel

# Import the class under test
from src.handler.llm_interaction_manager import LLMInteractionManager


# Define a test Pydantic model (prefixed with underscore to avoid collection)
class _SampleOutputModel(BaseModel):
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
    # agent.run_sync.return_value = mock_response # run_sync is no longer used
    agent.run = AsyncMock(return_value=mock_response) # run is now async
    return agent


@pytest.fixture
def llm_manager_instance(mock_agent_instance):
    """
    Provides an instance of LLMInteractionManager *after* __init__ but *before*
    initialize_agent is called. The internal agent is None.
    (Formerly assumed agent was initialized here).
    """
    config = {
        "base_system_prompt": "Test Base Prompt",
        "pydantic_ai_agent_config": {"temperature": 0.5},
    }
    # Patch the Agent class specifically for the duration of this fixture's setup
    # Use new_callable=MagicMock to ensure the mock class itself is truthy
    with patch(
        "src.handler.llm_interaction_manager.Agent", new_callable=MagicMock
    ) as MockAgentClassForFixture:
        # MockAgentClassForFixture.return_value = mock_agent_instance # No longer needed here

        manager = LLMInteractionManager(
            default_model_identifier="test:model", config=config
        )
        # Verify Agent was NOT called during init
        # MockAgentClassForFixture.assert_called_once_with(...) # <-- REMOVED ASSERTION

        # Ensure the instance's agent attribute is None after init
        assert manager.agent is None
        return manager

@pytest.fixture
def llm_manager_no_agent_init():
    """Provides an LLMInteractionManager instance *before* initialize_agent is called."""
    with patch("src.handler.llm_interaction_manager.Agent", new_callable=MagicMock):
        manager = LLMInteractionManager(
            default_model_identifier="test:model",
            config={"base_system_prompt": "Test Base Prompt"},
        )
    assert manager.agent is None
    return manager

@pytest.fixture
def initialized_llm_manager(llm_manager_no_agent_init):
    """
    Provides an LLMInteractionManager instance where initialize_agent
    has been successfully called with mock tools.
    Relies on llm_manager_no_agent_init fixture.
    """
    # Mock the Agent class for the initialize_agent call
    with patch("src.handler.llm_interaction_manager.Agent", new_callable=MagicMock) as MockAgentClass:
        # Create a mock agent instance to be returned by the constructor
        mock_agent_instance_for_init = MagicMock(name="AgentInstanceFromInit")
        # Configure mock response for execute_call tests using this fixture
        mock_response = MagicMock()
        mock_response.output = "Initialized Agent Response"
        mock_response.tool_calls = []
        mock_response.usage = {"prompt":5, "completion":5}
        # mock_agent_instance_for_init.run_sync.return_value = mock_response # run_sync is no longer used
        mock_agent_instance_for_init.run = AsyncMock(return_value=mock_response) # run is now async
        # Set the return value for the Agent class mock
        MockAgentClass.return_value = mock_agent_instance_for_init

        # Call initialize_agent on the manager provided by the other fixture
        mock_tools = [MagicMock(spec=callable)] # Provide some mock tools
        llm_manager_no_agent_init.initialize_agent(tools=mock_tools)

        # Verify initialization happened correctly within the fixture setup
        assert llm_manager_no_agent_init.agent is not None
        MockAgentClass.assert_called_once() # Verify constructor called
        # Store the mock agent instance on the manager if needed for assertions later
        llm_manager_no_agent_init._mock_agent_instance = mock_agent_instance_for_init

    # Yield the manager which now has an initialized agent
    yield llm_manager_no_agent_init


# --- Test Cases ---


# Replace the existing test_llm_manager_init_success function with this:
def test_llm_manager_init_stores_config_defers_agent(mock_agent_instance): # Renamed test
    """Test __init__ stores config and defers agent creation."""
    # Arrange
    config = {
        "base_system_prompt": "Init Prompt",
        "pydantic_ai_agent_config": {"temperature": 0.7}
        }
    model_id = "init:model"
    # Act
    # Patch Agent class import *just for this instantiation* to prevent side effects
    # Use new_callable=MagicMock to ensure the mock class itself is truthy
    with patch("src.handler.llm_interaction_manager.Agent", new_callable=MagicMock) as MockAgentClassForTest:
         manager = LLMInteractionManager(
             default_model_identifier=model_id, config=config
         )

    # Assert
    assert manager.agent is None, "Agent should be None after __init__" # Verify deferred init
    assert manager._model_id == model_id # Verify config stored
    assert manager._base_prompt == "Init Prompt" # Verify config stored
    assert manager._agent_config == {"temperature": 0.7} # Verify config stored
    MockAgentClassForTest.assert_not_called() # Verify Agent constructor was NOT called


# No patch needed here as the code checks for model ID before attempting Agent init
def test_llm_manager_init_no_model_id():
    """Test initialization failure when no model ID is provided."""
    # Act
    manager = LLMInteractionManager(default_model_identifier=None, config={})

    # Assert
    assert manager.agent is None
    # Agent constructor should NOT have been called


@patch("src.handler.llm_interaction_manager.logging.exception") # Patch logging.exception instead
@patch("src.handler.llm_interaction_manager.Agent", new_callable=MagicMock)
def test_initialize_agent_exception_handling(MockAgentClass, mock_log_exception, llm_manager_no_agent_init): # Rename mock param
    """Test exception handling within the initialize_agent method."""
    test_exception = ValueError("Agent init failed inside initialize_agent")
    MockAgentClass.side_effect = test_exception
    with pytest.raises(RuntimeError, match="AgentInitializationError: Agent init failed inside initialize_agent"):
        llm_manager_no_agent_init.initialize_agent(tools=[])
    assert llm_manager_no_agent_init.agent is None
    MockAgentClass.assert_called_once()
    # Assert logging.exception was called within initialize_agent's try/except block
    mock_log_exception.assert_called_once() # Check the new mock
    args, kwargs = mock_log_exception.call_args
    # Check the message passed to logging.exception
    assert "Failed to initialize agent" in args[0]
    assert "Agent init failed inside initialize_agent" in args[0]
    # logging.exception implicitly handles exc_info, no need to check kwargs


# No patch needed here as we are testing the manager's internal state
def test_llm_manager_set_debug_mode(initialized_llm_manager): # Use new fixture
    """Test setting the debug mode."""
    # Arrange: initialized_llm_manager fixture provides a manager
    assert initialized_llm_manager.debug_mode is False

    # Act & Assert
    initialized_llm_manager.set_debug_mode(True)
    assert initialized_llm_manager.debug_mode is True
    initialized_llm_manager.set_debug_mode(False)
    assert initialized_llm_manager.debug_mode is False


# Use the new fixture that provides an initialized agent
@pytest.mark.asyncio
async def test_manager_execute_call_success(initialized_llm_manager): # Use new fixture
    """Test a successful agent call via execute_call."""
    # Arrange
    prompt = "User query"
    history = [{"role": "user", "content": "Previous query"}]
    expected_response_content = "Initialized Agent Response" # Matches fixture setup
    # Access the mock agent instance created within the fixture
    mock_agent_instance = initialized_llm_manager._mock_agent_instance

    # Act
    result = await initialized_llm_manager.execute_call(prompt, history)

    # Assert
    assert result["success"] is True
    assert result["content"] == expected_response_content
    assert result["tool_calls"] == []
    assert result["usage"] == {"prompt": 5, "completion": 5} # Matches fixture setup
    assert result["error"] is None

    # Verify agent call arguments
    mock_agent_instance.run.assert_awaited_once()
    call_args, call_kwargs = mock_agent_instance.run.call_args
    assert call_args[0] == prompt  # Check positional arg
    assert call_kwargs.get("message_history") == history  # Check kwarg
    assert (
        call_kwargs.get("system_prompt") == initialized_llm_manager.base_system_prompt
    )  # Default
    # Tools were passed during initialize_agent, check they are NOT passed again by default
    assert "tools" not in call_kwargs
    assert "output_type" not in call_kwargs


# Use the new fixture
@pytest.mark.asyncio
async def test_manager_execute_call_with_overrides(initialized_llm_manager): # Use new fixture
    """Test execute_call with system prompt, tools, and output type overrides."""
    # Arrange
    prompt = "Query with overrides"
    history = []
    system_override = "Override System Prompt"
    tools_override = [lambda x: x]  # Example tool function

    class OutputModel:
        pass  # Example output type

    output_override = OutputModel

    # Access the mock agent instance created within the fixture
    mock_agent_instance = initialized_llm_manager._mock_agent_instance
    # Configure response for this specific test
    mock_response = MagicMock()
    mock_response.output = "Override response"
    mock_response.tool_calls = [{"name": "tool1"}]
    mock_response.usage = {}
    # mock_agent_instance.run_sync.return_value = mock_response # run_sync is no longer used
    mock_agent_instance.run.return_value = mock_response # run is now async

    # Act
    result = await initialized_llm_manager.execute_call(
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
    mock_agent_instance.run.assert_awaited_once()
    call_args, call_kwargs = mock_agent_instance.run.call_args
    assert call_args[0] == prompt  # Check positional arg
    assert call_kwargs.get("message_history") == history
    assert call_kwargs.get("system_prompt") == system_override  # Override used
    assert call_kwargs.get("tools") == tools_override # tools_override takes precedence
    assert call_kwargs.get("output_type") == output_override


# Use the new fixture
@pytest.mark.asyncio
async def test_manager_execute_call_agent_failure(initialized_llm_manager): # Use new fixture
    """Test execute_call when the agent's run raises an exception."""
    # Arrange
    prompt = "This will fail"
    history = []
    test_exception = ConnectionError("API unavailable")
    # Access the mock agent instance created within the fixture
    mock_agent_instance = initialized_llm_manager._mock_agent_instance
    # Configure the mock agent instance to raise an error
    # mock_agent_instance.run_sync.side_effect = test_exception # run_sync is no longer used
    mock_agent_instance.run.side_effect = test_exception # run is now async

    # Act
    result = await initialized_llm_manager.execute_call(prompt, history)

    # Assert
    assert result["success"] is False
    assert result["content"] is None
    assert result["tool_calls"] is None
    assert result["usage"] is None
    assert "Agent execution failed" in result["error"]
    assert str(test_exception) in result["error"]
    mock_agent_instance.run.assert_awaited_once()


# Use the fixture that provides an UNINITIALIZED agent
@pytest.mark.asyncio
async def test_manager_execute_call_no_agent(llm_manager_no_agent_init): # Use correct fixture
    """Test execute_call when the agent is not initialized."""
    # Arrange: llm_manager_no_agent_init provides a manager with agent=None

    # Act
    result = await llm_manager_no_agent_init.execute_call("Test", [])

    # Assert
    assert result["success"] is False
    assert "AgentNotInitializedError: LLM Agent not initialized." in result["error"]


# Use the new fixture
@pytest.mark.asyncio
async def test_manager_execute_call_structured_output_stringification(
    initialized_llm_manager, # Use new fixture
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
    # Access the mock agent instance created within the fixture
    mock_agent_instance = initialized_llm_manager._mock_agent_instance
    # Configure response for this specific test
    mock_response = MagicMock()
    mock_response.output = structured_output  # Agent returns the model instance
    mock_response.tool_calls = []
    mock_response.usage = {}
    # mock_agent_instance.run_sync.return_value = mock_response # run_sync is no longer used
    mock_agent_instance.run.return_value = mock_response # run is now async

    # Act
    result = await initialized_llm_manager.execute_call("Get structured data", [])

    # Assert
    assert result["success"] is True
    # Verify content is the JSON string representation
    assert result["content"] == '{"value": "structured data"}'
    mock_agent_instance.run.assert_awaited_once()


# Use the new fixture
@pytest.mark.asyncio
async def test_execute_call_with_output_type_override(
    initialized_llm_manager, # Use new fixture
):
    """Test that output_type_override is correctly passed to the agent.run call."""
    # Arrange
    prompt = "Get structured data"
    history = []
    # Access the mock agent instance created within the fixture
    mock_agent_instance = initialized_llm_manager._mock_agent_instance

    # Act
    result = await initialized_llm_manager.execute_call(
        prompt, history, output_type_override=_SampleOutputModel # Use renamed model
    )

    # Assert
    assert result["success"] is True
    # Verify that agent.run was called with output_type=_SampleOutputModel
    mock_agent_instance.run.assert_awaited_once()
    _, kwargs = mock_agent_instance.run.call_args
    assert kwargs.get("output_type") == _SampleOutputModel # Use renamed model


# Use the new fixture
@pytest.mark.asyncio
async def test_execute_call_with_pydantic_model_result(
    initialized_llm_manager, # Use new fixture
):
    """Test that Pydantic model in agent response is included in parsed_content."""
    # Arrange
    # Create an instance of our _SampleOutputModel to simulate agent response
    model_instance = _SampleOutputModel(result="test result", score=0.95) # Use renamed model

    # Access the mock agent instance created within the fixture
    mock_agent_instance = initialized_llm_manager._mock_agent_instance
    # Mock the agent response to return our model instance
    mock_response = MagicMock()
    mock_response.output = model_instance  # This is what pydantic-ai would return
    mock_response.tool_calls = []
    # mock_agent_instance.run_sync.return_value = mock_response # run_sync is no longer used
    mock_agent_instance.run.return_value = mock_response # run is now async

    # Act
    result = await initialized_llm_manager.execute_call("Get structured data", [])

    # Assert
    assert result["success"] is True
    # Check that the result contains the actual model instance
    assert result["parsed_content"] == model_instance
    # Content should still be a string representation
    assert "test result" in result["content"]
    assert "0.95" in result["content"]


# Use the new fixture
@pytest.mark.asyncio
async def test_execute_call_with_validation_error(initialized_llm_manager): # Use new fixture
    """Test error handling when agent.run raises a validation error."""
    # Arrange
    validation_error = ValueError("Validation failed for field 'score': expected float")
    # Access the mock agent instance created within the fixture
    mock_agent_instance = initialized_llm_manager._mock_agent_instance
    # mock_agent_instance.run_sync.side_effect = validation_error # run_sync is no longer used
    mock_agent_instance.run.side_effect = validation_error # run is now async

    # Act
    result = await initialized_llm_manager.execute_call("Get structured data", [])

    # Assert
    assert result["success"] is False
    assert result["error"] is not None
    assert "Validation failed" in result["error"]
    # Error should contain the specific validation error message
    assert str(validation_error) in result["error"]


# Use the new fixture
def test_get_provider_identifier_returns_model_id(
    initialized_llm_manager, # Use new fixture
):
    """Test that get_provider_identifier returns the model identifier when agent is available."""
    # Arrange - initialized_llm_manager has default_model_identifier="test:model" from fixture
    # Access the mock agent instance created within the fixture
    mock_agent_instance = initialized_llm_manager._mock_agent_instance
    assert initialized_llm_manager.agent == mock_agent_instance # Verify agent is set

    # Act
    result = initialized_llm_manager.get_provider_identifier()

    # Assert
    assert result == "test:model"


# Use the fixture that provides an UNINITIALIZED agent
def test_get_provider_identifier_returns_none_when_no_agent(llm_manager_no_agent_init): # Use correct fixture
    """Test that get_provider_identifier returns None when agent is not available."""
    # Arrange: llm_manager_no_agent_init provides manager with agent=None

    # Act
    with patch("logging.warning") as mock_warning:
        result = llm_manager_no_agent_init.get_provider_identifier()

    # Assert
    assert result is None
    mock_warning.assert_called_once()
    assert "Cannot get provider identifier: Agent is not initialized." in mock_warning.call_args[0][0]

# --- Tests for Phase 9.3: Model Override ---

@pytest.mark.asyncio
@patch('src.handler.llm_interaction_manager.Agent')
async def test_execute_call_uses_default_agent_no_override(mock_agent_constructor, initialized_llm_manager):
    """Test execute_call uses the default agent when no override is provided."""
    # Arrange
    manager = initialized_llm_manager
    mock_default_agent = manager.agent # Get the default agent set by the fixture
    assert mock_default_agent is not None, "Fixture should provide initialized default agent"
    # mock_default_agent.run_sync.return_value = MagicMock(output="Default response") # run_sync is no longer used
    mock_default_agent.run.return_value = MagicMock(output="Default response") # run is now async

    prompt = "Test prompt"
    history = []

    # Act
    result = await manager.execute_call(prompt, history, model_override=None) # No override

    # Assert
    assert result["success"] is True
    assert result["content"] == "Default response"
    # Verify default agent was called
    mock_default_agent.run.assert_awaited_once()
    # Verify constructor was NOT called again
    mock_agent_constructor.assert_not_called()

@pytest.mark.asyncio
@patch('src.handler.llm_interaction_manager.Agent')
async def test_execute_call_with_model_override_success(mock_agent_constructor, initialized_llm_manager):
    """Test execute_call successfully uses a temporary agent for a valid override."""
    # Arrange
    manager = initialized_llm_manager
    mock_default_agent = manager.agent
    override_model_id = "openai:gpt-4o-override"
    override_config = {"api_key": "override_key", "temperature": 0.8}
    # Add override config to the manager instance for this test
    manager.config['llm_providers'] = {override_model_id: override_config}

    # Configure the mock constructor to return a new mock agent for the override
    mock_temp_agent = MagicMock()
    # mock_temp_agent.run_sync.return_value = MagicMock(output="Override response") # run_sync is no longer used
    mock_temp_agent.run = AsyncMock(return_value=MagicMock(output="Override response")) # run is now async
    mock_agent_constructor.return_value = mock_temp_agent

    prompt = "Test override prompt"
    history = [{"role": "user", "content": "prev"}]
    # Get tools from default agent to pass to temp agent
    expected_tools = mock_default_agent.tools if hasattr(mock_default_agent, 'tools') else None

    # Act
    result = await manager.execute_call(prompt, history, model_override=override_model_id)

    # Assert
    assert result["success"] is True
    assert result["content"] == "Override response"
    # Verify constructor was called ONCE with override details
    mock_agent_constructor.assert_called_once()
    # Verify temporary agent's run was called
    mock_temp_agent.run.assert_awaited_once()
    # Verify default agent's run was NOT called
    mock_default_agent.run.assert_not_awaited()

@pytest.mark.asyncio
@patch('src.handler.llm_interaction_manager.Agent')
async def test_execute_call_override_config_lookup_fail(mock_agent_constructor, initialized_llm_manager):
    """Test execute_call fails gracefully if config for override model is missing."""
    # Arrange
    manager = initialized_llm_manager
    mock_default_agent = manager.agent
    override_model_id = "unknown:model-v1"
    # Ensure the override model is NOT in the config
    manager.config['llm_providers'] = {"openai:gpt-3.5": {}}

    prompt = "Test unknown override"
    history = []

    # Act
    result = await manager.execute_call(prompt, history, model_override=override_model_id)

    # Assert
    assert result["success"] is False
    assert result["content"] is None
    assert "Configuration not found" in result["error"]
    # Verify constructor was NOT called
    mock_agent_constructor.assert_not_called()
    # Verify default agent was NOT called
    mock_default_agent.run.assert_not_awaited()
    # Check error structure in notes
    assert "error" in result["notes"]
    assert result["notes"]["error"]["type"] == "TASK_FAILURE"
    assert result["notes"]["error"]["reason"] == "configuration_error"

@pytest.mark.asyncio
@patch('src.handler.llm_interaction_manager.Agent')
async def test_execute_call_override_agent_creation_fail(mock_agent_constructor, initialized_llm_manager):
    """Test execute_call fails gracefully if temporary agent creation fails."""
    # Arrange
    manager = initialized_llm_manager
    mock_default_agent = manager.agent
    override_model_id = "bad:init-model"
    override_config = {"some_setting": "value"}
    manager.config['llm_providers'] = {override_model_id: override_config}

    # Configure the mock constructor to RAISE an error for the override
    mock_agent_constructor.side_effect = Exception("Agent init failed badly")

    prompt = "Test bad agent init"
    history = []

    # Act
    result = await manager.execute_call(prompt, history, model_override=override_model_id)

    # Assert
    assert result["success"] is False
    assert result["content"] is None
    assert "Failed to initialize agent" in result["error"]
    # Verify constructor was called
    mock_agent_constructor.assert_called_once()
    # Verify run was NOT called on default agent
    mock_default_agent.run.assert_not_awaited()
    # Check error structure in notes
    assert "error" in result["notes"]
    assert result["notes"]["error"]["type"] == "TASK_FAILURE"
    assert result["notes"]["error"]["reason"] == "llm_error"

# --- Test to ensure tools_override still works with model_override ---
@pytest.mark.asyncio
@patch('src.handler.llm_interaction_manager.Agent')
async def test_execute_call_with_model_and_tool_overrides(mock_agent_constructor, initialized_llm_manager):
    """Test execute_call uses temporary agent AND tool_override when both are provided."""
    # Arrange
    manager = initialized_llm_manager
    mock_default_agent = manager.agent
    override_model_id = "openai:gpt-4o-override"
    override_config = {"api_key": "override_key"}
    manager.config['llm_providers'] = {override_model_id: override_config}

    # Mock temporary agent creation
    mock_temp_agent = MagicMock()
    # mock_temp_agent.run_sync.return_value = MagicMock(output="Override model+tools response") # run_sync is no longer used
    mock_temp_agent.run = AsyncMock(return_value=MagicMock(output="Override model+tools response")) # run is now async
    mock_agent_constructor.return_value = mock_temp_agent

    prompt = "Test combined overrides"
    history = []
    # Define specific tools for this call
    tool_override_list = [lambda x: f"tool_override_called_{x}"]

    # Act
    result = await manager.execute_call(
        prompt,
        history,
        model_override=override_model_id,
        tools_override=tool_override_list # Pass tool override
    )

    # Assert
    assert result["success"] is True
    assert result["content"] == "Override model+tools response"
    # Verify constructor was called ONCE with override details
    mock_agent_constructor.assert_called_once()
    # Verify temporary agent's run was called with the TOOL OVERRIDE list
    mock_temp_agent.run.assert_awaited_once()
    call_args, call_kwargs = mock_temp_agent.run.call_args
    assert call_args[0] == prompt
    assert call_kwargs.get("tools") == tool_override_list
    # Verify default agent's run was NOT called
    mock_default_agent.run.assert_not_awaited()
