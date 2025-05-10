"""
Unit tests for system-wide Pydantic models defined in src.system.models.
"""
import pytest
from pydantic import ValidationError
from datetime import datetime
from typing import List, Optional, Literal # Added imports

# Attempt to import models from the correct location
try:
    from src.system.models import (
        TurnMetrics, ContextMetrics, ResourceMetrics, ResourceLimits,
        MatchTuple, AssociativeMatchResult,
        TaskFailureReason, ResourceExhaustionError, TaskFailureDetails, TaskFailureError,
        InvalidOutputError, ValidationError as ModelValidationError, XMLParseError, TaskError, # Alias ValidationError
        ContextManagement, SUBTASK_CONTEXT_DEFAULTS,
        ReturnStatus, TaskType, AtomicTaskSubtype,
        HandlerConfig, TaskResult, ContextGenerationInput,
        # Import new models
        DevelopmentPlan, FeedbackResult, StructuredAnalysisResult
    )
except ImportError:
     pytest.skip("Skipping model tests, src.system.models not found or dependencies missing", allow_module_level=True)


# --- Test Resource Management Types ---

def test_turn_metrics_valid():
    now = datetime.now()
    metrics = TurnMetrics(used=5, limit=10, lastTurnAt=now)
    assert metrics.used == 5
    assert metrics.limit == 10
    assert metrics.lastTurnAt == now

def test_turn_metrics_defaults():
    metrics = TurnMetrics(used=0, limit=1)
    assert metrics.used == 0
    assert metrics.limit == 1
    assert metrics.lastTurnAt is None

def test_turn_metrics_invalid():
    with pytest.raises(ValidationError):
        TurnMetrics(used=-1, limit=10) # used must be non-negative
    with pytest.raises(ValidationError):
        TurnMetrics(used=5, limit=0) # limit must be positive

def test_context_metrics_valid():
    metrics = ContextMetrics(used=1000, limit=4000, peakUsage=1500)
    assert metrics.used == 1000
    assert metrics.limit == 4000
    assert metrics.peakUsage == 1500

def test_context_metrics_invalid():
    with pytest.raises(ValidationError):
        ContextMetrics(used=-1, limit=4000, peakUsage=1500)
    with pytest.raises(ValidationError):
        ContextMetrics(used=1000, limit=0, peakUsage=1500)
    with pytest.raises(ValidationError):
        ContextMetrics(used=1000, limit=4000, peakUsage=-1)

def test_resource_metrics_valid():
    turn_m = TurnMetrics(used=2, limit=5)
    context_m = ContextMetrics(used=500, limit=2000, peakUsage=600)
    metrics = ResourceMetrics(turns=turn_m, context=context_m)
    assert metrics.turns == turn_m
    assert metrics.context == context_m

def test_resource_limits_valid():
    limits = ResourceLimits(maxTurns=50, maxContextWindow=16000, warningThreshold=0.8, timeout=60)
    assert limits.maxTurns == 50
    assert limits.maxContextWindow == 16000
    assert limits.warningThreshold == 0.8
    assert limits.timeout == 60

def test_resource_limits_defaults():
    limits = ResourceLimits(maxTurns=50, maxContextWindow=16000, warningThreshold=0.8)
    assert limits.timeout is None

def test_resource_limits_invalid():
    with pytest.raises(ValidationError):
        ResourceLimits(maxTurns=0, maxContextWindow=16000, warningThreshold=0.8)
    with pytest.raises(ValidationError):
        ResourceLimits(maxTurns=50, maxContextWindow=0, warningThreshold=0.8)
    with pytest.raises(ValidationError):
        ResourceLimits(maxTurns=50, maxContextWindow=16000, warningThreshold=1.1)
    with pytest.raises(ValidationError):
        ResourceLimits(maxTurns=50, maxContextWindow=16000, warningThreshold=0.8, timeout=0)

# --- Test Associative Matching Types ---

def test_match_tuple_valid():
    match = MatchTuple(path="file.py", relevance=0.95, excerpt="def func():")
    assert match.path == "file.py"
    assert match.relevance == 0.95
    assert match.excerpt == "def func():"

def test_match_tuple_defaults():
    match = MatchTuple(path="file.py", relevance=0.9)
    assert match.excerpt is None

