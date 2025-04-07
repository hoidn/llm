"""Tests for template utility functions."""
import pytest
from unittest.mock import MagicMock
from task_system.template_utils import (
    resolve_parameters,
    ensure_template_compatibility,
    get_preferred_model,
    Environment,
    substitute_variables,
    resolve_template_variables,
    detect_function_calls,
    parse_function_call,
    evaluate_arguments,
    bind_arguments_to_parameters,
    resolve_function_calls,
    translate_function_call_to_ast
)
from task_system.ast_nodes import FunctionCallNode, ArgumentNode

class TestResolveParameters:
    """Tests for the resolve_parameters function."""
    
    def test_standard_parameters(self):
        """Test resolving parameters with valid inputs."""
        template = {
            "parameters": {
                "query": {"type": "string", "required": True},
                "max_results": {"type": "integer", "default": 10}
            }
        }
        
        args = {"query": "test query"}
        result = resolve_parameters(template, args)
        
        assert result["query"] == "test query"
        assert result["max_results"] == 10  # Default value applied
    
    def test_all_parameters_provided(self):
        """Test when all parameters are provided by the caller."""
        template = {
            "parameters": {
                "query": {"type": "string", "required": True},
                "max_results": {"type": "integer", "default": 10}
            }
        }
        
        args = {"query": "test query", "max_results": 20}
        result = resolve_parameters(template, args)
        
        assert result["query"] == "test query"
        assert result["max_results"] == 20  # User-provided value used instead of default
    
    def test_missing_required_parameter(self):
        """Test error when required parameter is missing."""
        template = {
            "parameters": {
                "query": {"type": "string", "required": True},
                "max_results": {"type": "integer", "default": 10}
            }
        }
        
        args = {}  # Missing required 'query' parameter
        
        with pytest.raises(ValueError) as excinfo:
            resolve_parameters(template, args)
        
        assert "Missing required parameter: query" in str(excinfo.value)
    
    def test_type_validation_string(self):
        """Test type validation for string parameters."""
        template = {
            "parameters": {
                "query": {"type": "string", "required": True}
            }
        }
        
        # Invalid type: number instead of string
        args = {"query": 123}
        
        with pytest.raises(ValueError) as excinfo:
            resolve_parameters(template, args)
        
        assert "expected type 'string'" in str(excinfo.value)
    
    def test_type_validation_integer(self):
        """Test type validation for integer parameters."""
        template = {
            "parameters": {
                "count": {"type": "integer", "required": True}
            }
        }
        
        # Invalid type: string instead of integer
        args = {"count": "10"}
        
        with pytest.raises(ValueError) as excinfo:
            resolve_parameters(template, args)
        
        assert "expected type 'integer'" in str(excinfo.value)
    
    def test_backward_compatibility(self):
        """Test backward compatibility with templates without parameters."""
        template = {}  # No parameters defined
        args = {"query": "test", "max_results": 5}
        
        # Should return args as-is
        result = resolve_parameters(template, args)
        
        assert result == args


class TestEnsureTemplateCompatibility:
    """Tests for the ensure_template_compatibility function."""
    
    def test_minimal_template_enhancement(self):
        """Test enhancing a minimal template with required fields."""
        minimal_template = {
            "type": "atomic",
            "subtype": "test"
        }
        
        enhanced = ensure_template_compatibility(minimal_template)
        
        # Check that all required fields were added
        assert "name" in enhanced
        assert enhanced["name"] == "atomic_test"
        assert "parameters" in enhanced
        assert "model" in enhanced
        assert "returns" in enhanced
    
    def test_convert_inputs_to_parameters(self):
        """Test converting legacy 'inputs' to structured 'parameters'."""
        legacy_template = {
            "type": "atomic",
            "subtype": "test",
            "inputs": {
                "query": "Search query",
                "limit": "Maximum results"
            }
        }
        
        enhanced = ensure_template_compatibility(legacy_template)
        
        # Check that inputs were converted to parameters
        assert "parameters" in enhanced
        assert "query" in enhanced["parameters"]
        assert enhanced["parameters"]["query"]["type"] == "string"
        assert enhanced["parameters"]["query"]["description"] == "Search query"
        assert enhanced["parameters"]["query"]["required"] is True
    
    def test_simple_model_to_structured(self):
        """Test converting simple string model to structured format."""
        template = {
            "type": "atomic",
            "subtype": "test",
            "model": "claude-3"
        }
        
        enhanced = ensure_template_compatibility(template)
        
        # Check that model was converted to structured format
        assert isinstance(enhanced["model"], dict)
        assert enhanced["model"]["preferred"] == "claude-3"
        assert "fallback" in enhanced["model"]
    
    def test_preserve_existing_fields(self):
        """Test that existing fields are preserved."""
        template = {
            "type": "atomic",
            "subtype": "test",
            "name": "custom_name",
            "description": "Custom description",
            "parameters": {
                "custom": {"type": "string"}
            }
        }
        
        enhanced = ensure_template_compatibility(template)
        
        # Check that existing fields were preserved
        assert enhanced["name"] == "custom_name"
        assert enhanced["description"] == "Custom description"
        assert "custom" in enhanced["parameters"]


