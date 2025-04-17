import pytest
from unittest.mock import MagicMock, patch, ANY
from typing import Dict, Any

# Import the class to test
from src.task_system.task_system import TaskSystem

# Import necessary types
from src.task_system.ast_nodes import SubtaskRequest
from src.task_system.template_utils import Environment
from src.system.errors import TaskError, create_task_failure, INPUT_VALIDATION_FAILURE, UNEXPECTED_ERROR

# Define TaskResult type hint
TaskResult = Dict[str, Any]


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

        # Act: Call the method
        result = task_system_instance.execute_subtask_directly(sample_request)

        # Assert: Check for failure due to template not found
        assert result["status"] == "FAILED"
        assert "Template not found" in result["content"]
        assert result["notes"]["error"]["reason"] == INPUT_VALIDATION_FAILURE

    # Patch Environment where it's imported in task_system.py
    @patch('src.task_system.task_system.Environment')
    def test_environment_creation(self, mock_env_class, task_system_instance, sample_request, sample_template, mock_evaluator):
        # Arrange:
        task_system_instance.find_template.return_value = sample_template
        # Mock the return values for Environment instantiation and extend
        mock_base_env = MagicMock()
        mock_extended_env = MagicMock()
        mock_env_class.return_value = mock_base_env
        mock_base_env.extend.return_value = mock_extended_env

        # Act: Call the method
        task_system_instance.execute_subtask_directly(sample_request)

        # Assert:
        # 1. Check that Environment was instantiated for the base environment
        mock_env_class.assert_called_once_with({}) # Check base env creation
        # 2. Check that extend was called on the base environment with request inputs
        mock_base_env.extend.assert_called_once_with(sample_request.inputs)
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

        # Act: Call the method
        result = task_system_instance.execute_subtask_directly(sample_request)

        # Assert: Check notes in the mock success result
        assert result["status"] == "COMPLETE" # Mock status
        assert "Using 2 explicit files" in result["content"] # Check mock content
        assert result["notes"]["explicit_paths_used"] is True
        assert result["notes"]["context_files_count"] == 2
        # Evaluator is not called in Phase 1, so no call assertion needed

    def test_context_explicit_template_paths(self, task_system_instance, sample_request, sample_template, mock_evaluator):
        # Arrange:
        sample_request.file_paths = [] # No paths in request
        sample_template["file_paths"] = ["/path/tmpl1.py"] # Paths defined in template
        task_system_instance.find_template.return_value = sample_template
        # No need to mock evaluator call for Phase 1 result check

        # Act: Call the method
        result = task_system_instance.execute_subtask_directly(sample_request)

        # Assert: Check notes in the mock success result
        assert result["status"] == "COMPLETE"
        assert "Using 1 explicit files" in result["content"]
        assert result["notes"]["explicit_paths_used"] is True
        assert result["notes"]["context_files_count"] == 1
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

        # Act: Call the method
        result = task_system_instance.execute_subtask_directly(sample_request)

        # Assert: Check notes in the mock success result
        assert result["status"] == "COMPLETE"
        assert "No explicit file context provided" in result["content"]
        assert result["notes"]["explicit_paths_used"] is False
        assert result["notes"]["context_files_count"] == 0
        # Crucially, assert that MemorySystem was NOT called for context (it isn't used here)
        # task_system_instance.memory_system.get_relevant_context_for.assert_not_called()
        # Evaluator is not called in Phase 1

    # Test error handling *within* execute_subtask_directly, before evaluator call
    # Example: Error during template finding (already covered by test_template_not_found)
    # Example: Error during Environment creation (less likely with basic dicts)

    # Test error handling for unexpected errors *before* the mock return
    @patch('src.task_system.task_system.Environment')
    def test_error_handling_unexpected_before_eval(self, mock_env_class, task_system_instance, sample_request, sample_template):
        # Arrange:
        task_system_instance.find_template.return_value = sample_template
        # Make Environment creation raise an unexpected error
        env_error = TypeError("Unexpected environment issue")
        mock_env_class.side_effect = env_error

        # Act: Call the method
        result = task_system_instance.execute_subtask_directly(sample_request)

        # Assert: Check for formatted unexpected error
        assert result["status"] == "FAILED"
        assert "An unexpected error occurred during direct execution" in result["content"]
        assert result["notes"]["error"]["reason"] == UNEXPECTED_ERROR
        assert result["notes"]["error"]["details"]["exception_type"] == "TypeError"

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
