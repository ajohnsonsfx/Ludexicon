"""
ProgressPanel — shows files that have been fully 'cleared'
(pattern + slots + values all confirmed) and committed/staged.
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush


class ProgressPanel(QFrame):
    """Right sidebar showing cleared/staged files as a progress tracker."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header = QLabel("✅ Progress")
        header.setStyleSheet("font-size: 13px; font-weight: bold; color: #5cb85c;")
        layout.addWidget(header)

        self.help_label = QLabel(
            "Files appear here once their\n"
            "pattern, slots, and values\n"
            "have been confirmed and staged."
        )
        self.help_label.setStyleSheet("color: #777; font-size: 10px; padding: 2px;")
        self.help_label.setWordWrap(True)
        layout.addWidget(self.help_label)

        self.count_label = QLabel("0 / 0 cleared")
        self.count_label.setStyleSheet("color: #5cb85c; font-size: 12px; font-weight: bold; padding: 2px;")
        layout.addWidget(self.count_label)

        self.cleared_list = QListWidget()
        self.cleared_list.setStyleSheet("""
            QListWidget {
                background-color: #1a2e1a;
                border: 1px solid #2d5a27;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 3px 6px;
                color: #8bc34a;
                font-size: 11px;
                border-bottom: 1px solid #1a3a1a;
            }
        """)
        layout.addWidget(self.cleared_list)

        self.setStyleSheet("""
            ProgressPanel {
                background-color: #121e12;
                border: 1px solid #2d5a27;
                border-radius: 6px;
            }
        """)

    def update_progress(self, staged_items: list, total_count: int):
        """Update the progress display.
        staged_items: list of (name, pattern_str) tuples for staged namesets.
        total_count: total number of candidate namesets.
        """
        self.cleared_list.clear()
        for name, pattern in staged_items:
            item = QListWidgetItem(f"✓ {name}")
            item.setToolTip(pattern)
            item.setForeground(QBrush(QColor("#8bc34a")))
            self.cleared_list.addItem(item)

        n = len(staged_items)
        self.count_label.setText(f"{n} / {total_count} cleared")

        if n > 0:
            self.help_label.setVisible(False)
        else:
            self.help_label.setVisible(True)