class TestGetPreferredModel:
    """Tests for the get_preferred_model function."""
    
    def test_preferred_model_available(self):
        """Test when preferred model is available."""
        template = {
            "model": {
                "preferred": "claude-3",
                "fallback": ["gpt-4", "llama-3"]
            }
        }
        
        available_models = ["claude-3", "gpt-4", "llama-3"]
        model = get_preferred_model(template, available_models)
        
        assert model == "claude-3"
    
    def test_fallback_model_selection(self):
        """Test fallback selection when preferred is unavailable."""
        template = {
            "model": {
                "preferred": "claude-3",
                "fallback": ["gpt-4", "llama-3"]
            }
        }
        
        available_models = ["gpt-4", "llama-3"]  # claude-3 not available
        model = get_preferred_model(template, available_models)
        
        assert model == "gpt-4"  # First fallback
    
    def test_second_fallback_selection(self):
        """Test second fallback selection."""
        template = {
            "model": {
                "preferred": "claude-3",
                "fallback": ["gpt-4", "llama-3"]
            }
        }
        
        available_models = ["llama-3"]  # Only second fallback available
        model = get_preferred_model(template, available_models)
        
        assert model == "llama-3"
    
    def test_default_when_no_match(self):
        """Test default behavior when no matches exist."""
        template = {
            "model": {
                "preferred": "claude-3",
                "fallback": ["gpt-4", "llama-3"]
            }
        }
        
        available_models = ["other-model"]  # No matches
        model = get_preferred_model(template, available_models)
        
        assert model == "other-model"  # Default to first available
    
    def test_string_model_preference(self):
        """Test with simple string model preference."""
        template = {
            "model": "claude-3"
        }
        
        available_models = ["claude-3", "gpt-4"]
        model = get_preferred_model(template, available_models)
        
        assert model == "claude-3"


class TestEnvironment:
    """Tests for the Environment class."""
    
    def test_simple_lookup(self):
        """Test simple variable lookup."""
        env = Environment({"name": "test", "value": 123})
        
        assert env.find("name") == "test"
        assert env.find("value") == 123
    
    def test_parent_lookup(self):
        """Test lookup through parent environment."""
        parent = Environment({"parent_var": "parent_value"})
        child = Environment({"child_var": "child_value"}, parent=parent)
        
        assert child.find("child_var") == "child_value"
        assert child.find("parent_var") == "parent_value"
    
    def test_variable_not_found(self):
        """Test error when variable not found."""
        env = Environment({"name": "test"})
        
        with pytest.raises(ValueError) as excinfo:
            env.find("unknown")
        
        assert "Variable 'unknown' not found" in str(excinfo.value)
    
    def test_environment_extension(self):
        """Test environment extension."""
        base = Environment({"base_var": "base_value"})
        extended = base.extend({"extended_var": "extended_value"})
        
        assert extended.find("base_var") == "base_value"
        assert extended.find("extended_var") == "extended_value"
        assert extended.parent == base
    
    def test_variable_shadowing(self):
        """Test variable shadowing in nested environments."""
        parent = Environment({"var": "parent_value"})
        child = Environment({"var": "child_value"}, parent=parent)
        
        assert child.find("var") == "child_value"  # Child's value shadows parent's


