"""Integration tests for the Evaluator component with other systems."""
from typing import Any, Dict, List, Optional
import pytest
from unittest.mock import MagicMock

from task_system.ast_nodes import ArgumentNode, FunctionCallNode
from task_system.template_utils import Environment
from task_system.task_system import TaskSystem
from evaluator.evaluator import Evaluator

class TestInputOutputBinding:
    """Tests for input-output binding functionality."""
    
    def test_input_output_binding_integration(self):
        """Test input-output binding across multiple components."""
        # Create TaskSystem with mock components
        task_system = TaskSystem()
        evaluator = Evaluator(task_system)
        task_system.evaluator = evaluator
        
        # Register test templates
        task_system.register_template({
            "name": "get_items",
            "type": "atomic",
            "subtype": "test",
            "parameters": {},
            "output_format": {"type": "json", "schema": "array"}
        })
        
        task_system.register_template({
            "name": "get_item",
            "type": "atomic",
            "subtype": "test",
            "parameters": {"index": {"type": "integer", "required": True}},
            "output_format": {"type": "json", "schema": "object"}
        })
        
        # Mock execute_task to return test data
        task_system.execute_task = MagicMock()
        from system.types import TaskResult
        task_system.execute_task.side_effect = lambda task_type, task_subtype, inputs, **kwargs: (
            TaskResult(content='[{"id": 1, "name": "first"}, {"id": 2, "name": "second"}]', status="COMPLETE", notes={})
            if task_subtype == "test" and task_type == "atomic" and "index" not in inputs else
            TaskResult(content=f'{{"id": {inputs["index"]}, "name": "item{inputs["index"]}"}}', status="COMPLETE", notes={})
        )
        
        # Create test environment
        env = Environment({"index": 1})
        
        # Test function call with plain argument
        call1 = FunctionCallNode("get_items", [])
        result1 = evaluator.evaluateFunctionCall(call1, env)
        
        assert "parsedContent" in result1.notes
        assert isinstance(result1.notes["parsedContent"], list)
        assert len(result1.notes["parsedContent"]) == 2
        
        # Now test a function call using the result of the previous call
        # First store the result in the environment (since we're not implementing automatic storage)
        env.bindings["result"] = result1
        
        # Create an argument using array indexing
        arg = ArgumentNode("{{result.parsedContent[0].id}}")
        call2 = FunctionCallNode("get_item", [arg])
        
        # Execute the second function call
        result2 = evaluator.evaluateFunctionCall(call2, env)
        
        # Verify the result
        assert "parsedContent" in result2.notes
        assert result2.notes["parsedContent"]["id"] == 1
