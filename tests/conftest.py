"""
Shared pytest fixtures for Ludexicon tests.
"""
import pytest
import os
import shutil
import tempfile
from core.taxonomy_manager import TaxonomyManager
from core.models import Wildcard, Value, NameSet, NameSetComponent, Trigger
from ingest.engine import TaxonomyIngestEngine

@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for dictionary files."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)

@pytest.fixture
def tax_manager(temp_data_dir):
    """Provide a clean TaxonomyManager instance."""
    core_path = os.path.join(temp_data_dir, "test_core.json")
    proj_path = os.path.join(temp_data_dir, "test_proj.json")
    return TaxonomyManager(core_path=core_path, project_path=proj_path)

@pytest.fixture
def ingest_engine(tax_manager):
    """Provide a TaxonomyIngestEngine instance."""
    return TaxonomyIngestEngine(tax_manager)

@pytest.fixture
def sample_taxonomy(tax_manager):
    """Populate a manager with basic test data."""
    # Core
    tax_manager.add_item("core", Wildcard("wc.entity_class", "Entity Class"))
    tax_manager.add_item("core", Wildcard("wc.action", "Action"))
    
    tax_manager.add_item("core", Value(
        id="val.class.mob",
        name="Mob",
        wildcard_id="wc.entity_class"
    ))
    tax_manager.add_item("core", Value(
        id="val.action.melee",
        name="Melee",
        wildcard_id="wc.action"
    ))
    
    # Project
    tax_manager.add_item("project", NameSet(
        id="ns.test",
        name="Test Pattern",
        nameset_structure=[
            NameSetComponent(type="wildcard", id="wc.entity_class"),
            NameSetComponent(type="literal", value="_"),
            NameSetComponent(type="wildcard", id="wc.action")
        ]
    ))
    return tax_manager
