import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from ingest_logic import WildcardNamer

def run_naming_tests():
    namer = WildcardNamer()
    
    tests = [
        {
            "values": ["Wood", "Metal", "Stone", "Concrete", "Grass", "Dirt"],
            "expect_contains": "Surface",
            "desc": "Surface materials"
        },
        {
            "values": ["Rifle", "Pistol", "Shotgun", "Sword", "Axe"],
            "expect_contains": "Weapon",
            "desc": "Weapons"
        },
        {
            "values": ["Walk", "Run", "Jump", "Idle", "Attack", "Shoot"],
            "expect_contains": "Action",
            "desc": "Actions"
        },
        {
            "values": ["Happy", "Sad", "Angry", "Scared", "Amused"],
            "expect_contains": "Emotion",
            "desc": "Emotions"
        },
        {
            "values": ["Forest", "Cave", "Desert", "Mountain", "Ocean"],
            "expect_contains": "Environment",
            "desc": "Environments"
        },
        {
            "values": ["xq7z", "fff", "bloop", "zzzap", "narf"],
            "expect_contains": None,  # Any fallback name is fine, we just check confidence=0
            "desc": "Nonsense (should fall back)"
        },
    ]
    
    all_passed = True
    used_names = set()
    
    for i, test in enumerate(tests):
        name, conf = namer.suggest_name(test["values"], i, len(tests), used_names)
        used_names.add(name)
        
        expected = test["expect_contains"]
        if expected is None:
            # For nonsense: just verify confidence is 0
            passed = conf == 0.0
        else:
            passed = expected.lower() in name.lower()
        status = "PASS" if passed else "FAIL"
        
        if not passed:
            all_passed = False
        
        print(f"[{status}] {test['desc']}: values={test['values'][:3]}... -> '{name}' (conf: {conf:.0f}%) "
              f"[expected containing '{expected}']")
    
    print(f"\n{'All tests passed!' if all_passed else 'Some tests failed.'}")
    return all_passed

if __name__ == "__main__":
    run_naming_tests()
