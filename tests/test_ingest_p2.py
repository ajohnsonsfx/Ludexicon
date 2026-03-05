import sys
import os

# Add src to path so we can import logic
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from logic import TaxonomyManager, Value, Wildcard, NameSet, NameSetComponent
from ingest_logic import TaxonomyIngestEngine

def run_tests():
    # 1. Setup a dummy TaxonomyManager
    tax_mgr = TaxonomyManager(core_path="dummy_core.json", project_path="dummy_proj.json")
    
    # Add some dummy data
    wc_weapon = Wildcard(id="wc.weapon", name="Weapon")
    wc_action = Wildcard(id="wc.action", name="Action")
    tax_mgr.add_item("core", wc_weapon)
    tax_mgr.add_item("core", wc_action)
    
    val_rifle = Value(id="val.rifle", name="Rifle", wildcard_id="wc.weapon", aliases=["RifleGuy", "Sniper"])
    val_sword = Value(id="val.sword", name="Sword", wildcard_id="wc.weapon")
    val_shoot = Value(id="val.shoot", name="Shoot", wildcard_id="wc.action", aliases=["Fire"])
    val_slash = Value(id="val.slash", name="Slash", wildcard_id="wc.action")
    
    tax_mgr.add_item("core", val_rifle)
    tax_mgr.add_item("core", val_sword)
    tax_mgr.add_item("core", val_shoot)
    tax_mgr.add_item("core", val_slash)
    
    # Create NameSet: Weapon_Action
    ns = NameSet(
        id="ns.weapon_action",
        name="Weapon Action",
        nameset_structure=[
            NameSetComponent(type="wildcard", id="wc.weapon"),
            NameSetComponent(type="literal", value="_"),
            NameSetComponent(type="wildcard", id="wc.action")
        ]
    )
    tax_mgr.add_item("core", ns)
    
    # 2. Initialize Engine
    engine = TaxonomyIngestEngine(tax_mgr)
    
    print("--- Known Names Cache ---")
    for name in sorted(engine._known_names):
        print(name)
        
    print("\n--- Tokenization Test ---")
    test_strings = [
        "Rifle_Shoot",       # Should be skipped (known, standard)
        "Sniper_Fire",       # Should be skipped (known, alias + alias)
        "HeavyMachineGun_Reload", # Unknown, PascalCase check
        "sword-slash",       # Unknown delimiter (-)
        "JumpAttack_01"      # Unknown, numbers
    ]
    
    for s in test_strings:
        tokens = engine.split_into_tokens(s)
        is_known = s in engine._known_names
        print(f"'{s}' -> Known: {is_known} | Tokens: {tokens}")

if __name__ == "__main__":
    run_tests()
