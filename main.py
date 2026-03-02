import sys
from PyQt6.QtWidgets import QApplication

from data_models import TaxonomyManager, Wildcard, Element, Pattern, PatternComponent, Trigger
from ui_main import MainWindow

def setup_dummy_data(manager: TaxonomyManager):
    """Populates the manager with some initial data so the UI isn't empty."""
    # Core
    manager.add_item("core", Wildcard("wc.entity_class", "Entity Class"))
    manager.add_item("core", Wildcard("wc.action", "Action"))
    manager.add_item("core", Wildcard("wc.mob_id", "Mob ID"))
    
    manager.add_item("core", Element(id="el.class.mob", name="Mob", wildcard_id="wc.entity_class", triggers=[Trigger(id="wc.mob_id", delimiter="_")]))
    manager.add_item("core", Element(id="el.action.melee", name="Melee", wildcard_id="wc.action"))
    manager.add_item("core", Element(id="el.action.ranged", name="Ranged", wildcard_id="wc.action"))
    manager.add_item("core", Element(id="el.action.impact", name="Impact", wildcard_id="wc.action"))
    manager.add_item("core", Element(id="el.action.walk", name="Walk", wildcard_id="wc.action"))
    
    # Project
    # Note: to properly show "Mob ID" in the taxonomy tree we should technically register it in project wildcards if it's purely project side,
    # but since it's triggered from core, we registered it in core wildcards.
    manager.add_item("project", Element(id="el.mob.saltdevil", name="SaltDevil", wildcard_id="wc.mob_id"))
    manager.add_item("project", Element(id="el.mob.firefiend", name="FireFiend", wildcard_id="wc.mob_id"))
    
    manager.add_item("project", Pattern(
        id="pat.combat.melee",
        name="Entity Attack",
        filename_structure=[
            PatternComponent(type="wildcard", id="wc.entity_class"),
            PatternComponent(type="literal", value="_"),
            PatternComponent(type="wildcard", id="wc.action")
        ]
    ))
    
    manager.save()

def main():
    app = QApplication(sys.argv)
    
    # Standard dense styling
    app.setStyleSheet("""
        QMainWindow { background-color: #2b2b2b; color: #e0e0e0; }
        QWidget { background-color: #2b2b2b; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
        QDockWidget { border: 1px solid #444; }
        QDockWidget::title { background: #3c3f41; padding: 4px; text-align: center; }
        QPushButton { background-color: #3c3f41; border: 1px solid #555; padding: 4px; border-radius: 2px; }
        QPushButton:hover { background-color: #4b4d4f; }
        QPushButton:checked { background-color: #5b5d5f; }
        QLineEdit, QTreeView, QListWidget, QScrollArea { background-color: #1e1e1e; border: 1px solid #3c3f41; }
        QHeaderView::section { background-color: #3c3f41; padding: 4px; border: 1px solid #333; }
        QTreeView::item:hover, QListWidget::item:hover { background-color: #2a2d2f; }
        QTreeView::item:selected, QListWidget::item:selected { background-color: #4b6eaf; }
        QMenu { background-color: #2b2b2b; border: 1px solid #555; }
        QMenu::item { padding: 4px 24px; }
        QMenu::item:selected { background-color: #4b6eaf; }
    """)
    
    manager = TaxonomyManager("core_lexicon.json", "project_taxonomy.json")
    setup_dummy_data(manager) # populate basic stuff for UX pass
    manager.load()
    
    window = MainWindow(manager)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
