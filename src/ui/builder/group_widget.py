"""
GroupWidget — container for multiple NameSet widgets in the builder.

Manages shared wildcard selection (the collapsible "Wildcards" section)
and aggregates generated names across all child NameSets.
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import pyqtSignal

from core.taxonomy_manager import TaxonomyManager
from ui.widgets.collapsible_box import CollapsibleBox
from ui.widgets.multi_select_combo import MultiSelectComboBox
from ui.builder.nameset_widget import NameSetWidget


class GroupWidget(QFrame):
    globalMatrixUpdated = pyqtSignal()

    def __init__(self, name: str, tax_manager: TaxonomyManager, parent=None):
        super().__init__(parent)
        self.tax_manager = tax_manager

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setStyleSheet("GroupWidget { background-color: #333333; margin-bottom: 10px; border-radius: 5px; }")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        self.header_layout = QHBoxLayout()
        self.header_label = QLabel(f"<h3 style='margin:0;'>Group: {name}</h3>")
        self.add_nameset_btn = QPushButton("+ Add NameSet")
        self.add_nameset_btn.clicked.connect(self.on_add_nameset)

        self.header_layout.addWidget(self.header_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.add_nameset_btn)
        self.main_layout.addLayout(self.header_layout)

        self.collapsible_box = CollapsibleBox(title="Wildcards (Expand to lock/select)")
        self.main_layout.addWidget(self.collapsible_box)

        self.namesets_layout = QVBoxLayout()
        self.namesets_layout.setSpacing(10)
        self.main_layout.addLayout(self.namesets_layout)

        self.namesets = []
        self.wildcard_combos = {}
        self.base_wildcards = set()

    def on_add_nameset(self):
        ns = self.tax_manager.get_nameset("ns.combat.melee")
        if ns:
            self.add_nameset(ns)

    def add_nameset(self, nameset):
        nw = NameSetWidget(nameset, self.tax_manager, self)
        nw.sequenceChanged.connect(self.update_base_wildcards)
        self.namesets_layout.addWidget(nw)
        self.namesets.append(nw)
        self.update_base_wildcards()

    def update_base_wildcards(self):
        new_base = set()
        for nw in self.namesets:
            for slot in nw.slots:
                if slot['type'] == 'wildcard' and slot['id']:
                    new_base.add(slot['id'])
        self.base_wildcards = new_base
        self.sync_combos()

    def sync_combos(self):
        required = set(self.base_wildcards)
        queue = list(required)
        i = 0
        triggered = set()

        while i < len(queue):
            curr_id = queue[i]
            if curr_id in self.wildcard_combos:
                selected = self.wildcard_combos[curr_id].get_selected_values()
                for v in selected:
                    for t in v.triggers:
                        if t.id not in required and t.id not in triggered:
                            triggered.add(t.id)
                            queue.append(t.id)
            i += 1

        total_required = required.union(triggered)

        existing = set(self.wildcard_combos.keys())
        for w_id in existing - total_required:
            combo = self.wildcard_combos.pop(w_id)
            self.collapsible_box.content_layout.removeWidget(combo)
            combo.deleteLater()

        for w_id in total_required - existing:
            self.create_combobox(w_id)

        if self.collapsible_box.is_expanded:
            self.collapsible_box.content_area.setMinimumHeight(self.collapsible_box.content_layout.sizeHint().height() + 20)
            self.collapsible_box.content_area.setMaximumHeight(self.collapsible_box.content_layout.sizeHint().height() + 20)

        self.regenerate_all_matrices()

    def create_combobox(self, wildcard_id: str):
        wildcard = self.tax_manager.get_wildcard(wildcard_id)
        name = wildcard.name if wildcard else wildcard_id
        combo = MultiSelectComboBox(f"[{name}]")

        for val in self.tax_manager.get_values_for_wildcard(wildcard_id):
            combo.add_value(val)

        combo.selectionChanged.connect(self.on_selection_changed)
        self.wildcard_combos[wildcard_id] = combo
        self.collapsible_box.content_layout.addWidget(combo)
        return combo

    def on_selection_changed(self):
        self.sync_combos()

    def get_selections(self):
        return {w_id: combo.get_selected_values() for w_id, combo in self.wildcard_combos.items()}

    def regenerate_all_matrices(self):
        selections = self.get_selections()
        for nw in self.namesets:
            nw.generate_and_preview(selections)
        self.globalMatrixUpdated.emit()

    def get_all_global_matrices(self):
        global_matrix = []
        for nw in self.namesets:
            global_matrix.extend(nw.last_generated_names)
        return global_matrix
