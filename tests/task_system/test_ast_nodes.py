"""Tests for AST node implementations."""
import pytest
from task_system.ast_nodes import ArgumentNode, FunctionCallNode

class TestArgumentNode:
    """Tests for the ArgumentNode class."""
    
    def test_positional_argument_initialization(self):
        """Test initializing a positional argument."""
        arg = ArgumentNode("test_value")
        
        assert arg.type == "argument"
        assert arg.value == "test_value"
        assert arg.name is None
        assert arg.is_positional() is True
        assert arg.is_named() is False
    
    def test_named_argument_initialization(self):
        """Test initializing a named argument."""
        arg = ArgumentNode("test_value", name="param1")
        
        assert arg.type == "argument"
        assert arg.value == "test_value"
        assert arg.name == "param1"
        assert arg.is_positional() is False
        assert arg.is_named() is True
    
    def test_argument_representation(self):
        """Test string representation of arguments."""
        pos_arg = ArgumentNode(42)
        named_arg = ArgumentNode("hello", name="greeting")
        
        # Test __repr__
        assert repr(pos_arg) == "ArgumentNode(value=42)"
        assert repr(named_arg) == "ArgumentNode(name='greeting', value='hello')"
        
        # Test __str__
        assert str(pos_arg) == "42"
        assert str(named_arg) == "greeting=hello"
    
    def test_different_value_types(self):
        """Test argument with different value types."""
        # Integer value
        assert ArgumentNode(123).value == 123
        
        # String value
        assert ArgumentNode("test").value == "test"
        
        # Boolean value
        assert ArgumentNode(True).value is True
        
        # None value
        assert ArgumentNode(None).value is None
        
        # List value
        list_value = [1, 2, 3]
        assert ArgumentNode(list_value).value == list_value
        
        # Dict value
        dict_value = {"key": "value"}
        assert ArgumentNode(dict_value).value == dict_value


class TestFunctionCallNode:
    """Tests for the FunctionCallNode class."""
    
    def test_function_call_initialization(self):
        """Test initializing a function call node."""
        args = [
            ArgumentNode(10),
            ArgumentNode("test", name="param")
        ]
        func_call = FunctionCallNode("test_function", args)
        
        assert func_call.type == "call"
        assert func_call.template_name == "test_function"
        assert func_call.arguments == args
        assert len(func_call.arguments) == 2
    
    def test_function_call_representation(self):
        """Test string representation of function calls."""
        args = [
            ArgumentNode(10),
            ArgumentNode("test", name="param")
        ]
        func_call = FunctionCallNode("test_function", args)
        
        # Test __repr__
        assert "FunctionCallNode" in repr(func_call)
        assert "template_name='test_function'" in repr(func_call)
        assert "ArgumentNode" in repr(func_call)
        
        # Test __str__
        assert str(func_call) == "test_function(10, param=test)"
    
    def test_argument_access_methods(self):
        """Test methods for accessing arguments."""
        # Create a function call with mixed argument types
        args = [
            ArgumentNode(1),
            ArgumentNode(2),
            ArgumentNode("hello", name="greeting"),
            ArgumentNode(42, name="answer")
        ]
        func_call = FunctionCallNode("test_function", args)
        
        # Test getting positional arguments
        pos_args = func_call.get_positional_arguments()
        assert len(pos_args) == 2
        assert pos_args[0].value == 1
        assert pos_args[1].value == 2
        
        # Test getting named arguments
        named_args = func_call.get_named_arguments()
        assert len(named_args) == 2
        assert "greeting" in named_args
        assert "answer" in named_args
        assert named_args["greeting"].value == "hello"
        assert named_args["answer"].value == 42
        
        # Test has_argument method
        assert func_call.has_argument("greeting") is True
        assert func_call.has_argument("answer") is True
        assert func_call.has_argument("unknown") is False
        
        # Test get_argument method
        greeting_arg = func_call.get_argument("greeting")
        assert greeting_arg is not None
        assert greeting_arg.value == "hello"
        
        answer_arg = func_call.get_argument("answer")
        assert answer_arg is not None
        assert answer_arg.value == 42
        
        unknown_arg = func_call.get_argument("unknown")
        assert unknown_arg is None
    
    def test_empty_arguments_list(self):
        """Test function call with no arguments."""
        func_call = FunctionCallNode("empty_function", [])
        
        assert func_call.template_name == "empty_function"
        assert len(func_call.arguments) == 0
        assert func_call.get_positional_arguments() == []
        assert func_call.get_named_arguments() == {}
        assert func_call.has_argument("any") is False
        assert func_call.get_argument("any") is None
        assert str(func_call) == "empty_function()"
