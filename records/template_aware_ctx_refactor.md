# Template-Aware Context Generation: Revised Implementation Plan

## Overview

This revised plan implements Template-Aware Context Generation with a pure LLM-based approach for context retrieval, removing all string-matching fallbacks. It maintains clean architectural boundaries with TaskSystem serving as the exclusive mediator between Memory System and Handler.

## Core Principles

1. **Single Input Format**: Use only `ContextGenerationInput` throughout the system
2. **Clean Architectural Boundaries**: Memory System → TaskSystem → Handler → LLM
3. **Three-Dimensional Context Model**: Implement inherit_context, accumulate_data, and fresh_context
4. **Pure LLM Approach**: Remove all string-matching fallbacks, use only LLM for context matching
5. **Robust Error Handling**: Properly handle failures without silent fallbacks
6. **Complete Testing**: Comprehensive tests to verify the new architecture

## Phase 1: Define ContextGenerationInput Structure (Complete)

The existing implementation is appropriate. No changes needed.

- `ContextGenerationInput` class provides standardized input format
- `AssociativeMatchResult` class provides standardized results
- Both include proper inheritance and conversion from legacy formats

## Phase 2: Implement TaskSystem Mediator Pattern (Revised)

### 1. Enhance `generate_context_for_memory_system` for Robustness

```python
def generate_context_for_memory_system(self, 
                                     context_input: ContextGenerationInput, 
                                     global_index: Dict[str, str]) -> AssociativeMatchResult:
    """Generate context for Memory System using LLM capabilities.
    
    This method serves as a mediator between Memory System and Handler,
    maintaining proper architectural boundaries.
    
    Args:
        context_input: Context generation input from Memory System
        global_index: Global file metadata index
        
    Returns:
        AssociativeMatchResult containing context and file matches
    """
    if not global_index:
        return AssociativeMatchResult(context="No files available", matches=[])
        
    try:
        # Execute specialized context generation task
        result = self._execute_context_generation_task(context_input, global_index)
        
        # Extract relevant files from result
        file_matches = []
        try:
            import json
            content = result.get("content", "[]")
            matches_data = json.loads(content) if isinstance(content, str) else content
            
            if isinstance(matches_data, list):
                # Process file matches
                for item in matches_data:
                    if isinstance(item, dict) and "path" in item:
                        path = item["path"]
                        relevance = item.get("relevance", "Relevant to query")
                        if path in global_index:
                            file_matches.append((path, relevance))
        except Exception as e:
            # Handle parsing errors without crashing
            print(f"Error parsing context generation result: {str(e)}")
            # Return a partial result if possible
            if "matches" in result.get("notes", {}) and isinstance(result["notes"]["matches"], list):
                for path in result["notes"]["matches"]:
                    if path in global_index:
                        file_matches.append((path, "Relevant to query"))
        
        # Create context summary
        if file_matches:
            context = f"Found {len(file_matches)} relevant files."
        else:
            context = "No relevant files found."
            
        return AssociativeMatchResult(context=context, matches=file_matches)
    except Exception as e:
        # Log the error for debugging
        print(f"Error in TaskSystem mediator: {str(e)}")
        # Re-raise so Memory System can handle it
        raise
```

### 2. Improve `_execute_context_generation_task` for Error Handling

```python
def _execute_context_generation_task(self, 
                                   context_input: ContextGenerationInput, 
                                   global_index: Dict[str, str]) -> Dict[str, Any]:
    """Execute specialized context generation task using LLM.
    
    Args:
        context_input: Context generation input
        global_index: Global file metadata index
        
    Returns:
        Task result with relevant file information
        
    Raises:
        Exception: If task execution fails critically
    """
    # Create specialized inputs for context generation
    inputs = {
        "query": context_input.template_description,
        "metadata": global_index,
        "relevance_map": context_input.context_relevance,
        "additional_context": {
            name: value for name, value in context_input.inputs.items()
            if context_input.context_relevance.get(name, True)
        }
    }
    
    if context_input.inherited_context:
        inputs["inherited_context"] = context_input.inherited_context
        
    if context_input.previous_outputs:
        inputs["previous_outputs"] = context_input.previous_outputs
    
    # Execute task to find relevant files
    try:
        return self.execute_task(
            task_type="atomic",
            task_subtype="associative_matching",
            inputs=inputs
        )
    except Exception as e:
        print(f"Error executing context generation task: {str(e)}")
        # Return a minimal valid result that indicates the error
        return {
            "status": "FAILED",
            "content": "[]",
            "notes": {
                "error": f"Failed to execute context generation: {str(e)}"
            }
        }
```

