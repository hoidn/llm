"""Automatic mode handling for AiderBridge."""
from typing import Dict, List, Optional, Any, Set, Tuple
import os
import sys
import tempfile
from pathlib import Path

class AiderAutomaticHandler:
    """
    Handler for automatic Aider tasks with auto-confirmation.
    
    This class provides functionality for executing non-interactive Aider
    tasks that automatically apply code changes without user confirmation.
    """
    
    def __init__(self, bridge):
        """
        Initialize an automatic mode handler.
        
        Args:
            bridge: The AiderBridge instance managing this handler
        """
        self.bridge = bridge
        self.last_result = None
        
    def execute_task(self, prompt: str, file_context: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Execute a single Aider task with auto-confirmation.
        
        Args:
            prompt: The instruction for code changes
            file_context: Optional explicit file paths to include, defaults to
                        current file context from bridge
                        
        Returns:
            Dict containing the task result in standard TaskResult format
        """
        from aider_bridge.result_formatter import format_automatic_result
        
        if not self.bridge.aider_available:
            return format_automatic_result(
                status="FAILED",
                content="Aider is not available. Please install Aider to use automatic mode.",
                error="Aider dependency not installed"
            )
            
        try:
            # Use provided file context or current context from bridge
            files = file_context or list(self.bridge.file_context)
            
            # If no context files, try to find relevant files based on prompt
            if not files and prompt:
                files = self.bridge.get_context_for_query(prompt)
                
                # If still no context files, return error
                if not files:
                    return format_automatic_result(
                        status="FAILED",
                        content="No relevant files found for the given prompt.",
                        error="No file context available"
                    )
            
            # Execute the code editing operation using the bridge
            result = self.bridge.execute_code_edit(prompt, files)
            
            # Store result for future reference
            self.last_result = result
            
            # Make sure result follows the TaskResult format for automatic mode
            if result.get("status") == "error":
                # Convert error format to standard TaskResult format
                return format_automatic_result(
                    status="FAILED",
                    content=result.get("content", "Task execution failed."),
                    error=result.get("notes", {}).get("error", "Unknown error")
                )
                
            # Format as automatic result
            return format_automatic_result(
                status=result.get("status", "COMPLETE"),
                content=result.get("content", "Task executed."),
                files_modified=result.get("notes", {}).get("files_modified", []),
                changes=result.get("notes", {}).get("changes", [])
            )
        except Exception as e:
            return format_automatic_result(
                status="FAILED",
                content=f"Error executing task: {str(e)}",
                error=str(e)
            )
            
    def get_last_result(self) -> Optional[Dict[str, Any]]:
        """
        Get the result of the last executed task.
        
        Returns:
            The last task result or None if no task has been executed
        """
        return self.last_result
