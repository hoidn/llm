**Implementation Plan: Phase Lambda - Adding Anonymous Functions (`lambda`)**

**Goal:** Enhance the S-expression DSL by implementing the `lambda` special form, enabling the creation of anonymous, first-class functions with proper lexical scoping (closures).

**Prerequisites:**

*   Phases 0-6 are complete and verified.
*   `SexpEvaluator` and `SexpEnvironment` exist and function correctly for existing features (`let`, `if`, `quote`, primitives, task/tool calls).
*   Relevant IDLs (`sexp_evaluator_IDL.md`, `sexp_environment_IDL.md`) have been updated as per the "Update IDLs for `lambda`" instructions.

**Core Components to Modify/Create:**

1.  **`src/sexp_evaluator/closure.py` (New File):** Define the `Closure` class.
2.  **`src/sexp_evaluator/sexp_evaluator.py`:** Modify `SexpEvaluator` significantly.
3.  **`tests/sexp_evaluator/test_sexp_evaluator.py`:** Add extensive new tests.

**Detailed Steps:**

**Step 1: Define the `Closure` Class**

1.  **Create File:** `src/sexp_evaluator/closure.py`
2.  **Implement `Closure`:**
    *   Define a Python class named `Closure`.
    *   The `__init__` method should accept and store:
        *   `params`: A list of parameter names (strings or symbols, depending on parser output).
        *   `body`: The body of the function (likely a single S-expression AST node, or a list of nodes if `progn` is implicit).
        *   `definition_env`: A reference to the `SexpEnvironment` instance where the `lambda` was defined.
    *   Add basic validation (e.g., params is a list, body exists, env is an environment).
    *   Implement a `__repr__` or `__str__` method for easier debugging (e.g., `<Closure params=(...) env_id=...>`).
    *   *(Optional)* Add type hints, potentially using forward references for `SexpEnvironment`.

**Step 2: Integrate `lambda` into `SexpEvaluator` Dispatch**

1.  **Modify `_eval_list`:**
    *   In `src/sexp_evaluator/sexp_evaluator.py`, locate `_eval_list`.
    *   Add `"lambda"` to the `special_forms` set.
2.  **Modify `_eval_special_form`:**
    *   In `src/sexp_evaluator/sexp_evaluator.py`, locate `_eval_special_form`.
    *   Add an `elif op_str == "lambda":` block.
    *   **Inside the block:**
        *   Validate syntax: `(lambda (param...) body...)`. Check for at least 2 args, first arg is list (params), rest is body. Ensure params are symbols/strings.
        *   Extract the parameter list (`params_ast`) and body expression(s) (`body_ast`). If multiple body expressions, implicitly wrap them in a `(progn ...)` structure or store them as a list to be evaluated sequentially later.
        *   Create a `Closure` instance, passing `params_ast`, `body_ast`, and the *current* `env`.
        *   Return the newly created `Closure` object.

**Step 3: Implement Function Application Logic in `SexpEvaluator`**

1.  **Modify `_eval_list` (Dispatch):**
    *   Locate the part of the dispatch logic (likely step 5 in the IDL description) where the operator is evaluated, and the result (`evaluated_operator`) is checked.
    *   Add a specific check: `if isinstance(evaluated_operator, Closure):`.
2.  **Create `_apply_closure` Helper Method:**
    *   Define a new private method `_apply_closure(self, closure: Closure, call_args: list, calling_env: SexpEnvironment) -> Any`.
    *   **Inside `_apply_closure`:**
        *   **Argument Count Check:** Compare the number of formal parameters (`len(closure.params)`) with the number of arguments provided in the call (`len(call_args)`). Raise `SexpEvaluationError` if they don't match.
        *   **Evaluate Arguments:** Iterate through `call_args` (which are the *unevaluated* argument expressions from the call site). For each `arg_expr`, call `self._eval(arg_expr, calling_env)` to get the evaluated argument value. Store these evaluated values in a list.
        *   **Create New Environment:** Get the captured environment from the closure: `definition_env = closure.definition_env`. Create the new frame for the function call: `call_env = definition_env.extend({})`.
        *   **Bind Parameters:** Iterate through the formal parameter names (`closure.params`) and the evaluated argument values. For each pair, call `call_env.define(param_name, arg_value)`.
        *   **Evaluate Body:** Evaluate the function body (`closure.body`) using the *new call environment*: `result = self._eval(closure.body, call_env)`. If the body is implicitly a `progn` (list of expressions), evaluate them sequentially and return the result of the last one.
        *   Return the final `result`.
3.  **Call `_apply_closure`:** In the `_eval_list` dispatch logic, when `evaluated_operator` is identified as a `Closure`, call `self._apply_closure(evaluated_operator, args, env)` (where `args` are the unevaluated arguments from the call site and `env` is the calling environment).

**Step 4: Testing**

1.  **Create/Update Test File:** `tests/sexp_evaluator/test_sexp_evaluator.py`.
2.  **Write `Closure` Tests (Optional but good):** Basic tests ensuring `Closure` stores params, body, and env correctly.
3.  **Write `lambda` Special Form Tests:**
    *   Test that `(lambda (x) x)` evaluates to a `Closure` object.
    *   Test that the captured environment is correct (might require inspecting the closure or testing behavior).
    *   Test syntax errors (wrong number of args, invalid param list).
4.  **Write Function Application Tests:**
    *   Simple application: `((lambda (x) (+ x 1)) 5)` should return `6`.
    *   Lexical Scope Test 1 (Capture): `(let ((x 10)) ((lambda () x)))` should return `10`.
    *   Lexical Scope Test 2 (Shadowing): `(let ((x 10)) ((lambda (x) x) 20))` should return `20`.
    *   Lexical Scope Test 3 (Outer Scope Access): `(let ((x 10)) (let ((f (lambda (y) (+ x y)))) (f 5)))` should return `15`.
    *   Multiple Arguments: `((lambda (x y) (+ x y)) 3 4)` should return `7`.
    *   Multiple Body Expressions: `((lambda (x) (define y (+ x 1)) (* y 2)) 5)` should return `12`.
    *   Error Handling: Test calling with wrong number of arguments. Test unbound symbols *inside* a lambda body.
5.  **Regression Testing:** Ensure all existing evaluator tests still pass.

**Step 5: Documentation (Already Drafted)**

1.  Apply the IDL documentation changes previously drafted for `sexp_evaluator_IDL.md` and `sexp_environment_IDL.md`.
2.  Update any user-facing DSL documentation to explain how to use `lambda`.

**Effort Estimate:** ~25-45 hours (as previously estimated), with significant portions dedicated to implementing `_apply_closure` correctly and writing comprehensive tests.

**Sequence:** This phase should likely occur *after* Phase 5 (`defatom`) and Phase 6 (Top-Level Integration), as it's a major internal enhancement to the evaluator, building upon the fully integrated system. It could potentially be done earlier, but carries more risk.
