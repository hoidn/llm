"""
System-wide Pydantic models based on docs/system/contracts/types.md
"""

import importlib
import logging
from datetime import datetime
from enum import Enum # Add Enum
from typing import Any, Dict, List, Literal, Optional, Type, Union # Record is not standard, using Dict instead

from pydantic import BaseModel, Field, PositiveInt, NonNegativeInt, conint, confloat, model_validator # Ensure confloat, NonNegativeInt, PositiveInt

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


# --- MatchItemContentType Enum (NEW) ---
class MatchItemContentType(str, Enum):
    FILE_CONTENT = "file_content"
    FILE_SUMMARY = "file_summary"
    WEB_EXCERPT = "web_excerpt"
    DATABASE_RECORD_SUMMARY = "database_record_summary"
    CODE_CHUNK = "code_chunk"
    TEXT_CHUNK = "text_chunk" # Generic text chunk from a larger document


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

class MatchItem(BaseModel):
    """
    Represents a contextual item retrieved through associative matching or context gathering.
    [Type:System:MatchItem:1.0]
    """
    id: str = Field(description="A unique identifier for this item (e.g., absolute file path, URL + anchor, DB record ID). This helps in de-duplication and referencing.")
    content: str = Field(description="The primary textual content of this item. Could be file content, a summary, an excerpt, or a serialized representation of structured data.")
    relevance_score: confloat(ge=0.0, le=1.0) = Field(description="The relevance score of this item to the query (0.0 to 1.0).")
    content_type: str = Field(description=f"Describes the nature of the 'content' and 'id'. Examples: {[e.value for e in MatchItemContentType]}.") # Or content_type: MatchItemContentType if using Enum directly
    source_path: Optional[str] = Field(None, description="Optional: The original source path from which this item was derived if 'id' isn't sufficient or if 'content' is a processed version.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional: Additional metadata about this item (e.g., line numbers, last modified date, language).")


class AssociativeMatchResult(BaseModel):
    """
    Result of associative matching operations (Memory System output)
    [Type:System:AssociativeMatchResult:1.1] // Version incremented
    """
    context_summary: str
    matches: List[MatchItem]  # REVISED: Uses new MatchItem
    error: Optional[str] = None


class DataContext(BaseModel):
    """
    Holds the result of associative matching and other context gathering, managed by the BaseHandler.
    Separate from conversational session history.
    [Type:System:DataContext:1.0]
    """
    retrieved_at: str = Field(description="ISO datetime string of when the context was retrieved.")
    source_query: Optional[str] = Field(None, description="The query that led to this context.")
    items: List[MatchItem] = Field(description="List of retrieved contextual items.")
    overall_summary: Optional[str] = Field(None, description="An overall summary of the context, if available.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata about the context retrieval itself (e.g., sources consulted, timings).")


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
    'context_priming_failure', # ADD THIS IF MISSING
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
    inheritContext='none',  # Changed from 'subset' to 'none' to be compatible with freshContext='enabled'
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


class WorkflowStepDefinition(BaseModel):
    """
    Defines a single step in a Python-driven workflow, including input mappings.
    Used by PythonWorkflowManager.
    [Type:System:WorkflowStepDefinition:1.0]
    """
    task_name: str = Field(description="Name of the task/tool to execute (e.g., 'user:generate-plan', 'system:read_files').")
    static_inputs: Optional[Dict[str, Any]] = Field(None, description="Static input values provided directly for this task. { \"param_template_name\": \"literal_value\", ... }")
    dynamic_input_mappings: Optional[Dict[str, str]] = Field(None, description="Mappings for inputs from previous steps' outputs. { \"param_template_name\": \"source_step_output_name.field.subfield\", ... }")
    output_name: str = Field(description="Name under which this step's TaskResult will be stored in the workflow context. Must be unique within the workflow.")


class HistoryConfigSettings(BaseModel):
    use_session_history: bool = Field(True, description="If false, task starts with empty history for LLM call.")
    history_turns_to_include: Optional[PositiveInt] = Field(None, description="If use_session_history=true, max past turns to include.")
    record_in_session_history: bool = Field(True, description="If true, this task's turn is added to session history.")

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
    history_config: Optional[HistoryConfigSettings] = None 

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

# --- Aider Loop Specific Models ---

class DevelopmentPlan(BaseModel):
    """
    Structured plan generated by Model A for the coding task.
    Expected output schema for the 'user:generate-plan' task.
    """
    instructions: str = Field(description="Detailed step-by-step instructions for the coding task, suitable for passing directly to an AI coding assistant like Aider.")
    files: List[str] = Field(description="List of file paths (relative to the repository root) that the coding assistant should focus on or modify.")
    test_command: Optional[str] = Field(None, description="The exact shell command needed to run the relevant tests for this task within the repository.")
    # Consider adding model_config = ConfigDict(extra='ignore') if needed

