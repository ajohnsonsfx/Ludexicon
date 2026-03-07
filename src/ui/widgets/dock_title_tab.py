"""
Custom tab-style title bar widget for dock panels.
"""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt


class DockTitleTab(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("DockTitleTab { background-color: #1e1e1e; border-bottom: 1px solid #444; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(0)

        self.label = QLabel(title)
        self.label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                color: #e0e0e0;
                padding: 4px 12px;
                border: 1px solid #444;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-top: 2px;
            }
        """)

        layout.addWidget(self.label)
        layout.addStretch()