class TestVariableSubstitution:
    """Tests for variable substitution functions."""
    
    def test_basic_substitution(self):
        """Test basic variable substitution."""
        env = Environment({"name": "test", "count": 42})
        text = "Hello {{name}}, your count is {{count}}."
        
        result = substitute_variables(text, env)
        assert result == "Hello test, your count is 42."
    
    def test_nested_variable_lookup(self):
        """Test variable substitution with nested environments."""
        parent = Environment({"parent_var": "parent_value"})
        child = Environment({"child_var": "child_value"}, parent=parent)
        
        text = "Parent: {{parent_var}}, Child: {{child_var}}"
        result = substitute_variables(text, child)
        
        assert result == "Parent: parent_value, Child: child_value"
    
    def test_undefined_variable(self):
        """Test handling of undefined variables."""
        env = Environment({"name": "test"})
        text = "Hello {{name}}, count is {{count}}"
        
        result = substitute_variables(text, env)
        assert result == "Hello test, count is {{undefined:count}}"
    
    def test_non_string_input(self):
        """Test handling of non-string input."""
        env = Environment({"name": "test"})
        
        # Non-string inputs should be returned unchanged
        assert substitute_variables(123, env) == 123
        assert substitute_variables(None, env) is None
        assert substitute_variables({"key": "value"}, env) == {"key": "value"}


class TestTemplateVariableResolution:
    """Tests for template variable resolution."""
    
    def test_resolve_template_variables(self):
        """Test resolving variables in template fields."""
        template = {
            "type": "atomic",
            "subtype": "test",
            "description": "Test for {{name}}",
            "system_prompt": "Process query {{query}} with limit {{limit}}"
        }
        
        env = Environment({
            "name": "test_user",
            "query": "test_query",
            "limit": 10
        })
        
        resolved = resolve_template_variables(template, env)
        
        # Check that variables were resolved
        assert resolved["description"] == "Test for test_user"
        assert resolved["system_prompt"] == "Process query test_query with limit 10"
        
        # Check that original template wasn't modified
        assert template["description"] == "Test for {{name}}"
        assert template["system_prompt"] == "Process query {{query}} with limit {{limit}}"
    
    def test_missing_fields(self):
        """Test resolution with missing fields."""
        template = {
            "type": "atomic",
            "subtype": "test"
            # No description or system_prompt
        }
        
        env = Environment({"name": "test"})
        resolved = resolve_template_variables(template, env)
        
        # Template should be returned with same structure
        assert resolved["type"] == "atomic"
        assert resolved["subtype"] == "test"
        assert "description" not in resolved
        assert "system_prompt" not in resolved


class TestFunctionCallDetection:
    """Tests for function call detection."""
    
    def test_detect_simple_function_call(self):
        """Test detecting a simple function call."""
        text = "Text with {{func()}} call"
        calls = detect_function_calls(text)
        
        assert len(calls) == 1
        assert calls[0]["name"] == "func"
        assert calls[0]["args_text"] == ""
        assert calls[0]["match"] == "{{func()}}"
    
    def test_detect_function_call_with_args(self):
        """Test detecting a function call with arguments."""
        text = "Text with {{func(1, 'test', true)}} call"
        calls = detect_function_calls(text)
        
        assert len(calls) == 1
        assert calls[0]["name"] == "func"
        assert calls[0]["args_text"] == "1, 'test', true"
    
    def test_detect_multiple_function_calls(self):
        """Test detecting multiple function calls."""
        text = "Text with {{func1()}} and {{func2(arg)}} calls"
        calls = detect_function_calls(text)
        
        assert len(calls) == 2
        assert calls[0]["name"] == "func1"
        assert calls[1]["name"] == "func2"
        assert calls[1]["args_text"] == "arg"
    
    def test_non_string_input(self):
        """Test handling of non-string input."""
        # Should return empty list for non-string inputs
        assert detect_function_calls(123) == []
        assert detect_function_calls(None) == []
        assert detect_function_calls({"key": "value"}) == []


