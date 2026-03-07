"""
ImportSourceTree — collapsible tree showing imported sources and their
deduplicated filenames, grouped by import batch.
"""
from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QAbstractItemView, QFrame,
    QVBoxLayout, QLabel,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont


class ImportSourceTree(QFrame):
    """Shows imported files grouped by source (CSV file, folder, paste).
    Each top-level node is a source, children are deduplicated filenames."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QLabel("📂 Imported Sources")
        header.setStyleSheet("font-size: 12px; font-weight: bold; color: #8ab4f8; padding: 2px;")
        layout.addWidget(header)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tree.setIndentation(16)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1a1a2e;
                border: 1px solid #333;
                border-radius: 4px;
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 2px 4px;
                color: #bbb;
            }
            QTreeWidget::item:hover {
                background-color: #2a2a4e;
            }
        """)
        layout.addWidget(self.tree)

        self._source_nodes = {}  # source_label -> QTreeWidgetItem

    def clear(self):
        self.tree.clear()
        self._source_nodes = {}

    def add_source_group(self, source_label: str, filenames: list):
        """Add a collapsible group for one import source."""
        if source_label in self._source_nodes:
            # Update existing group
            node = self._source_nodes[source_label]
            existing = set()
            for i in range(node.childCount()):
                existing.add(node.child(i).text(0))
            for fn in filenames:
                if fn not in existing:
                    child = QTreeWidgetItem(node, [fn])
                    child.setForeground(0, QBrush(QColor("#999")))
            node.setText(0, f"📁 {source_label}  ({node.childCount()} files)")
        else:
            node = QTreeWidgetItem(self.tree)
            node.setText(0, f"📁 {source_label}  ({len(filenames)} files)")
            node.setForeground(0, QBrush(QColor("#8ab4f8")))
            font = QFont()
            font.setBold(True)
            node.setFont(0, font)

            for fn in filenames:
                child = QTreeWidgetItem(node, [fn])
                child.setForeground(0, QBrush(QColor("#999")))

            self._source_nodes[source_label] = node
            node.setExpanded(False)  # collapsed by default

    def populate_from_session(self, source_groups: dict):
        """Populate from a StagingSession's source_groups dict."""
        self.clear()
        for label, filenames in source_groups.items():
            self.add_source_group(label, filenames)
