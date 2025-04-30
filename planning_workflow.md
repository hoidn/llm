# Development Process Guide: IDL-First Implementation

This guide outlines the step-by-step process for implementing system tool executors based on Interface Definition Language (IDL) specifications.

## <process-step id="1">
<step-title>Understand IDL Specifications</step-title>
<step-actions>
- Read and analyze the IDL for `execute_get_context` and `execute_read_files` to understand their contracts
- Identify key components: Input/output signatures, preconditions, postconditions, expected behavior, and error handling
- Note dependencies: Identify `MemorySystem` and `FileAccessManager` as critical dependencies
</step-actions>
</process-step>

## <process-step id="2">
<step-title>Stub Implementation Components</step-title>
<step-actions>
- Create minimal implementation stubs that match the IDL contracts
- Add detailed docstrings documenting input/output formats and expected behavior directly in the stubs
- Define proper type annotations matching the IDL's parameter and return types
- Identify imports by listing all required model imports from other modules
</step-actions>
</process-step>

## <process-step id="3">
<step-title>Stub Test Cases</step-title>
<step-actions>
- Map test cases to IDL requirements by creating test stubs for each behavior specified in the IDL
- Create test fixtures for `mock_memory_system` and `mock_file_manager`
- Draft assertions and validations specifying what each test will verify
- Define success and failure scenarios with tests for both normal operation and error handling
</step-actions>
</process-step>

## <process-step id="4">
<step-title>Develop Detailed Implementation Specification</step-title>
<step-actions>
- Create a detailed specification with pseudocode before diving into implementation
- Identify validation logic specifying how parameters will be validated
- Define error formatting determining how error responses will be structured
- Specify integration with dependencies documenting how `memory_system` and `file_manager` will be used
</step-actions>
</process-step>

## <process-step id="5">
<step-title>Develop Test Specification</step-title>
<step-actions>
- Create a detailed test specification before implementing tests
- Define fixtures thoroughly specifying the behavior of mock dependencies
- Set up test assertions detailing the exact assertions needed to validate the IDL contract
- Cover edge cases by adding tests for parameter validation, error handling, and unexpected behavior
</step-actions>
</process-step>

## <process-step id="6">
<step-title>Implement Production Code</step-title>
<step-actions>
- Implement validation logic for required parameters
- Add code to transform input parameters to the format expected by dependencies
- Implement the main business logic that integrates with dependencies
- Add comprehensive error handling and result formatting
- Ensure the output matches the TaskResult structure specified in the IDL
</step-actions>
</process-step>

## <key-lessons>
<lesson-title>Lessons Learned</lesson-title>
<lessons>
1. **IDL-First Development**: Starting with the IDL provides a clear contract to implement against
2. **Stub Before Implementing**: Creating stubs helps identify integration issues early
3. **Test Against the Contract**: Tests should verify compliance with the IDL specification
4. **Detailed Specifications**: Creating detailed specifications before coding helps clarify requirements
5. **Focus on Dependencies**: Understanding how to integrate with dependencies is crucial
</lessons>
</key-lessons>

This development process ensures that both the implementation and tests are tightly aligned with the IDL specification, leading to more maintainable and consistent code that fulfills the contract requirements.
