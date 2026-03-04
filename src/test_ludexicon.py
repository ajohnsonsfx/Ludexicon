from logic import TaxonomyManager, Wildcard, Value, NameSet, NameSetComponent, Trigger

def run_tests():
    # Instantiate manager with file paths
    manager = TaxonomyManager()
    
    # 1. Setup Core Taxonomy
    manager.add_item("core", Wildcard("wc.entity_class", "Entity Class"))
    manager.add_item("core", Wildcard("wc.action", "Action"))
    manager.add_item("core", Wildcard("wc.mob_id", "Mob ID"))
    
    # Adding Values
    manager.add_item("core", Value(
        id="val.class.mob",
        name="Mob",
        wildcard_id="wc.entity_class",
        triggers=[Trigger(id="wc.mob_id", delimiter="_")]
    ))
    
    manager.add_item("core", Value(
        id="val.action.melee",
        name="Melee",
        wildcard_id="wc.action"
    ))
    manager.add_item("core", Value(
        id="val.action.ranged",
        name="Ranged",
        wildcard_id="wc.action"
    ))
    manager.add_item("core", Value(
        id="val.action.impact",
        name="Impact",
        wildcard_id="wc.action"
    ))
    manager.add_item("core", Value(
        id="val.action.walk",
        name="Walk",
        wildcard_id="wc.action"
    ))
    
    # 2. Setup Project Taxonomy
    manager.add_item("project", Value(
        id="val.mob.saltdevil",
        name="SaltDevil",
        wildcard_id="wc.mob_id"
    ))
    
    # NameSet
    manager.add_item("project", NameSet(
        id="ns.combat.melee",
        name="Entity Attack",
        nameset_structure=[
            NameSetComponent(type="wildcard", id="wc.entity_class"),
            NameSetComponent(type="literal", value="_"),
            NameSetComponent(type="wildcard", id="wc.action")
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
        "wc.entity_class": [new_manager.get_value("val.class.mob")],
        "wc.mob_id": [new_manager.get_value("val.mob.saltdevil")], 
        "wc.action": [
            new_manager.get_value("val.action.melee"),
            new_manager.get_value("val.action.ranged"),
            new_manager.get_value("val.action.impact")
        ]
    }
    
    print("Generating matrix of 3 asset names in memory...")
    names = new_manager.generate_names("ns.combat.melee", selections)
    
    for i, name in enumerate(names, 1):
        print(f"[{i}] -> {name}")
        
    print("-" * 40)
    print("Data Logic test completed.")

if __name__ == "__main__":
    run_tests()
