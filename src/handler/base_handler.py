"""Base handler providing common functionality for all handlers."""
from typing import Dict, List, Optional, Any, Callable, Tuple, Union

from handler.model_provider import ProviderAdapter, ClaudeProvider
from handler.file_access import FileAccessManager
from handler.command_executor import execute_command_safely, parse_file_paths_from_output
from memory.context_generation import ContextGenerationInput
from system.prompt_registry import registry as prompt_registry

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
    
    def execute_file_path_command(self, command: str) -> List[str]:
        """Execute command and return file paths.
        
        Args:
            command: Shell command to execute
            
        Returns:
            List of file paths returned by the command
        """
        self.log_debug(f"Executing file path command: {command}")
        
        # Execute command safely
        result = execute_command_safely(command)
        
        if not result["success"]:
            self.log_debug(f"Command execution failed: {result['error']}")
            return []
            
        # Parse file paths from output
        file_paths = parse_file_paths_from_output(result["output"])
        self.log_debug(f"Command returned {len(file_paths)} file paths")
        
        return file_paths
    
    def _get_relevant_files(self, query: str, inputs: Optional[Dict[str, Any]] = None,
                          context_relevance: Optional[Dict[str, bool]] = None) -> List[str]:
        """Get relevant files from memory system based on query and context.
        
        Args:
            query: User's query
            inputs: Optional dictionary of additional inputs
            context_relevance: Optional mapping of input names to relevance
            
        Returns:
            List of relevant file paths
        """
        # Create context generation input
        context_input = ContextGenerationInput(
            template_description=query,
            inputs=inputs or {},
            context_relevance=context_relevance
        )
        
        # Use memory system to find relevant files
        context_result = self.memory_system.get_relevant_context_for(context_input)
        
        # Extract file paths from matches (maintain backward compatibility)
        if hasattr(context_result, 'matches'):
            # Object-style result
            relevant_files = [match[0] for match in context_result.matches]
        else:
            # Dict-style result
            relevant_files = [match[0] for match in context_result.get('matches', [])]
        
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
        
    def _build_system_prompt(self, template=None, file_context=None) -> str:
        """Build the complete system prompt by combining base, template, and file context.
        
        Implements the Hierarchical System Prompt Pattern by combining:
        1. Base system prompt (universal behaviors)
        2. Template-specific system prompt (task-specific instructions)
        3. File context (relevant files for the current query)
        
        Args:
            template: Optional template with system_prompt
            file_context: Optional file context string
            
        Returns:
            Complete system prompt
        """
        # Start with base system prompt
        system_prompt = self.base_system_prompt
        
        # Add template-specific system prompt if available
        if template and "system_prompt" in template:
            template_prompt = template["system_prompt"]
            system_prompt = f"{system_prompt}\n\n===\n\n{template_prompt}"
            self.log_debug("Added template-specific system prompt")
        
        # Add file context if available
        if file_context:
            system_prompt = f"{system_prompt}\n\n===\n\nRelevant files:\n{file_context}"
            self.log_debug(f"Added file context with {file_context.count('File:')}")
        
        self.log_debug(f"Built system prompt with {len(system_prompt)} characters")
        return system_prompt
        
    def _build_file_relevance_message(self, query: str, inputs: Dict[str, Any], file_metadata: Dict[str, str]) -> str:
        """Build user message for file relevance determination.
        
        Args:
            query: Main query or template description
            inputs: Dictionary of relevant input parameters
            file_metadata: Dictionary of file metadata
            
        Returns:
            Formatted user message
        """
        # Build context with query
        message = f"Query: {query}\n\n"
        
        # Add inputs if available
        if inputs:
            message += "Additional context:\n"
            for name, value in inputs.items():
                message += f"{name}: {value}\n"
            message += "\n"
        
        # Add file metadata
        message += "Available files:\n\n"
        for i, (path, metadata) in enumerate(file_metadata.items(), 1):
            message += f"File {i}: {path}\n"
            message += f"Metadata: {metadata}\n\n"
        
        message += "Select the files most relevant to this context."
        return message
        
    def determine_relevant_files(self, query_input: Union[str, ContextGenerationInput], file_metadata: Dict[str, str]) -> List[Tuple[str, str]]:
        """Determine relevant files for a query using LLM.
        
        Args:
            query_input: The user query/task or ContextGenerationInput object
            file_metadata: Dictionary mapping file paths to their metadata
            
        Returns:
            List of tuples containing (file_path, relevance_context)
        """
        # Extract query and relevant inputs based on input type
        query = ""
        relevant_inputs = {}
        
        if isinstance(query_input, str):
            query = query_input
            self.log_debug(f"Determining relevant files for query string: '{query}'")
        elif isinstance(query_input, ContextGenerationInput):
            query = query_input.template_description
            self.log_debug(f"Determining relevant files for template: '{query}'")
            
            # Extract relevant inputs
            for name, value in query_input.inputs.items():
                if name in query_input.context_relevance and query_input.context_relevance[name]:
                    relevant_inputs[name] = value
                    
            if relevant_inputs:
                self.log_debug(f"Including {len(relevant_inputs)} relevant inputs in context")
        elif isinstance(query_input, dict):
            # Legacy format support
            query = query_input.get("taskText", "")
            self.log_debug(f"Determining relevant files for legacy format: '{query}'")
        
        self.log_debug(f"Number of files to evaluate: {len(file_metadata)}")
        
        # Build user message
        user_message = self._build_file_relevance_message(query, relevant_inputs, file_metadata)
        
        # Get system prompt from registry
        system_prompt = prompt_registry.get_prompt("file_relevance")
        if not system_prompt:
            system_prompt = "You are a file relevance assistant. Select files relevant to the query."
        
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
