"""
Centralized stylesheet and theme constants for the Ludexicon UI.
"""

# Color palette
COLORS = {
    "bg_dark": "#1e1e1e",
    "bg_medium": "#2b2b2b",
    "bg_light": "#333333",
    "bg_button": "#3c3f41",
    "bg_button_hover": "#4b4d4f",
    "bg_button_checked": "#5b5d5f",
    "bg_selected": "#4b6eaf",
    "bg_hover": "#2a2d2f",
    "border": "#444",
    "border_light": "#555",
    "border_dark": "#333",
    "text": "#e0e0e0",
    "text_dim": "#aaaaaa",
}

GLOBAL_STYLESHEET = """
    QMainWindow { background-color: #2b2b2b; color: #e0e0e0; }
    QWidget { background-color: #2b2b2b; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
    QDockWidget { border: 1px solid #444; titlebar-close-icon: url(''); titlebar-normal-icon: url(''); }
    QDockWidget::title { background: #1e1e1e; padding: 0px; margin: 0px; }
    QTabWidget { background-color: #1e1e1e; }
    QTabWidget::pane { border: 1px solid #444; background-color: #2b2b2b; top: -1px; }
    QTabBar { background-color: #1e1e1e; }
    QTabBar::tab {
        background-color: #3c3f41;
        color: #aaaaaa;
        padding: 4px 12px;
        border: 1px solid #444;
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        margin-top: 2px;
        margin-right: 2px;
    }
    QTabBar::tab:first { margin-left: 4px; }
    QTabBar::tab:selected { background-color: #2b2b2b; color: #e0e0e0; }
    QPushButton { background-color: #3c3f41; border: 1px solid #555; padding: 4px; border-radius: 2px; }
    QPushButton:hover { background-color: #4b4d4f; }
    QPushButton:checked { background-color: #5b5d5f; }
    QLineEdit, QTreeView, QListWidget, QScrollArea { background-color: #1e1e1e; border: 1px solid #3c3f41; }
    QHeaderView::section { background-color: #3c3f41; padding: 2px 4px; border: 1px solid #333; }
    QTreeView::item:hover, QListWidget::item:hover { background-color: #2a2d2f; }
    QTreeView::item:selected, QListWidget::item:selected { background-color: #4b6eaf; }
    QMenu { background-color: #2b2b2b; border: 1px solid #555; }
    QMenu::item { padding: 4px 24px; }
    QMenu::item:selected { background-color: #4b6eaf; }
"""