class FeedbackResult(BaseModel):
    """
    Structured feedback generated by Model A after analyzing an Aider result.
    Expected output schema for the 'user:analyze-aider-result' task.
    """
    status: Literal['SUCCESS', 'REVISE', 'ABORT'] = Field(description="Verdict on the Aider iteration: SUCCESS (task complete), REVISE (needs refinement), ABORT (unrecoverable error).")
    next_prompt: Optional[str] = Field(None, description="If status is REVISE, the revised prompt to give Aider for the next iteration.")
    explanation: Optional[str] = Field(None, description="Brief explanation for the status (e.g., why it succeeded, failed, or needs revision).")
    # Consider adding model_config = ConfigDict(extra='ignore') if needed

    @model_validator(mode='after')
    def check_next_prompt_on_revise(self) -> 'FeedbackResult':
        if self.status == 'REVISE' and self.next_prompt is None:
            raise ValueError("'next_prompt' is required when status is 'REVISE'")
        # It's okay for next_prompt to be None if status is SUCCESS or ABORT
        return self

class CombinedAnalysisResult(BaseModel):
    """
    Structured result from the combined analysis task, deciding the next step.
    """
    verdict: Literal['SUCCESS', 'RETRY', 'FAILURE'] = Field(description="Overall verdict: SUCCESS (tests passed), RETRY (tests failed, suggest retry), FAILURE (tests failed, stop).")
    next_prompt: Optional[str] = Field(None, description="If verdict is RETRY, the revised prompt for the next Aider iteration.")
    message: str = Field(description="A concise explanation of the verdict.")
    next_files: Optional[List[str]] = Field(None, description="If verdict is RETRY, the list of files for the next Aider iteration. If None, previous files might be reused.")


    @model_validator(mode='after')
    def check_next_prompt_on_retry(self) -> 'CombinedAnalysisResult':
        if self.verdict == 'RETRY':
            if self.next_prompt is None:
                raise ValueError("'next_prompt' is required when verdict is 'RETRY'")
            # next_files can be optional even on RETRY, implying orchestrator might reuse.
            # If next_files must be provided on RETRY, add validation here.
            # For now, we allow it to be None.
        return self

class StructuredAnalysisResult(BaseModel):
    """
    Structured output from the LLM analysis task called within the
    iterative-loop's controller phase. Provides feedback on iteration success
    and guidance for the next step.
    [Type: Loop:StructuredAnalysisResult:1.0]
    """
    success: bool = Field(description="True if the iteration's goal was met (e.g., tests passed and goal achieved).")
    analysis: str = Field(description="Explanation/summary of the iteration's outcome.")
    next_input: Optional[str] = Field(default=None, description="The prompt/input for the *next* executor iteration. Required if success=false.")
    new_files: Optional[List[str]] = Field(default=None, description="Optional list of new file paths identified during analysis to add/consider for the next iteration's context.")

    @model_validator(mode='after')
    def check_next_input_on_failure(self) -> 'StructuredAnalysisResult':
        """Validate that next_input is provided if success is False."""
        # The validator function in Pydantic v2 should return self
        if not self.success and self.next_input is None:
            # Raise ValueError for Pydantic v2 validation errors within model_validator
            raise ValueError("'next_input' is required when success is False")
        # It's okay for next_input to be None if success is True
        return self

class ControllerAnalysisResult(BaseModel):
    """
    Structured output from the LLM analysis task called within the
    iterative-loop's controller phase. Provides feedback on iteration success
    and guidance for the next step.
    [Type: Loop:ControllerAnalysisResult:1.0]
    """
    decision: Literal["CONTINUE", "STOP_SUCCESS", "STOP_FAILURE"] = Field(description="Decision for the loop control flow.")
    next_plan: Optional[Dict[str, Any]] = Field(None, description="Required if decision is CONTINUE. Contains {'instructions': str, 'files': List[str]} for the next Aider execution.")
    analysis: str = Field(description="Explanation of the decision based on Aider and test results.")

    @model_validator(mode='after')
    def check_next_plan_on_continue(self) -> 'ControllerAnalysisResult':
        """Validate that next_plan is provided and structured correctly if decision is CONTINUE."""
        if self.decision == 'CONTINUE':
            if self.next_plan is None:
                raise ValueError("'next_plan' dictionary is required when decision is 'CONTINUE'")
            if not isinstance(self.next_plan, dict):
                raise ValueError("'next_plan' must be a dictionary when decision is 'CONTINUE'")
            if "instructions" not in self.next_plan or not isinstance(self.next_plan["instructions"], str):
                raise ValueError("'next_plan' must contain 'instructions' (string) when decision is 'CONTINUE'")
            if "files" not in self.next_plan or not isinstance(self.next_plan["files"], list):
                raise ValueError("'next_plan' must contain 'files' (list) when decision is 'CONTINUE'")
            # Check for list elements being strings
            if not all(isinstance(f, str) for f in self.next_plan["files"]):
                raise ValueError("'next_plan.files' must be a list of strings")
        return self
