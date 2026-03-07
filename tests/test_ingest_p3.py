import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from logic import TaxonomyManager
from ingest_logic import TaxonomyIngestEngine, ParsedAsset

def run_p3_tests():
    tax_mgr = TaxonomyManager(core_path="dummy_core.json", project_path="dummy_proj.json")
    engine = TaxonomyIngestEngine(tax_mgr)
    
    # 1. Manually add ParsedAssets to engine representing a dummy directory scan
    test_files = [
        "Rifle_Shoot",
        "Rifle_Reload",
        "Rifle_Equip",
        "Pistol_Shoot",
        "Pistol_Reload",
        "Pistol_Equip",
        "Shotgun_Shoot",
        "Shotgun_Reload",
        "Shotgun_Equip",
        "AlienGun_Charge",
        "Footstep_Dirt_Walk_01",
        "Footstep_Wood_Walk_02",
        "sword-slash",
    ]
    
    for f in test_files:
        tokens = engine.split_into_tokens(f)
        engine.pending_assets.append(ParsedAsset(
            original_path=f"C:/fake/{f}.wav",
            filename=f,
            tokens=tokens,
            skipped=False
        ))
        
    session = engine.run_inference()
    
    print(f"Total Candidate Patterns: {len(session.candidate_namesets)}")
    for ns in session.candidate_namesets:
        print(f"\n--- Pattern [{ns.temp_id}] '{ns.suggested_name}' (Conf: {ns.confidence}%) ---")
        print(f"Structure: {ns.structure}")
        print(f"Matched Assets: {len(ns.matched_assets)}")
        
    print(f"\nTotal Candidate Slots: {len(session.candidate_wildcards)}")
    for wc_id, wc in session.candidate_wildcards.items():
        print(f"\n--- Slot [{wc_id}] '{wc.suggested_name}' (Conf: {wc.confidence}%) ---")
        for val in wc.values:
            print(f"  - Value: '{val.name}' (Conf: {val.confidence}%)")

    # Verify that wildcard names are NOT generic temp IDs
    print("\n=== NAMING VERIFICATION ===")
    all_passed = True
    for wc_id, wc in session.candidate_wildcards.items():
        if wc.suggested_name.startswith("wc_temp_"):
            print(f"FAIL: Slot {wc_id} still has a generic temp name: {wc.suggested_name}")
            all_passed = False
        else:
            print(f"OK: Slot {wc_id} named '{wc.suggested_name}'")
    
    if all_passed:
        print("\nAll slots have meaningful names!")
    else:
        print("\nSome slots still have generic names (may need heuristic tuning)")

if __name__ == "__main__":
    run_p3_tests()
