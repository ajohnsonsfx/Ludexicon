"""
Tests for core taxonomy logic (models, manager, persistence).
"""
import os
from core.models import Wildcard, Value, NameSet, NameSetComponent, Trigger

def test_manager_persistence(tax_manager):
    """Verify saving and loading taxonomies."""
    tax_manager.add_item("core", Wildcard("wc.test", "Test Wildcard"))
    tax_manager.save()
    
    assert os.path.exists(tax_manager.core_path)
    
    # Reload in a new manager
    new_manager = type(tax_manager)(
        core_path=tax_manager.core_path, 
        project_path=tax_manager.project_path
    )
    new_manager.load()
    
    wc = new_manager.get_wildcard("wc.test")
    assert wc is not None
    assert wc.name == "Test Wildcard"

def test_matrix_generation(sample_taxonomy):
    """Verify asset name permutation logic."""
    # Setup selections
    selections = {
        "wc.entity_class": [sample_taxonomy.get_value("val.class.mob")],
        "wc.action": [sample_taxonomy.get_value("val.action.melee")]
    }
    
    names = sample_taxonomy.generate_names("ns.test", selections)
    assert len(names) == 1
    assert names[0] == "Mob_Melee"

def test_triggers(tax_manager):
    """Verify that triggers add required wildcards to the UI selection set."""
    tax_manager.add_item("core", Wildcard("wc.base", "Base"))
    tax_manager.add_item("core", Wildcard("wc.sub", "Sub"))
    tax_manager.add_item("core", Value(
        id="val.triggered", 
        name="Trigger", 
        wildcard_id="wc.base",
        triggers=[Trigger(id="wc.sub", delimiter="-")]
    ))
    
    # This logic is usually handled in UI, but the manager's 
    # generate_names_from_ns handles trigger resolution.
    
    structure = [
        NameSetComponent(type="wildcard", id="wc.base")
    ]
    ns = NameSet(id="ns.trigger", name="Trigger Test", nameset_structure=structure)
    
    # If wc.base= Trigger, then wc.sub is resolved
    selections = {
        "wc.base": [tax_manager.get_value("val.triggered")],
        "wc.sub": [Value(id="val.s1", name="S1", wildcard_id="wc.sub")]
    }
    
    names = tax_manager.generate_names_from_ns(ns, selections)
    assert "Trigger-S1" in names
