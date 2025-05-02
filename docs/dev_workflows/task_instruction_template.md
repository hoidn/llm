**`docs/dev_workflows/task_instruction_template.md`**

*(Instructions for Tech Lead: Fill in all sections below with specific details for the assigned task. Replace bracketed placeholders `[...]` with actual information. Be precise and clear.)*

---

# Task Implementation Instructions

*   **Task Name/ID:** `[Link to Issue Tracker Ticket or Task Name]`
*   **Assigned To:** `[Junior Developer Name]`
*   **Assigned By:** `[Tech Lead Name]`
*   **Date Assigned:** `[Date]`
*   **Relevant ADRs/Docs:** `[Link to relevant ADRs, patterns, library docs, etc.]`

---

**1. Task Goal:**

*   `[Clearly describe the overall objective of this task. What feature should be implemented or what bug should be fixed? What is the desired outcome? Keep it concise.]`

**2. Context & Requirements:**

*   **Primary IDL(s) & Contract:**
    *   The main specification for the component(s) you will be working on is defined in: `[Link(s) to primary *_IDL.md file(s)]`.
    *   **Key Focus Areas:** Pay close attention to the following methods/behaviors/error conditions defined in the IDL:
        *   `[Method/Behavior 1 from IDL - e.g., `BaseHandler.register_tool`]`
        *   `[Method/Behavior 2 from IDL - e.g., Handling of `output_format.schema` in `AtomicTaskExecutor`]`
        *   `[Error condition from IDL - e.g., `@raises_error(condition="ModelNotFoundError", ...)`]`
        *   `[...]`
*   **Dependencies & Interactions:**
    **Action Required:** Before implementing the interactions below, please review the linked `IDL/Docs` for each dependency. Pay close attention to the documentation for any external libraries, APIs, or tools to fully understand their expected usage, parameters, and return values. # <-- UPDATED SECTION
    *   This task involves interacting with the following components/libraries:
        *   **`[Dependency 1 Name, e.g., MemorySystem]`:**
            *   IDL/Docs: `[Link to Dependency 1 IDL or relevant docs]`
            *   Key Interaction: `[Explain how your code should use this dependency. E.g., "You will need to call `memory_system.get_relevant_context_for(input_data)` using a `ContextGenerationInput` object. Expect an `AssociativeMatchResult` back. Handle potential `result.error`."] `
        *   **`[Dependency 2 Name, e.g., External Aider MCP Server]`:**
            *   IDL/Docs: `[Link to relevant docs, e.g., AiderBridge IDL, Aider MCP Server docs]`
            *   Key Interaction: `[E.g., "Use the `AiderBridge` instance (passed as `aider_bridge`) to call the MCP server via `aider_bridge.call_aider_tool('tool_name', params)`. Ensure you construct the `params` dictionary correctly based on the Aider MCP tool's requirements. Handle potential MCP connection/timeout errors."] `
        *   **`[...]`**
    *   **Data Structures:** You will primarily work with these data structures defined in `docs/system/contracts/types.md`: `[List relevant Pydantic models, e.g., TaskResult, SubtaskRequest, ContextGenerationInput]`

**3. Provided Stubs:**

*   I have created the following skeleton files and test stubs for you to work with:
    *   `[path/to/implementation_file.py]` (Contains class/function stubs)
    *   `[path/to/test_file.py]` (Contains empty test function stubs)
    *   `[...]`
*   Please implement the logic directly within these files. Ensure you fetch the latest changes if working on a shared branch.

**4. Implementation Plan:**

*   Implement the logic for `[ClassName.method_name or function_name]` in `[path/to/implementation_file.py]`.
*   Follow these specific steps:
    1.  `[Detailed step 1: e.g., "Retrieve the `output_format` dictionary from the `atomic_task_def` parameter."]`
    2.  `[Detailed step 2: e.g., "Check if `output_format.get('schema')` exists and is a string."]`
    3.  `[Detailed step 3: e.g., "If yes, call the `resolve_model_class(schema_name)` helper function (import it from `src.system.models`). Wrap this call in a `try...except ModelNotFoundError` block."]`
        *   `[Sub-step/detail: e.g., "If `ModelNotFoundError` occurs, log a warning and store the error message in a local variable `schema_warning_note`."] `
    4.  `[Detailed step 4: e.g., "Call `self.handler._execute_llm_call(...)`, passing the resolved model class (or `None`) as the `output_type_override` parameter."]`
    5.  `[Detailed step 5: e.g., "After the handler call returns a result dictionary (`handler_result`), check if it contains a key 'parsed_content'."]`
    6.  `[Detailed step 6: e.g., "If 'parsed_content' exists, move its value to the `parsedContent` key of the final `TaskResult` dictionary you will return. Remove the 'parsed_content' key from the handler result."]`
    7.  `[Detailed step 7: e.g., "If `schema_warning_note` was set earlier, add it to the `notes` dictionary of the final `TaskResult`."] `
    8.  `[Detailed step 8: e.g., "Implement error handling for `ParameterMismatchError` as shown in existing code."]`
    9.  `[...]`