## Phase 3: Update Memory System (Revised)

### 1. Reimplement `get_relevant_context_for` to Remove Fallbacks

```python
def get_relevant_context_for(self, input_data: Union[Dict[str, Any], ContextGenerationInput]) -> Any:
    """Get relevant context for a task using exclusively the TaskSystem mediator.
    
    Args:
        input_data: Context generation input
    
    Returns:
        Object containing context and file matches
    """
    print(f"MEMORY SYSTEM get_relevant_context_for CALLED with: {type(input_data)}")
    
    # Convert input to ContextGenerationInput if needed
    if isinstance(input_data, dict):
        # Handle legacy format with taskText
        context_input = ContextGenerationInput.from_legacy_format(input_data)
        print(f"Converted dict to ContextGenerationInput: {context_input.template_description}")
    else:
        context_input = input_data
        if hasattr(context_input, 'template_description'):
            print(f"Using existing ContextGenerationInput: {context_input.template_description}")
    
    # Create result class for backward compatibility
    class Result:
        def __init__(self, context, matches):
            self.context = context
            self.matches = matches
    
    # Check if fresh context is disabled
    if hasattr(context_input, 'fresh_context') and context_input.fresh_context == "disabled":
        print("Fresh context disabled, returning inherited context only")
        return Result(
            context=context_input.inherited_context or "No context available",
            matches=[]
        )
    
    # Verify TaskSystem is available
    if not hasattr(self, 'task_system') or not self.task_system:
        error_msg = "TaskSystem is required for context generation but not available"
        print(error_msg)
        return Result(context=error_msg, matches=[])
    
    try:
        # Get file metadata
        file_metadata = self.get_global_index()
        if not file_metadata:
            return Result(context="No files in index", matches=[])
        
        # Use TaskSystem mediator pattern exclusively
        from memory.context_generation import AssociativeMatchResult
        associative_result = self.task_system.generate_context_for_memory_system(
            context_input, file_metadata
        )
        
        # Convert to legacy Result object for backward compatibility
        return Result(context=associative_result.context, matches=associative_result.matches)
    except Exception as e:
        # Improved error handling - return empty result with error message
        error_msg = f"Error during context generation: {str(e)}"
        print(error_msg)
        return Result(context=error_msg, matches=[])
```

### 2. Remove Fallback Methods

- Delete `_get_relevant_context_standard` method
- Delete `_get_relevant_context_sharded` method
- Update sharding configuration methods to maintain API compatibility but disable functionality

## Phase 4: Implement Associative Matching Template (Revised)

### 1. Enhance Template for Error Handling and Edge Cases

```python
ASSOCIATIVE_MATCHING_TEMPLATE = {
    "type": "atomic",
    "subtype": "associative_matching",
    "name": "find_relevant_files",
    "description": "Find relevant files for '{{query}}'",
    "parameters": {
        "query": {
            "type": "string",
            "description": "The query for context matching",
            "required": True
        },
        "metadata": {
            "type": "object",
            "description": "File metadata dictionary",
            "required": True
        },
        "relevance_map": {
            "type": "object",
            "description": "Map of input names to relevance flags",
            "default": {}
        },
        "additional_context": {
            "type": "object",
            "description": "Additional context from relevant inputs",
            "default": {}
        },
        "inherited_context": {
            "type": "string",
            "description": "Context inherited from parent tasks",
            "default": ""
        },
        "previous_outputs": {
            "type": "array",
            "description": "Outputs from previous steps",
            "default": []
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of files to return",
            "default": 10
        }
    },
    "context_management": {
        "inherit_context": "enabled",
        "accumulate_data": true,
        "fresh_context": "disabled"
    },
    "output_format": {
        "type": "json",
        "schema": "array"
    },
    "system_prompt": """You are a context retrieval assistant. Your task is to find the most relevant files for a given query.

Examine the provided metadata and determine which files would be most useful for addressing the query.

Consider the following in your analysis:
1. The main query: {{query}}
2. Additional context: {{additional_context | json}}
3. Inherited context (if any): {{inherited_context}}
4. File metadata content

Focus on files that contain:
- Direct keyword matches
- Semantically similar content
- Relevant functionality
- Associated concepts

If the query is very general, prioritize core files and important modules.
If the query is specific, focus on files most likely to contain the exact functionality.

RETURN ONLY a JSON array of objects with this format:
[{"path": "path/to/file1.py", "relevance": "Reason this file is relevant"}, ...]

Include at most {{max_results}} files, prioritizing the most relevant ones.
The "relevance" field should briefly explain why the file is relevant.
"""
}
```