def test_match_tuple_invalid():
    with pytest.raises(ValidationError):
        MatchTuple(path="file.py", relevance=1.1) # relevance > 1.0
    with pytest.raises(ValidationError):
        MatchTuple(path="file.py", relevance=-0.1) # relevance < 0.0

def test_associative_match_result_valid():
    matches = [MatchTuple(path="f1.py", relevance=0.8), MatchTuple(path="f2.py", relevance=0.7)]
    result = AssociativeMatchResult(context_summary="Summary", matches=matches, error=None)
    assert result.context_summary == "Summary"
    assert result.matches == matches
    assert result.error is None

def test_associative_match_result_with_error():
    result = AssociativeMatchResult(context_summary="", matches=[], error="Failed to index")
    assert result.error == "Failed to index"

# --- Test Error Types ---

# Note: Testing the full TaskError union requires creating instances of each variant.
def test_resource_exhaustion_error_valid():
    error = ResourceExhaustionError(
        resource='context',
        message="Context limit exceeded",
        metrics={'used': 4001, 'limit': 4000},
        content="Partial text..."
    )
    assert error.type == 'RESOURCE_EXHAUSTION'
    assert error.resource == 'context'
    assert error.message == "Context limit exceeded"
    assert error.metrics == {'used': 4001, 'limit': 4000}
    assert error.content == "Partial text..."

def test_task_failure_error_valid():
    details = TaskFailureDetails(violations=["Schema mismatch"], script_exit_code=1)
    error = TaskFailureError(
        reason='output_format_failure',
        message="Output did not match expected format",
        notes={'task_id': '123'},
        details=details,
        content="Invalid output..."
    )
    assert error.type == 'TASK_FAILURE'
    assert error.reason == 'output_format_failure'
    assert error.message == "Output did not match expected format"
    assert error.notes == {'task_id': '123'}
    assert error.details == details
    assert error.content == "Invalid output..."

def test_invalid_output_error_valid():
    error = InvalidOutputError(
        message="Malformed JSON",
        content="{invalid json",
        violations=["Unexpected token 'i'"]
    )
    assert error.type == 'INVALID_OUTPUT'
    assert error.message == "Malformed JSON"
    assert error.content == "{invalid json"
    assert error.violations == ["Unexpected token 'i'"]

def test_validation_error_valid():
    error = ModelValidationError( # Use alias
        message="Input validation failed",
        path="user.email",
        invalidModel=True,
        content="user={'email': 'invalid'}"
    )
    assert error.type == 'VALIDATION_ERROR'
    assert error.message == "Input validation failed"
    assert error.path == "user.email"
    assert error.invalidModel is True
    assert error.content == "user={'email': 'invalid'}"

def test_xml_parse_error_valid():
    error = XMLParseError(
        message="Mismatched tag",
        location="Line 5, Column 10",
        content="<tag>...</error>"
    )
    assert error.type == 'XML_PARSE_ERROR'
    assert error.message == "Mismatched tag"
    assert error.location == "Line 5, Column 10"
    assert error.content == "<tag>...</error>"

# --- Test Context Management Types ---

def test_context_management_valid():
    cm = ContextManagement(
        inheritContext='subset',
        accumulateData=True,
        accumulationFormat='full_output',
        freshContext='disabled'
    )
    assert cm.inheritContext == 'subset'
    assert cm.accumulateData is True
    assert cm.accumulationFormat == 'full_output'
    assert cm.freshContext == 'disabled'

def test_context_management_defaults():
    cm = ContextManagement() # Use defaults
    assert cm.inheritContext == 'subset' # Default changed based on SUBTASK_CONTEXT_DEFAULTS rationale
    assert cm.accumulateData is False
    assert cm.accumulationFormat == 'notes_only'
    assert cm.freshContext == 'enabled'

def test_context_management_invalid():
    with pytest.raises(ValidationError):
        ContextManagement(inheritContext='invalid_value')
    with pytest.raises(ValidationError):
        ContextManagement(accumulationFormat='invalid_value')
    with pytest.raises(ValidationError):
        ContextManagement(freshContext='invalid_value')

def test_subtask_context_defaults():
    assert isinstance(SUBTASK_CONTEXT_DEFAULTS, ContextManagement)
    assert SUBTASK_CONTEXT_DEFAULTS.inheritContext == 'none'
    assert SUBTASK_CONTEXT_DEFAULTS.accumulateData is False
    assert SUBTASK_CONTEXT_DEFAULTS.accumulationFormat == 'notes_only'
    assert SUBTASK_CONTEXT_DEFAULTS.freshContext == 'enabled'

