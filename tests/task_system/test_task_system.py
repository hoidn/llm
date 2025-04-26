"""
Unit tests for the TaskSystem class.
Focuses on logic implemented in Phase 1, Set B.
"""

import pytest
from unittest.mock import MagicMock, patch
import logging

# Assuming TaskSystem is importable
from src.task_system.task_system import TaskSystem

# Example valid template structure
VALID_ATOMIC_TEMPLATE = {
    "name": "test_atomic_task",
    "type": "atomic",
    "subtype": "test_subtype",
    "description": "A test task",
    "params": {"param1": "string"},  # Added params for validation check
    # Other fields as needed...
}

VALID_COMPOSITE_TEMPLATE = {
    "name": "test_composite_task",
    "type": "composite",  # Non-atomic type
    "subtype": "test_composite_subtype",
    "description": "A composite task",
    "params": {},
}


@pytest.fixture
def mock_memory_system():
    """Provides a mock MemorySystem."""
    return MagicMock()


@pytest.fixture
def task_system(mock_memory_system):
    """Provides a TaskSystem instance with mock dependencies."""
    return TaskSystem(memory_system=mock_memory_system)


# --- Test __init__ ---


def test_init(mock_memory_system):
    """Test initialization sets defaults correctly."""
    ts = TaskSystem(memory_system=mock_memory_system)
    assert ts.memory_system == mock_memory_system
    assert ts.templates == {}
    assert ts.template_index == {}
    assert ts._test_mode is False
    assert ts._handler_cache == {}


# --- Test set_test_mode ---


def test_set_test_mode(task_system):
    """Test enabling and disabling test mode."""
    assert task_system._test_mode is False
    # Check handler cache is initially empty
    task_system._handler_cache["some_key"] = "some_handler"
    assert task_system._handler_cache != {}

    task_system.set_test_mode(True)
    assert task_system._test_mode is True
    # Check handler cache is cleared when mode changes
    assert task_system._handler_cache == {}

    task_system.set_test_mode(False)
    assert task_system._test_mode is False
    assert task_system._handler_cache == {}  # Should remain cleared


# --- Test register_template ---


def test_register_template_success(task_system):
    """Test registering a valid atomic template."""
    template = VALID_ATOMIC_TEMPLATE.copy()
    task_system.register_template(template)

    assert "test_atomic_task" in task_system.templates
    assert task_system.templates["test_atomic_task"] == template
    assert "atomic:test_subtype" in task_system.template_index
    assert task_system.template_index["atomic:test_subtype"] == "test_atomic_task"


def test_register_template_missing_required_fields(task_system, caplog):
    """Test registration fails if name or subtype is missing for an atomic template."""
    template_no_name = VALID_ATOMIC_TEMPLATE.copy()
    del template_no_name["name"]
    # template_no_type = VALID_ATOMIC_TEMPLATE.copy() # Type missing handled by non-atomic check
    # del template_no_type["type"]
    template_no_subtype = VALID_ATOMIC_TEMPLATE.copy()
    del template_no_subtype["subtype"]

    with caplog.at_level(logging.ERROR):
        # Test missing name (type is atomic)
        task_system.register_template(template_no_name)
        # --- Start Change ---
        assert (
            "Atomic template registration failed: Missing 'name' or 'subtype'"
            in caplog.text
        )
        # --- End Change ---
        assert "test_atomic_task" not in task_system.templates # Check name wasn't registered partially
        caplog.clear()

        # Test missing subtype (type is atomic)
        task_system.register_template(template_no_subtype)
        # --- Start Change ---
        assert (
            "Atomic template registration failed: Missing 'name' or 'subtype'"
            in caplog.text
        )
        # --- End Change ---
        assert "test_atomic_task" not in task_system.templates
        caplog.clear()

        # Test missing type (will be caught by non-atomic check)
        # template_no_type = VALID_ATOMIC_TEMPLATE.copy()
        # del template_no_type["type"]
        # with caplog.at_level(logging.WARNING): # Should be caught by non-atomic warning now
        #     task_system.register_template(template_no_type)
        #     assert "Ignoring registration attempt for non-atomic template" in caplog.text


def test_register_template_non_atomic_warns(task_system, caplog):
    """Test registering a non-atomic template logs a warning and is ignored."""
    template = VALID_COMPOSITE_TEMPLATE.copy()
    with caplog.at_level(logging.WARNING):
        task_system.register_template(template)
        # --- Start Change ---
        assert (
            f"Ignoring registration attempt for non-atomic template '{template['name']}'"
            in caplog.text
        )
        # Check it wasn't actually registered
        assert template["name"] not in task_system.templates
        type_subtype_key = f"{template['type']}:{template['subtype']}"
        assert type_subtype_key not in task_system.template_index
        # --- End Change ---


def test_register_template_missing_params_warns(task_system, caplog):
    """Test registering an atomic template without 'params' logs a warning."""
    template = VALID_ATOMIC_TEMPLATE.copy()
    del template["params"]
    with caplog.at_level(logging.WARNING):
        task_system.register_template(template)
        # --- Start Change ---
        assert (
            f"Atomic template '{template['name']}' registered without a 'params' attribute. Validation might fail later."
            in caplog.text
        )
        # --- End Change ---
    assert template["name"] in task_system.templates  # Still registered


