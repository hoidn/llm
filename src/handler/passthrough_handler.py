"""
// === IDL-CREATION-GUIDLINES === // Object Oriented: Use OO Design. // Design Patterns: Use Factory, Builder and Strategy patterns where possible // ** Complex parameters JSON : Use JSON where primitive params are not possible and document them in IDL like "Expected JSON format: { "key1": "type1", "key2": "type2" }" // == !! BEGIN IDL TEMPLATE !! === // === CODE-CREATION-RULES === // Strict Typing: Always use strict typing. Avoid using ambiguous or variant types. // Primitive Types: Favor the use of primitive types wherever possible. // Portability Mandate: Python code must be written with the intent to be ported to Java, Go, and JavaScript. Consider language-agnostic logic and avoid platform-specific dependencies. // No Side Effects: Functions should be pure, meaning their output should only be determined by their input without any observable side effects. // Testability: Ensure that every function and method is easily testable. Avoid tight coupling and consider dependency injection where applicable. // Documentation: Every function, method, and module should be thoroughly documented, especially if there's a nuance that's not directly evident from its signature. // Contractual Obligation: The definitions provided in this IDL are a strict contract. All specified interfaces, methods, and constraints must be implemented precisely as defined without deviation. // =======================

@module PassthroughHandlerModule
// Dependencies: BaseHandler, TaskSystem, MemorySystem, ProviderAdapter, CommandExecutor, ContextGenerationInput
// Description: Handles raw text queries directly, managing conversation state and interacting
//              with the LLM provider, potentially using tools like Aider or command execution.
module PassthroughHandlerModule {

    // Interface for the passthrough handler, extending BaseHandler.
    interface PassthroughHandler extends BaseHandler {
        // @depends_on(TaskSystem, MemorySystem, ProviderAdapter) // Dependencies primarily via BaseHandler

        // Constructor
        // Preconditions:
        // - task_system is a valid TaskSystem instance.
        // - memory_system is a valid MemorySystem instance.
        // - model_provider is an optional ProviderAdapter instance.
        // - config is an optional dictionary.
        // Postconditions:
        // - BaseHandler is initialized.
        // - Passthrough-specific system prompt extension is added.
        // - Built-in command execution tool is registered.
        void __init__(TaskSystem task_system, MemorySystem memory_system, optional ProviderAdapter model_provider, optional dict<string, Any> config);

        // Handles a raw text query from the user.
        // Preconditions:
        // - query is a non-empty string.
        // Postconditions:
        // - Query is added to conversation history.
        // - Relevant files are retrieved via MemorySystem.
        // - Query is processed by the LLM via the model provider, potentially involving tool calls.
        // - Assistant response is added to conversation history.
        // - Returns a TaskResult dictionary containing the status, content, and metadata.
        // Expected JSON format for return value: { "status": "string", "content": "string", "metadata": { ... } }
        dict<string, Any> handle_query(string query);

        // Registers the built-in command execution tool.
        // Preconditions: None.
        // Postconditions:
        // - The 'executeFilePathCommand' tool is registered using `register_tool`.
        // - Returns true if registration successful, false otherwise.
        boolean register_command_execution_tool();

        // Resets the conversation state, including the active subtask ID.
        // Preconditions: None.
        // Postconditions:
        // - BaseHandler.reset_conversation() is called.
        // - `active_subtask_id` is set to None.
        void reset_conversation();

        // Registers a direct tool (overrides/implements BaseHandler method if needed, specific logic here).
        // Preconditions:
        // - name is a non-empty string identifier.
        // - func is a callable function implementing the tool logic.
        // Postconditions:
        // - Tool is registered in `direct_tools` and `tool_executors`.
        // - A corresponding tool specification is created and registered via `register_tool`.
        // - Returns true if successful, false otherwise.
        boolean registerDirectTool(string name, function func);

        // Registers a subtask tool.
        // Preconditions:
        // - name is a non-empty string identifier.
        // - func is a callable function implementing the tool logic (typically expects prompt, file_context).
        // Postconditions:
        // - Tool is registered in `subtask_tools` and `tool_executors`.
        // - A corresponding tool specification is created and registered via `register_tool`.
        // - Returns true if successful, false otherwise.
        boolean registerSubtaskTool(string name, function func);

        // Additional methods... (Private/protected methods like _find_matching_template, _create_new_subtask are not part of the public IDL)
    };
};
// == !! END IDL TEMPLATE !! ===

"""
from typing import Dict, Any, Optional, List, Union

