"""Base handler providing common functionality for all handlers."""
from typing import Dict, List, Optional, Any, Callable, Tuple, Union

from .model_provider import ProviderAdapter, ClaudeProvider
from .file_access import FileAccessManager
from .command_executor import execute_command_safely, parse_file_paths_from_output
from ..memory.context_generation import ContextGenerationInput
from ..system.prompt_registry import registry as prompt_registry

class BaseHandler:
    """Base class for all handlers with common functionality.
    
    Provides shared capabilities for system prompts, tool management,
    conversation state, and LLM interaction. Context generation is handled
    through the Memory System with TaskSystem acting as mediator.
    
    Context Generation Flow:
    1. BaseHandler calls memory_system.get_relevant_context_for()
    2. MemorySystem delegates to TaskSystem.generate_context_for_memory_system()
    3. TaskSystem uses specialized templates via Handler for LLM-based matching
    
    This flow ensures clean separation of concerns and more accurate context matching.
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
        self.registered_tools = {}      # Tool specifications (for LLM tool use)
        self.tool_executors = {}        # Tool executor functions (for LLM tool use)
        self.direct_tool_executors = {} # Direct executor functions (for programmatic calls)

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

    def registerDirectTool(self, tool_name: str, executor_func: Callable) -> bool:
        """Register a direct tool executor function.

        These tools are intended for programmatic invocation via the dispatcher,
        not necessarily for LLM tool use.

        Args:
            tool_name: Name of the tool (identifier)
            executor_func: Function that implements the tool

        Returns:
            True if registration successful, False otherwise
        """
        try:
            if not tool_name:
                self.log_debug(f"Error registering direct tool: Missing tool name")
                return False

            self.log_debug(f"Registering direct tool: {tool_name}")
            self.direct_tool_executors[tool_name] = executor_func
            return True
        except Exception as e:
            self.log_debug(f"Error registering direct tool {tool_name}: {str(e)}")
            return False

    def _execute_tool(self, tool_name: str, tool_params: Any) -> Optional[Dict[str, Any]]:
        """Execute a registered tool (typically called by LLM).
        
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
        
        This is the preferred method for retrieving relevant files, using the
        Memory System with TaskSystem mediator for accurate context matching.
        
        Args:
            query: User's query
            inputs: Optional dictionary of additional inputs
            context_relevance: Optional mapping of input names to relevance
            
        Returns:
            List of relevant file paths
        """
        try:
            # Initialize input dictionaries if not provided
            if inputs is None:
                inputs = {"query": query}
            elif "query" not in inputs:
                # Add query to inputs if not already present
                inputs["query"] = query
                
            if context_relevance is None:
                context_relevance = {"query": True}
                # Add relevance for all inputs if not specified
                for key in inputs:
                    if key != "query":  # Skip query as we already set it
                        context_relevance[key] = True
            
            # Create context generation input
            context_input = ContextGenerationInput(
                template_description=query,
                inputs=inputs,
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
            
            self.log_debug(f"Found {len(relevant_files)} relevant files for query: '{query}'")
            return relevant_files
        except Exception as e:
            self.log_debug(f"Error getting relevant files: {str(e)}")
            return []  # Return empty list on error to avoid breaking callers
    
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
        
def determine_relevant_files(self, query_input: Union[str, ContextGenerationInput], file_metadata: Dict[str, str]) -> List[Tuple[str, str]]:
    """DEPRECATED: Use Memory System with TaskSystem mediator instead.
    
    This method is maintained for backward compatibility only.
    Please use MemorySystem.get_relevant_context_for() with a TaskSystem mediator.
    
    Args:
        query_input: Query string or ContextGenerationInput
        file_metadata: Dictionary mapping file paths to metadata
        
    Returns:
        List of (file_path, relevance) tuples
    """
    import warnings
    warnings.warn(
        "determine_relevant_files is deprecated. Use MemorySystem.get_relevant_context_for() with a TaskSystem mediator instead.",
        DeprecationWarning, 
        stacklevel=2
    )
    
    # Create a basic result for backward compatibility
    matches = []
    
    try:
        # Handle string vs ContextGenerationInput
        if isinstance(query_input, str):
            query = query_input
            context_input = ContextGenerationInput(
                template_description=query,
                inputs={"query": query},
                context_relevance={"query": True}
            )
        else:
            query = query_input.template_description
            context_input = query_input
            
        # Call memory system if available
        if hasattr(self, 'memory_system') and self.memory_system:
            result = self.memory_system.get_relevant_context_for(context_input)
            if hasattr(result, 'matches'):
                matches = result.matches
                
        # Log result
        self.log_debug(f"DEPRECATED determine_relevant_files found {len(matches)} matches for '{query}'")
    except Exception as e:
        self.log_debug(f"Error in deprecated determine_relevant_files: {str(e)}")
        
    return matches

def _build_file_relevance_message(self, query: str, inputs: Dict[str, Any], file_metadata: Dict[str, str]) -> str:
    """DEPRECATED: Use Memory System with TaskSystem mediator instead.
    
    This method is maintained for backward compatibility only.
    Please use MemorySystem.get_relevant_context_for() with a TaskSystem mediator.
    
    Args:
        query: User query
        inputs: Additional inputs
        file_metadata: Dictionary mapping file paths to metadata
        
    Returns:
        Message for LLM to determine file relevance
    """
    import warnings
    warnings.warn(
        "_build_file_relevance_message is deprecated. Use MemorySystem.get_relevant_context_for() with a TaskSystem mediator instead.",
        DeprecationWarning, 
        stacklevel=2
    )
    
    # Return a minimal message for backward compatibility
    return f"""Find files relevant to: {query}
    
Available files:
{", ".join(file_metadata.keys())}

Return only the file paths that are most relevant."""
