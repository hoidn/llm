# Provider-Agnostic Handler Restructuring Specification
> Ingest the information from this file, implement the Low-Level Tasks, and generate the code that will satisfy the High and Mid-Level Objectives.

## High-Level Objective

- Extract common functionality from PassthroughHandler into a base handler class to improve code organization and maintainability
- Implement a provider-agnostic approach to tool use that works with modern LLM APIs

## Mid-Level Objective

- Create a BaseHandler class containing common functionality shared by all handlers
- Implement provider adapters to handle provider-specific tool call patterns
- Refactor PassthroughHandler to inherit from BaseHandler
- Update existing tests and add new tests to verify correct behavior
- Maintain backward compatibility with existing code

## Implementation Notes
- Follow KISS (Keep It Simple, Stupid) and YAGNI (You Aren't Gonna Need It) principles
- Use duck typing rather than formal interfaces as per project rules
- Add comprehensive docstrings following Google style
- Include type hints for all function and method signatures
- Only extract functionality that is truly common, leaving specialized behavior in PassthroughHandler
- Create clean abstractions between provider-specific details and the general tool use pattern
- Ensure all tests pass after refactoring
- Make the minimal set of changes required to implement the new structure

## Context

### Beginning context
- `handler/__init__.py` - Existing handler package initialization
- `handler/model_provider.py` - Model provider integration
- `handler/passthrough_handler.py` - Existing PassthroughHandler implementation
- `handler/file_access.py` - File access manager
- `tests/handler/__init__.py` - Test package initialization
- `tests/handler/test_passthrough_handler.py` - Existing tests for PassthroughHandler
- `tests/conftest.py` - Common test fixtures

### Ending context  
- `handler/__init__.py` - Updated to expose BaseHandler
- `handler/base_handler.py` - New BaseHandler implementation
- `handler/model_provider.py` - Updated with provider adapter pattern
- `handler/passthrough_handler.py` - Updated to inherit from BaseHandler
- `handler/file_access.py` - Unchanged
- `tests/handler/__init__.py` - Unchanged
- `tests/handler/test_base_handler.py` - New tests for BaseHandler
- `tests/handler/test_passthrough_handler.py` - Updated tests for PassthroughHandler
- `tests/handler/test_handler_integration.py` - New integration tests
- `tests/handler/test_model_provider.py` - New tests for provider adapters
- `tests/conftest.py` - Unchanged

## Low-Level Tasks
> Ordered from start to finish

1. Update model_provider.py to add provider adapter pattern
```aider
UPDATE handler/model_provider.py:
    # Add a base ProviderAdapter interface using duck typing
    ADD class ProviderAdapter:
        """Base adapter interface for model providers.
        
        This interface defines methods that all provider adapters should implement.
        Specific providers will have their own adapter implementations.
        """
        
        With methods:
        - send_message(messages, system_prompt, tools): To send a message to the provider
        - extract_tool_calls(response): To extract tool calls from provider responses in a standardized format
    
    # Convert ClaudeProvider to implement adapter pattern
    UPDATE class ClaudeProvider to inherit from or match ProviderAdapter interface
    
    # Add extract_tool_calls method to ClaudeProvider:
        """Extract tool calls from a response into a standardized format.
        
        Args:
            response: Raw response from the Claude API
            
        Returns:
            Dict with standardized tool call information:
            {
                "content": str,  # Text content from the response
                "tool_calls": [  # List of tool calls (empty if none)
                    {
                        "name": str,      # Tool name
                        "parameters": {},  # Tool parameters
                    },
                    ...
                ],
                "awaiting_tool_response": bool  # Whether the model is waiting for a tool response
            }
        """
        
        Method should:
        - Handle string responses (no tool calls)
        - Handle Claude's structured tool call format
        - Return standardized format regardless of provider-specific details
        - NOT attempt to parse text for tool mentions
        - Set awaiting_tool_response based on whether tools were called
```

2. Create BaseHandler class with common functionality
```aider
CREATE handler/base_handler.py:
    """Base handler providing common functionality for all handlers."""
    from typing import Dict, List, Optional, Any, Callable, Tuple
    
    from handler.model_provider import ProviderAdapter, ClaudeProvider
    from handler.file_access import FileAccessManager
    
    class BaseHandler:
        """Base class for all handlers with common functionality.
        
        Provides shared capabilities for system prompts, tool management,
        conversation state, and LLM interaction.
        """
        
        def __init__(self, task_system, memory_system, model_provider: Optional[ProviderAdapter] = None, config: Optional[Dict[str, Any]] = None):
            """Initialize the base handler.
            
            Args:
                task_system: The Task System instance
                memory_system: The Memory System instance
                model_provider: Provider adapter for model interactions
                config: Optional configuration dictionary
            """
            self.task_system = task_system
            self.memory_system = memory_system
            self.model_provider = model_provider or ClaudeProvider()
            self.file_manager = FileAccessManager()
            
            # Configuration
            self.config = config or {}
            
            # Debug mode
            self.debug_mode = False
            
            # Tool registration
            self.registered_tools = {}  # Tool specifications
            self.tool_executors = {}    # Tool executor functions
            
            # Conversation state
            self.conversation_history = []
            
            # Base system prompt - can be overridden by configuration
            self.base_system_prompt = self.config.get("base_system_prompt", """You are a helpful assistant that responds to user queries.""")
            
        def register_tool(self, tool_spec: Dict[str, Any], executor_func: Callable) -> bool:
            """Register a tool for use by the handler.
            
            Follows a provider-agnostic format that will be adapted to specific
            provider requirements by the provider adapter.
            
            Args:
                tool_spec: Tool specification with name, description, and schema
                executor_func: Function that implements the tool
                
            Returns:
                True if registration successful, False otherwise
            """
            try:
                tool_name = tool_spec.get('name')
                if not tool_name:
                    self.log_debug(f"Error registering tool: Missing tool name")
                    return False
                    
                self.log_debug(f"Registering tool: {tool_name}")
                self.registered_tools[tool_name] = tool_spec
                self.tool_executors[tool_name] = executor_func
                return True
            except Exception as e:
                self.log_debug(f"Error registering tool: {str(e)}")
                return False
        
        def _execute_tool(self, tool_name: str, tool_params: Any) -> Optional[Dict[str, Any]]:
            """Execute a registered tool.
            
            Args:
                tool_name: Name of the tool to execute
                tool_params: Parameters to pass to the tool
                
            Returns:
                Tool execution result if tool exists, None otherwise
            """
            # Check if tool exists
            if tool_name in self.tool_executors:
                try:
                    # Execute tool
                    result = self.tool_executors[tool_name](tool_params)
                    self.log_debug(f"Tool execution result: {result.get('status', 'unknown')}")
                    return result
                except Exception as e:
                    self.log_debug(f"Error executing tool {tool_name}: {str(e)}")
                    return {
                        "status": "error",
                        "content": f"Error executing tool {tool_name}: {str(e)}",
                        "metadata": {"error": str(e)}
                    }
            else:
                self.log_debug(f"Tool {tool_name} not found")
                return None
        
        def _get_relevant_files(self, query: str) -> List[str]:
            """Get relevant files from memory system based on query.
            
            Args:
                query: User's query
                
            Returns:
                List of relevant file paths
            """
            # Use memory system to find relevant files
            context_input = {
                "taskText": query,
                "inheritedContext": "",  # No inherited context for fresh queries
            }
            
            context_result = self.memory_system.get_relevant_context_for(context_input)
            
            # Extract file paths from matches
            relevant_files = [match[0] for match in context_result.matches]
            return relevant_files
        
        def _create_file_context(self, file_paths: List[str]) -> str:
            """Create a context string from file paths.
            
            Args:
                file_paths: List of file paths
                
            Returns:
                Context string with file information
            """
            if not file_paths:
                return ""
            
            file_contexts = []
            for path in file_paths:
                content = self.file_manager.read_file(path)
                if content:
                    # Format the file content with proper markdown
                    file_contexts.append(f"File: {path}\n```\n{content}\n```\n")
                else:
                    file_contexts.append(f"File: {path} (could not be read)")
            
            if file_contexts:
                return "\n".join(file_contexts)
            else:
                return "No file contents available."
        
        def reset_conversation(self) -> None:
            """Reset the conversation state."""
            self.conversation_history = []
        
        def log_debug(self, message: str) -> None:
            """Log debug information if debug mode is enabled.
            
            Args:
                message: Debug message to log
            """
            if self.debug_mode:
                print(f"[DEBUG] {message}")
                
        def set_debug_mode(self, enabled: bool) -> None:
            """Set debug mode.
            
            Args:
                enabled: Whether debug mode should be enabled
            """
            self.debug_mode = enabled
            self.log_debug(f"Debug mode {'enabled' if enabled else 'disabled'}")
            
        def determine_relevant_files(self, query: str, file_metadata: Dict[str, str]) -> List[Tuple[str, str]]:
            """Determine relevant files for a query using LLM.
            
            Args:
                query: The user query or task
                file_metadata: Dictionary mapping file paths to their metadata
                
            Returns:
                List of tuples containing (file_path, relevance_context)
            """
            self.log_debug(f"Determining relevant files for query: '{query}'")
            self.log_debug(f"Number of files to evaluate: {len(file_metadata)}")
            
            file_context = "Available files:\n\n"
            for i, (path, metadata) in enumerate(file_metadata.items(), 1):
                file_context += f"File {i}: {path}\n"
                file_context += f"Metadata: {metadata}\n\n"
            
            system_prompt = """You are a file relevance assistant. Your task is to select files that are relevant to a user's query.
            Examine the metadata of each file and determine which files would be most useful to address the query.
            
            Return ONLY a JSON array of objects with the following format:
            [{"path": "path/to/file1.py", "relevance": "Reason this file is relevant"}, ...]
            
            Include only files that are truly relevant to the query. 
            The "relevance" field should briefly explain why the file is relevant to the query.
            
            Do not include explanations or other text in your response, just the JSON array.
            """
            
            user_message = f"Query: {query}\n\n{file_context}\n\nSelect the files most relevant to this query."
            
            try:
                messages = [{"role": "user", "content": user_message}]
                response = self.model_provider.send_message(
                    messages=messages,
                    system_prompt=system_prompt
                )
                
                self.log_debug(f"LLM response for file relevance: {response[:100]}...")
                
                # Response parsing
                import json
                import re
                
                # Parse JSON response
                if isinstance(response, str):
                    json_pattern = r'\[\s*\{.*?\}\s*\]'
                    match = re.search(json_pattern, response, re.DOTALL)
                    if match:
                        json_str = match.group(0)
                        try:
                            json_str = json_str.replace("'", '"')  # Fix single quotes
                            file_selections = json.loads(json_str)
                                
                            if isinstance(file_selections, list):
                                result = []
                                for item in file_selections:
                                    if isinstance(item, dict) and "path" in item:
                                        path = item["path"]
                                        relevance = item.get("relevance", "Relevant to query")
                                        if path in file_metadata:
                                            result.append((path, relevance))
                                    
                                self.log_debug(f"Selected {len(result)} relevant files")
                                return result
                        except Exception:
                            # Continue to fallback if JSON parsing fails
                            pass
                    
                # Fallback to regex path extraction
                path_pattern = r'(?:"|\')?([\/\w\.-]+\.[\w]+)(?:"|\')?' 
                matches = re.findall(path_pattern, response)
                if matches:
                    valid_paths = [path for path in matches if path in file_metadata]
                    result = [(path, "Relevant to query") for path in valid_paths]
                    self.log_debug(f"Extracted {len(result)} file paths from response")
                    return result
            except Exception as e:
                self.log_debug(f"Error determining relevant files: {str(e)}")
            
            self.log_debug("Using fallback selection strategy")
            # Return top 5 files rather than all files to avoid context overload
            result = [(path, "Included in fallback selection") 
                     for path in list(file_metadata.keys())[:5]]
            return result
```

3. Update handler package initialization to expose BaseHandler
```aider
UPDATE handler/__init__.py:
    """Handler components for LLM interaction."""
    from handler.base_handler import BaseHandler
    from handler.model_provider import ProviderAdapter, ClaudeProvider
```

4. Refactor PassthroughHandler to inherit from BaseHandler and use provider adapter
```aider
UPDATE handler/passthrough_handler.py:
    """Passthrough handler for processing raw text queries."""
    from typing import Dict, Any, Optional, List, Union
    
    from handler.base_handler import BaseHandler
    
    class PassthroughHandler(BaseHandler):
        """Handles raw text queries without AST compilation.
        
        Processes queries in "passthrough mode" by wrapping them in subtasks
        while maintaining conversation state and context management.
        """
        
        def __init__(self, task_system, memory_system, model_provider=None, config=None):
            """Initialize the passthrough handler.
            
            Args:
                task_system: The Task System instance
                memory_system: The Memory System instance
                model_provider: Provider for model interactions
                config: Optional configuration dictionary
            """
            super().__init__(task_system, memory_system, model_provider, config)
            
            # Passthrough-specific attributes
            self.active_subtask_id = None
            
            # Extend base system prompt with passthrough-specific instructions
            passthrough_extension = """
            When referring to code or files, cite the relevant file paths.
            Be precise and helpful, focusing on the user's specific question.
            
            For code editing tasks, you can use the aiderInteractive or aiderAutomatic tools.
            Use aiderInteractive for complex tasks requiring user interaction.
            Use aiderAutomatic for straightforward changes that don't need user confirmation.
            """
            self.base_system_prompt = f"{self.base_system_prompt}\n\n{passthrough_extension}"
        
        def handle_query(self, query: str) -> Dict[str, Any]:
            """Handle a raw text query in passthrough mode.
            
            Creates or continues a subtask for the query, maintaining
            conversation state between queries.
            
            Args:
                query: Raw text query from the user
                
            Returns:
                Task result containing the response
            """
            self.log_debug(f"Processing query: {query}")
            
            # Add user message to conversation history
            self.conversation_history.append({"role": "user", "content": query})
            
            # Get relevant files from memory system based on query
            relevant_files = self._get_relevant_files(query)
            self.log_debug(f"Found relevant files: {relevant_files}")
            
            # Check if query is an Aider command
            is_aider_command = query.startswith("/aider")
            if is_aider_command:
                self.log_debug("Detected Aider command")
            
            if not self.active_subtask_id:
                self.log_debug("Creating new subtask")
                result = self._create_new_subtask(query, relevant_files)
            else:
                self.log_debug(f"Continuing subtask: {self.active_subtask_id}")
                result = self._continue_subtask(query, relevant_files)
                
            # Add assistant response to conversation history
            self.conversation_history.append({"role": "assistant", "content": result["content"]})
            
            self.log_debug(f"Query processing complete. Status: {result.get('status', 'unknown')}")
            return result
        
        def _create_new_subtask(self, query: str, relevant_files: List[str]) -> Dict[str, Any]:
            """Create a new subtask for the initial query.
            
            Args:
                query: Initial query from the user
                relevant_files: List of relevant file paths
                
            Returns:
                Task result from the subtask
            """
            # Create a unique subtask ID
            self.active_subtask_id = f"subtask_{len(self.conversation_history)}"
            
            # Create file context
            file_context = self._create_file_context(relevant_files)
            
            # Send to model and get response
            response_text = self._send_to_model(query, file_context)
            
            return {
                "status": "success",
                "content": response_text,
                "metadata": {
                    "subtask_id": self.active_subtask_id,
                    "relevant_files": relevant_files
                }
            }
        
        def _continue_subtask(self, query: str, relevant_files: List[str]) -> Dict[str, Any]:
            """Continue an existing subtask with a follow-up query.
            
            Args:
                query: Follow-up query from the user
                relevant_files: List of relevant file paths
                
            Returns:
                Task result from the continued subtask
            """
            # Create file context
            file_context = self._create_file_context(relevant_files)
            
            # Send to model and get response
            response_text = self._send_to_model(query, file_context)
            
            return {
                "status": "success",
                "content": response_text,
                "metadata": {
                    "subtask_id": self.active_subtask_id,
                    "relevant_files": relevant_files
                }
            }
            
        def _send_to_model(self, query: str, file_context: str) -> str:
            """Send query to model and get response.
            
            Args:
                query: User's query
                file_context: Context string with file information
                
            Returns:
                Model response text
            """
            self.log_debug(f"Sending query to model: '{query[:50]}...' with {len(self.tool_executors)} registered tools")
            # Format conversation history for provider
            formatted_messages = [
                {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                for msg in self.conversation_history
            ]
            
            # Add file context to system prompt if available
            if file_context:
                system_prompt = f"{self.base_system_prompt}\n\nRelevant files:\n{file_context}"
            else:
                system_prompt = self.base_system_prompt
            
            # Prepare tools if available
            tools = list(self.registered_tools.values()) if self.registered_tools else None
            
            if tools:
                self.log_debug(f"Available tools: {[t['name'] for t in tools]}")
            
            try:
                # Send to model
                response = self.model_provider.send_message(
                    messages=formatted_messages,
                    system_prompt=system_prompt,
                    tools=tools
                )
                
                # Extract tool calls using provider adapter
                extracted = self.model_provider.extract_tool_calls(response)
                content = extracted.get("content", "")
                tool_calls = extracted.get("tool_calls", [])
                
                # Check for tool calls
                if tool_calls:
                    self.log_debug(f"Found {len(tool_calls)} tool calls")
                    for tool_call in tool_calls:
                        tool_name = tool_call.get("name")
                        tool_params = tool_call.get("parameters")
                        
                        self.log_debug(f"Executing tool {tool_name}")
                        tool_result = self._execute_tool(tool_name, tool_params)
                        
                        if tool_result:
                            self.log_debug("Tool was executed, returning tool result")
                            return tool_result.get("content", f"Tool execution completed: {tool_result.get('status', 'unknown')}")
                
                # Check if the model is awaiting a tool response (provider-specific handling)
                if extracted.get("awaiting_tool_response", False):
                    # In a complete implementation, this would handle multi-step tool interactions
                    # For now, just inform the user that tool calls need to be handled
                    return "The model is requesting to use a tool, but multi-step tool interactions are not fully implemented yet."
                
                # Return the regular response if no tool was executed
                if not content and isinstance(response, str):
                    # Fallback if extraction doesn't return content
                    return response
                return content or f"Processed query: {query}"
            except Exception as e:
                # Fallback for tests or when API is unavailable
                print(f"Error sending to model: {str(e)}")
                return f"Processed query: {query}"
            
        def reset_conversation(self):
            """Reset the conversation state."""
            super().reset_conversation()
            self.active_subtask_id = None
            
        def registerDirectTool(self, name: str, func: Any) -> bool:
            """Register a direct tool.
            
            This method is called by the tool registration system to register
            direct tools that can be invoked by the handler.
            
            Args:
                name: Name of the tool
                func: Function to call when the tool is invoked
                
            Returns:
                True if registration successful, False otherwise
            """
            self.log_debug(f"Registering direct tool: {name}")
            
            # Create a wrapper function that adapts to the provider-agnostic tool format
            def tool_wrapper(input_data: Dict[str, Any]) -> Any:
                # If input is a dict with a query key, extract it
                if isinstance(input_data, dict) and "query" in input_data:
                    query = input_data["query"]
                    file_context = input_data.get("file_context")
                    return func(query, file_context)
                # Otherwise pass the input directly
                return func(input_data)
            
            # Store the tool in both dictionaries
            if not hasattr(self, "direct_tools"):
                self.direct_tools = {}
            self.direct_tools[name] = func
            
            # Also register as a regular tool
            self.tool_executors[name] = tool_wrapper
            
            # Create and register the tool specification
            tool_spec = {
                "name": name,
                "description": f"Execute {name} operation directly",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The query or instruction to process"
                        },
                        "file_context": {
                            "type": "array",
                            "description": "Optional list of file paths for context",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["query"]
                }
            }
            self.register_tool(tool_spec, tool_wrapper)
            
            return True
        
        def registerSubtaskTool(self, name: str, func: Any) -> bool:
            """Register a subtask tool.
            
            This method is called by the tool registration system to register
            subtask tools that can be invoked by the handler.
            
            Args:
                name: Name of the tool
                func: Function to call when the tool is invoked
                
            Returns:
                True if registration successful, False otherwise
            """
            self.log_debug(f"Registering subtask tool: {name}")
            
            # Create a wrapper function that adapts to the provider-agnostic tool format
            def tool_wrapper(input_data: Dict[str, Any]) -> Any:
                # If input is a dict with a prompt key, extract it
                if isinstance(input_data, dict) and "prompt" in input_data:
                    prompt = input_data["prompt"]
                    file_context = input_data.get("file_context")
                    return func(prompt, file_context)
                # Otherwise pass the input directly
                return func(input_data)
            
            # Store the tool in both dictionaries
            if not hasattr(self, "subtask_tools"):
                self.subtask_tools = {}
            self.subtask_tools[name] = func
            
            # Also register as a regular tool
            self.tool_executors[name] = tool_wrapper
            
            # Create and register the tool specification
            tool_spec = {
                "name": name,
                "description": f"Execute {name} operation as a subtask",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The prompt or instruction to process"
                        },
                        "file_context": {
                            "type": "array",
                            "description": "Optional list of file paths for context",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["prompt"]
                }
            }
            self.register_tool(tool_spec, tool_wrapper)
            
            return True
```

5. Create tests for BaseHandler
```aider
CREATE tests/handler/test_base_handler.py:
    """Tests for the BaseHandler."""
    import pytest
    from unittest.mock import patch, MagicMock, call
    
    from handler.base_handler import BaseHandler
    
    class TestBaseHandler:
        """Tests for the BaseHandler class."""
    
        def test_init(self, mock_task_system, mock_memory_system):
            """Test BaseHandler initialization."""
            # Create BaseHandler
            handler = BaseHandler(mock_task_system, mock_memory_system)
            
            # Check that attributes were initialized correctly
            assert handler.task_system == mock_task_system
            assert handler.memory_system == mock_memory_system
            assert handler.conversation_history == []
            assert isinstance(handler.base_system_prompt, str)
            assert handler.debug_mode is False
            assert handler.registered_tools == {}
            assert handler.tool_executors == {}
            
        def test_register_tool(self, mock_task_system, mock_memory_system):
            """Test tool registration."""
            # Create BaseHandler
            handler = BaseHandler(mock_task_system, mock_memory_system)
            
            # Create a mock tool
            tool_spec = {
                "name": "test_tool",
                "description": "Test tool",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "param": {"type": "string", "description": "Test parameter"}
                    }
                }
            }
            tool_function = MagicMock(return_value={"status": "success", "content": "Tool executed"})
            
            # Register the tool
            result = handler.register_tool(tool_spec, tool_function)
            
            # Check result and registration
            assert result is True
            assert "test_tool" in handler.registered_tools
            assert handler.registered_tools["test_tool"] == tool_spec
            assert handler.tool_executors["test_tool"] == tool_function
            
        def test_execute_tool(self, mock_task_system, mock_memory_system):
            """Test tool execution."""
            # Create BaseHandler
            handler = BaseHandler(mock_task_system, mock_memory_system)
            
            # Create a mock tool
            tool_spec = {
                "name": "test_tool",
                "description": "Test tool",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "param": {"type": "string", "description": "Test parameter"}
                    }
                }
            }
            tool_function = MagicMock(return_value={"status": "success", "content": "Tool executed"})
            
            # Register the tool
            handler.register_tool(tool_spec, tool_function)
            
            # Execute the tool
            result = handler._execute_tool("test_tool", {"param": "value"})
            
            # Check result
            assert result["status"] == "success"
            assert result["content"] == "Tool executed"
            
            # Check that tool function was called with correct params
            tool_function.assert_called_once_with({"param": "value"})
            
        def test_create_file_context(self, mock_task_system, mock_memory_system):
            """Test file context creation."""
            # Mock file manager
            with patch('handler.file_access.FileAccessManager') as mock_file_manager_class:
                # Setup file manager mock
                mock_file_manager = MagicMock()
                mock_file_manager.read_file.side_effect = lambda path: f"Content of {path}" if path == "file1.py" else None
                mock_file_manager_class.return_value = mock_file_manager
                
                # Create handler
                handler = BaseHandler(mock_task_system, mock_memory_system)
                handler.file_manager = mock_file_manager
                
                # Get file context
                file_context = handler._create_file_context(["file1.py", "file2.py"])
                
                # Check file context
                assert "file1.py" in file_context
                assert "Content of file1.py" in file_context
                assert "file2.py" in file_context
                assert "could not be read" in file_context
                
        def test_get_relevant_files(self, mock_task_system, mock_memory_system):
            """Test getting relevant files from memory system."""
            # Setup memory system mock
            mock_memory_system.get_relevant_context_for.return_value = MagicMock(
                matches=[("file1.py", "metadata1"), ("file2.py", "metadata2")]
            )
            
            # Create handler
            handler = BaseHandler(mock_task_system, mock_memory_system)
            
            # Get relevant files
            relevant_files = handler._get_relevant_files("test query")
            
            # Check relevant files
            assert len(relevant_files) == 2
            assert "file1.py" in relevant_files
            assert "file2.py" in relevant_files
            
            # Check that memory system was called with correct input
            mock_memory_system.get_relevant_context_for.assert_called_once_with({
                "taskText": "test query",
                "inheritedContext": ""
            })
    
        def test_reset_conversation(self, mock_task_system, mock_memory_system):
            """Test conversation reset."""
            # Create handler
            handler = BaseHandler(mock_task_system, mock_memory_system)
            
            # Add some conversation history
            handler.conversation_history = [
                {"role": "user", "content": "test query"},
                {"role": "assistant", "content": "test response"}
            ]
            
            # Reset conversation
            handler.reset_conversation()
            
            # Check that conversation history was reset
            assert handler.conversation_history == []
            
        def test_set_debug_mode(self, mock_task_system, mock_memory_system, capsys):
            """Test setting debug mode."""
            # Create handler
            handler = BaseHandler(mock_task_system, mock_memory_system)
            
            # Initially debug mode should be off
            assert handler.debug_mode is False
            
            # Set debug mode on
            handler.set_debug_mode(True)
            
            # Check that debug mode was set
            assert handler.debug_mode is True
            
            # Log something and check output
            handler.log_debug("Debug message")
            captured = capsys.readouterr()
            assert "[DEBUG]" in captured.out
            assert "Debug message" in captured.out
            
            # Set debug mode off
            handler.set_debug_mode(False)
            
            # Check that debug mode was set
            assert handler.debug_mode is False
            
            # Log something and check no output
            handler.log_debug("Debug message")
            captured = capsys.readouterr()
            assert captured.out == ""
```

6. Update tests for PassthroughHandler
```aider
UPDATE tests/handler/test_passthrough_handler.py:
    """Add test_send_to_model_with_tool_extraction test and update existing tests."""
    
    # Add import for BaseHandler
    from handler.base_handler import BaseHandler
    
    # Update test_init to check inheritance
    def test_init(self, mock_task_system, mock_memory_system):
        """Test PassthroughHandler initialization."""
        # Mock the ProviderAdapter and FileAccessManager to avoid API key requirement in tests
        with patch('handler.model_provider.ClaudeProvider') as mock_provider_class, \
             patch('handler.file_access.FileAccessManager') as mock_file_manager_class:
            mock_provider = MagicMock()
            mock_provider_class.return_value = mock_provider
            
            mock_file_manager = MagicMock()
            mock_file_manager_class.return_value = mock_file_manager
            
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            
            # Check inheritance
            assert isinstance(handler, BaseHandler)
            
            # Check PassthroughHandler specific attributes
            assert handler.task_system == mock_task_system
            assert handler.memory_system == mock_memory_system
            assert handler.active_subtask_id is None
            assert handler.conversation_history == []
            assert handler.model_provider == mock_provider
            assert handler.file_manager == mock_file_manager
    
    # Add test for tool extraction with provider adapter
    def test_send_to_model_with_tool_extraction(self, mock_task_system, mock_memory_system):
        """Test _send_to_model with tool extraction using provider adapter."""
        # Mock the provider and FileAccessManager
        with patch('handler.model_provider.ClaudeProvider') as mock_provider_class, \
             patch('handler.file_access.FileAccessManager'):
            # Create mock provider
            mock_provider = MagicMock()
            mock_provider.send_message.return_value = "Response with tool call"
            
            # Mock tool extraction with standardized format
            mock_provider.extract_tool_calls.return_value = {
                "content": "Using tool",
                "tool_calls": [
                    {"name": "test_tool", "parameters": {"param": "value"}}
                ],
                "awaiting_tool_response": False
            }
            
            mock_provider_class.return_value = mock_provider
            
            # Create handler
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            handler.model_provider = mock_provider
            
            # Mock tool execution
            with patch.object(handler, '_execute_tool') as mock_execute_tool:
                mock_execute_tool.return_value = {
                    "status": "success",
                    "content": "Tool executed"
                }
                
                # Send to model
                result = handler._send_to_model("test query", "file context")
                
                # Check that tool was executed
                mock_execute_tool.assert_called_once_with("test_tool", {"param": "value"})
                
                # Check result
                assert result == "Tool executed"
                
                # Verify provider was called correctly
                mock_provider.send_message.assert_called_once()
                mock_provider.extract_tool_calls.assert_called_once_with("Response with tool call")
                
    # Test handling of awaiting_tool_response
    def test_send_to_model_awaiting_tool_response(self, mock_task_system, mock_memory_system):
        """Test handling of awaiting_tool_response flag."""
        # Mock the provider
        with patch('handler.model_provider.ClaudeProvider') as mock_provider_class, \
             patch('handler.file_access.FileAccessManager'):
            # Create mock provider
            mock_provider = MagicMock()
            mock_provider.send_message.return_value = "Response requesting tool"
            
            # Mock tool extraction with awaiting_tool_response=True
            mock_provider.extract_tool_calls.return_value = {
                "content": "I need to use a tool",
                "tool_calls": [],  # No specific tool calls yet
                "awaiting_tool_response": True  # Indicates model is waiting for tool response
            }
            
            mock_provider_class.return_value = mock_provider
            
            # Create handler
            handler = PassthroughHandler(mock_task_system, mock_memory_system)
            handler.model_provider = mock_provider
            
            # Send to model
            result = handler._send_to_model("test query", "file context")
            
            # Check that the response indicates waiting for tool response
            assert "The model is requesting to use a tool" in result
            assert "multi-step tool interactions" in result
            
            # Verify provider methods were called
            mock_provider.send_message.assert_called_once()
            mock_provider.extract_tool_calls.assert_called_once()
```

7. Create integration tests for handler system
```aider
CREATE tests/handler/test_handler_integration.py:
    """Integration tests for handler system."""
    import pytest
    from unittest.mock import patch, MagicMock, call
    
    from handler.base_handler import BaseHandler
    from handler.passthrough_handler import PassthroughHandler
    from handler.model_provider import ProviderAdapter
    
    class TestHandlerIntegration:
        """Integration tests for handler system."""
    
        def test_inheritance_and_overrides(self, mock_task_system, mock_memory_system):
            """Test that inheritance works correctly with method overrides."""
            # Create handlers with mocked dependencies
            with patch('handler.model_provider.ClaudeProvider'), \
                 patch('handler.file_access.FileAccessManager'):
                base_handler = BaseHandler(mock_task_system, mock_memory_system)
                passthrough_handler = PassthroughHandler(mock_task_system, mock_memory_system)
                
                # Check base functionality is available in both
                assert hasattr(base_handler, 'register_tool')
                assert hasattr(passthrough_handler, 'register_tool')
                
                # Check that PassthroughHandler has specialized functionality
                assert not hasattr(base_handler, 'handle_query')
                assert hasattr(passthrough_handler, 'handle_query')
                
                # Check that both handlers have reset_conversation but implementations differ
                assert hasattr(base_handler, 'reset_conversation')
                assert hasattr(passthrough_handler, 'reset_conversation')
                
                # Reset conversation in both handlers
                base_handler.conversation_history = [{"role": "user", "content": "test"}]
                passthrough_handler.conversation_history = [{"role": "user", "content": "test"}]
                passthrough_handler.active_subtask_id = "test-id"
                
                base_handler.reset_conversation()
                passthrough_handler.reset_conversation()
                
                # Check that PassthroughHandler's implementation resets additional state
                assert passthrough_handler.active_subtask_id is None
        
        def test_tool_registration_and_execution(self, mock_task_system, mock_memory_system):
            """Test that tool registration and execution work across inheritance."""
            # Create a tool specification and executor
            tool_spec = {
                "name": "test_tool",
                "description": "Test tool",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "param": {"type": "string", "description": "Test parameter"}
                    }
                }
            }
            tool_executor = MagicMock(return_value={"status": "success", "content": "Tool executed"})
            
            # Create handler with mocked dependencies
            with patch('handler.model_provider.ClaudeProvider') as mock_provider_class, \
                 patch('handler.file_access.FileAccessManager'):
                # Mock provider to return a tool invocation response
                mock_provider = MagicMock()
                mock_provider.send_message.return_value = "Response with tool call"
                mock_provider.extract_tool_calls.return_value = {
                    "content": "Using tool",
                    "tool_calls": [
                        {"name": "test_tool", "parameters": {"param": "value"}}
                    ],
                    "awaiting_tool_response": False
                }
                mock_provider_class.return_value = mock_provider
                
                # Create handler and register tool
                handler = PassthroughHandler(mock_task_system, mock_memory_system)
                handler.model_provider = mock_provider
                handler.register_tool(tool_spec, tool_executor)
                
                # Handle a query that will trigger tool invocation
                result = handler.handle_query("Use test_tool")
                
                # Check that tool was executed
                tool_executor.assert_called_once_with({"param": "value"})
                
                # Check that result contains tool execution result
                assert result["content"] == "Tool executed"
        
        def test_direct_vs_subtask_tool_registration(self, mock_task_system, mock_memory_system):
            """Test the difference between direct and subtask tool registration."""
            with patch('handler.model_provider.ClaudeProvider'), \
                 patch('handler.file_access.FileAccessManager'):
                # Create handler
                handler = PassthroughHandler(mock_task_system, mock_memory_system)
                
                # Test registerDirectTool
                direct_func = MagicMock(return_value={"status": "success", "content": "Direct tool executed"})
                direct_result = handler.registerDirectTool("directTool", direct_func)
                
                # Test registerSubtaskTool
                subtask_func = MagicMock(return_value={"status": "success", "content": "Subtask tool executed"})
                subtask_result = handler.registerSubtaskTool("subtaskTool", subtask_func)
                
                # Check registration results
                assert direct_result is True
                assert subtask_result is True
                
                # Check tool registrations
                assert "directTool" in handler.registered_tools
                assert "subtaskTool" in handler.registered_tools
                assert "directTool" in handler.tool_executors
                assert "subtaskTool" in handler.tool_executors
                
                # Check that direct tools have correct wrappers
                direct_wrapper = handler.tool_executors["directTool"]
                subtask_wrapper = handler.tool_executors["subtaskTool"]
                
                # Test direct tool wrapper with query
                direct_wrapper({"query": "test query", "file_context": ["file.py"]})
                direct_func.assert_called_with("test query", ["file.py"])
                
                # Test subtask tool wrapper with prompt
                subtask_wrapper({"prompt": "test prompt", "file_context": ["file.py"]})
                subtask_func.assert_called_with("test prompt", ["file.py"])
```

8. Create tests for provider adapters
```aider
CREATE tests/handler/test_model_provider.py:
    """Tests for the provider adapters."""
    import pytest
    from unittest.mock import patch, MagicMock
    
    from handler.model_provider import ProviderAdapter, ClaudeProvider
    
    class TestProviderAdapter:
        """Tests for the ProviderAdapter."""
        
        def test_provider_adapter_interface(self):
            """Test that ProviderAdapter defines the expected interface."""
            assert hasattr(ProviderAdapter, 'send_message')
            assert hasattr(ProviderAdapter, 'extract_tool_calls')
    
    class TestClaudeProvider:
        """Tests for the ClaudeProvider class."""
        
        def test_extract_tool_calls_official_format(self):
            """Test extracting tool calls in official format."""
            provider = ClaudeProvider(api_key="test_key")
            
            # Test with official Anthropic tool call format
            response = {
                "content": [{"type": "text", "text": "I'll use the test_tool"}],
                "tool_calls": [
                    {"name": "test_tool", "input": {"param": "value"}}
                ]
            }
            
            result = provider.extract_tool_calls(response)
            
            assert "content" in result
            assert result["content"] == "I'll use the test_tool"
            assert "tool_calls" in result
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["name"] == "test_tool"
            assert result["tool_calls"][0]["parameters"] == {"param": "value"}
            assert "awaiting_tool_response" in result
            assert result["awaiting_tool_response"] is False
        
        def test_extract_tool_calls_string_response(self):
            """Test extracting tool calls from string response."""
            provider = ClaudeProvider(api_key="test_key")
            
            # Test with string response
            response = "I'll use the test_tool with parameter value"
            
            result = provider.extract_tool_calls(response)
            
            assert "content" in result
            assert result["content"] == response
            assert "tool_calls" in result
            assert len(result["tool_calls"]) == 0  # No tool calls in string response
            assert "awaiting_tool_response" in result
            assert result["awaiting_tool_response"] is False
        
        def test_extract_tool_calls_awaiting_tool_response(self):
            """Test detecting when model is awaiting tool response."""
            provider = ClaudeProvider(api_key="test_key")
            
            # Test with response that indicates awaiting tool response
            response = {
                "content": [{"type": "text", "text": "I need to use a tool"}],
                "stop_reason": "tool_use"  # Anthropic's indicator for awaiting tool response
            }
            
            result = provider.extract_tool_calls(response)
            
            assert "content" in result
            assert result["content"] == "I need to use a tool"
            assert "tool_calls" in result
            assert len(result["tool_calls"]) == 0  # No specific tool calls yet
            assert "awaiting_tool_response" in result
            assert result["awaiting_tool_response"] is True  # Should detect awaiting response
        
        def test_extract_tool_calls_non_standard_format(self):
            """Test extracting tool calls from non-standard format."""
            provider = ClaudeProvider(api_key="test_key")
            
            # Test with a format from a different provider
            response = {
                "text": "I'll use a tool",
                "function_calls": [
                    {"function": "test_tool", "arguments": {"param": "value"}}
                ]
            }
            
            # Should still extract and standardize
            result = provider.extract_tool_calls(response)
            
            assert "content" in result
            assert result["content"] == "I'll use a tool"
            assert "tool_calls" in result
            # Should be empty since we're not explicitly handling this format
            assert len(result["tool_calls"]) == 0
            assert "awaiting_tool_response" in result
            assert result["awaiting_tool_response"] is False
        
        def test_send_message_with_tools(self):
            """Test sending a message with tools."""
            with patch('anthropic.Anthropic') as mock_anthropic:
                mock_client = MagicMock()
                mock_anthropic.return_value = mock_client
                mock_response = MagicMock()
                mock_response.content = [{"type": "text", "text": "Response text"}]
                mock_client.messages.create.return_value = mock_response
                
                provider = ClaudeProvider(api_key="test_key")
                provider.client = mock_client
                
                messages = [{"role": "user", "content": "Test message"}]
                system_prompt = "You are a helpful assistant"
                tools = [
                    {
                        "name": "test_tool",
                        "description": "Test tool",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "param": {"type": "string", "description": "Test parameter"}
                            }
                        }
                    }
                ]
                
                response = provider.send_message(
                    messages=messages,
                    system_prompt=system_prompt,
                    tools=tools
                )
                
                # Check response
                assert response == "Response text"
                
                # Check that client was called with correct parameters
                mock_client.messages.create.assert_called_once()
                call_args = mock_client.messages.create.call_args[1]
                
                assert call_args["model"] == provider.model
                assert call_args["system"] == system_prompt
                assert call_args["messages"] == messages
                assert "tools" in call_args
                assert call_args["tools"] == tools
```
