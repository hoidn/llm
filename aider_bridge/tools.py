"""Tools registration utilities for AiderBridge integration."""
from typing import Dict, List, Optional, Any, Callable

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
    # Check if handler has registerDirectTool method
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
    
    try:
        # Define the tool handler function
        def aider_interactive_tool(query: str, file_context: Optional[List[str]] = None):
            return aider_bridge.start_interactive_session(query, file_context)
        
        # Register the tool
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
    # Check if handler has register_subtask_tool or registerSubtaskTool method
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
    
    try:
        # Define the tool handler function
        def aider_automatic_tool(prompt: str, file_context: Optional[List[str]] = None):
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
