from logic import TaxonomyManager, Wildcard, Element, Pattern, PatternComponent, Trigger

def run_tests():
    # Instantiate manager with file paths
    manager = TaxonomyManager()
    
    # 1. Setup Core Taxonomy
    manager.add_item("core", Wildcard("wc.entity_class", "Entity Class"))
    manager.add_item("core", Wildcard("wc.action", "Action"))
    manager.add_item("core", Wildcard("wc.mob_id", "Mob ID"))
    
    # Adding Elements
    manager.add_item("core", Element(
        id="el.class.mob",
        name="Mob",
        wildcard_id="wc.entity_class",
        triggers=[Trigger(id="wc.mob_id", delimiter="_")]
    ))
    
    manager.add_item("core", Element(
        id="el.action.melee",
        name="Melee",
        wildcard_id="wc.action"
    ))
    manager.add_item("core", Element(
        id="el.action.ranged",
        name="Ranged",
        wildcard_id="wc.action"
    ))
    manager.add_item("core", Element(
        id="el.action.impact",
        name="Impact",
        wildcard_id="wc.action"
    ))
    manager.add_item("core", Element(
        id="el.action.walk",
        name="Walk",
        wildcard_id="wc.action"
    ))
    
    # 2. Setup Project Taxonomy
    manager.add_item("project", Element(
        id="el.mob.saltdevil",
        name="SaltDevil",
        wildcard_id="wc.mob_id"
    ))
    
    # Pattern
    manager.add_item("project", Pattern(
        id="pat.combat.melee",
        name="Entity Attack",
        filename_structure=[
            PatternComponent(type="wildcard", id="wc.entity_class"),
            PatternComponent(type="literal", value="_"),
            PatternComponent(type="wildcard", id="wc.action")
        ]
    ))
    
    # 3. Save to JSON deterministically
    print("Saving Core and Project Taxonomies...")
    manager.save()
    print("Files 'dictionary_core.json' and 'dictionary_project.json' saved successfully.")
    print("-" * 40)
    
    # Reload from JSON to verify saving/parsing works
    new_manager = TaxonomyManager()
    new_manager.load()
    
    # 4. Matrix Generation
    # Let's say the user clicks specific checkboxes in the unified builder:
    selections = {
        "wc.entity_class": [new_manager.get_element("el.class.mob")],
        "wc.mob_id": [new_manager.get_element("el.mob.saltdevil")], 
        "wc.action": [
            new_manager.get_element("el.action.melee"),
            new_manager.get_element("el.action.ranged"),
            new_manager.get_element("el.action.impact")
        ]
    }
    
    print("Generating matrix of 3 asset names in memory...")
    names = new_manager.generate_names("pat.combat.melee", selections)
    
    for i, name in enumerate(names, 1):
        print(f"[{i}] -> {name}")
        
    print("-" * 40)
    print("Data Logic test completed.")

if __name__ == "__main__":
    run_tests()