*   **Data Models:** `[Specify any Pydantic models the JD needs to use or be aware of, e.g., "Ensure the final return value is a dictionary conforming to the `TaskResult` structure."]`
*   **Key Considerations:** `[Highlight any tricky parts, edge cases to consider, or specific project patterns to follow, e.g., "Remember to use the `resolve_model_class` helper, don't implement dynamic imports yourself.", "Ensure all external calls are within try/except blocks."] `

**5. Testing Plan:**

*   **Testing Strategy Overview:** `[TL provides brief context, e.g., "Focus on unit testing the new logic in AtomicTaskExecutor. Mock the handler call and the model resolver."]`
*   **Test Files:** Implement tests in `[path/to/test_file.py]`.
*   **Detailed Test Cases:** Implement the following test functions (stubs provided):
    *   **`test_function_name_scenario_1`**:
        *   **Purpose:** `[e.g., "Verify handler is called with output_type_override=None when template has no schema."]`
        *   **Setup/Fixtures:** `[e.g., "Use `mock_handler` fixture. Use `@patch('src.executors.atomic_executor.resolve_model_class')` to mock the resolver."]`
        *   **Assertions:** `[e.g., "`mock_resolve_model_class.assert_not_called()`. `mock_handler._execute_llm_call.assert_called_once()`. Check `kwargs['output_type_override']` is `None` in the handler call."]`
    *   **`test_function_name_scenario_2`**:
        *   **Purpose:** `[e.g., "Verify handler is called with the correct Pydantic class when schema is valid."]`
        *   **Setup/Fixtures:** `[e.g., "Use `mock_handler`. Mock `resolve_model_class` to return `TestOutputModel`. Define a sample `task_def` with `output_format.schema = 'TestOutputModel'`."]`
        *   **Assertions:** `[e.g., "`mock_resolve_model_class.assert_called_once_with('TestOutputModel')`. Check `kwargs['output_type_override']` is `TestOutputModel` in the handler call."]`
    *   **`test_function_name_scenario_3`**:
        *   **Purpose:** `[e.g., "Verify `parsedContent` is correctly populated when handler returns `parsed_content`."]`
        *   **Setup/Fixtures:** `[e.g., "Use `mock_handler`. Mock `resolve_model_class`. Configure `mock_handler._execute_llm_call` to return a dict containing `{'parsed_content': TestOutputModel(...)}`."]`
        *   **Assertions:** `[e.g., "`assert 'parsedContent' in result_dict`. `assert result_dict['parsedContent'] == expected_model_instance`."]`
    *   **`test_function_name_error_case_1`**:
        *   **Purpose:** `[e.g., "Verify behavior when `resolve_model_class` raises `ModelNotFoundError`."]`
        *   **Setup/Fixtures:** `[e.g., "Use `mock_handler`. Mock `resolve_model_class` using `side_effect=ModelNotFoundError(...)`. Configure handler mock to return a basic COMPLETE result."]`
        *   **Assertions:** `[e.g., "`assert result_dict['status'] == 'COMPLETE'`. `assert 'schema_warning' in result_dict['notes']`."]`
    *   `[...]` *(Add entries for all required test cases)*

**6. Running Tests & Debugging:**

*   **Running Tests:**
    *   To run all tests for this component: `[e.g., `pytest tests/executors/test_atomic_executor.py`]`
    *   To run a specific test: `[e.g., `pytest tests/executors/test_atomic_executor.py -k test_function_name_scenario_1`]`
*   **Debugging Tips:**
    *   `[Tip 1: e.g., "Use `logging.debug()` extensively within your implemented logic to trace variable values."]`
    *   `[Tip 2: e.g., "Set breakpoints using `breakpoint()` before critical calls like `handler._execute_llm_call` or `resolve_model_class` to inspect inputs."]`
    *   `[Tip 3: e.g., "If tests fail on assertions about mock calls (`assert_called_once_with`), print the `mock_handler.method_calls` attribute to see exactly how the mock was called."]`
    *   `[Tip 4: e.g., "Common Issue: Ensure Pydantic models referenced by schema names actually exist in `src/system/models.py`."]`
    *   **Asking for Help:** If you are stuck for more than `[e.g., 30-60 minutes]` after trying to debug, please reach out. Explain what you are trying to achieve, what you have tried, and what error you are seeing.

**7. Definition of Done:**

*   [ ] All implementation steps in Section 4 are completed.
*   [ ] All detailed test cases in Section 5 are implemented and pass.
*   [ ] Code passes linting (`make lint` or `ruff check . --fix`).
*   [ ] Code passes formatting (`make format` or `black .`).
*   [ ] The full project test suite passes (`pytest tests/` or `make test`).
*   [ ] You have performed a self-review of your code for clarity and correctness.
*   [ ] `docs/memory.md` has been updated with your work.
*   [ ] Code is committed with a clear commit message.
*   [ ] Pull Request (if applicable) is created and linked to the issue ticket.

**8. Notes/Questions (For Junior Developer):**

*   *(Leave this section blank for the JD to use)*

