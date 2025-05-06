"""
Unit tests for the SexpEnvironment class.
"""

import pytest

# Attempt to import the class under test
try:
    from src.sexp_evaluator.sexp_environment import SexpEnvironment
except ImportError:
    pytest.skip("Skipping sexp_environment tests, src.sexp_evaluator.sexp_environment not found or dependencies missing", allow_module_level=True)

# --- Test Initialization ---

def test_init_no_parent():
    """Test creating a top-level environment."""
    env = SexpEnvironment()
    assert env._parent is None
    assert env._bindings == {}

def test_init_with_parent():
    """Test creating a child environment."""
    parent_env = SexpEnvironment()
    child_env = SexpEnvironment(parent=parent_env)
    assert child_env._parent is parent_env
    assert child_env._bindings == {}

# --- Test define ---

def test_define_new_variable():
    """Test defining a new variable."""
    env = SexpEnvironment()
    env.define("x", 10)
    assert env._bindings == {"x": 10}
    env.define("y", "hello")
    assert env._bindings == {"x": 10, "y": "hello"}

def test_define_redefine_variable():
    """Test redefining an existing variable in the same scope."""
    env = SexpEnvironment()
    env.define("x", 10)
    env.define("x", 20) # Redefine
    assert env._bindings == {"x": 20}

# --- Test lookup ---

def test_lookup_local_variable():
    """Test looking up a variable defined in the local scope."""
    env = SexpEnvironment()
    env.define("x", 10)
    env.define("y", "test")
    assert env.lookup("x") == 10
    assert env.lookup("y") == "test"

def test_lookup_parent_variable():
    """Test looking up a variable defined in a parent scope."""
    parent_env = SexpEnvironment()
    parent_env.define("a", 100)
    parent_env.define("b", True)

    child_env = SexpEnvironment(parent=parent_env)
    child_env.define("c", "local")

    assert child_env.lookup("a") == 100
    assert child_env.lookup("b") is True
    assert child_env.lookup("c") == "local" # Ensure local lookup still works

def test_lookup_grandparent_variable():
    """Test looking up a variable defined two levels up."""
    grandparent_env = SexpEnvironment()
    grandparent_env.define("gvar", 5.5)

    parent_env = SexpEnvironment(parent=grandparent_env)
    parent_env.define("pvar", "parent")

    child_env = SexpEnvironment(parent=parent_env)
    child_env.define("cvar", [1, 2])

    assert child_env.lookup("gvar") == 5.5
    assert child_env.lookup("pvar") == "parent"
    assert child_env.lookup("cvar") == [1, 2]

    # Test deeper nesting
    great_grandparent_env = SexpEnvironment()
    great_grandparent_env.define("ggvar", "level3")
    grandparent_env._parent = great_grandparent_env # Manually link for this test extension

    assert child_env.lookup("ggvar") == "level3"


def test_lookup_shadowing():
    """Test that local variables shadow parent variables."""
    parent_env = SexpEnvironment()
    parent_env.define("x", 10)
    parent_env.define("y", "parent")

    child_env = SexpEnvironment(parent=parent_env)
    child_env.define("x", 20) # Shadows parent's x

    assert child_env.lookup("x") == 20 # Should get child's value
    assert child_env.lookup("y") == "parent" # Should get parent's value

    # Test shadowing with deeper nesting (simulating lambda call frame shadowing definition env)
    inner_child_env = child_env.extend({"x": 30, "y": "inner_child"}) # x shadows child, y shadows parent
    inner_child_env.define("z_local", "local_to_inner")

    assert inner_child_env.lookup("x") == 30 # Innermost x
    assert inner_child_env.lookup("y") == "inner_child" # Innermost y
    assert inner_child_env.lookup("z_local") == "local_to_inner"
    # Check that parent_env is not affected by child's shadowing for its own lookups
    assert parent_env.lookup("x") == 10

    # Simulate lambda lexical scope and parameter shadowing
    global_env = SexpEnvironment(bindings={"global_z": 500, "x": 1}) # Global 'x'
    
    # def_env captures 'global_z' and shadows global 'x' with its own 'x'
    def_env = global_env.extend({"x": 10, "captured_y": 20}) # Lambda defined here
    
    # call_env is for a call to the lambda. 'x' is a parameter, shadowing def_env's 'x'.
    # 'param_arg' is another parameter.
    call_env = def_env.extend({"x": 100, "param_arg": 30}) # Lambda called here

    assert call_env.lookup("x") == 100  # 'x' from call_env (parameter)
    assert call_env.lookup("param_arg") == 30 # 'param_arg' from call_env (parameter)
    assert call_env.lookup("captured_y") == 20 # 'captured_y' from def_env (lexical capture)
    assert call_env.lookup("global_z") == 500 # 'global_z' from global_env (lexical capture)
    
    # Verify original environments are untouched
    assert def_env.lookup("x") == 10
    with pytest.raises(NameError): # param_arg not in def_env
        def_env.lookup("param_arg")
    assert global_env.lookup("x") == 1


