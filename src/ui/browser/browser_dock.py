"""
Browser dock panel — taxonomy tree viewer with search/filter support.
"""
from PyQt6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QLineEdit, QTreeView,
)
from PyQt6.QtCore import Qt, QSortFilterProxyModel
from PyQt6.QtGui import QStandardItemModel, QStandardItem

from core.taxonomy_manager import TaxonomyManager
from ui.widgets.dock_title_tab import DockTitleTab


class BrowserDock(QDockWidget):
    """A dockable taxonomy browser with a filterable tree view."""

    def __init__(self, title: str, tax_manager: TaxonomyManager, parent=None):
        super().__init__(title, parent)
        self.tax_manager = tax_manager

        self.setTitleBarWidget(DockTitleTab(title, self))
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)

        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search Taxonomy...")
        self.search_bar.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_bar)

        # Source model holds the actual data
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(["Name", "ID", "Tags"])

        # Proxy model enables live filtering
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.tree_model)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(-1)  # search all columns

        self.tree_view = QTreeView()
        self.tree_view.setModel(self.proxy_model)

        self.tree_view.setColumnWidth(0, 300)
        self.tree_view.setColumnWidth(1, 200)
        self.tree_view.setColumnWidth(2, 200)

        layout.addWidget(self.tree_view)

        self.setWidget(widget)
        self.populate()

    def _on_search_changed(self, text: str):
        """Filter the tree as the user types."""
        self.proxy_model.setFilterFixedString(text)
        if text:
            self.tree_view.expandAll()

    def populate(self):
        """Refreshes the browser tree with the latest taxonomy data."""
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(["Name", "ID", "Tags"])
        root = self.tree_model.invisibleRootItem()

        # Core
        core_node = [QStandardItem("Core Lexicon"), QStandardItem(""), QStandardItem("")]
        for wc_id, wc in self.tax_manager.core_registry["wildcards"].items():
            wc_name = QStandardItem(wc.name)
            wc_id_item = QStandardItem(f"[{wc_id}]")
            wc_tags = QStandardItem("")

            for v in self.tax_manager.get_values_for_wildcard(wc_id):
                # Only show values registered in the core registry
                if v.id in self.tax_manager.core_registry["values"]:
                    v_name = QStandardItem(v.name)
                    v_id_item = QStandardItem(f"[{v.id}]")
                    tags_str = ", ".join(getattr(v, 'tags', []))
                    v_tags = QStandardItem(tags_str)
                    wc_name.appendRow([v_name, v_id_item, v_tags])
            core_node[0].appendRow([wc_name, wc_id_item, wc_tags])

        # Project
        proj_node = [QStandardItem("Project Taxonomy"), QStandardItem(""), QStandardItem("")]
        for wc_id, wc in self.tax_manager.project_registry["wildcards"].items():
            wc_name = QStandardItem(wc.name)
            wc_id_item = QStandardItem(f"[{wc_id}]")
            wc_tags = QStandardItem("")

            for v in self.tax_manager.get_values_for_wildcard(wc_id):
                if v.id in self.tax_manager.project_registry["values"]:
                    v_name = QStandardItem(v.name)
                    v_id_item = QStandardItem(f"[{v.id}]")
                    tags_str = ", ".join(getattr(v, 'tags', []))
                    v_tags = QStandardItem(tags_str)
                    wc_name.appendRow([v_name, v_id_item, v_tags])
            proj_node[0].appendRow([wc_name, wc_id_item, wc_tags])

        root.appendRow(core_node)
        root.appendRow(proj_node)
        self.tree_view.expandAll()
