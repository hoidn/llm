"""
System-wide Pydantic models based on docs/system/contracts/types.md
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union, Record # Record is not standard, using Dict instead

from pydantic import BaseModel, Field, PositiveInt, NonNegativeInt, conint, confloat

# --- Resource Management Types ---

class TurnMetrics(BaseModel):
    """Metrics for conversation turns."""
    used: NonNegativeInt
    limit: PositiveInt
    lastTurnAt: Optional[datetime] = None # Made optional as it might not be set initially

class ContextMetrics(BaseModel):
    """Metrics for context usage."""
    used: NonNegativeInt
    limit: PositiveInt
    peakUsage: NonNegativeInt

class ResourceMetrics(BaseModel):
    """
    Resource metrics tracking for Handler sessions
    [Type:System:ResourceMetrics:1.0]
    """
    turns: TurnMetrics
    context: ContextMetrics

class ResourceLimits(BaseModel):
    """
    Resource limits configuration
    [Type:System:ResourceLimits:1.0]
    """
    maxTurns: PositiveInt
    maxContextWindow: PositiveInt # Assuming context window is measured in tokens or similar unit
    warningThreshold: confloat(ge=0.0, le=1.0) # Percentage threshold
    timeout: Optional[PositiveInt] = None # Optional timeout in seconds

# --- Associative Matching Types ---

class MatchTuple(BaseModel):
    """
    Individual match result with relevance information
    [Type:System:MatchTuple:1.0]
    """
    path: str  # Path to the matched item (e.g., file path)
    relevance: confloat(ge=0.0, le=1.0)  # Relevance score (0.0 to 1.0)
    excerpt: Optional[str] = None  # Optional excerpt from the matched content

class AssociativeMatchResult(BaseModel):
    """
    Result of associative matching operations
    [Type:System:AssociativeMatchResult:1.0]
    """
    context_summary: str  # Summarized context information
    matches: List[MatchTuple]  # List of matching items with relevance scores
    error: Optional[str] = None  # Error message if the matching operation failed

# --- Error Types ---

TaskFailureReason = Literal[
    'context_retrieval_failure',
    'context_matching_failure',
    'context_parsing_failure',
    'xml_validation_failure',
    'output_format_failure',
    'execution_timeout',
    'execution_halted',
    'subtask_failure',
    'input_validation_failure',
    'unexpected_error'
]
"""
Reasons for task failure
[Type:System:TaskFailureReason:1.0]
"""

# Forward references for nested types
class SubtaskRequest(BaseModel):
    # Define fields for SubtaskRequest if known, otherwise use Any or Dict
    # Example:
    task_id: str
    inputs: Dict[str, Any]
    # ... other relevant fields ...
    pass # Placeholder until structure is defined

# Define base model for discriminated union
class BaseTaskError(BaseModel):
    message: str
    content: Optional[str] = None # Partial output or relevant content

# Specific Error Variants
class ResourceExhaustionError(BaseTaskError):
    """Error due to resource exhaustion."""
    type: Literal['RESOURCE_EXHAUSTION'] = 'RESOURCE_EXHAUSTION'
    resource: Literal['turns', 'context', 'output']
    metrics: Optional[Dict[str, Any]] = None # e.g., {'used': number, 'limit': number}

class TaskFailureDetails(BaseModel):
    """Detailed information for task failures."""
    partial_context: Optional[Any] = None
    context_metrics: Optional[Any] = None
    violations: Optional[List[str]] = None
    subtaskRequest: Optional[Any] = None # Using Any until SubtaskRequest is fully defined
    subtaskError: Optional[Any] = None # Recursive TaskError structure, use Any for now
    nestingDepth: Optional[NonNegativeInt] = None
    s_expression_environment: Optional[Dict[str, Any]] = None
    failing_expression: Optional[str] = None
    script_stdout: Optional[str] = None
    script_stderr: Optional[str] = None
    script_exit_code: Optional[int] = None

class TaskFailureError(BaseTaskError):
    """Error indicating a general task failure."""
    type: Literal['TASK_FAILURE'] = 'TASK_FAILURE'
    reason: TaskFailureReason
    notes: Optional[Dict[str, Any]] = None
    details: Optional[TaskFailureDetails] = None

class InvalidOutputError(BaseTaskError):
    """Error for structurally invalid output (e.g., malformed XML/JSON)."""
    type: Literal['INVALID_OUTPUT'] = 'INVALID_OUTPUT'
    violations: Optional[List[str]] = None

class ValidationError(BaseTaskError):
    """Error related to data validation."""
    type: Literal['VALIDATION_ERROR'] = 'VALIDATION_ERROR'
    path: Optional[str] = None
    invalidModel: Optional[bool] = None

class XMLParseError(BaseTaskError):
    """Error during XML parsing."""
    type: Literal['XML_PARSE_ERROR'] = 'XML_PARSE_ERROR'
    location: Optional[str] = None

# Discriminated Union for TaskError
TaskError = Union[
    ResourceExhaustionError,
    TaskFailureError,
    InvalidOutputError,
    ValidationError,
    XMLParseError
]
"""
Standardized task error structure using Pydantic's discriminated union.
[Type:System:TaskError:1.0]
"""

# --- Context Management Types ---

class ContextManagement(BaseModel):
    """
    Defines context management settings using the standardized three-dimensional model.
    Note: fresh_context="enabled" cannot be combined with inherit_context="full" or "subset"
    [Type:System:ContextManagement:1.0]
    """
    inheritContext: Literal['full', 'none', 'subset'] = 'subset' # Default based on SUBTASK_CONTEXT_DEFAULTS rationale
    accumulateData: bool = False
    accumulationFormat: Literal['full_output', 'notes_only'] = 'notes_only'
    freshContext: Literal['enabled', 'disabled'] = 'enabled'

# Default context management settings for atomic tasks invoked as subtasks
SUBTASK_CONTEXT_DEFAULTS: ContextManagement = ContextManagement(
    inheritContext='subset',
    accumulateData=False,
    accumulationFormat='notes_only',
    freshContext='enabled'
)
"""
Default context management settings for atomic tasks invoked as subtasks
[Type:System:SubtaskContextDefaults:1.0]
"""

# --- Task Execution Types ---

ReturnStatus = Literal["COMPLETE", "CONTINUATION", "FAILED"]
"""
Task execution status
[Type:System:ReturnStatus:1.0]
"""

TaskType = Literal["atomic"]
"""
Core task type (now only atomic defined in XML)
[Type:System:TaskType:1.0]
"""

AtomicTaskSubtype = Literal["standard", "subtask", "director", "evaluator"]
"""
Atomic task subtypes
[Type:System:AtomicTaskSubtype:1.0]
"""

class HandlerConfig(BaseModel):
    """
    Handler configuration
    [Type:System:HandlerConfig:1.0]
    """
    provider: str  # e.g., "anthropic", "openai"
    maxTurns: PositiveInt
    maxContextWindowFraction: confloat(gt=0.0, le=1.0) # Fraction, e.g. 0.8
    defaultModel: Optional[str] = None
    systemPrompt: str
    tools: Optional[List[str]] = None # Tool types needed ("file_access", "bash", etc.)

class TaskResult(BaseModel):
    """
    Task execution result
    [Type:TaskSystem:TaskResult:1.0]
    """
    content: str # Complete or partial output
    status: ReturnStatus # COMPLETE, CONTINUATION, FAILED
    criteria: Optional[str] = None
    parsedContent: Optional[Any] = None # If output was parsed JSON
    notes: Dict[str, Any] = Field(default_factory=dict) # Ensure notes is always a dict

class ContextGenerationInput(BaseModel):
    """
    Input structure for Memory System context requests.
    Can be called with template context or a direct query.
    [Type:Memory:ContextGenerationInput:4.0]
    """
    templateDescription: Optional[str] = None
    templateType: Optional[str] = None
    templateSubtype: Optional[str] = None
    query: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    inheritedContext: Optional[str] = None
    previousOutputs: Optional[str] = None
