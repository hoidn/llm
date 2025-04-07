# Function Call Refactoring: Detailed Plan for Remaining Phases

## Phase 3: Translation Mechanism

### Objective
Implement the translation mechanism that converts template-level function calls (`{{function_name(arg1, arg2)}}`) into AST nodes before execution, ensuring a single execution path.

### Key Components
1. **Function Detection**: Enhance the function call detection to provide precise location information
2. **Argument Parsing**: Improve argument parsing to handle both positional and named arguments
3. **AST Node Creation**: Convert detected function calls into FunctionCallNode and ArgumentNode instances
4. **Evaluator Integration**: Use the Evaluator component to execute the translated AST nodes

### Detailed Tasks
1. Update `detect_function_calls` in template_utils.py to provide exact position information
2. Refine `parse_function_call` to convert raw arguments into structured data
3. Modify `resolve_function_calls` to create AST nodes and delegate to Evaluator
4. Add tests for the translation mechanism

### Expected Outcomes
- Template-level function calls are properly translated to AST nodes
- Single execution path for all function calls
- Consistent behavior between XML-based and template-level function calls

## Phase 4: Integration with Task System

### Objective
Ensure proper integration between components and complete the single execution path implementation.

### Key Components
1. **Template Variable Resolution**: Update template variable resolution to use the translation mechanism
2. **Template Processing Flow**: Update the TaskSystem to use Evaluator for all function calls
3. **XML/Template Integration**: Ensure both XML-based and template-level calls behave identically

### Detailed Tasks
1. Update TaskSystem's execute_task method to use the Evaluator for function calls
2. Modify template variable substitution to use the translation mechanism
3. Ensure correct context propagation between components
4. Add integration tests for the complete execution flow

### Expected Outcomes
- Complete integration between TaskSystem and Evaluator
- Both XML-based and template-level function calls follow the same execution path
- Consistent error handling and behavior

## Phase 5: Final Validation and Documentation

### Objective
Validate the implementation with comprehensive testing and update documentation.

### Key Components
1. **Edge Case Testing**: Test edge cases and error scenarios
2. **Performance Testing**: Validate that the new approach doesn't introduce performance issues
3. **Documentation Update**: Update technical documentation to reflect the new architecture
4. **Code Quality**: Final code review and refactoring

### Detailed Tasks
1. Add tests for complex nested function calls
2. Add tests for error handling scenarios
3. Update README and documentation files
4. Perform code quality review

### Expected Outcomes
- Comprehensive test coverage
- Clear documentation of the new architecture
- High-quality, maintainable code

## Additional Considerations

### Backward Compatibility
- The refactoring should maintain backward compatibility with existing templates
- Error messages should remain helpful and clear

### Performance
- The translation mechanism should have minimal performance impact
- Consider simple optimizations if needed, but focus on correctness first

### Function Call Nesting
- Ensure proper handling of nested function calls (e.g., `{{func1(func2(arg))}}`)
- Test with realistic nested scenarios

### Error Handling
- Maintain detailed error reporting with clear source location information
- Ensure error messages help template authors debug issues