class TestFunctionCallParsing:
    """Tests for function call parsing."""
    
    def test_parse_function_call_no_args(self):
        """Test parsing a function call with no arguments."""
        func_name, pos_args, named_args = parse_function_call("func", "")
        
        assert func_name == "func"
        assert pos_args == []
        assert named_args == {}
    
    def test_parse_function_call_positional_args(self):
        """Test parsing a function call with positional arguments."""
        func_name, pos_args, named_args = parse_function_call("func", "1, 'test', true, null")
        
        assert func_name == "func"
        assert len(pos_args) == 4
        assert pos_args[0] == 1
        assert pos_args[1] == "test"
        assert pos_args[2] is True
        assert pos_args[3] is None
        assert named_args == {}
    
    def test_parse_function_call_named_args(self):
        """Test parsing a function call with named arguments."""
        func_name, pos_args, named_args = parse_function_call("func", "a=1, b='test', c=true")
        
        assert func_name == "func"
        assert pos_args == []
        assert len(named_args) == 3
        assert named_args["a"] == 1
        assert named_args["b"] == "test"
        assert named_args["c"] is True
    
    def test_parse_function_call_mixed_args(self):
        """Test parsing a function call with mixed positional and named arguments."""
        func_name, pos_args, named_args = parse_function_call("func", "1, 'test', a=true, b=null")
        
        assert func_name == "func"
        assert len(pos_args) == 2
        assert pos_args[0] == 1
        assert pos_args[1] == "test"
        assert len(named_args) == 2
        assert named_args["a"] is True
        assert named_args["b"] is None
    
    def test_parse_function_call_quoted_strings(self):
        """Test parsing a function call with quoted strings."""
        func_name, pos_args, named_args = parse_function_call("func", "'hello, world', \"quoted, string\"")
        
        assert func_name == "func"
        assert len(pos_args) == 2
        assert pos_args[0] == "hello, world"
        assert pos_args[1] == "quoted, string"


class TestArgumentEvaluation:
    """Tests for argument evaluation."""
    
    def test_evaluate_positional_args(self):
        """Test evaluating positional arguments."""
        env = Environment({"var1": "value1", "var2": 42})
        pos_args = ["static", "{{var1}}", "{{var2}}"]
        named_args = {}
        
        eval_pos, eval_named = evaluate_arguments(pos_args, named_args, env)
        
        assert len(eval_pos) == 3
        assert eval_pos[0] == "static"
        assert eval_pos[1] == "value1"
        assert eval_pos[2] == 42  # Should be numeric, not string
    
    def test_evaluate_named_args(self):
        """Test evaluating named arguments."""
        env = Environment({"var1": "value1", "var2": 42})
        pos_args = []
        named_args = {"a": "static", "b": "{{var1}}", "c": "{{var2}}"}
        
        eval_pos, eval_named = evaluate_arguments(pos_args, named_args, env)
        
        assert eval_pos == []
        assert len(eval_named) == 3
        assert eval_named["a"] == "static"
        assert eval_named["b"] == "value1"
        assert eval_named["c"] == 42  # Should be numeric, not string


class TestParameterBinding:
    """Tests for parameter binding."""
    
    def test_bind_arguments_to_parameters(self):
        """Test binding arguments to parameters."""
        template = {
            "name": "test_func",
            "parameters": {
                "a": {"type": "string", "required": True},
                "b": {"type": "integer", "required": True},
                "c": {"type": "boolean", "default": False}
            }
        }
        
        pos_args = ["value", 42]
        named_args = {}
        
        bindings = bind_arguments_to_parameters(template, pos_args, named_args)
        
        assert len(bindings) == 3
        assert bindings["a"] == "value"
        assert bindings["b"] == 42
        assert bindings["c"] is False  # Default value
    
    def test_bind_arguments_with_named_overrides(self):
        """Test binding arguments with named arguments overriding positional."""
        template = {
            "name": "test_func",
            "parameters": {
                "a": {"type": "string", "required": True},
                "b": {"type": "integer", "required": True},
                "c": {"type": "boolean", "default": False}
            }
        }
        
        pos_args = ["value", 42]
        named_args = {"b": 99}  # Override positional argument
        
        bindings = bind_arguments_to_parameters(template, pos_args, named_args)
        
        assert bindings["a"] == "value"
        assert bindings["b"] == 99  # Named arg overrides positional
        assert bindings["c"] is False  # Default value
    
    def test_bind_arguments_missing_required(self):
        """Test error when required parameter is missing."""
        template = {
            "name": "test_func",
            "parameters": {
                "a": {"type": "string", "required": True},
                "b": {"type": "integer", "required": True}
            }
        }
        
        pos_args = ["value"]  # Missing required parameter b
        named_args = {}
        
        with pytest.raises(ValueError) as excinfo:
            bind_arguments_to_parameters(template, pos_args, named_args)
        
        assert "Missing required parameter" in str(excinfo.value)
    
    def test_bind_arguments_too_many_positional(self):
        """Test error when too many positional arguments are provided."""
        template = {
            "name": "test_func",
            "parameters": {
                "a": {"type": "string", "required": True}
            }
        }
        
        pos_args = ["value", "extra"]  # Extra positional argument
        named_args = {}
        
        with pytest.raises(ValueError) as excinfo:
            bind_arguments_to_parameters(template, pos_args, named_args)
        
        assert "Too many positional arguments" in str(excinfo.value)


