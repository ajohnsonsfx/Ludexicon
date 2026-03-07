"""
CategoryBucket and DraggableNameSetList — components for organizing
candidate NameSets during ingestion.
"""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QToolButton,
    QListWidget, QListWidgetItem, QAbstractItemView, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QDrag


class DraggableNameSetList(QListWidget):
    """List widget that supports dragging items out."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setStyleSheet("""
            QListWidget {
                background-color: #1a1a2e;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 2px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #2a2a3e;
                color: #ddd;
            }
            QListWidget::item:selected {
                background-color: #3a3a5e;
                color: #fff;
            }
            QListWidget::item:hover {
                background-color: #2a2a4e;
            }
        """)

    def startDrag(self, supportedActions):
        items = self.selectedItems()
        if not items:
            return
        drag = QDrag(self)
        mime = QMimeData()
        ids = [item.data(Qt.ItemDataRole.UserRole) for item in items if item.data(Qt.ItemDataRole.UserRole)]
        mime.setText("\n".join(ids))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)


class CategoryBucket(QFrame):
    """A collapsible category container that accepts drops."""
    itemsDropped = pyqtSignal(str, list)  # category_name, list of temp_ids
    itemSelected = pyqtSignal(str)  # temp_id
    stageRequested = pyqtSignal(str)  # category_name
    renameRequested = pyqtSignal(str)  # category_name
    deleteRequested = pyqtSignal(str)  # category_name

    def __init__(self, category_name: str, parent=None):
        super().__init__(parent)
        self.category_name = category_name
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self._items = {}  # temp_id -> display_text

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Header
        header = QHBoxLayout()
        self.title_label = QLabel(f"\U0001f4c1 {category_name}")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #8ab4f8;")
        header.addWidget(self.title_label)
        header.addStretch()
        self.count_label = QLabel("0 items")
        self.count_label.setStyleSheet("color: #888; font-size: 11px;")
        header.addWidget(self.count_label)
        self.toggle_btn = QToolButton()
        self.toggle_btn.setText("\u25be")
        self.toggle_btn.setStyleSheet("border: none; color: #888; font-size: 14px;")
        self.toggle_btn.clicked.connect(self._toggle)
        header.addWidget(self.toggle_btn)
        layout.addLayout(header)

        # Items list
        self.item_list = QListWidget()
        self.item_list.setMaximumHeight(200)
        self.item_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.item_list.itemClicked.connect(lambda item: self.itemSelected.emit(item.data(Qt.ItemDataRole.UserRole)))
        self.item_list.setStyleSheet("""
            QListWidget {
                background-color: #16213e;
                border: 1px solid #2a2a4e;
                border-radius: 3px;
            }
            QListWidget::item { padding: 4px 6px; color: #ccc; border-bottom: 1px solid #1a1a3e; }
            QListWidget::item:selected { background-color: #3a3a5e; }
        """)
        layout.addWidget(self.item_list)

        self.setStyleSheet("""
            CategoryBucket {
                background-color: #0f3460;
                border: 1px solid #1a5276;
                border-radius: 6px;
            }
            CategoryBucket:hover {
                border-color: #6a9fd8;
            }
        """)
        self._expanded = True

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _toggle(self):
        self._expanded = not self._expanded
        self.item_list.setVisible(self._expanded)
        self.toggle_btn.setText("\u25be" if self._expanded else "\u25b8")

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1e1e2e; color: #ddd; } QMenu::item:selected { background-color: #3a3a5e; }")
        rename_act = menu.addAction("Rename Category")
        stage_act = menu.addAction("Stage All in Category")
        menu.addSeparator()
        delete_act = menu.addAction("Delete Category (move items back)")
        action = menu.exec(self.mapToGlobal(pos))
        if action == rename_act:
            self.renameRequested.emit(self.category_name)
        elif action == stage_act:
            self.stageRequested.emit(self.category_name)
        elif action == delete_act:
            self.deleteRequested.emit(self.category_name)

    def add_item(self, temp_id: str, display_text: str):
        if temp_id in self._items:
            return
        self._items[temp_id] = display_text
        item = QListWidgetItem(display_text)
        item.setData(Qt.ItemDataRole.UserRole, temp_id)
        self.item_list.addItem(item)
        self._update_count()

    def remove_item(self, temp_id: str):
        if temp_id not in self._items:
            return
        del self._items[temp_id]
        for i in range(self.item_list.count()):
            w = self.item_list.item(i)
            if w.data(Qt.ItemDataRole.UserRole) == temp_id:
                self.item_list.takeItem(i)
                break
        self._update_count()

    def get_all_ids(self) -> list:
        return list(self._items.keys())

    def _update_count(self):
        n = len(self._items)
        self.count_label.setText(f"{n} item{'s' if n != 1 else ''}")

    def rename(self, new_name: str):
        self.category_name = new_name
        self.title_label.setText(f"\U0001f4c1 {new_name}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet("""
                CategoryBucket {
                    background-color: #1a5276;
                    border: 2px solid #6a9fd8;
                    border-radius: 6px;
                }
            """)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            CategoryBucket {
                background-color: #0f3460;
                border: 1px solid #1a5276;
                border-radius: 6px;
            }
            CategoryBucket:hover {
                border-color: #6a9fd8;
            }
        """)

    def dropEvent(self, event):
        self.setStyleSheet("""
            CategoryBucket {
                background-color: #0f3460;
                border: 1px solid #1a5276;
                border-radius: 6px;
            }
            CategoryBucket:hover {
                border-color: #6a9fd8;
            }
        """)
        if event.mimeData().hasText():
            ids = event.mimeData().text().split("\n")
            ids = [i for i in ids if i.strip()]
            if ids:
                self.itemsDropped.emit(self.category_name, ids)
            event.acceptProposedAction()