### 2. Improve Error Handling in Template Execution

```python
def execute_template(query: str, memory_system, max_results: int = 10) -> List[str]:
    """Execute the associative matching template logic.
    
    Args:
        query: The user query or task
        memory_system: The Memory System instance
        max_results: Maximum number of files to return
        
    Returns:
        List of relevant file paths selected by the LLM
        
    Raises:
        Exception: If template execution fails
    """
    try:
        print(f"Executing associative matching for query: '{query}'")
        
        # Get global index from memory system
        file_metadata = get_global_index(memory_system)
        if not file_metadata:
            print("No indexed files found. Run index_git_repository first.")
            return []
        
        print(f"Found {len(file_metadata)} indexed files")
        
        # Create context input
        from memory.context_generation import ContextGenerationInput
        context_input = ContextGenerationInput(
            template_description=query,
            template_type="atomic",
            template_subtype="associative_matching",
            inputs={"query": query, "max_results": max_results},
            context_relevance={"query": True, "max_results": False}
        )
        
        # Use memory_system to get relevant context
        context_result = memory_system.get_relevant_context_for(context_input)
        
        # Extract file paths from matches
        relevant_files = [match[0] for match in context_result.matches]
        
        # Limit to max_results
        relevant_files = relevant_files[:max_results]
        
        print(f"Selected {len(relevant_files)} relevant files")
        for i, path in enumerate(relevant_files[:5], 1):
            print(f"  {i}. {path}")
        if len(relevant_files) > 5:
            print(f"  ... and {len(relevant_files) - 5} more")
        
        return relevant_files
    except Exception as e:
        print(f"Error executing associative matching template: {str(e)}")
        # Re-raise for proper error handling
        raise
```

## Phase 5: Identify and Update All Call Sites (Revised)

### 1. Update AiderBridge.get_context_for_query

```python
def get_context_for_query(self, query: str) -> List[str]:
    """Get relevant file context for a query using ContextGenerationInput.
    
    Args:
        query: The query to find relevant files for
            
    Returns:
        List of relevant file paths
    """
    try:
        # Use memory system with ContextGenerationInput
        from memory.context_generation import ContextGenerationInput
        
        context_input = ContextGenerationInput(
            template_description=query,
            template_type="atomic",
            template_subtype="associative_matching",
            inputs={"query": query},
            context_relevance={"query": True},
            inherited_context="",
            fresh_context="enabled"
        )
        
        context_result = self.memory_system.get_relevant_context_for(context_input)
        
        # Extract file paths from matches
        relevant_files = []
        if hasattr(context_result, 'matches') and context_result.matches:
            relevant_files = [match[0] for match in context_result.matches]
        
        # Update file context
        if relevant_files:
            self.file_context = set(relevant_files)
            self.context_source = "associative_matching"
        
        return relevant_files
    except Exception as e:
        print(f"Error getting context for query: {str(e)}")
        return []
```

### 2. Update PassthroughHandler._find_matching_template

```python
def _find_matching_template(self, query: str):
    """Find a matching template for the query using ContextGenerationInput.
    
    Args:
        query: User query
            
    Returns:
        Matching template or None
    """
    try:
        if not hasattr(self.task_system, 'find_matching_tasks'):
            self.log_debug("Task system does not support template matching")
            return None
            
        # Create context input for memory system
        from memory.context_generation import ContextGenerationInput
        context_input = ContextGenerationInput(
            template_description=query,
            template_type="atomic",
            template_subtype="generic",
            inputs={},
            context_relevance={},
            fresh_context="enabled"
        )
            
        # Get matching tasks from task system
        matching_tasks = self.task_system.find_matching_tasks(query, self.memory_system)
        
        if not matching_tasks:
            self.log_debug("No matching templates found")
            return None
            
        # Get highest scoring template
        best_match = matching_tasks[0]
        self.log_debug(f"Found matching template: {best_match['taskType']}:{best_match['subtype']} (score: {best_match['score']:.2f})")
        return best_match["task"]
    except Exception as e:
        self.log_debug(f"Error finding matching template: {str(e)}")
        return None
```

### 3. Other Integration Points

Identify and update any other call sites that might rely on string-matching fallbacks to handle errors properly.

## Phase 6: Remove Deprecated Handler Methods

### 1. Remove `determine_relevant_files` Method from BaseHandler

```python
# Remove from handler/base_handler.py
def determine_relevant_files(self, query_input: Union[str, ContextGenerationInput], file_metadata: Dict[str, str]) -> List[Tuple[str, str]]:
    """Method has been removed with the transition to TaskSystem-mediated context generation."""
    raise NotImplementedError("This method has been removed. Use Memory System with TaskSystem mediator instead.")
```

