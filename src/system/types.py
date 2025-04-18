"""Core data models for the system.

This module contains Pydantic models for core data structures used throughout the system,
providing type validation, serialization, and deserialization capabilities.
"""
from typing import Dict, Any, List, Optional, Literal, Union, Tuple
from pydantic import BaseModel, Field

# Define allowed status values for better validation
TaskStatus = Literal["COMPLETE", "FAILED", "PENDING", "ERROR", "PARTIAL", "SUCCESS"]

class TaskResult(BaseModel):
    """Result of a task execution.
    
    This model represents the standardized result format returned by task executors,
    handlers, and other components that perform operations.
    """
    status: TaskStatus
    content: Any = Field(description="Content of the result, can be any type depending on the task")
    notes: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about the execution")

    class Config:
        """Pydantic configuration."""
        use_enum_values = True  # Ensure Literal values are used correctly
