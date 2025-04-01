"""Utilities for formatting Aider results into standardized TaskResult objects."""
from typing import Dict, List, Any, Optional

def format_task_result(
    operation_type: str,
    status: str,
    content: str,
    files_modified: Optional[List[str]] = None,
    changes: Optional[List[Dict[str, str]]] = None,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format the result of an Aider operation as a standardized TaskResult.
    
    Args:
        operation_type: Type of operation ('interactive' or 'automatic')
        status: Operation status ('COMPLETE', 'PARTIAL', 'FAILED')
        content: Main content of the result
        files_modified: List of modified file paths
        changes: List of change descriptions
        error: Optional error message
        
    Returns:
        Standardized TaskResult dictionary
    """
    result = {
        "content": content,
        "status": status,
        "notes": {}
    }
    
    # Add files_modified if available
    if files_modified:
        result["notes"]["files_modified"] = files_modified
    
    # Add changes if available
    if changes:
        result["notes"]["changes"] = changes
    
    # Add operation type
    result["notes"]["operation_type"] = operation_type
    
    # Add error if available
    if error:
        result["notes"]["error"] = error
    
    return result

def format_interactive_result(
    status: str,
    content: str,
    files_modified: Optional[List[str]] = None,
    session_summary: Optional[str] = None,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format the result of an interactive Aider session.
    
    Args:
        status: Session status ('COMPLETE', 'PARTIAL', 'FAILED')
        content: Main content of the result
        files_modified: List of modified file paths
        session_summary: Optional summary of the session
        error: Optional error message
        
    Returns:
        Standardized TaskResult dictionary
    """
    changes = None
    if files_modified:
        changes = [
            {"file": file_path, "description": f"Modified in interactive session"}
            for file_path in files_modified
        ]
    
    result = format_task_result(
        operation_type="interactive",
        status=status,
        content=content,
        files_modified=files_modified,
        changes=changes,
        error=error
    )
    
    # Add session summary if available
    if session_summary:
        result["notes"]["session_summary"] = session_summary
    
    return result

def format_automatic_result(
    status: str,
    content: str,
    files_modified: Optional[List[str]] = None,
    changes: Optional[List[Dict[str, str]]] = None,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format the result of an automatic Aider operation.
    
    Args:
        status: Operation status ('COMPLETE', 'PARTIAL', 'FAILED')
        content: Main content of the result
        files_modified: List of modified file paths
        changes: List of change descriptions
        error: Optional error message
        
    Returns:
        Standardized TaskResult dictionary
    """
    # Generate basic changes if not provided
    if files_modified and not changes:
        changes = [
            {"file": file_path, "description": f"Modified {file_path}"}
            for file_path in files_modified
        ]
    
    return format_task_result(
        operation_type="automatic",
        status=status,
        content=content,
        files_modified=files_modified,
        changes=changes,
        error=error
    )
