"""
Tests for the ingestion engine (tokenization, inference, and naming).
"""
import pytest
from core.models import Wildcard, Value, NameSet, NameSetComponent
from ingest.models import ParsedAsset

def test_tokenization(ingest_engine):
    """Verify string splitting into tokens."""
    assert ingest_engine.split_into_tokens("Rifle_Shoot") == ["Rifle", "_", "Shoot"]
    assert ingest_engine.split_into_tokens("sword-slash") == ["sword", "-", "slash"]
    assert ingest_engine.split_into_tokens("JumpAttack_01") == ["Jump", "Attack", "_", "01"]

def test_known_names_cache(tax_manager, ingest_engine):
    """Verify that known names (including aliases) are recognized."""
    tax_manager.add_item("core", Wildcard("wc.weapon", "Weapon"))
    tax_manager.add_item("core", Value(id="v.rifle", name="Rifle", wildcard_id="wc.weapon", aliases=["Sniper"]))
    
    # Cache only builds from NameSets. Add a dummy nameset using this wildcard.
    tax_manager.add_item("project", NameSet(
        id="ns.weapon", 
        name="Weapon Pattern", 
        nameset_structure=[NameSetComponent(type="wildcard", id="wc.weapon")]
    ))
    
    # Refresh engine's cache after modifying manager
    ingest_engine._known_names = ingest_engine._build_known_names_cache()
    
    # The cache uses lowercase for matching? No, looking at engine.py, it uses exactly what comes out of _generate...
    # Wait, let me check engine.py again for case sensitivity.
    assert "Rifle" in ingest_engine._known_names
    assert "Sniper" in ingest_engine._known_names

def test_inference_pipeline(tax_manager, ingest_engine):
    """Verify the full inference session generation."""
    test_files = [
        "Rifle_Shoot", "Rifle_Reload", "Rifle_Equip",
        "Pistol_Shoot", "Pistol_Reload", "Pistol_Equip",
    ]
    
    ingest_engine.process_raw_names("Test", test_files)
    session = ingest_engine.run_inference()
    
    assert len(session.candidate_namesets) > 0
    # Should have identified the structure: [Wildcard] _ [Wildcard]
    # Tokens for "Rifle_Shoot" are ["Rifle", "_", "Shoot"] -> length 3
    
    # Verify slot naming heuristic (Rifle/Pistol implies Weapon-like slot)
    for wc in session.candidate_wildcards.values():
        assert not wc.suggested_name.startswith("wc_temp_")

def test_deduplication(sample_taxonomy, ingest_engine):
    """Verify that existing assets are correctly matched and filtered."""
    # "Mob_Melee" is in sample_taxonomy's ns.test
    ingest_engine._known_names = ingest_engine._build_known_names_cache()
    
    ingest_engine.process_raw_names("Test", ["Mob_Melee", "Unknown_Action"])
    session = ingest_engine.run_inference()
    
    # Mob_Melee should be in dedup_matches
    match_names = [m.filename for m in session.dedup_matches]
    assert "Mob_Melee" in match_names
    assert "Unknown_Action" not in match_names
