"""
Ludexicon — Game Asset Taxonomy Engine

Entry point for the application.
"""
import sys
import os
import logging

# ─── Logging Setup ───────────────────────────────────────────────────
# Configure logging BEFORE importing any application modules so that
# all log calls throughout the app go to the log file.

_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_log_path = os.path.join(_root_dir, "ludexicon.log")

logging.basicConfig(
    filename=_log_path,
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ludexicon")

# Also keep stderr for critical errors visible
_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setLevel(logging.ERROR)
logging.getLogger().addHandler(_stderr_handler)


# ─── Application ─────────────────────────────────────────────────────

from PyQt6.QtWidgets import QApplication

from core.models import Value, Wildcard, NameSet, NameSetComponent, Trigger
from core.taxonomy_manager import TaxonomyManager
from ui.main_window import MainWindow
from ui.styles import GLOBAL_STYLESHEET


def setup_dummy_data(manager: TaxonomyManager):
    """Populates the manager with some initial data so the UI isn't empty."""
    # Core
    manager.add_item("core", Wildcard("wc.entity_class", "Entity Class"))
    manager.add_item("core", Wildcard("wc.action", "Action"))
    manager.add_item("core", Wildcard("wc.mob_id", "Mob ID"))

    manager.add_item("core", Value(id="val.class.mob", name="Mob", wildcard_id="wc.entity_class", triggers=[Trigger(id="wc.mob_id", delimiter="_")]))
    manager.add_item("core", Value(id="val.action.melee", name="Melee", wildcard_id="wc.action"))
    manager.add_item("core", Value(id="val.action.ranged", name="Ranged", wildcard_id="wc.action"))
    manager.add_item("core", Value(id="val.action.impact", name="Impact", wildcard_id="wc.action"))
    manager.add_item("core", Value(id="val.action.walk", name="Walk", wildcard_id="wc.action"))

    # Project
    manager.add_item("project", Value(id="val.mob.saltdevil", name="SaltDevil", wildcard_id="wc.mob_id"))
    manager.add_item("project", Value(id="val.mob.firefiend", name="FireFiend", wildcard_id="wc.mob_id"))

    manager.add_item("project", NameSet(
        id="ns.combat.melee",
        name="Entity Attack",
        nameset_structure=[
            NameSetComponent(type="wildcard", id="wc.entity_class"),
            NameSetComponent(type="literal", value="_"),
            NameSetComponent(type="wildcard", id="wc.action")
        ]
    ))

    manager.save()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(GLOBAL_STYLESHEET)

    manager = TaxonomyManager()
    setup_dummy_data(manager)  # populate basic stuff for UX pass
    manager.load()

    window = MainWindow(manager)
    window.show()

    logger.info("Application started.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
