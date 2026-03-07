"""
NameSetWidget — visual representation of a single NameSet in the builder.

Displays the structural slot sequence (literals + wildcard dropdowns)
and a local matrix preview.
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QComboBox, QPushButton, QListWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal

from core.models import NameSet, NameSetComponent
from core.taxonomy_manager import TaxonomyManager


class NameSetWidget(QFrame):
    sequenceChanged = pyqtSignal()

    def __init__(self, nameset: NameSet, tax_manager: TaxonomyManager, parent=None):
        super().__init__(parent)
        self.base_nameset = nameset
        self.tax_manager = tax_manager

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("NameSetWidget { background-color: #2b2b2b; border: 1px solid #444; border-radius: 3px; }")

        self.slots = []
        for c in nameset.nameset_structure:
            self.slots.append({'type': c.type, 'id': c.id, 'value': c.value})

        self.slots_layout = QHBoxLayout()
        self.slots_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.slots_container = QWidget()
        self.slots_container.setLayout(self.slots_layout)

        self.build_slots_ui_from_scratch()

        self.preview_list = QListWidget()
        self.preview_list.setMaximumHeight(80)
        self.preview_list.setStyleSheet("QListWidget { background-color: #1e1e1e; border: 1px solid #3c3f41; }")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(f"<b>NameSet component: {nameset.name}</b>"))

        main_layout.addLayout(header_layout)
        main_layout.addWidget(self.slots_container)
        main_layout.addWidget(QLabel("<i>Local Matrix Preview:</i>"))
        main_layout.addWidget(self.preview_list)

        self.last_generated_names = []

    def build_slots_ui_from_scratch(self):
        while self.slots_layout.count():
            item = self.slots_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        all_wcs = self.tax_manager.get_all_wildcards()

        for i, slot in enumerate(self.slots):
            if slot['type'] == 'literal':
                label = QLabel(slot['value'])
                label.setStyleSheet("font-weight: bold; padding: 0px 5px; font-size: 14px;")
                self.slots_layout.addWidget(label)
            elif slot['type'] == 'wildcard':
                combo = QComboBox()
                combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
                for wc in all_wcs:
                    combo.addItem(f"[{wc.name}]", userData=wc.id)
                    if wc.id == slot['id']:
                        combo.setCurrentIndex(combo.count() - 1)

                combo.currentIndexChanged.connect(lambda idx, slot_idx=i, cb=combo: self.on_wildcard_changed(slot_idx, cb))
                self.slots_layout.addWidget(combo)

        self.append_btn = QPushButton("+")
        self.append_btn.setFixedSize(24, 24)
        self.append_btn.setStyleSheet("font-weight: bold;")
        self.append_btn.clicked.connect(self.on_append_clicked)
        self.slots_layout.addWidget(self.append_btn)
        self.slots_layout.addStretch()

    def on_wildcard_changed(self, slot_idx, combo):
        self.slots[slot_idx]['id'] = combo.currentData()
        self.sequenceChanged.emit()

    def on_append_clicked(self):
        self.slots.append({'type': 'literal', 'value': '_'})
        all_wcs = self.tax_manager.get_all_wildcards()
        first_id = all_wcs[0].id if all_wcs else ""
        self.slots.append({'type': 'wildcard', 'id': first_id})

        self.build_slots_ui_from_scratch()
        self.sequenceChanged.emit()

    def generate_and_preview(self, selections):
        """Generate names from the current slot configuration using the manager's engine."""
        # Build a temporary NameSet from current slot state and delegate to the manager
        structure = [
            NameSetComponent(type=s['type'], id=s.get('id'), value=s.get('value'))
            for s in self.slots
        ]
        temp_ns = NameSet(id="_preview", name="_preview", nameset_structure=structure)
        names = self.tax_manager.generate_names_from_ns(temp_ns, selections)

        self.preview_list.clear()
        valid_names = []
        for name in names:
            if name and len(name) > 2:
                valid_names.append(name)
                self.preview_list.addItem(name)

        self.last_generated_names = valid_names
        return valid_names
