"""Tools registration utilities for AiderBridge integration."""
from typing import Dict, List, Optional, Any, Callable, Union

def create_aider_tool_specs() -> Dict[str, Dict[str, Any]]:
    """
    Create tool specifications following Anthropic's tool use format.
    
    Returns:
        Dict of tool specifications by name
    """
    return {
        "aiderInteractive": {
            "name": "aiderInteractive",
            "description": """Start an interactive Aider session for complex code editing tasks.
                This tool transfers control to an interactive terminal session where the user can
                directly interact with Aider. Use this for complex refactoring, architectural changes,
                or when multiple files need coordinated changes. The interactive mode is best when
                the changes require user feedback or clarification during the process.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The initial query or instruction for the Aider session"}
                },
                "required": ["query"]
            }
        },
        "aiderAutomatic": {
            "name": "aiderAutomatic",
            "description": """Execute an automatic Aider task with auto-confirmation for straightforward code changes.
                This tool makes code changes without requiring user confirmation for each change.
                Use this for simple, well-defined tasks like adding docstrings, fixing bugs with clear solutions,
                or implementing straightforward features. The automatic mode is best when the changes are
                predictable and don't require user interaction.""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The instruction for code changes"},
                    "file_context": {
                        "type": "array", 
                        "items": {"type": "string"},
                        "description": "Optional explicit file paths to include (if empty, relevant files will be found automatically)"
                    }
                },
                "required": ["prompt"]
            }
        }
    }

def register_aider_tools(handler: Any, aider_bridge: Any) -> Dict[str, Dict[str, Any]]:
    """
    Register Aider tools with the Handler.
    
    Registers both interactive and automatic tools with the provided handler,
    allowing the LLM to select between different processing modes.
    
    Args:
        handler: The Handler instance to register tools with
        aider_bridge: The AiderBridge instance to use for tool operations
        
    Returns:
        Dict with registration results for each tool type
    """
    results = {
        "interactive": register_interactive_tool(handler, aider_bridge),
        "automatic": register_automatic_tool(handler, aider_bridge)
    }
    
    return results

def register_interactive_tool(handler: Any, aider_bridge: Any) -> Dict[str, Any]:
    """
    Register the interactive Aider tool with the Handler.
    
    Registers the aiderInteractive direct tool for starting interactive
    Aider sessions. This tool transfers control to an interactive Aider
    session where the user can directly interact with Aider.
    
    Args:
        handler: The Handler instance to register the tool with
        aider_bridge: The AiderBridge instance to use for the tool
        
    Returns:
        Dict with registration result including status and tool details
    """
    try:
        # Check if handler supports Anthropic tool format
        if hasattr(handler, "register_tool"):
            # Get tool specification
            tool_specs = create_aider_tool_specs()
            tool_spec = tool_specs["aiderInteractive"]
            
            # Define the tool executor function for Anthropic format
            def aider_interactive_executor(input_data: Dict[str, Any]) -> Dict[str, Any]:
                query = input_data["query"]
                # Get relevant files based on query
                file_context = aider_bridge.get_context_for_query(query)
                return aider_bridge.start_interactive_session(query, file_context)
            
            # Register the tool with Anthropic format
            handler.register_tool(tool_spec, aider_interactive_executor)
            
            return {
                "status": "success",
                "name": "aiderInteractive",
                "type": "anthropic_tool",
                "description": "Start an interactive Aider session"
            }
        else:
            # Fall back to legacy format
            register_method = None
            if hasattr(handler, "registerDirectTool"):
                register_method = handler.registerDirectTool
            elif hasattr(handler, "register_direct_tool"):
                register_method = handler.register_direct_tool
                
            if not register_method:
                return {
                    "status": "error",
                    "message": "Handler does not support direct tool registration method"
                }
            
            # Define the tool handler function for legacy format
            def aider_interactive_tool(query: str, file_context: Optional[List[str]] = None):
                if file_context is None:
                    file_context = aider_bridge.get_context_for_query(query)
                return aider_bridge.start_interactive_session(query, file_context)
            
            # Register the tool with legacy format
            register_method("aiderInteractive", aider_interactive_tool)
            
            return {
                "status": "success",
                "name": "aiderInteractive",
                "type": "direct",
                "description": "Start an interactive Aider session"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error registering interactive tool: {str(e)}",
            "error": str(e)
        }

def register_automatic_tool(handler: Any, aider_bridge: Any) -> Dict[str, Any]:
    """
    Register the automatic Aider tool with the Handler.
    
    Registers the aiderAutomatic subtask tool for executing
    automatic Aider tasks with auto-confirmation. This tool allows
    the LLM to make code changes without requiring user confirmation
    for each change.
    
    Args:
        handler: The Handler instance to register the tool with
        aider_bridge: The AiderBridge instance to use for the tool
        
    Returns:
        Dict with registration result including status and tool details
    """
    try:
        # Check if handler supports Anthropic tool format
        if hasattr(handler, "register_tool"):
            # Get tool specification
            tool_specs = create_aider_tool_specs()
            tool_spec = tool_specs["aiderAutomatic"]
            
            # Define the tool executor function for Anthropic format
            def aider_automatic_executor(input_data: Dict[str, Any]) -> Dict[str, Any]:
                prompt = input_data["prompt"]
                file_context = input_data.get("file_context")
                
                # If no explicit file context, get relevant files based on prompt
                if not file_context:
                    file_context = aider_bridge.get_context_for_query(prompt)
                    
                return aider_bridge.execute_automatic_task(prompt, file_context)
            
            # Register the tool with Anthropic format
            handler.register_tool(tool_spec, aider_automatic_executor)
            
            return {
                "status": "success",
                "name": "aiderAutomatic",
                "type": "anthropic_tool",
                "description": "Execute automatic Aider task with auto-confirmation"
            }
        else:
            # Fall back to legacy format
            register_method = None
            if hasattr(handler, "register_subtask_tool"):
                register_method = handler.register_subtask_tool
            elif hasattr(handler, "registerSubtaskTool"):
                register_method = handler.registerSubtaskTool
                
            if not register_method:
                return {
                    "status": "error",
                    "message": "Handler does not support subtask tool registration method"
                }
            
            # Define the tool handler function for legacy format
            def aider_automatic_tool(prompt: str, file_context: Optional[List[str]] = None):
                if file_context is None:
                    file_context = aider_bridge.get_context_for_query(prompt)
                return aider_bridge.execute_automatic_task(prompt, file_context)
            
            # Register the tool
            register_method("aiderAutomatic", aider_automatic_tool)
            
            return {
                "status": "success",
                "name": "aiderAutomatic",
                "type": "subtask",
                "description": "Execute automatic Aider task with auto-confirmation"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error registering automatic tool: {str(e)}",
            "error": str(e)
        }