### 2. Remove `_build_file_relevance_message` Method from BaseHandler

```python
# Remove from handler/base_handler.py
def _build_file_relevance_message(self, query: str, inputs: Dict[str, Any], file_metadata: Dict[str, str]) -> str:
    """Method has been removed with the transition to TaskSystem-mediated context generation."""
    raise NotImplementedError("This method has been removed. Use Memory System with TaskSystem mediator instead.")
```

### 3. Update Documentation to Reflect the New Architecture

Update README and developer documentation to explain the new context generation architecture.

## Phase 7: Update TaskSystem.execute_task

### 1. Enhance Context Management in TaskSystem.execute_task

```python
def execute_task(self, task_type: str, task_subtype: str, inputs: Dict[str, Any], 
                memory_system=None, **kwargs) -> Dict[str, Any]:
    """Execute a task with proper context management.

    Args:
        task_type: Type of task
        task_subtype: Subtype of task
        inputs: Task inputs
        memory_system: Optional Memory System instance
        **kwargs: Additional execution options
    
    Returns:
        Task result
    """
    # Get template
    task_key = f"{task_type}:{task_subtype}"
    template_name = self.template_index.get(task_key)
    if not template_name or template_name not in self.templates:
        return {
            "status": "FAILED",
            "content": f"Unknown task type: {task_key}",
            "notes": {
                "error": "Task type not registered"
            }
        }
    
    template = self.templates[template_name]
    
    # Resolve parameters
    try:
        resolved_inputs = resolve_parameters(template, inputs)
    except ValueError as e:
        return {
            "status": "FAILED",
            "content": str(e),
            "notes": {
                "error": "PARAMETER_ERROR"
            }
        }
        
    # Extract context management settings
    context_mgmt = template.get("context_management", {})
    inherit_context = context_mgmt.get("inherit_context", "none")
    accumulate_data = context_mgmt.get("accumulate_data", False)
    fresh_context = context_mgmt.get("fresh_context", "enabled")
    
    # Extract context relevance from template
    context_relevance = template.get("context_relevance", {})
    if not context_relevance:
        # Default all parameters to relevant if not specified
        context_relevance = {param: True for param in resolved_inputs}
    
    # Create file context through Memory System if available
    file_context = None
    if memory_system:
        # Create context generation input
        context_input = ContextGenerationInput(
            template_description=template.get("description", ""),
            template_type=template.get("type", ""),
            template_subtype=template.get("subtype", ""),
            inputs=resolved_inputs,
            context_relevance=context_relevance,
            inherited_context=kwargs.get("inherited_context", "") if inherit_context != "none" else "",
            previous_outputs=kwargs.get("previous_outputs", []) if accumulate_data else [],
            fresh_context=fresh_context
        )
        
        try:
            # Get relevant context
            context_result = memory_system.get_relevant_context_for(context_input)
            
            # Extract file paths from matches
            file_paths = [match[0] for match in context_result.matches]
            
            # Create file context if paths are available
            if file_paths:
                # This would be replaced with actual file content loading
                file_context = f"Files: {', '.join(file_paths)}"
        except Exception as e:
            print(f"Error retrieving context: {str(e)}")
            # Continue without context rather than failing the task
    
    # Execute task using handler
    handler = self._get_handler(model=template.get("model"))
    result = handler.execute_prompt(
        template.get("description", ""),  # Task description
        template.get("system_prompt", ""),  # System prompt
        file_context  # File context
    )
    
    return result
```

## Phase 8: Comprehensive Testing (Revised)

### 1. Test TaskSystem Mediator

```python
def test_task_system_mediator_error_handling(self):
    """Test TaskSystem mediator error handling."""
    # Create components
    task_system = TaskSystem()
    memory_system = MemorySystem(task_system=task_system)
    
    # Set up mock for execute_task that throws an exception
    with patch.object(task_system, 'execute_task', side_effect=Exception("Test error")):
        # Create test input
        context_input = ContextGenerationInput(
            template_description="Test query",
            template_type="atomic",
            template_subtype="test",
            inputs={},
            context_relevance={}
        )
        
        # Create mock global index
        memory_system.global_index = {"file.py": "Test metadata"}
        
        # Call the function and check it handles errors
        try:
            result = task_system.generate_context_for_memory_system(context_input, memory_system.global_index)
            assert False, "Should have raised an exception"
        except Exception as e:
            assert "Test error" in str(e)
```

### 2. Test Memory System's Error Handling

