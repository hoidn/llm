"""
Unit tests for the TemplateRegistry class.
"""

import pytest
import logging
from src.task_system.template_registry import TemplateRegistry

# Basic valid atomic template structure for tests
VALID_ATOMIC_TEMPLATE_REG = {
    "name": "test_reg_atomic", 
    "type": "atomic", 
    "subtype": "standard",
    "description": "A test template", 
    "params": {"input1": {}}
}

VALID_COMPOSITE_TEMPLATE_REG = {
    "name": "test_reg_composite",
    "type": "composite",  # Non-atomic type
    "subtype": "test_composite_subtype",
    "description": "A composite task",
    "params": {},
}

@pytest.fixture
def registry():
    """Fixture for a clean TemplateRegistry instance."""
    return TemplateRegistry()

# --- Test register method ---

def test_register_success(registry):
    """Test registering a valid atomic template."""
    template = VALID_ATOMIC_TEMPLATE_REG.copy()
    result = registry.register(template)

    assert result is True
    assert "test_reg_atomic" in registry.templates
    assert registry.templates["test_reg_atomic"] == template
    assert f"atomic:{template['subtype']}" in registry.template_index
    assert registry.template_index[f"atomic:{template['subtype']}"] == "test_reg_atomic"

def test_register_missing_required_fields(registry, caplog):
    """Test registration fails if name, subtype, or params is missing for an atomic template."""
    template_no_name = VALID_ATOMIC_TEMPLATE_REG.copy()
    del template_no_name["name"]
    template_no_subtype = VALID_ATOMIC_TEMPLATE_REG.copy()
    del template_no_subtype["subtype"]
    template_no_params = VALID_ATOMIC_TEMPLATE_REG.copy()
    del template_no_params["params"]

    with caplog.at_level(logging.ERROR):
        # Test missing name
        result = registry.register(template_no_name)
        assert result is False
        assert "Registration failed: Atomic template missing 'name' or 'subtype'" in caplog.text
        caplog.clear()

        # Test missing subtype
        result = registry.register(template_no_subtype)
        assert result is False
        assert "Registration failed: Atomic template missing 'name' or 'subtype'" in caplog.text
        caplog.clear()
        
        # Test missing params
        result = registry.register(template_no_params)
        assert result is False
        assert "Registration failed: Atomic template 'test_reg_atomic' must have a 'params' definition" in caplog.text

def test_register_non_atomic_is_rejected(registry, caplog):
    """Test registering a non-atomic template is rejected."""
    template = VALID_COMPOSITE_TEMPLATE_REG.copy()
    with caplog.at_level(logging.ERROR):
        result = registry.register(template)
        assert result is False
        assert "Registration failed: Template 'test_reg_composite' is not atomic" in caplog.text
        # Check it wasn't actually registered
        assert template["name"] not in registry.templates
        type_subtype_key = f"{template['type']}:{template['subtype']}"
        assert type_subtype_key not in registry.template_index

def test_register_missing_description_warns(registry, caplog):
    """Test registering an atomic template without 'description' logs a warning."""
    template = VALID_ATOMIC_TEMPLATE_REG.copy()
    name = template["name"]
    del template["description"] # Remove description
    with caplog.at_level(logging.WARNING):
        result = registry.register(template)
        assert result is True
        assert f"Atomic template '{name}' registered without a 'description'" in caplog.text
    assert template["name"] in registry.templates  # Still registered

def test_register_invalid_params_is_rejected(registry, caplog):
    """Test registering an atomic template with invalid 'params' type is rejected."""
    template_invalid_params = VALID_ATOMIC_TEMPLATE_REG.copy()
    template_invalid_params["params"] = "not a dictionary"  # Invalid params type
    
    with caplog.at_level(logging.ERROR):
        result = registry.register(template_invalid_params)
        assert result is False
        assert "Registration failed: Atomic template 'test_reg_atomic' has invalid 'params' definition" in caplog.text
        
    # Verify template was not registered
    assert "test_reg_atomic" not in registry.templates

def test_register_overwrites(registry):
    """Test registering a template with the same name overwrites the previous one."""
    template1 = VALID_ATOMIC_TEMPLATE_REG.copy()
    template1_subtype = template1["subtype"]
    template2 = VALID_ATOMIC_TEMPLATE_REG.copy()
    template2["description"] = "Updated description"
    template2["subtype"] = "new_subtype"  # Change subtype to check index update

    registry.register(template1)
    assert registry.templates["test_reg_atomic"]["description"] == "A test template"
    assert registry.template_index[f"atomic:{template1_subtype}"] == "test_reg_atomic"
    assert "atomic:new_subtype" not in registry.template_index

    registry.register(template2)
    assert registry.templates["test_reg_atomic"]["description"] == "Updated description"
    # Index should be updated to the new subtype for that name
    assert registry.template_index["atomic:new_subtype"] == "test_reg_atomic"
    # Old index key should be removed
    assert f"atomic:{template1_subtype}" not in registry.template_index

# --- Test find method ---

def test_find_by_name(registry):
    """Test finding an atomic template by its name."""
    template = VALID_ATOMIC_TEMPLATE_REG.copy()
    registry.register(template)
    found = registry.find("test_reg_atomic")
    assert found == template

def test_find_by_type_subtype(registry):
    """Test finding an atomic template by its type:subtype."""
    template = VALID_ATOMIC_TEMPLATE_REG.copy()
    registry.register(template)
    found = registry.find(f"atomic:{template['subtype']}")
    assert found == template

def test_find_not_found(registry):
    """Test finding a non-existent template returns None."""
    assert registry.find("non_existent_task") is None
    assert registry.find("atomic:non_existent") is None

def test_find_index_inconsistency(registry, caplog):
    """Test handling of index inconsistency."""
    # Manually create an inconsistent state
    registry.template_index["atomic:test"] = "missing_template"
    
    with caplog.at_level(logging.ERROR):
        result = registry.find("atomic:test")
        assert result is None
        assert "Registry index inconsistency" in caplog.text

# --- Test get_all_atomic_templates method ---

def test_get_all_atomic_templates(registry):
    """Test retrieving all atomic templates."""
    template1 = VALID_ATOMIC_TEMPLATE_REG.copy()
    template2 = VALID_ATOMIC_TEMPLATE_REG.copy()
    template2["name"] = "test_reg_atomic2"
    template2["subtype"] = "another_subtype"
    
    registry.register(template1)
    registry.register(template2)
    
    templates = registry.get_all_atomic_templates()
    assert len(templates) == 2
    assert template1 in templates
    assert template2 in templates