class TestTranslationMechanism:
    """Tests for the function call translation mechanism."""
    
    def test_translate_function_call_to_ast(self):
        """Test translating a text function call to AST nodes."""
        # Test with positional args
        node = translate_function_call_to_ast("test_func", "arg1, 42")
        
        assert isinstance(node, FunctionCallNode)
        assert node.template_name == "test_func"
        assert len(node.arguments) == 2
        assert node.arguments[0].value == "arg1"
        assert node.arguments[1].value == 42
        assert node.arguments[0].is_positional()
        
        # Test with named args
        node = translate_function_call_to_ast("test_func", "name=\"value\", count=5")
        
        assert isinstance(node, FunctionCallNode)
        assert node.template_name == "test_func"
        assert len(node.arguments) == 2
        assert node.arguments[0].value == "value"
        assert node.arguments[0].name == "name"
        assert node.arguments[1].value == 5
        assert node.arguments[1].name == "count"
        assert node.arguments[0].is_named()
        
        # Test with mixed args
        node = translate_function_call_to_ast("test_func", "arg1, param=42")
        
        assert isinstance(node, FunctionCallNode)
        assert node.template_name == "test_func"
        assert len(node.arguments) == 2
        assert node.arguments[0].value == "arg1"
        assert node.arguments[0].is_positional()
        assert node.arguments[1].value == 42
        assert node.arguments[1].name == "param"
        assert node.arguments[1].is_named()
    
    def test_resolve_function_calls(self):
        """Test resolving function calls in text."""
        # Create mock TaskSystem
        mock_task_system = MagicMock()
        mock_task_system.executeCall.return_value = {
            "content": "Executed function result",
            "status": "COMPLETE"
        }
        
        # Create environment
        env = Environment({"var1": "test_value", "var2": 42})
        
        # Test with single call
        text = "This is a {{test_function(var1, count=var2)}} in text"
        result = resolve_function_calls(text, mock_task_system, env)
        
        assert "Executed function result" in result
        assert mock_task_system.executeCall.call_count == 1
        
        # Check the FunctionCallNode passed to executeCall
        call_args = mock_task_system.executeCall.call_args[0]
        func_call = call_args[0]
        assert isinstance(func_call, FunctionCallNode)
        assert func_call.template_name == "test_function"
        assert len(func_call.arguments) == 2
        
        # Test with error handling
        mock_task_system.executeCall.side_effect = ValueError("Test error")
        result = resolve_function_calls(text, mock_task_system, env)
        
        assert "error in test_function()" in result
        assert "Test error" in result
        
        # Test with no calls
        text = "No function calls here"
        result = resolve_function_calls(text, mock_task_system, env)
        assert result == "No function calls here"
        
        # Test with invalid input
        assert resolve_function_calls(None, mock_task_system, env) is None
        assert resolve_function_calls(123, mock_task_system, env) == 123
    
    def test_integration_with_variable_substitution(self):
        """Test integration between function calls and variable substitution."""
        # Mock task system that returns the arguments as content
        mock_task_system = MagicMock()
        mock_task_system.executeCall.return_value = {
            "content": "Args received: test_value and 42",
            "status": "COMPLETE"
        }
        
        # Environment with variables
        env = Environment({"var1": "test_value", "var2": 42})
        
        # Test text with both variable references and function calls
        text = "{{var1}} is {{test_function(var1, count=var2)}} and {{var2}}"
        
        # First do variable substitution
        var_substituted = substitute_variables(text, env)
        assert "test_value is {{test_function(var1, count=var2)}} and 42" == var_substituted
        
        # Then resolve function calls
        result = resolve_function_calls(var_substituted, mock_task_system, env)
        assert "test_value is Args received: test_value and 42 and 42" == result