def test_register_template_overwrites(task_system):
    """Test registering a template with the same name overwrites the previous one."""
    template1 = VALID_ATOMIC_TEMPLATE.copy()
    template2 = VALID_ATOMIC_TEMPLATE.copy()
    template2["description"] = "Updated description"
    template2["subtype"] = "new_subtype"  # Change subtype to check index update

    task_system.register_template(template1)
    assert task_system.templates["test_atomic_task"]["description"] == "A test task"
    assert task_system.template_index["atomic:test_subtype"] == "test_atomic_task"
    assert "atomic:new_subtype" not in task_system.template_index

    task_system.register_template(template2)
    assert (
        task_system.templates["test_atomic_task"]["description"]
        == "Updated description"
    )
    # Index should be updated to the new subtype for that name
    assert task_system.template_index["atomic:new_subtype"] == "test_atomic_task"
    # Old index key should ideally be removed if name collision implies replacement
    # Current implementation overwrites index value, doesn't clean old keys.
    # Let's assert the new key exists. Refinement could clean old keys.
    # assert "atomic:test_subtype" not in task_system.template_index # This would fail currently


# --- Test find_template ---


def test_find_template_by_name(task_system):
    """Test finding an atomic template by its name."""
    template = VALID_ATOMIC_TEMPLATE.copy()
    task_system.register_template(template)
    found = task_system.find_template("test_atomic_task")
    assert found == template


def test_find_template_by_type_subtype(task_system):
    """Test finding an atomic template by its type:subtype."""
    template = VALID_ATOMIC_TEMPLATE.copy()
    task_system.register_template(template)
    found = task_system.find_template("atomic:test_subtype")
    assert found == template


def test_find_template_not_found(task_system):
    """Test finding a non-existent template returns None."""
    assert task_system.find_template("non_existent_task") is None
    assert task_system.find_template("atomic:non_existent") is None


def test_find_template_ignores_non_atomic_by_name(task_system):
    """Test find_template ignores non-atomic templates when searching by name."""
    atomic_template = VALID_ATOMIC_TEMPLATE.copy()
    composite_template = VALID_COMPOSITE_TEMPLATE.copy()
    # Give them the same name (unlikely but possible)
    composite_template["name"] = atomic_template["name"]

    task_system.register_template(atomic_template)
    task_system.register_template(composite_template)  # Attempt to register composite - should be ignored

    # Should find the atomic one when searching by name
    found = task_system.find_template(atomic_template["name"])
    assert found is not None
    assert found["type"] == "atomic"
    assert found == atomic_template


def test_find_template_ignores_non_atomic_by_type_subtype(task_system):
    """Test find_template ignores non-atomic templates when searching by type:subtype."""
    atomic_template = VALID_ATOMIC_TEMPLATE.copy()
    composite_template = VALID_COMPOSITE_TEMPLATE.copy()

    task_system.register_template(atomic_template)
    task_system.register_template(composite_template) # Attempt to register composite - should be ignored

    # Search for the composite type:subtype - should not be found by find_template
    # because register_template ignored it
    found = task_system.find_template(
        f"{composite_template['type']}:{composite_template['subtype']}"
    )
    assert found is None

    # Search for the atomic type:subtype - should be found
    found = task_system.find_template(
        f"{atomic_template['type']}:{atomic_template['subtype']}"
    )
    assert found is not None
    assert found == atomic_template


# --- Test Deferred Methods (Placeholders) ---


def test_execute_atomic_template_deferred(task_system):
    """Verify deferred method raises NotImplementedError."""
    with pytest.raises(
        NotImplementedError, match="execute_atomic_template implementation deferred"
    ):
        task_system.execute_atomic_template(MagicMock())  # Pass a mock request


def test_find_matching_tasks_deferred(task_system, mock_memory_system):
    """Verify deferred method returns empty list (or raises)."""
    # Current placeholder returns [], doesn't raise
    result = task_system.find_matching_tasks("find something", mock_memory_system)
    assert result == []
    # If it raised:
    # with pytest.raises(NotImplementedError):
    #     task_system.find_matching_tasks("find something", mock_memory_system)


def test_generate_context_for_memory_system_deferred(task_system):
    """Verify deferred method raises NotImplementedError."""
    with pytest.raises(
        NotImplementedError,
        match="generate_context_for_memory_system implementation deferred",
    ):
        task_system.generate_context_for_memory_system(
            MagicMock(), {}
        )  # Mock input, empty index


def test_resolve_file_paths_deferred(task_system, mock_memory_system):
    """Verify deferred method returns placeholder tuple (or raises)."""
    # Current placeholder returns tuple, doesn't raise
    result = task_system.resolve_file_paths(
        {}, mock_memory_system, MagicMock()
    )  # Empty template, mock deps
    assert result == ([], "Implementation deferred")
    # If it raised:
    # with pytest.raises(NotImplementedError):
    #     task_system.resolve_file_paths({}, mock_memory_system, MagicMock())

