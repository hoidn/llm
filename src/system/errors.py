"""Standardized error handling for the system.

This module provides utilities for creating and handling standardized
error types according to the system error taxonomy.
"""
from typing import Any, Dict, List, Optional, Union, Type

# Error types
TASK_FAILURE = "TASK_FAILURE"
RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"

# Task failure reason codes
CONTEXT_RETRIEVAL_FAILURE = "context_retrieval_failure"    # Failure to retrieve context data
CONTEXT_MATCHING_FAILURE = "context_matching_failure"      # Failure in associative matching algorithm
CONTEXT_PARSING_FAILURE = "context_parsing_failure"        # Failure to parse or process retrieved context
XML_VALIDATION_FAILURE = "xml_validation_failure"          # Output doesn't conform to expected XML schema
OUTPUT_FORMAT_FAILURE = "output_format_failure"            # Output doesn't meet format requirements
EXECUTION_TIMEOUT = "execution_timeout"                    # Task execution exceeded time limits
EXECUTION_HALTED = "execution_halted"                      # Task execution was deliberately terminated
SUBTASK_FAILURE = "subtask_failure"                        # A subtask failed, causing parent task failure
INPUT_VALIDATION_FAILURE = "input_validation_failure"      # Input data didn't meet requirements
UNEXPECTED_ERROR = "unexpected_error"                      # Catch-all for truly unexpected errors


class TaskError(Exception):
    """Base class for standardized task errors."""
    
    def __init__(self, 
                 message: str,
                 error_type: str,
                 reason: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None,
                 source_node: Optional[Any] = None):
        """
        Initialize a TaskError.
        
        Args:
            message: Human-readable error message
            error_type: Error type (e.g., TASK_FAILURE)
            reason: Specific reason code for the error
            details: Additional structured error details
            source_node: Optional AST node that caused the error
        """
        self.error_type = error_type
        self.reason = reason
        self.details = details or {}
        self.source_node = source_node
        self.message = message
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation."""
        result = {
            "type": self.error_type,
            "message": self.message
        }
        
        if self.reason:
            result["reason"] = self.reason
            
        if self.details:
            result["details"] = self.details
            
        return result


def create_task_failure(message: str, 
                        reason: str = UNEXPECTED_ERROR,
                        details: Optional[Dict[str, Any]] = None,
                        source_node: Optional[Any] = None) -> TaskError:
    """
    Create a standardized task failure error.
    
    Args:
        message: Human-readable error message
        reason: Failure reason code from the standardized taxonomy
        details: Additional structured error details
        source_node: Optional AST node that caused the error
        
    Returns:
        TaskError instance with TASK_FAILURE type
    """
    return TaskError(
        message=message,
        error_type=TASK_FAILURE,
        reason=reason,
        details=details,
        source_node=source_node
    )


def create_input_validation_error(message: str,
                                 details: Optional[Dict[str, Any]] = None,
                                 source_node: Optional[Any] = None) -> TaskError:
    """
    Create an input validation error.
    
    Args:
        message: Human-readable error message
        details: Additional structured error details
        source_node: Optional AST node that caused the error
        
    Returns:
        TaskError instance with INPUT_VALIDATION_FAILURE reason
    """
    return create_task_failure(
        message=message,
        reason=INPUT_VALIDATION_FAILURE,
        details=details,
        source_node=source_node
    )


def create_context_retrieval_error(message: str,
                                  details: Optional[Dict[str, Any]] = None,
                                  source_node: Optional[Any] = None) -> TaskError:
    """
    Create a context retrieval error.
    
    Args:
        message: Human-readable error message
        details: Additional structured error details
        source_node: Optional AST node that caused the error
        
    Returns:
        TaskError instance with CONTEXT_RETRIEVAL_FAILURE reason
    """
    return create_task_failure(
        message=message,
        reason=CONTEXT_RETRIEVAL_FAILURE,
        details=details,
        source_node=source_node
    )


def create_unexpected_error(message: str,
                           exception: Optional[Exception] = None,
                           source_node: Optional[Any] = None) -> TaskError:
    """
    Create an unexpected error.
    
    Args:
        message: Human-readable error message
        exception: Original exception that caused this error
        source_node: Optional AST node that caused the error
        
    Returns:
        TaskError instance with UNEXPECTED_ERROR reason
    """
    details = {}
    if exception:
        details["original_exception"] = str(exception)
        details["exception_type"] = type(exception).__name__
    
    return create_task_failure(
        message=message,
        reason=UNEXPECTED_ERROR,
        details=details,
        source_node=source_node
    )


def format_error_result(error: TaskError) -> Dict[str, Any]:
    """
    Format an error as a task result.
    
    Args:
        error: TaskError instance
        
    Returns:
        Task result dictionary with error information
    """
    return {
        "status": "FAILED",
        "content": error.message,
        "notes": {
            "error": error.to_dict()
        }
    }
