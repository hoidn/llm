"""
Unit tests for system-wide Pydantic models defined in src.system.models.
"""
import pytest
from pydantic import ValidationError
from datetime import datetime
from typing import List, Optional, Literal # Added imports

import pytest
from pydantic import ValidationError
from datetime import datetime
from typing import List, Optional, Literal, Any, Dict # Added Any, Dict
from enum import Enum # Added Enum

# Attempt to import models from the correct location
try:
    from src.system.models import (
        TurnMetrics, ContextMetrics, ResourceMetrics, ResourceLimits,
        MatchItemContentType, MatchItem, AssociativeMatchResult, DataContext, WorkflowStepDefinition, # Added new models, removed MatchTuple
        TaskFailureReason, ResourceExhaustionError, TaskFailureDetails, TaskFailureError,
        InvalidOutputError, ValidationError as ModelValidationError, XMLParseError, TaskError, # Alias ValidationError
        ContextManagement, SUBTASK_CONTEXT_DEFAULTS,
        ReturnStatus, TaskType, AtomicTaskSubtype,
        HandlerConfig, TaskResult, ContextGenerationInput, HistoryConfigSettings, # Added HistoryConfigSettings
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

# Placeholder for MatchItemContentType if you implement it
# from src.system.models import MatchItemContentType 

def test_match_item_instantiation_valid():
    item = MatchItem(id="item1", content="some text", relevance_score=0.75, content_type="file_content")
    assert item.id == "item1"
    assert item.content == "some text"
    assert item.relevance_score == 0.75
    assert item.content_type == "file_content" # or MatchItemContentType.FILE_CONTENT.value
    assert item.source_path is None
    assert item.metadata is None

def test_match_item_relevance_score_constraints():
    MatchItem(id="i", content="c", relevance_score=0.0, content_type="ct") # Valid
    MatchItem(id="i", content="c", relevance_score=1.0, content_type="ct") # Valid
    with pytest.raises(ValidationError):
        MatchItem(id="i", content="c", relevance_score=-0.1, content_type="ct")
    with pytest.raises(ValidationError):
        MatchItem(id="i", content="c", relevance_score=1.1, content_type="ct")

def test_match_item_optional_fields_default_to_none():
    item = MatchItem(id="item1", content="some text", relevance_score=0.75, content_type="file_content")
    assert item.source_path is None
    assert item.metadata is None
    item_with_opts = MatchItem(id="item2", content="c2", relevance_score=0.5, content_type="ct2", source_path="/path", metadata={"key": "val"})
    assert item_with_opts.source_path == "/path"
    assert item_with_opts.metadata == {"key": "val"}

def test_match_item_invalid_types_raise_validation_error():
    with pytest.raises(ValidationError): # score wrong type
        MatchItem(id="i", content="c", relevance_score="high", content_type="ct")
    with pytest.raises(ValidationError): # content_type missing
        MatchItem(id="i", content="c", relevance_score=0.5)
    # Add more for other fields as necessary

# Add if MatchItemContentType Enum is used:
# def test_match_item_with_content_type_enum():
#     item = MatchItem(id="item1", content="some text", relevance_score=0.75, content_type=MatchItemContentType.CODE_CHUNK)
#     assert item.content_type == MatchItemContentType.CODE_CHUNK.value
#     with pytest.raises(ValidationError):
#         MatchItem(id="i", content="c", relevance_score=0.5, content_type="invalid_enum_value")

def test_associative_match_result_valid():
    # Replace MatchTuple with MatchItem
    matches = [
        MatchItem(id="f1.py", content="content1", relevance_score=0.8, content_type="file_content"),
        MatchItem(id="f2.py", content="content2", relevance_score=0.7, content_type="file_content")
    ]
    result = AssociativeMatchResult(context_summary="Summary", matches=matches, error=None)
    assert result.context_summary == "Summary"
    assert result.matches == matches
    assert result.error is None
    assert result.matches[0].id == "f1.py"


def test_associative_match_result_with_error():
    result = AssociativeMatchResult(context_summary="", matches=[], error="Failed to index")
    assert result.error == "Failed to index"

def test_associative_match_result_empty_matches():
    result = AssociativeMatchResult(context_summary="Summary", matches=[])
    assert result.matches == []

def test_associative_match_result_invalid_match_item_in_list():
    # Case 1: List contains a dictionary that CANNOT be coerced to MatchItem
    # (e.g., missing required 'content' field)
    with pytest.raises(ValidationError, match="content\n  Field required"): # Check for specific error message part
        AssociativeMatchResult(context_summary="s", matches=[
            {"id": "item1", "relevance_score": 0.5, "content_type": "text"} # Missing 'content'
        ])

    # Case 2: List contains a valid MatchItem and an invalid dictionary
    # (e.g., one that is just an integer, or a dict with wrong field types)
    valid_item = MatchItem(id="item1", content="c", relevance_score=0.5, content_type="text")
    with pytest.raises(ValidationError): # Pydantic will try to parse each item in list
        AssociativeMatchResult(context_summary="s", matches=[valid_item, {"id": "item2", "content": 123, "relevance_score": "high", "content_type": True}])

    # Case 3: List contains something completely not a MatchItem or dict
    with pytest.raises(ValidationError):
        AssociativeMatchResult(context_summary="s", matches=[123]) # A number instead of a MatchItem or dict


# --- Test DataContext ---
def test_data_context_instantiation_valid():
    items = [MatchItem(id="item1", content="c1", relevance_score=0.8, content_type="t1")]
    dt_now = datetime.now().isoformat()
    context = DataContext(retrieved_at=dt_now, items=items, source_query="test query")
    assert context.retrieved_at == dt_now
    assert context.items == items
    assert context.source_query == "test query"
    assert context.overall_summary is None
    assert context.metadata is None

def test_data_context_optional_fields_default_to_none():
    dt_now = datetime.now().isoformat()
    context = DataContext(retrieved_at=dt_now, items=[])
    assert context.source_query is None
    assert context.overall_summary is None
    assert context.metadata is None

def test_data_context_requires_match_items_in_list():
    dt_now = datetime.now().isoformat()
    with pytest.raises(ValidationError):
        DataContext(retrieved_at=dt_now, items=[{"id": "not_a_match_item"}])

def test_data_context_invalid_types_raise_validation_error():
    with pytest.raises(ValidationError): # retrieved_at missing
        DataContext(items=[])
    # Add more for other fields


# --- Test WorkflowStepDefinition ---
def test_workflow_step_definition_instantiation_valid():
    step = WorkflowStepDefinition(task_name="task:run", output_name="step1_out", static_inputs={"p1": "v1"})
    assert step.task_name == "task:run"
    assert step.output_name == "step1_out"
    assert step.static_inputs == {"p1": "v1"}
    assert step.dynamic_input_mappings is None

def test_workflow_step_definition_optional_fields_default_to_none():
    step = WorkflowStepDefinition(task_name="task:run", output_name="step1_out")
    assert step.static_inputs is None
    assert step.dynamic_input_mappings is None

def test_workflow_step_definition_invalid_types_raise_validation_error():
    with pytest.raises(ValidationError): # task_name missing
        WorkflowStepDefinition(output_name="out")
    # Add more for other fields


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

# --- Test HistoryConfigSettings ---

def test_history_config_settings_defaults():
    """Test HistoryConfigSettings defaults."""
    settings = HistoryConfigSettings()
    assert settings.use_session_history is True
    assert settings.history_turns_to_include is None
    assert settings.record_in_session_history is True

def test_history_config_settings_custom_values():
    """Test HistoryConfigSettings with custom values."""
    settings = HistoryConfigSettings(
        use_session_history=False,
        history_turns_to_include=5,
        record_in_session_history=False
    )
    assert settings.use_session_history is False
    assert settings.history_turns_to_include == 5
    assert settings.record_in_session_history is False

def test_history_config_settings_invalid_types():
    """Test HistoryConfigSettings with invalid data types."""
    with pytest.raises(ValidationError):
        HistoryConfigSettings(use_session_history="not_a_bool")
    with pytest.raises(ValidationError):
        HistoryConfigSettings(history_turns_to_include="not_an_int")
    with pytest.raises(ValidationError):
        HistoryConfigSettings(history_turns_to_include=-1) # Must be PositiveInt
    with pytest.raises(ValidationError):
        HistoryConfigSettings(record_in_session_history="not_a_bool")

def test_history_config_settings_partial_override():
    """Test HistoryConfigSettings with partial overrides, ensuring defaults apply."""
    settings = HistoryConfigSettings(use_session_history=False)
    assert settings.use_session_history is False
    assert settings.history_turns_to_include is None # Default
    assert settings.record_in_session_history is True  # Default

    settings2 = HistoryConfigSettings(history_turns_to_include=10)
    assert settings2.use_session_history is True # Default
    assert settings2.history_turns_to_include == 10
    assert settings2.record_in_session_history is True # Default

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
