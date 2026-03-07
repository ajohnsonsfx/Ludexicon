"""
BuilderWidget — the main tabbed builder pane.

Contains groups of NameSet widgets, an output pane with generated names,
and clipboard/export controls.
"""
import csv
import io
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QScrollArea,
    QPushButton, QCheckBox, QListWidget, QApplication, QFileDialog,
)
from PyQt6.QtCore import Qt

from core.taxonomy_manager import TaxonomyManager
from ui.builder.group_widget import GroupWidget


class BuilderWidget(QWidget):
    def __init__(self, tax_manager: TaxonomyManager, parent=None):
        super().__init__(parent)
        self.tax_manager = tax_manager
        self.groups = []
        self.current_matrix = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        lay.addWidget(self.splitter)

        # Left side: Builder
        self.builder_widget = QWidget()
        self.builder_layout = QVBoxLayout(self.builder_widget)
        self.builder_layout.setContentsMargins(10, 10, 10, 10)

        self.toolbar_layout = QHBoxLayout()
        self.add_group_btn = QPushButton("+ Add Group")
        self.add_group_btn.clicked.connect(self.add_dummy_group)
        self.toolbar_layout.addWidget(self.add_group_btn)
        self.toolbar_layout.addStretch()
        self.builder_layout.addLayout(self.toolbar_layout)

        self.group_scroll = QScrollArea()
        self.group_scroll.setWidgetResizable(True)
        self.group_container = QWidget()
        self.group_layout = QVBoxLayout(self.group_container)
        self.group_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.group_scroll.setWidget(self.group_container)
        self.builder_layout.addWidget(self.group_scroll)

        # Right side: Output
        self.output_widget = QWidget()
        self.right_layout = QVBoxLayout(self.output_widget)
        self.right_layout.setContentsMargins(10, 10, 10, 10)

        self.ext_checkbox = QCheckBox("Append .wav extension")
        self.ext_checkbox.stateChanged.connect(self.update_output_log)
        self.right_layout.addWidget(self.ext_checkbox)

        self.output_list = QListWidget()
        self.right_layout.addWidget(self.output_list)

        self.btn_layout = QHBoxLayout()
        self.copy_btn = QPushButton("Copy All to Clipboard")
        self.export_btn = QPushButton("Export to CSV")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        self.export_btn.clicked.connect(self.export_to_csv)
        self.btn_layout.addWidget(self.copy_btn)
        self.btn_layout.addWidget(self.export_btn)
        self.right_layout.addLayout(self.btn_layout)

        self.splitter.addWidget(self.builder_widget)
        self.splitter.addWidget(self.output_widget)
        self.splitter.setSizes([600, 400])

    def add_dummy_group(self):
        name = f"Asset Group {len(self.groups) + 1}"
        self.add_group(name)

    def add_group(self, name):
        group = GroupWidget(name, self.tax_manager)
        group.globalMatrixUpdated.connect(self.on_matrix_updated)
        self.group_layout.addWidget(group)
        self.groups.append(group)

        # Add the first dummy NameSet immediately for UX demonstration
        if len(self.groups) == 1:
            group.on_add_nameset()

    def on_matrix_updated(self):
        all_matrices = []
        for g in self.groups:
            all_matrices.extend(g.get_all_global_matrices())
        self.current_matrix = all_matrices
        self.update_output_log()

    def update_output_log(self):
        self.output_list.clear()
        append_ext = self.ext_checkbox.isChecked()
        for string in self.current_matrix:
            if string and ("_" in string or len(string) > 2):
                final_str = string + ".wav" if append_ext else string
                self.output_list.addItem(final_str)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        items = [self.output_list.item(i).text() for i in range(self.output_list.count())]
        clipboard.setText("\n".join(items))

    def export_to_csv(self):
        """Export the current output list to a CSV file."""
        items = [self.output_list.item(i).text() for i in range(self.output_list.count())]
        if not items:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export to CSV", "", "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Asset Name"])
            for item in items:
                writer.writerow([item])