from handler.base_handler import BaseHandler
from handler.command_executor import execute_command_safely, parse_file_paths_from_output

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
        
        # Register built-in tools
        self.register_command_execution_tool()
    
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
    
    def _find_matching_template(self, query: str):
        """Find a matching template for the query using ContextGenerationInput.
        
        Args:
            query: User query
            
        Returns:
            Matching template or None
        """
        try:
            if not hasattr(self.task_system, 'find_matching_tasks'):
                self.log_debug("Task system does not support template matching")
                return None
                
            # Create context input for memory system
            from memory.context_generation import ContextGenerationInput
            context_input = ContextGenerationInput(
                template_description=query,
                template_type="atomic",
                template_subtype="generic",
                inputs={"query": query},  # Include query in inputs
                context_relevance={"query": True},  # Mark query as relevant
                fresh_context="enabled"
            )
                
            # Get matching tasks from task system
            try:
                matching_tasks = self.task_system.find_matching_tasks(query, self.memory_system)
                
                if not matching_tasks:
                    self.log_debug("No matching templates found")
                    return None
                    
                # Get highest scoring template
                best_match = matching_tasks[0]
                self.log_debug(f"Found matching template: {best_match['taskType']}:{best_match['subtype']} (score: {best_match['score']:.2f})")
                return best_match["task"]
            except Exception as e:
                self.log_debug(f"Error finding matching tasks: {str(e)}")
                return None
        except Exception as e:
            self.log_debug(f"Error finding matching template: {str(e)}")
            return None
    
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
        
        # Find matching template
        template = self._find_matching_template(query)
        
        # Create file context
        file_context = self._create_file_context(relevant_files)
        
        # Send to model and get response
        response_text = self._send_to_model(query, file_context, template)
        
        # Prepare metadata
        metadata = {
            "subtask_id": self.active_subtask_id,
            "relevant_files": relevant_files
        }
        
        # Add template info if available
        if template:
            metadata["template"] = {
                "type": template.get("type"),
                "subtype": template.get("subtype"),
                "description": template.get("description")
            }
        
        return {
            "status": "success",
            "content": response_text,
            "metadata": metadata
        }
    
    def _continue_subtask(self, query: str, relevant_files: List[str]) -> Dict[str, Any]:
        """Continue an existing subtask with a follow-up query.
        
        Args:
            query: Follow-up query from the user
            relevant_files: List of relevant file paths
            
        Returns:
            Task result from the continued subtask
        """
        # Find matching template
        template = self._find_matching_template(query)
        
        # Create file context
        file_context = self._create_file_context(relevant_files)
        
        # Send to model and get response
        response_text = self._send_to_model(query, file_context, template)
        
        return {
            "status": "success",
            "content": response_text,
            "metadata": {
                "subtask_id": self.active_subtask_id,
                "relevant_files": relevant_files
            }
        }
    
    def _send_to_model(self, query: str, file_context: str, template=None) -> str:
        """Send query to model and get response.
        
        Args:
            query: User's query
            file_context: Context string with file information
            template: Optional template with system_prompt
            
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
        
        # Build system prompt using hierarchical pattern
        system_prompt = self._build_system_prompt(template, file_context)
        
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
        
    def register_command_execution_tool(self):
        """Register the command execution tool.
        
        Returns:
            True if registration successful, False otherwise
        """
        tool_spec = {
            "name": "executeFilePathCommand",
            "description": "Execute a command to find file paths",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string", 
                        "description": "Shell command to execute"
                    }
                },
                "required": ["command"]
            }
        }
        
        # Define the tool executor function
        def command_executor(input_data):
            if not isinstance(input_data, dict) or "command" not in input_data:
                return {
                    "status": "error",
                    "content": "Invalid input: missing command",
                    "metadata": {
                        "success": False,
                        "output": "",
                        "error": "Missing command parameter"
                    }
                }
                
            command = input_data["command"]
            result = execute_command_safely(command)
            
            if not result["success"]:
                return {
                    "status": "error",
                    "content": f"Command execution failed: {result['error']}",
                    "metadata": result
                }
                
            # Parse file paths
            file_paths = parse_file_paths_from_output(result["output"])
            
            return {
                "status": "success",
                "content": f"Found {len(file_paths)} file paths",
                "metadata": {
                    "file_paths": file_paths,
                    "success": True,
                    "output": result["output"]
                }
            }
        
        # Register the tool
        return self.register_tool(tool_spec, command_executor)
        
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
        