def test_lookup_not_found_local():
    """Test looking up a non-existent variable in a top-level scope."""
    env = SexpEnvironment()
    with pytest.raises(NameError, match="Name 'z' is not defined."):
        env.lookup("z")

def test_lookup_not_found_in_chain():
    """Test looking up a non-existent variable in a nested scope."""
    parent_env = SexpEnvironment()
    parent_env.define("a", 1)
    child_env = SexpEnvironment(parent=parent_env)
    child_env.define("b", 2)

    with pytest.raises(NameError, match="Unbound symbol: Name 'z' is not defined."):
        child_env.lookup("z")

# --- Test extend ---

def test_extend_creates_child():
    """Test that extend creates a new environment with the correct parent."""
    parent_env = SexpEnvironment()
    parent_env.define("p", 1)

    child_env = parent_env.extend({"c": 2, "d": 3})

    assert isinstance(child_env, SexpEnvironment)
    assert child_env._parent is parent_env
    # Verify that the parent of the child_env is indeed the parent_env instance
    # This is crucial for lexical scoping in closures.
    # Accessing _parent directly for test verification is acceptable here.
    assert child_env._parent is parent_env, \
        f"Child environment's parent ID {id(child_env._parent)} does not match parent_env ID {id(parent_env)}"


def test_extend_adds_bindings():
    """Test that extend adds the specified bindings to the child."""
    parent_env = SexpEnvironment()
    bindings = {"x": 10, "y": "hello"}
    child_env = parent_env.extend(bindings)

    assert child_env.get_local_bindings() == bindings
    # Ensure parent bindings are not affected
    assert parent_env.get_local_bindings() == {}

def test_extend_lookup_inherited_and_new():
    """Test lookup in an extended environment."""
    parent_env = SexpEnvironment()
    parent_env.define("a", 100)

    child_env = parent_env.extend({"b": 200, "c": 300})

    assert child_env.lookup("a") == 100 # Inherited
    assert child_env.lookup("b") == 200 # New
    assert child_env.lookup("c") == 300 # New

def test_extend_does_not_modify_parent():
    """Test that extend does not modify the parent environment."""
    parent_env = SexpEnvironment()
    parent_env.define("a", 1)
    parent_bindings_before = parent_env.get_local_bindings()

    child_env = parent_env.extend({"b": 2})

    assert parent_env.get_local_bindings() == parent_bindings_before # Parent unchanged
    assert child_env.lookup("b") == 2

# --- Test get_local_bindings ---

def test_get_local_bindings():
    """Test retrieving only local bindings."""
    parent_env = SexpEnvironment()
    parent_env.define("p", 1)

    child_env = parent_env.extend({"c": 2})
    child_env.define("d", 3) # Define another local var after extend

    local_bindings = child_env.get_local_bindings()
    assert local_bindings == {"c": 2, "d": 3}
    assert "p" not in local_bindings # Parent binding should not be included
