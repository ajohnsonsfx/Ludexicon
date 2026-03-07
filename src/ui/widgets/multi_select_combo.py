"""
Reusable multi-select dropdown button using QMenu.
"""
from PyQt6.QtWidgets import QPushButton, QMenu
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction

from core.models import Value


class MultiSelectComboBox(QPushButton):
    """
    A multi-select dropdown button using QMenu.
    """
    selectionChanged = pyqtSignal()

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.title_base = title

        self.menu = QMenu(self)
        self.setMenu(self.menu)

        self._action_value_map = {}

        self.menu.triggered.connect(self._on_action_triggered)
        self.setStyleSheet("text-align: left;")

    def add_value(self, value: Value):
        action = QAction(value.name, self.menu)
        action.setCheckable(True)
        self.menu.addAction(action)
        self._action_value_map[action] = value

    def clear(self):
        self.menu.clear()
        self._action_value_map.clear()
        self.setText(self.title_base)

    def _on_action_triggered(self, action: QAction):
        self.menu.show()  # keep open
        self.update_title()
        self.selectionChanged.emit()

    def update_title(self):
        selected = self.get_selected_values()
        if not selected:
            self.setText(self.title_base)
        elif len(selected) == 1:
            self.setText(f"{self.title_base}: {selected[0].name}")
        else:
            self.setText(f"{self.title_base}: [ {len(selected)} selected ]")

    def get_selected_values(self):
        return [self._action_value_map[act] for act, val in self._action_value_map.items() if act.isChecked()]
