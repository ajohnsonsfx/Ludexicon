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
        "AlienGun_Charge", # 10 files of length 3 (if we keep delimiter)
        "Footstep_Dirt_Walk_01",
        "Footstep_Wood_Walk_02", # 2 files of length 7
        "sword-slash", # length 3, different delimiter
    ]
    
    for f in test_files:
        tokens = engine.split_into_tokens(f)
        engine.pending_assets.append(ParsedAsset(
            original_path=f"C:/fake/{f}.wav",
            filename=f,
            tokens=tokens,
            skipped=False
        ))
        
    namesets, wildcards = engine.run_inference()
    
    print(f"Total Candidate NameSets: {len(namesets)}")
    for ns in namesets:
        print(f"\n--- NameSet [{ns.temp_id}] (Conf: {ns.confidence}%) ---")
        print(f"Structure: {ns.structure}")
        print(f"Matched Assets: {len(ns.matched_assets)}")
        
    print(f"\nTotal Candidate Wildcards: {len(wildcards)}")
    for wc_id, wc in wildcards.items():
        print(f"\n--- Wildcard [{wc_id}] (Conf: {wc.confidence}%) ---")
        for val in wc.values:
            print(f"  - Value: '{val.name}' (Conf: {val.confidence}%)")

if __name__ == "__main__":
    run_p3_tests()