```python
def test_memory_system_error_handling(self):
    """Test Memory System error handling with TaskSystem failures."""
    # Create mock TaskSystem that raises an exception
    mock_task_system = MagicMock(spec=TaskSystem)
    mock_task_system.generate_context_for_memory_system.side_effect = Exception("Test error")
    
    # Create MemorySystem with mock TaskSystem
    memory_system = MemorySystem(task_system=mock_task_system)
    memory_system.global_index = {"file.py": "Test metadata"}
    
    # Create context input
    context_input = ContextGenerationInput(
        template_description="Test query",
        template_type="atomic",
        template_subtype="test",
        inputs={},
        context_relevance={}
    )
    
    # Call get_relevant_context_for
    result = memory_system.get_relevant_context_for(context_input)
    
    # Verify error handling
    assert "Error during context generation" in result.context
    assert len(result.matches) == 0
```

### 3. Integration Test for Complete Flow

```python
def test_context_generation_integration(self):
    """Test the complete context generation flow."""
    # Create real components
    task_system = TaskSystem()
    memory_system = MemorySystem(task_system=task_system)
    
    # Register the associative matching template
    from task_system.templates.associative_matching import register_template
    register_template(task_system)
    
    # Create mock file metadata
    memory_system.update_global_index({
        "auth.py": "Authentication module for login system",
        "user.py": "User management module with profile handling",
        "config.py": "Configuration settings module"
    })
    
    # Mock the execute_task to return a predictable result
    with patch.object(task_system, 'execute_task') as mock_execute_task:
        mock_execute_task.return_value = {
            "status": "COMPLETE",
            "content": '[{"path": "auth.py", "relevance": "Related to authentication"}, {"path": "user.py", "relevance": "Contains user management code"}]'
        }
        
        # Create context input for finding authentication code
        context_input = ContextGenerationInput(
            template_description="Find authentication code",
            template_type="atomic",
            template_subtype="test",
            inputs={"feature": "login"},
            context_relevance={"feature": True}
        )
        
        # Get relevant context
        result = memory_system.get_relevant_context_for(context_input)
        
        # Verify result structure
        assert hasattr(result, "context")
        assert hasattr(result, "matches")
        assert len(result.matches) == 2
        assert result.matches[0][0] == "auth.py"
        assert result.matches[1][0] == "user.py"
        
        # Verify TaskSystem.execute_task was called correctly
        mock_execute_task.assert_called_once()
        args, kwargs = mock_execute_task.call_args
        assert kwargs.get('task_type') == "atomic"
        assert kwargs.get('task_subtype') == "associative_matching"
        assert "query" in kwargs.get('inputs', {})
```

### 4. Test Template Integration

```python
def test_template_integration(self):
    """Test template integration with context generation."""
    # Create TaskSystem and register template
    task_system = TaskSystem()
    from task_system.templates.associative_matching import register_template, ASSOCIATIVE_MATCHING_TEMPLATE
    register_template(task_system)
    
    # Verify template was registered
    template = task_system.find_template("find_relevant_files")
    assert template is not None
    assert template.get("type") == "atomic"
    assert template.get("subtype") == "associative_matching"
    
    # Verify template has proper context management settings
    context_mgmt = template.get("context_management", {})
    assert context_mgmt.get("fresh_context") == "disabled"
    
    # Verify template has appropriate parameters
    parameters = template.get("parameters", {})
    assert "query" in parameters
    assert "metadata" in parameters
    assert "max_results" in parameters
```

## Timeline

- **Phase 1**: Complete - ContextGenerationInput Structure Defined
- **Phase 2**: Days 1-2 - Enhance TaskSystem Mediator Pattern
- **Phase 3**: Days 3-4 - Update Memory System to Remove Fallbacks
- **Phase 4**: Day 5 - Enhance Associative Matching Template
- **Phase 5**: Days 6-7 - Update All Call Sites
- **Phase 6**: Day 8 - Remove Deprecated Handler Methods
- **Phase 7**: Day 9 - Update TaskSystem.execute_task
- **Phase 8**: Days 10-12 - Comprehensive Testing

## Success Criteria

1. **Pure LLM Approach**: All context retrieval uses TaskSystem mediator with LLM
2. **No String Matching Fallbacks**: All fallback methods removed
3. **Robust Error Handling**: System gracefully handles failures
4. **Clean Architecture**: Memory System → TaskSystem → Handler → LLM
5. **Three-Dimensional Context**: inherit_context, accumulate_data, and fresh_context implemented
6. **Test Coverage**: Comprehensive tests for normal operation and error handling
7. **Backward Compatibility**: Legacy API calls still work without fallbacks
