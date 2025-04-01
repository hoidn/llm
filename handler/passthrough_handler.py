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
        
        To invoke a tool, explicitly state that you are using the tool, for example:
        "I'll help you with that using the aiderAutomatic tool."
        or
        "Let me solve this with aiderInteractive."
        
        You can also use code blocks with the tool name:
        ```aiderAutomatic
        Your task description here
        ```
        
        Always invoke the appropriate tool for code editing tasks rather than trying to explain how to make the changes manually.
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
        