# --- Test Task Execution Types ---

def test_handler_config_valid():
    config = HandlerConfig(
        provider="anthropic",
        maxTurns=100,
        maxContextWindowFraction=0.75,
        defaultModel="claude-3-opus",
        systemPrompt="You are helpful.",
        tools=["file_access", "bash"]
    )
    assert config.provider == "anthropic"
    assert config.maxTurns == 100
    assert config.maxContextWindowFraction == 0.75
    assert config.defaultModel == "claude-3-opus"
    assert config.systemPrompt == "You are helpful."
    assert config.tools == ["file_access", "bash"]

def test_handler_config_defaults():
     config = HandlerConfig(
        provider="anthropic",
        maxTurns=100,
        maxContextWindowFraction=0.75,
        systemPrompt="You are helpful."
    )
     assert config.defaultModel is None
     assert config.tools is None

def test_handler_config_invalid():
    with pytest.raises(ValidationError):
         HandlerConfig(provider="anthropic", maxTurns=0, maxContextWindowFraction=0.75, systemPrompt="Hi") # maxTurns must be positive
    with pytest.raises(ValidationError):
         HandlerConfig(provider="anthropic", maxTurns=100, maxContextWindowFraction=0.0, systemPrompt="Hi") # fraction must be > 0
    with pytest.raises(ValidationError):
         HandlerConfig(provider="anthropic", maxTurns=100, maxContextWindowFraction=1.1, systemPrompt="Hi") # fraction must be <= 1

def test_task_result_valid():
    result = TaskResult(
        content="Final answer",
        status="COMPLETE",
        criteria="Accuracy > 90%",
        parsedContent={"answer": 42},
        notes={"steps": 5, "confidence": 0.95}
    )
    assert result.content == "Final answer"
    assert result.status == "COMPLETE"
    assert result.criteria == "Accuracy > 90%"
    assert result.parsedContent == {"answer": 42}
    assert result.notes == {"steps": 5, "confidence": 0.95}

def test_task_result_defaults():
     result = TaskResult(content="Output", status="FAILED")
     assert result.criteria is None
     assert result.parsedContent is None
     assert result.notes == {} # Default factory creates empty dict

def test_task_result_invalid():
     with pytest.raises(ValidationError):
         TaskResult(content="Output", status="INVALID_STATUS")

def test_context_generation_input_valid():
    input_data = ContextGenerationInput(
        templateDescription="Generate code",
        templateType="atomic",
        templateSubtype="code_generation",
        query="Create a python function",
        inputs={"language": "python", "task": "sort list"},
        inheritedContext="Previous context...",
        previousOutputs="Step 1 output..."
    )
    assert input_data.templateDescription == "Generate code"
    assert input_data.query == "Create a python function"
    assert input_data.inputs == {"language": "python", "task": "sort list"}
    assert input_data.inheritedContext == "Previous context..."
    assert input_data.previousOutputs == "Step 1 output..."
    assert input_data.matching_strategy is None # Check new field default

def test_context_generation_input_minimal():
    # Test with only optional fields provided
    input_data = ContextGenerationInput(query="Find relevant files")
    assert input_data.query == "Find relevant files"
    assert input_data.templateDescription is None
    assert input_data.inputs is None
    # ... check other fields are None ...

def test_context_generation_input_empty():
    # Test completely empty input
    input_data = ContextGenerationInput()
    assert input_data.query is None
    assert input_data.matching_strategy is None
    # ... check all fields are None ...

def test_context_generation_input_v5_with_strategy():
    """Test ContextGenerationInput v5.0 with valid matching_strategy."""
    input_data = ContextGenerationInput(query="test", matching_strategy='content')
    assert input_data.query == "test"
    assert input_data.matching_strategy == 'content'

    input_data_meta = ContextGenerationInput(query="test", matching_strategy='metadata')
    assert input_data_meta.matching_strategy == 'metadata'

def test_context_generation_input_v5_default_strategy():
    """Test ContextGenerationInput v5.0 defaults matching_strategy to None."""
    input_data = ContextGenerationInput(query="test")
    assert input_data.matching_strategy is None

