"""
System-wide Pydantic models based on docs/system/contracts/types.md
"""

import importlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Type, Union # Record is not standard, using Dict instead

from pydantic import BaseModel, Field, PositiveInt, NonNegativeInt, conint, confloat

# Configure logger
logger = logging.getLogger(__name__)

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
    # Removed 'score' as it's not in the IDL/Type definition

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
    'template_not_found', # Added common failure reason
    'tool_execution_error', # Added common failure reason
    'llm_error', # Added common failure reason
    'dependency_error', # Added for handler/dependency issues
    'connection_error', # Added for MCP/network issues
    'protocol_error', # Added for MCP protocol issues
    'configuration_error', # Added for config issues (e.g., MCP command)
    'unexpected_error'
]
"""
Reasons for task failure
[Type:System:TaskFailureReason:1.0]
"""

# Forward references for nested types - Updated SubtaskRequest definition below
# class SubtaskRequest(BaseModel):
#     # Define fields for SubtaskRequest if known, otherwise use Any or Dict
#     # Example:
#     task_id: str
#     inputs: Dict[str, Any]
#     # ... other relevant fields ...
#     pass # Placeholder until structure is defined

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
    subtaskRequest: Optional[Any] = None # Using Any until SubtaskRequest is fully defined below
    subtaskError: Optional['TaskError'] = None # Recursive TaskError structure, use string forward reference
    nestingDepth: Optional[NonNegativeInt] = None
    s_expression_environment: Optional[Dict[str, Any]] = None
    failing_expression: Optional[str] = None
    script_stdout: Optional[str] = None
    script_stderr: Optional[str] = None
    script_exit_code: Optional[int] = None
    notes: Optional[Dict[str, Any]] = None # Added missing notes field

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

AtomicTaskSubtype = Literal["standard", "subtask", "director", "evaluator", "associative_matching"] # Added matching
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
    [Type:System:ContextGenerationInput:5.0]
    """
    templateDescription: Optional[str] = None
    templateType: Optional[str] = None
    templateSubtype: Optional[str] = None
    query: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    inheritedContext: Optional[str] = None
    previousOutputs: Optional[str] = None
    matching_strategy: Optional[Literal['content', 'metadata']] = None # Default handled by consumer

# --- Subtask Request Definition ---
class SubtaskRequest(BaseModel):
    """
    Subtask Request structure used by Dispatcher and SexpEvaluator to invoke tasks via TaskSystem.
    Based on src/task_system/task_system_IDL.md execute_atomic_template args and docs/system/contracts/types.md.
    [Type:System:SubtaskRequest:1.0]
    """
    task_id: str # Unique identifier for this specific request instance

    # Fields from IDL/Type definition
    type: TaskType # Should always be "atomic" for direct execution
    name: str # Name of the atomic template to execute
    description: Optional[str] = None # Optional description for logging/context
    inputs: Dict[str, Any] # Input parameters for the subtask

    # Optional fields from IDL/Type definition
    template_hints: Optional[List[str]] = None
    context_management: Optional[ContextManagement] = None # Use the ContextManagement model
    max_depth: Optional[PositiveInt] = None
    file_paths: Optional[List[str]] = None

# --- Evaluation Result Definition ---
class EvaluationResult(TaskResult):
    """
    Specialized result structure potentially returned by 'evaluator' subtype tasks.
    Extends the base TaskResult with evaluation-specific notes.
    [Type:System:EvaluationResult:1.0]
    """
    notes: Dict[str, Any] = Field(default_factory=dict) # Override notes to add specific fields

    # Pydantic v2 doesn't directly support extending nested dicts like this easily.
    # We define the full structure expected within notes for clarity.
    # Consumers will need to access notes['success'], notes['feedback'], etc.
    # It's recommended to define a separate Pydantic model for the notes structure
    # if it becomes complex, e.g., class EvaluationNotes(BaseModel): ...

    # Example structure expected within notes:
    # success: bool
    # feedback: str
    # details: Optional[Dict[str, Any]] = None # e.g., {'metrics': {...}, 'violations': [...]}

# --- Model Resolution for Pydantic Output ---

class ModelNotFoundError(Exception):
    """Exception raised when a specified Pydantic model cannot be found."""
    pass

def resolve_model_class(schema_name: str) -> Type[BaseModel]:
    """
    Resolves a schema name string to an actual Pydantic model class.
    
    Args:
        schema_name: A string in the format "module.submodule.ModelName" or just "ModelName"
                     If just "ModelName" is provided, defaults to looking in src.system.models.
    
    Returns:
        The Pydantic model class.
    
    Raises:
        ModelNotFoundError: If the model cannot be found or is not a valid Pydantic BaseModel.
        ImportError: If the specified module cannot be imported.
    """
    logger.debug(f"Attempting to resolve model class for schema: {schema_name}")
    
    # Check if schema_name includes module path
    if '.' in schema_name:
        # Extract module path and class name
        module_path, class_name = schema_name.rsplit('.', 1)
        try:
            module = importlib.import_module(module_path)
            logger.debug(f"Successfully imported module: {module_path}")
        except ImportError as e:
            logger.error(f"Failed to import module {module_path}: {e}")
            raise ModelNotFoundError(f"Failed to import module {module_path}: {e}")
    else:
        # Default to looking in src.system.models
        module_path = "src.system.models"
        class_name = schema_name
        try:
            module = importlib.import_module(module_path)
            logger.debug(f"Using default module: {module_path}")
        except ImportError as e:
            logger.error(f"Failed to import default module {module_path}: {e}")
            raise ModelNotFoundError(f"Failed to import default module {module_path}: {e}")
    
    # Try to get the model class from the module
    if not hasattr(module, class_name):
        logger.error(f"Model class {class_name} not found in module {module_path}")
        raise ModelNotFoundError(f"Model class {class_name} not found in module {module_path}")
    
    model_class = getattr(module, class_name)
    
    # Verify it's a Pydantic BaseModel
    if not isinstance(model_class, type) or not issubclass(model_class, BaseModel):
        logger.error(f"{module_path}.{class_name} is not a Pydantic BaseModel subclass")
        raise ModelNotFoundError(f"{module_path}.{class_name} is not a Pydantic BaseModel subclass")
    
    logger.debug(f"Successfully resolved model class: {model_class.__name__}")
    return model_class
