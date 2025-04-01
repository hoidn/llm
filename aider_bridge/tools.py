"""Tools registration utilities for AiderBridge integration."""
from typing import Dict, List, Optional, Any, Callable

def register_aider_tools(handler, aider_bridge):
    """
    Register Aider tools with the Handler.
    
    Args:
        handler: The Handler instance to register tools with
        aider_bridge: The AiderBridge instance to use for tool operations
        
    Returns:
        Dict with registration results
    """
    results = {
        "interactive": register_interactive_tool(handler, aider_bridge),
        # "automatic" will be registered in Phase 7
    }
    
    return results

def register_interactive_tool(handler, aider_bridge):
    """
    Register the interactive Aider tool with the Handler.
    
    Registers the aiderInteractive direct tool for starting interactive
    Aider sessions.
    
    Args:
        handler: The Handler instance to register the tool with
        aider_bridge: The AiderBridge instance to use for the tool
        
    Returns:
        Dict with registration result
    """
    # Check if handler has registerDirectTool method
    if not hasattr(handler, "registerDirectTool"):
        return {
            "status": "error",
            "message": "Handler does not support registerDirectTool method"
        }
    
    try:
        # Define the tool handler function
        def aider_interactive_tool(query: str, file_context: Optional[List[str]] = None):
            return aider_bridge.start_interactive_session(query, file_context)
        
        # Register the tool
        handler.registerDirectTool("aiderInteractive", aider_interactive_tool)
        
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