def test_context_generation_input_v5_invalid_strategy():
    """Test ContextGenerationInput v5.0 raises error for invalid matching_strategy."""
    with pytest.raises(ValidationError):
        ContextGenerationInput(query="test", matching_strategy='invalid')
    with pytest.raises(ValidationError):
        ContextGenerationInput(query="test", matching_strategy=123)

# --- Test Aider Loop Specific Models ---

def test_development_plan_valid():
    """Test successful validation of DevelopmentPlan."""
    data = {
        "instructions": "1. Do this.\n2. Do that.",
        "files": ["src/main.py", "tests/test_main.py"],
        "test_command": "pytest tests/test_main.py"
    }
    plan = DevelopmentPlan.model_validate(data)
    assert plan.instructions == data["instructions"]
    assert plan.files == data["files"]
    assert plan.test_command == data["test_command"]

def test_development_plan_invalid_missing_fields():
    """Test DevelopmentPlan validation fails with missing required fields."""
    # test_command is optional, so this should NOT raise an error
    DevelopmentPlan.model_validate({"instructions": "...", "files": []})
    
    # These should raise errors for missing required fields
    with pytest.raises(ValidationError):
        DevelopmentPlan.model_validate({"instructions": "...", "test_command": "..."}) # Missing files
    with pytest.raises(ValidationError):
        DevelopmentPlan.model_validate({"files": [], "test_command": "..."}) # Missing instructions

def test_development_plan_invalid_types():
    """Test DevelopmentPlan validation fails with incorrect data types."""
    with pytest.raises(ValidationError): # instructions not string
        DevelopmentPlan.model_validate({"instructions": 123, "files": [], "test_command": "..."})
    with pytest.raises(ValidationError): # files not list
        DevelopmentPlan.model_validate({"instructions": "...", "files": "src/main.py", "test_command": "..."})
    with pytest.raises(ValidationError): # files list contains non-string
        DevelopmentPlan.model_validate({"instructions": "...", "files": ["src/main.py", 123], "test_command": "..."})
    with pytest.raises(ValidationError): # test_command not string
        DevelopmentPlan.model_validate({"instructions": "...", "files": [], "test_command": ["pytest"]})

def test_feedback_result_valid_success():
    """Test successful validation of FeedbackResult with SUCCESS."""
    data = {"status": "SUCCESS", "explanation": "Looks good!"}
    feedback = FeedbackResult.model_validate(data)
    assert feedback.status == "SUCCESS"
    assert feedback.next_prompt is None
    assert feedback.explanation == "Looks good!"

def test_feedback_result_valid_revise():
    """Test successful validation of FeedbackResult with REVISE."""
    data = {"status": "REVISE", "next_prompt": "Try adding error handling.", "explanation": "Missing edge case."}
    feedback = FeedbackResult.model_validate(data)
    assert feedback.status == "REVISE"
    assert feedback.next_prompt == "Try adding error handling."
    assert feedback.explanation == "Missing edge case."

def test_feedback_result_valid_abort():
    """Test successful validation of FeedbackResult with ABORT."""
    data = {"status": "ABORT", "explanation": "Cannot proceed."}
    feedback = FeedbackResult.model_validate(data)
    assert feedback.status == "ABORT"
    assert feedback.next_prompt is None
    assert feedback.explanation == "Cannot proceed."

def test_feedback_result_invalid_missing_fields():
    """Test FeedbackResult validation fails with missing required fields."""
    with pytest.raises(ValidationError):
        FeedbackResult.model_validate({}) # Missing status

    # Test case: status is REVISE but next_prompt is missing
    with pytest.raises(ValidationError, match="'next_prompt' is required when status is 'REVISE'"):
         FeedbackResult.model_validate({"status": "REVISE", "explanation": "Needs changes"})

    # Test case: status is REVISE and next_prompt is None (explicitly)
    with pytest.raises(ValidationError, match="'next_prompt' is required when status is 'REVISE'"):
         FeedbackResult.model_validate({"status": "REVISE", "next_prompt": None})

    # Test case: status is SUCCESS/ABORT, next_prompt can be None (should NOT raise error)
    FeedbackResult.model_validate({"status": "SUCCESS", "next_prompt": None})
    FeedbackResult.model_validate({"status": "ABORT", "next_prompt": None})

