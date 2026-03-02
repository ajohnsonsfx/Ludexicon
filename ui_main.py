import sys
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeView, QListWidget, QScrollArea, QPushButton, QCheckBox,
    QLineEdit, QLabel, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QStandardItemModel, QStandardItem

from data_models import TaxonomyManager
from ui_widgets import GroupWidget

class MainWindow(QMainWindow):
    def __init__(self, tax_manager: TaxonomyManager):
        super().__init__()
        self.tax_manager = tax_manager
        self.setWindowTitle("Ludexicon - Game Asset Taxonomy Engine")
        self.resize(1200, 800)
        
        # Core data structures for matrix generation tracking
        self.groups = [] 
        
        self.init_ui()

    def init_ui(self):
        # Center Pane: Unified Builder
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.central_layout = QVBoxLayout(self.central_widget)
        self.central_layout.setContentsMargins(10, 10, 10, 10)
        
        # Toolbar / Add Group
        self.toolbar_layout = QHBoxLayout()
        self.add_group_btn = QPushButton("+ Add Group")
        self.add_group_btn.clicked.connect(self.add_dummy_group)
        self.toolbar_layout.addWidget(self.add_group_btn)
        self.toolbar_layout.addStretch()
        self.central_layout.addLayout(self.toolbar_layout)
        
        # Scroll area for groups
        self.group_scroll = QScrollArea()
        self.group_scroll.setWidgetResizable(True)
        self.group_container = QWidget()
        self.group_layout = QVBoxLayout(self.group_container)
        self.group_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.group_scroll.setWidget(self.group_container)
        
        self.central_layout.addWidget(self.group_scroll)

        # Left Pane: Lexicon Browser
        self.left_dock = QDockWidget("Lexicon Browser", self)
        self.left_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.left_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_widget)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search Taxonomy...")
        self.left_layout.addWidget(self.search_bar)
        
        self.tree_view = QTreeView()
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(["Lexicon Data"])
        self.tree_view.setModel(self.tree_model)
        self.populate_lexicon_tree()
        self.left_layout.addWidget(self.tree_view)
        
        self.left_dock.setWidget(self.left_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.left_dock)

        # Right Pane: Output Log
        self.right_dock = QDockWidget("Output Log", self)
        self.right_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.right_widget = QWidget()
        self.right_layout = QVBoxLayout(self.right_widget)
        
        self.ext_checkbox = QCheckBox("Append .wav extension")
        self.ext_checkbox.stateChanged.connect(self.update_output_log)
        self.right_layout.addWidget(self.ext_checkbox)
        
        self.output_list = QListWidget()
        self.right_layout.addWidget(self.output_list)
        
        self.btn_layout = QHBoxLayout()
        self.copy_btn = QPushButton("Copy All to Clipboard")
        self.export_btn = QPushButton("Export to CSV")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        self.btn_layout.addWidget(self.copy_btn)
        self.btn_layout.addWidget(self.export_btn)
        self.right_layout.addLayout(self.btn_layout)
        
        self.right_dock.setWidget(self.right_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.right_dock)
        
        self.current_matrix = []

    def populate_lexicon_tree(self):
        root = self.tree_model.invisibleRootItem()
        
        # Core
        core_node = QStandardItem("Core Lexicon")
        for wc_id, wc in self.tax_manager.core_registry["wildcards"].items():
            wc_item = QStandardItem(f"{wc.name} [{wc_id}]")
            for el_id, el in self.tax_manager.core_registry["elements"].items():
                if el.wildcard_id == wc_id:
                    el_item = QStandardItem(f"{el.name} [{el_id}]")
                    wc_item.appendRow(el_item)
            core_node.appendRow(wc_item)
            
        # Project
        proj_node = QStandardItem("Project Taxonomy")
        for wc_id, wc in self.tax_manager.project_registry["wildcards"].items():
            wc_item = QStandardItem(f"{wc.name} [{wc_id}]")
            for el_id, el in self.tax_manager.project_registry["elements"].items():
                if el.wildcard_id == wc_id:
                    el_item = QStandardItem(f"{el.name} [{el_id}]")
                    wc_item.appendRow(el_item)
            proj_node.appendRow(wc_item)
            
        root.appendRow(core_node)
        root.appendRow(proj_node)
        self.tree_view.expandAll()

    def add_dummy_group(self):
        name = f"Asset Group {len(self.groups) + 1}"
        self.add_group(name)

    def add_group(self, name):
        group = GroupWidget(name, self.tax_manager)
        group.globalMatrixUpdated.connect(self.on_matrix_updated)
        self.group_layout.addWidget(group)
        self.groups.append(group)
        
        # Add the first dummy pattern immediately for UX demonstration
        group.on_add_pattern()

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
            if string and "_" in string or len(string) > 2:
                final_str = string + ".wav" if append_ext else string
                self.output_list.addItem(final_str)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        items = [self.output_list.item(i).text() for i in range(self.output_list.count())]
        clipboard.setText("\n".join(items))
