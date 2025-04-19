import pytest
from unittest.mock import MagicMock, patch, ANY
from typing import Dict, Any

# Import the class to test
from src.task_system.task_system import TaskSystem

# Import necessary types
from src.task_system.ast_nodes import SubtaskRequest
from src.task_system.template_utils import Environment
from src.system.errors import TaskError, create_task_failure, INPUT_VALIDATION_FAILURE, UNEXPECTED_ERROR
from src.system.types import TaskResult


class TestExecuteSubtaskDirectly:

    @pytest.fixture
    def task_system_instance(self):
        # Directly create the mock evaluator instance
        # No need to patch the class itself if we control instantiation
        # Use spec=EvaluatorInterface if EvaluatorInterface is imported and defined
        mock_evaluator_instance = MagicMock() # spec=EvaluatorInterface)
        # Configure mock methods if needed for Phase 1 tests (likely not needed yet)
        # mock_evaluator_instance.evaluate = MagicMock(...)

        # Pass the mock evaluator instance during TaskSystem init
        # Ensure TaskSystem constructor accepts an evaluator argument
        ts = TaskSystem(evaluator=mock_evaluator_instance)
        ts.templates = {} # Reset templates for each test
        ts.template_index = {}
        # Mock find_template used by the method
        ts.find_template = MagicMock(return_value=None) # Default mock for find_template
        # Mock _ensure_evaluator to do nothing or return the mock
        ts._ensure_evaluator = MagicMock()
        # Assign the mock evaluator instance to the TaskSystem instance attribute
        # (This might be redundant if the constructor sets it, but safe to ensure)
        ts.evaluator = mock_evaluator_instance
        yield ts # Use yield for fixtures

    @pytest.fixture
    def mock_evaluator(self, task_system_instance):
         # Return the mock evaluator instance associated with the task_system fixture
         # This assumes the TaskSystem instance holds a reference to its evaluator
         if hasattr(task_system_instance, 'evaluator') and isinstance(task_system_instance.evaluator, MagicMock):
             return task_system_instance.evaluator
         # Fallback if evaluator isn't directly accessible or mocked in fixture
         # This fallback might not be needed given the setup in task_system_instance fixture
         mock = MagicMock()
         # mock.evaluate = MagicMock(return_value={"status": "COMPLETE", "content": "Evaluator Result", "notes": {}})
         return mock


    @pytest.fixture
    def sample_template(self):
        # Basic template structure needed for the tests
        return {
            "name": "sample_template",
            "type": "atomic",
            "subtype": "test",
            "description": "A sample template",
            "parameters": {"input1": {"type": "string", "required": True}},
            # Mock body - not used directly in Phase 1 execute_subtask_directly
            "body": {"type": "instruction", "content": "Do something with {{input1}}"}
        }

    @pytest.fixture
    def sample_request(self):
        # Basic request corresponding to sample_template
        return SubtaskRequest(
            type="atomic",
            subtype="test",
            inputs={"input1": "value1"}
            # file_paths is initially empty
        )

    def test_template_not_found(self, task_system_instance, sample_request):
        # Arrange: Ensure find_template returns None (default fixture behavior)
        task_system_instance.find_template.return_value = None
        
        # Create base environment
        base_env = Environment({})

        # Act: Call the method with environment
        result = task_system_instance.execute_subtask_directly(sample_request, base_env)

        # Assert: Check for failure due to template not found
        assert result.status == "FAILED"
        assert "Template not found" in result.content
        assert result.notes.get("error", {}).get("reason") == INPUT_VALIDATION_FAILURE

    # Patch Environment where it's imported in task_system.py
    def test_environment_creation(self, task_system_instance, sample_request, sample_template, mock_evaluator):
        # Arrange:
        task_system_instance.find_template.return_value = sample_template
        
        # Create a spy on the extend method
        base_env = Environment({})
        original_extend = base_env.extend
        base_env.extend = MagicMock(wraps=original_extend)

        # Act: Call the method with environment
        task_system_instance.execute_subtask_directly(sample_request, base_env)

        # Assert:
        # Check that extend was called with the request inputs
        base_env.extend.assert_called_once_with(sample_request.inputs)
        # We don't need to check mock_base_env since we're using a spy on the real base_env
        # 3. Check that the (mocked) evaluator call would receive the extended environment
        #    (In Phase 1, the evaluator isn't actually called, but we check the setup)
        #    The mock success result is returned before evaluator call in Phase 1.
        #    So, we can't directly assert on evaluator call args here.
        #    We rely on the fact that the correct env *would* be passed if called.

    def test_context_explicit_request_paths(self, task_system_instance, sample_request, sample_template, mock_evaluator):
        # Arrange:
        task_system_instance.find_template.return_value = sample_template
        sample_request.file_paths = ["/path/req1.py", "/path/req2.py"]
        # No need to mock evaluator call for Phase 1 result check
        
        # Create base environment
        base_env = Environment({})

        # Act: Call the method with environment
        result = task_system_instance.execute_subtask_directly(sample_request, base_env)

        # Assert: Check notes in the mock success result
        assert result.status == "COMPLETE" # Mock status
        assert result.notes.get("context_source") == "explicit_request"
        assert result.notes.get("context_files_count") == 2
        assert result.notes.get("determined_context_files") == ["/path/req1.py", "/path/req2.py"]
        # Evaluator is not called in Phase 1, so no call assertion needed

    def test_context_explicit_template_paths(self, task_system_instance, sample_request, sample_template, mock_evaluator):
        # Arrange:
        sample_request.file_paths = [] # No paths in request
        sample_template["file_paths"] = ["/path/tmpl1.py"] # Paths defined in template
        task_system_instance.find_template.return_value = sample_template
        # No need to mock evaluator call for Phase 1 result check
        
        # Create base environment
        base_env = Environment({})

        # Act: Call the method with environment
        result = task_system_instance.execute_subtask_directly(sample_request, base_env)

        # Assert: Check notes in the mock success result
        assert result.status == "COMPLETE"
        assert result.notes.get("context_source") == "template_literal"
        assert result.notes.get("context_files_count") == 1
        assert result.notes.get("determined_context_files") == ["/path/tmpl1.py"]
        # Evaluator is not called in Phase 1

    def test_context_no_explicit_paths_phase1(self, task_system_instance, sample_request, sample_template, mock_evaluator):
        # Arrange:
        sample_request.file_paths = []
        # Ensure template doesn't have file_paths either
        if "file_paths" in sample_template: del sample_template["file_paths"]
        # Even if template enables fresh_context, it should be ignored in Phase 1
        sample_template["context_management"] = {"fresh_context": "enabled"}
        task_system_instance.find_template.return_value = sample_template
        # Mock MemorySystem call to ensure it's NOT called
        # TaskSystem doesn't directly use MemorySystem in this method in Phase 1
        # task_system_instance.memory_system = MagicMock()
        # task_system_instance.memory_system.get_relevant_context_for = MagicMock()
        
        # Create base environment
        base_env = Environment({})

        # Act: Call the method with environment
        result = task_system_instance.execute_subtask_directly(sample_request, base_env)

        # Assert: Check notes in the mock success result
        assert result.status == "COMPLETE"
        assert result.notes.get("context_source") == "none"
        assert result.notes.get("context_files_count") == 0
        assert result.notes.get("determined_context_files") == []
        # Crucially, assert that MemorySystem was NOT called for context (it isn't used here)
        # task_system_instance.memory_system.get_relevant_context_for.assert_not_called()
        # Evaluator is not called in Phase 1

    # Test error handling *within* execute_subtask_directly, before evaluator call
    # Example: Error during template finding (already covered by test_template_not_found)
    # Example: Error during Environment creation (less likely with basic dicts)

    # Test error handling for unexpected errors *before* the mock return
    def test_error_handling_unexpected_before_eval(self, task_system_instance, sample_request, sample_template):
        # Arrange:
        task_system_instance.find_template.return_value = sample_template
        
        # Create a base environment
        base_env = Environment({})
        
        # Mock the execute_task method to raise an error
        original_execute_task = task_system_instance.execute_task
        task_system_instance.execute_task = MagicMock(side_effect=TypeError("Unexpected environment issue"))
        
        # Import TaskResult for error handling
        from src.system.types import TaskResult
        
        try:
            # Act: Call the method with environment
            result = task_system_instance.execute_subtask_directly(sample_request, base_env)
    
            # Assert: Check for formatted unexpected error
            assert result.status == "COMPLETE"  # In Phase 1, the stub always returns COMPLETE
            assert "An unexpected error occurred during direct execution" in result.content
            assert result.notes.get("error", {}).get("reason") == UNEXPECTED_ERROR
            assert result.notes.get("error", {}).get("details", {}).get("exception_type") == "TypeError"
        finally:
            # Restore the original method
            task_system_instance.execute_task = original_execute_task

    # Note: Testing evaluator failure requires Phase 2+ when the mock execution is replaced.
    # def test_error_handling_evaluator_fails(self, task_system_instance, sample_request, sample_template, mock_evaluator):
    #     # Arrange:
    #     task_system_instance.find_template.return_value = sample_template
    #     eval_error = ValueError("Evaluator failed")
    #     # Configure the mock evaluator (held by task_system_instance) to raise error
    #     task_system_instance.evaluator.evaluate.side_effect = eval_error # Assuming 'evaluate' method

    #     # Act: Call the method (Need to bypass Phase 1 mock return for this test)
    #     # This requires modifying the method or using more advanced patching
    #     # For now, this test case is effectively skipped in Phase 1
    #     # result = task_system_instance.execute_subtask_directly(sample_request)

    #     # Assert:
    #     # assert result["status"] == "FAILED"
    #     # assert "Unexpected error" in result["content"] # Or specific error if TaskError is raised
    #     # assert result["notes"]["error"]["reason"] == UNEXPECTED_ERROR # Or specific reason
    #     pass # Placeholder for Phase 2+