def test_feedback_result_invalid_types():
    """Test FeedbackResult validation fails with incorrect data types."""
    with pytest.raises(ValidationError): # status not valid literal
        FeedbackResult.model_validate({"status": "MAYBE"})
    with pytest.raises(ValidationError): # next_prompt not string when present
        FeedbackResult.model_validate({"status": "REVISE", "next_prompt": 123})
    with pytest.raises(ValidationError): # explanation not string when present
        FeedbackResult.model_validate({"status": "SUCCESS", "explanation": []})

# --- Test Iterative Loop Specific Models ---

class TestStructuredAnalysisResult:
    def test_structured_analysis_result_success_no_next(self):
        """Test valid success case, next_input can be None."""
        data = {
            "success": True,
            "analysis": "Everything looks great!",
            "next_input": None, # Explicitly None
            "new_files": ["new_feature.py"]
        }
        res = StructuredAnalysisResult.model_validate(data)
        assert res.success is True
        assert res.analysis == "Everything looks great!"
        assert res.next_input is None
        assert res.new_files == ["new_feature.py"]

        data_no_next_input_field = { # next_input field omitted entirely
            "success": True,
            "analysis": "Everything looks great!",
        }
        res2 = StructuredAnalysisResult.model_validate(data_no_next_input_field)
        assert res2.next_input is None # Default is None

    def test_structured_analysis_result_failure_requires_next_input(self):
        """Test valid failure case, next_input is provided."""
        data = {
            "success": False,
            "analysis": "Tests failed, need to revise.",
            "next_input": "Please fix the failing tests in test_feature.py.",
            "new_files": None # Explicitly None
        }
        res = StructuredAnalysisResult.model_validate(data)
        assert res.success is False
        assert res.analysis == "Tests failed, need to revise."
        assert res.next_input == "Please fix the failing tests in test_feature.py."
        assert res.new_files is None

        data_no_new_files_field = { # new_files field omitted entirely
            "success": False,
            "analysis": "Tests failed.",
            "next_input": "Revise."
        }
        res2 = StructuredAnalysisResult.model_validate(data_no_new_files_field)
        assert res2.new_files is None # Default is None

    def test_structured_analysis_result_failure_missing_next_input_raises_error(self):
        """Test failure case where next_input is missing raises ValidationError."""
        data_missing_next_input = {
            "success": False,
            "analysis": "This should fail validation."
            # next_input is missing
        }
        with pytest.raises(ValidationError, match="'next_input' is required when success is False"):
            StructuredAnalysisResult.model_validate(data_missing_next_input)

        data_next_input_is_none = {
            "success": False,
            "analysis": "This should also fail validation.",
            "next_input": None # Explicitly None when success is False
        }
        with pytest.raises(ValidationError, match="'next_input' is required when success is False"):
            StructuredAnalysisResult.model_validate(data_next_input_is_none)

    def test_structured_analysis_result_invalid_types(self):
        """Test validation failure for incorrect data types."""
        with pytest.raises(ValidationError): # success not bool
            StructuredAnalysisResult.model_validate({"success": 123, "analysis": "..."}) # Use 123 instead of "true"
        with pytest.raises(ValidationError): # analysis not string
            StructuredAnalysisResult.model_validate({"success": True, "analysis": 123})
        # --- UPDATE INVALID TYPE FOR next_input and new_files ---
        with pytest.raises(ValidationError): # next_input not string (when success=False)
            StructuredAnalysisResult.model_validate({"success": False, "analysis": "...", "next_input": ["list"]})
        with pytest.raises(ValidationError): # new_files not list
            StructuredAnalysisResult.model_validate({"success": True, "analysis": "...", "new_files": "a_string"})
        with pytest.raises(ValidationError): # new_files list contains non-string
            StructuredAnalysisResult.model_validate({"success": True, "analysis": "...", "new_files": ["file.txt", 123]})

    def test_structured_analysis_result_minimal_valid_success(self):
        """Test minimal valid success case."""
        data = {"success": True, "analysis": "Minimal success."}
        res = StructuredAnalysisResult.model_validate(data)
        assert res.success is True
        assert res.analysis == "Minimal success."
        assert res.next_input is None
        assert res.new_files is None

    def test_structured_analysis_result_minimal_valid_failure(self):
        """Test minimal valid failure case."""
        data = {"success": False, "analysis": "Minimal failure.", "next_input": "Fix it."}
        res = StructuredAnalysisResult.model_validate(data)
        assert res.success is False
        assert res.analysis == "Minimal failure."
        assert res.next_input == "Fix it."
        assert res.new_files is None
