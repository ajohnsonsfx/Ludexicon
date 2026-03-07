from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSplitter,
    QTreeWidget, QTreeWidgetItem, QPushButton, QFrame,
    QScrollArea, QWidget, QCheckBox, QMenu, QInputDialog, QTextEdit,
    QListWidget, QListWidgetItem, QAbstractItemView, QHeaderView,
    QLineEdit, QGroupBox, QMessageBox, QFileDialog, QProgressBar,
    QToolButton, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint
from PyQt6.QtGui import QColor, QBrush, QAction, QDrag, QFont
import os
import tempfile

from ingest_logic import (
    TaxonomyIngestEngine, CandidateNameSet, CandidateWildcard,
    StagingSession, DedupMatch
)
from logic import NameSet, Wildcard, Value, NameSetComponent


# ─── Drop Zone ───────────────────────────────────────────────────────

class IngestInputArea(QTextEdit):
    filesDropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText("Drag & drop folders or files here, or paste filenames (one per line)...")
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                border: 2px dashed #555;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                color: #ccc;
            }
            QTextEdit:hover {
                border-color: #6a9fd8;
            }
        """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = [url.toLocalFile() for url in event.mimeData().urls()]
            self.filesDropped.emit(urls)
        else:
            super().dropEvent(event)


# ─── Draggable NameSet List ──────────────────────────────────────────

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


# ─── Category Bucket ─────────────────────────────────────────────────

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
        self.title_label = QLabel(f"📁 {category_name}")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #8ab4f8;")
        header.addWidget(self.title_label)
        header.addStretch()
        self.count_label = QLabel("0 items")
        self.count_label.setStyleSheet("color: #888; font-size: 11px;")
        header.addWidget(self.count_label)
        self.toggle_btn = QToolButton()
        self.toggle_btn.setText("▾")
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
        self.toggle_btn.setText("▾" if self._expanded else "▸")

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
        self.title_label.setText(f"📁 {new_name}")

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


# ─── Main Dialog ─────────────────────────────────────────────────────

class TaxonomyIngestDialog(QDialog):
    def __init__(self, tax_manager, parent=None):
        super().__init__(parent)
        self.tax_manager = tax_manager
        self.engine = TaxonomyIngestEngine(tax_manager)

        self.setWindowTitle("Ingestion Workspace")
        self.resize(1400, 900)

        self.session: StagingSession = None
        self.category_buckets: dict = {}  # name -> CategoryBucket

        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        # Apply global dark theme
        self.setStyleSheet("""
            QDialog { background-color: #121212; color: #e0e0e0; }
            QLabel { color: #e0e0e0; }
            QPushButton {
                background-color: #2a2a3e;
                color: #ddd;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #3a3a5e; border-color: #6a9fd8; }
            QPushButton:disabled { background-color: #1a1a2e; color: #666; }
            QLineEdit {
                background-color: #1e1e2e;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 4px 8px;
                color: #ddd;
            }
            QLineEdit:focus { border-color: #6a9fd8; }
            QTreeWidget {
                background-color: #1a1a2e;
                border: 1px solid #333;
                border-radius: 4px;
                color: #ddd;
            }
            QTreeWidget::item { padding: 3px; }
            QTreeWidget::item:selected { background-color: #3a3a5e; }
            QHeaderView::section {
                background-color: #1e1e2e;
                color: #aaa;
                border: none;
                border-bottom: 1px solid #333;
                padding: 4px;
            }
            QSplitter::handle { background-color: #333; }
            QScrollArea { border: none; }
        """)

        # ─── Phase 1: Import ─────────────────────────────────────
        import_frame = QFrame()
        import_frame.setStyleSheet("QFrame { background-color: #1a1a2e; border-radius: 6px; padding: 4px; }")
        import_layout = QVBoxLayout(import_frame)
        import_layout.setContentsMargins(8, 8, 8, 8)
        import_layout.setSpacing(4)

        import_header = QLabel("① Import Files")
        import_header.setStyleSheet("font-size: 14px; font-weight: bold; color: #8ab4f8;")
        import_layout.addWidget(import_header)

        self.input_area = IngestInputArea()
        self.input_area.filesDropped.connect(self._on_files_dropped)
        self.input_area.setMaximumHeight(100)
        import_layout.addWidget(self.input_area)

        options_row = QHBoxLayout()
        options_row.addWidget(QLabel("Strip suffixes:"))
        self.chk_ignore_vars = QCheckBox("Variations (_01, 02)")
        self.chk_ignore_versions = QCheckBox("Versions (_v01)")
        self.chk_ignore_dates = QCheckBox("Dates (_20240101)")
        self.chk_ignore_vars.setChecked(True)
        for chk in (self.chk_ignore_vars, self.chk_ignore_versions, self.chk_ignore_dates):
            chk.setStyleSheet("QCheckBox { color: #bbb; }")
            options_row.addWidget(chk)
        options_row.addStretch()

        self.btn_analyze = QPushButton("⚡ Analyze")
        self.btn_analyze.setStyleSheet("background-color: #1a5276; font-weight: bold; padding: 6px 20px;")
        self.btn_analyze.clicked.connect(self._on_analyze)
        options_row.addWidget(self.btn_analyze)

        self.btn_load_session = QPushButton("📂 Load Session")
        self.btn_load_session.clicked.connect(self._on_load_session)
        options_row.addWidget(self.btn_load_session)

        import_layout.addLayout(options_row)

        # Dedup summary bar (hidden until we have results)
        self.dedup_frame = QFrame()
        self.dedup_frame.setStyleSheet("QFrame { background-color: #1a3a2e; border-radius: 4px; padding: 4px; }")
        self.dedup_frame.setVisible(False)
        dedup_layout = QHBoxLayout(self.dedup_frame)
        dedup_layout.setContentsMargins(8, 4, 8, 4)
        self.dedup_label = QLabel()
        self.dedup_label.setStyleSheet("color: #8bc34a; font-weight: bold;")
        dedup_layout.addWidget(self.dedup_label)
        dedup_layout.addStretch()
        self.btn_show_matches = QPushButton("Show Matches ▾")
        self.btn_show_matches.setStyleSheet("background-color: transparent; color: #8bc34a; border: none; text-decoration: underline;")
        self.btn_show_matches.clicked.connect(self._toggle_match_details)
        dedup_layout.addWidget(self.btn_show_matches)
        import_layout.addWidget(self.dedup_frame)

        self.match_details_tree = QTreeWidget()
        self.match_details_tree.setHeaderLabels(["Matched Filename", "Matched Pattern"])
        self.match_details_tree.setVisible(False)
        self.match_details_tree.setMaximumHeight(150)
        import_layout.addWidget(self.match_details_tree)

        root.addWidget(import_frame)

        # ─── Phase 2: Organize Workspace ──────────────────────────
        workspace_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Unsorted items
        unsorted_frame = QFrame()
        unsorted_layout = QVBoxLayout(unsorted_frame)
        unsorted_layout.setContentsMargins(4, 4, 4, 4)
        unsorted_header = QLabel("Unsorted Items")
        unsorted_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #f0ad4e;")
        unsorted_layout.addWidget(unsorted_header)
        self.unsorted_list = DraggableNameSetList()
        self.unsorted_list.itemClicked.connect(self._on_item_selected)
        self.unsorted_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.unsorted_list.customContextMenuRequested.connect(self._unsorted_context_menu)
        unsorted_layout.addWidget(self.unsorted_list)

        # Button row under unsorted
        unsorted_btn_row = QHBoxLayout()
        self.btn_stage_selected = QPushButton("Stage Selected ▸")
        self.btn_stage_selected.setStyleSheet("background-color: #2d5a27; font-weight: bold;")
        self.btn_stage_selected.clicked.connect(self._stage_selected_items)
        unsorted_btn_row.addWidget(self.btn_stage_selected)
        unsorted_btn_row.addStretch()
        unsorted_layout.addLayout(unsorted_btn_row)

        workspace_splitter.addWidget(unsorted_frame)

        # Center: Categories
        cat_frame = QFrame()
        cat_layout = QVBoxLayout(cat_frame)
        cat_layout.setContentsMargins(4, 4, 4, 4)
        cat_header_row = QHBoxLayout()
        cat_header = QLabel("Categories")
        cat_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #8ab4f8;")
        cat_header_row.addWidget(cat_header)
        cat_header_row.addStretch()
        self.btn_new_category = QPushButton("+ New Category")
        self.btn_new_category.setStyleSheet("background-color: #1a5276; font-size: 11px; padding: 4px 10px;")
        self.btn_new_category.clicked.connect(self._create_category)
        cat_header_row.addWidget(self.btn_new_category)
        cat_layout.addLayout(cat_header_row)

        self.cat_scroll = QScrollArea()
        self.cat_scroll.setWidgetResizable(True)
        self.cat_scroll_widget = QWidget()
        self.cat_scroll_layout = QVBoxLayout(self.cat_scroll_widget)
        self.cat_scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cat_scroll_layout.setSpacing(6)
        self.cat_scroll.setWidget(self.cat_scroll_widget)
        self.cat_scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        cat_layout.addWidget(self.cat_scroll)

        workspace_splitter.addWidget(cat_frame)

        # Right: Detail panel
        detail_frame = QFrame()
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(4, 4, 4, 4)
        detail_header = QLabel("② Details")
        detail_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #bb86fc;")
        detail_layout.addWidget(detail_header)

        # NameSet name editor
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Pattern name:"))
        self.ns_name_edit = QLineEdit()
        self.ns_name_edit.setPlaceholderText("Select an item to see details")
        self.ns_name_edit.editingFinished.connect(self._on_ns_name_edited)
        name_row.addWidget(self.ns_name_edit)
        detail_layout.addLayout(name_row)

        # Structure preview
        self.structure_label = QLabel("Structure: \u2014")
        self.structure_label.setStyleSheet("color: #aaa; font-family: monospace; padding: 4px;")
        detail_layout.addWidget(self.structure_label)

        # Wildcard details tree
        wc_label = QLabel("Slots:")
        wc_label.setStyleSheet("font-weight: bold; margin-top: 6px;")
        detail_layout.addWidget(wc_label)
        self.wc_tree = QTreeWidget()
        self.wc_tree.setHeaderLabels(["Slot Name", "Values", "Confidence"])
        self.wc_tree.setColumnWidth(0, 150)
        self.wc_tree.setColumnWidth(1, 120)
        self.wc_tree.itemDoubleClicked.connect(self._on_wc_rename)
        detail_layout.addWidget(self.wc_tree)

        # Example filenames
        ex_label = QLabel("Example filenames:")
        ex_label.setStyleSheet("font-weight: bold; margin-top: 6px;")
        detail_layout.addWidget(ex_label)
        self.example_list = QListWidget()
        self.example_list.setMaximumHeight(120)
        self.example_list.setStyleSheet("""
            QListWidget { background-color: #1a1a2e; border: 1px solid #333; border-radius: 3px; }
            QListWidget::item { color: #aaa; padding: 2px 6px; font-family: monospace; font-size: 11px; }
        """)
        detail_layout.addWidget(self.example_list)

        workspace_splitter.addWidget(detail_frame)
        workspace_splitter.setSizes([350, 350, 400])

        root.addWidget(workspace_splitter, stretch=1)

        # ─── Phase 3: Staging Area ─────────────────────────────────
        staging_frame = QFrame()
        staging_frame.setStyleSheet("QFrame { background-color: #1a1a2e; border-radius: 6px; }")
        staging_layout = QVBoxLayout(staging_frame)
        staging_layout.setContentsMargins(8, 6, 8, 6)

        staging_header_row = QHBoxLayout()
        staging_header = QLabel("③ Staging Area (reviewed patterns)")
        staging_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #2d5a27;")
        staging_header_row.addWidget(staging_header)
        self.staged_count_label = QLabel("0 items staged")
        self.staged_count_label.setStyleSheet("color: #888; font-size: 11px;")
        staging_header_row.addWidget(self.staged_count_label)
        staging_header_row.addStretch()

        self.btn_unstage = QPushButton("◂ Unstage Selected")
        self.btn_unstage.clicked.connect(self._unstage_selected)
        staging_header_row.addWidget(self.btn_unstage)

        self.btn_save_session = QPushButton("💾 Save Session")
        self.btn_save_session.clicked.connect(self._save_session)
        staging_header_row.addWidget(self.btn_save_session)

        self.btn_commit = QPushButton("✅ Commit All to Project")
        self.btn_commit.setStyleSheet("background-color: #2d5a27; font-weight: bold; padding: 6px 20px;")
        self.btn_commit.setEnabled(False)
        self.btn_commit.clicked.connect(self._on_commit)
        staging_header_row.addWidget(self.btn_commit)

        staging_layout.addLayout(staging_header_row)

        self.staging_tree = QTreeWidget()
        self.staging_tree.setHeaderLabels(["Pattern Name", "Structure", "Slots", "Values"])
        self.staging_tree.setMaximumHeight(160)
        self.staging_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        staging_layout.addWidget(self.staging_tree)

        root.addWidget(staging_frame)

        # ─── Status bar ───────────────────────────────────────────
        status_row = QHBoxLayout()
        self.status_label = QLabel("Ready. Drop files above to begin.")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        self.btn_cancel = QPushButton("Close")
        self.btn_cancel.clicked.connect(self.reject)
        status_row.addWidget(self.btn_cancel)
        root.addLayout(status_row)

        # Internal tracking
        self._selected_ns_id = None
        self._ns_map = {}  # temp_id -> CandidateNameSet

    # ─── File import handlers ─────────────────────────────────────

    def _on_files_dropped(self, paths):
        extracted_names = []
        for path in paths:
            if os.path.isdir(path):
                for dirpath, dirnames, filenames in os.walk(path):
                    for f in filenames:
                        name, _ = os.path.splitext(f)
                        extracted_names.append(name)
            elif os.path.isfile(path) and path.lower().endswith(('.csv', '.txt')):
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        for part in line.split(','):
                            cleaned = part.strip()
                            if cleaned:
                                extracted_names.append(cleaned)

        if extracted_names:
            current_text = self.input_area.toPlainText().strip()
            new_text = "\n".join(extracted_names)
            if current_text:
                self.input_area.setPlainText(current_text + "\n" + new_text)
            else:
                self.input_area.setPlainText(new_text)
            self.status_label.setText(f"{len(extracted_names)} names loaded. Click 'Analyze' to process.")

    def _on_analyze(self):
        text = self.input_area.toPlainText().strip()
        if not text:
            return

        names = []
        for line in text.split('\n'):
            for part in line.split(','):
                cleaned = part.strip()
                if cleaned:
                    names.append(cleaned)

        if not names:
            return

        self.engine = TaxonomyIngestEngine(self.tax_manager)
        self.engine.ignore_variations = self.chk_ignore_vars.isChecked()
        self.engine.ignore_versions = self.chk_ignore_versions.isChecked()
        self.engine.ignore_dates = self.chk_ignore_dates.isChecked()

        self.status_label.setText(f"Processing {len(names)} names...")
        self.engine.process_raw_names("Input", names)

        self.session = self.engine.run_inference()
        self._populate_from_session()

    def _on_load_session(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Session", "", "JSON Files (*.json)")
        if not path:
            return
        try:
            self.session = self.engine.load_session(path)
            self._populate_from_session()
            self.status_label.setText(f"Session loaded from {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.warning(self, "Load Failed", f"Could not load session:\n{e}")

    def _populate_from_session(self):
        """Refresh all UI panels from the current session."""
        if not self.session:
            return

        self._ns_map = {ns.temp_id: ns for ns in self.session.candidate_namesets}

        # Dedup bar
        dedup_count = len(self.session.dedup_matches)
        total = self.session.total_input_count
        unknowns = total - dedup_count
        if dedup_count > 0:
            self.dedup_label.setText(
                f"✓ {dedup_count} of {total} filenames already exist in the dictionary. "
                f"{unknowns} new items to organize."
            )
            self.dedup_frame.setVisible(True)
            self._populate_match_details()
        else:
            self.dedup_frame.setVisible(False)

        # Unsorted list (non-staged, non-categorized items)
        self.unsorted_list.clear()
        for ns in self.session.candidate_namesets:
            if not ns.staged and not ns.category:
                self._add_to_unsorted(ns)

        # Rebuild categories
        for cat_name in self.session.categories:
            if cat_name not in self.category_buckets:
                self._add_category_widget(cat_name)

        # Put categorized items in their buckets
        for ns in self.session.candidate_namesets:
            if ns.category and not ns.staged:
                if ns.category in self.category_buckets:
                    self.category_buckets[ns.category].add_item(ns.temp_id, self._ns_display_text(ns))

        # Staging tree
        self._refresh_staging_tree()

        ns_count = len([ns for ns in self.session.candidate_namesets if not ns.staged])
        self.status_label.setText(
            f"Analysis complete. {ns_count} patterns found, {dedup_count} duplicates filtered."
        )

    def _add_to_unsorted(self, ns: CandidateNameSet):
        text = self._ns_display_text(ns)
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, ns.temp_id)
        if ns.confidence >= 90:
            item.setForeground(QBrush(QColor("#5cb85c")))
        elif ns.confidence >= 50:
            item.setForeground(QBrush(QColor("#f0ad4e")))
        else:
            item.setForeground(QBrush(QColor("#d9534f")))
        self.unsorted_list.addItem(item)

    def _ns_display_text(self, ns: CandidateNameSet) -> str:
        parts = []
        for part in ns.structure:
            if part["type"] == "literal":
                parts.append(part["value"])
            elif part["type"] == "wildcard":
                wc = self.session.candidate_wildcards.get(part["temp_id"])
                name = wc.suggested_name if wc else part["temp_id"]
                parts.append(f"[{name}]")
        pattern = "".join(parts)
        return f"{ns.suggested_name}  ({len(ns.matched_assets)} files)  {pattern}"

    # ─── Dedup details ─────────────────────────────────────────────

    def _populate_match_details(self):
        self.match_details_tree.clear()
        if not self.session:
            return
        # Group by matched nameset
        groups = {}
        for m in self.session.dedup_matches:
            key = m.matched_nameset_name
            if key not in groups:
                groups[key] = []
            groups[key].append(m)

        for ns_name, matches in sorted(groups.items()):
            parent = QTreeWidgetItem(self.match_details_tree, [f"{ns_name} ({len(matches)} matches)", ""])
            parent.setForeground(0, QBrush(QColor("#8bc34a")))
            for m in matches[:50]:  # cap display
                QTreeWidgetItem(parent, [m.filename, m.matched_nameset_name])

    def _toggle_match_details(self):
        vis = not self.match_details_tree.isVisible()
        self.match_details_tree.setVisible(vis)
        self.btn_show_matches.setText("Hide Matches ▴" if vis else "Show Matches ▾")

    # ─── Item selection / detail panel ─────────────────────────────

    def _on_item_selected(self, item):
        temp_id = item.data(Qt.ItemDataRole.UserRole)
        self._show_details(temp_id)

    def _show_details(self, temp_id: str):
        if not self.session or temp_id not in self._ns_map:
            return
        self._selected_ns_id = temp_id
        ns = self._ns_map[temp_id]

        self.ns_name_edit.setText(ns.suggested_name)

        # Structure preview
        parts = []
        for part in ns.structure:
            if part["type"] == "literal":
                parts.append(part["value"])
            else:
                wc = self.session.candidate_wildcards.get(part["temp_id"])
                name = wc.suggested_name if wc else part["temp_id"]
                parts.append(f"[{name}]")
        self.structure_label.setText(f"Structure: {''.join(parts)}")

        # Wildcard tree
        self.wc_tree.clear()
        for part in ns.structure:
            if part["type"] == "wildcard":
                wc = self.session.candidate_wildcards.get(part["temp_id"])
                if wc:
                    wc_item = QTreeWidgetItem(self.wc_tree, [
                        wc.suggested_name,
                        f"{len(wc.values)} values",
                        f"{wc.confidence:.0f}%"
                    ])
                    wc_item.setData(0, Qt.ItemDataRole.UserRole, wc.temp_id)
                    wc_item.setExpanded(True)
                    for val in sorted(wc.values, key=lambda x: x.confidence, reverse=True)[:30]:
                        QTreeWidgetItem(wc_item, [val.name, "", f"{val.confidence:.0f}%"])

        # Example filenames
        self.example_list.clear()
        for asset in ns.matched_assets[:30]:
            self.example_list.addItem(asset.filename)

    def _on_ns_name_edited(self):
        if self._selected_ns_id and self._selected_ns_id in self._ns_map:
            new_name = self.ns_name_edit.text().strip()
            if new_name:
                self._ns_map[self._selected_ns_id].suggested_name = new_name

    def _on_wc_rename(self, item, column):
        """Double-click on a slot to rename it."""
        wc_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not wc_id or wc_id not in self.session.candidate_wildcards:
            return
        wc = self.session.candidate_wildcards[wc_id]
        new_name, ok = QInputDialog.getText(self, "Rename Slot", f"New name for '{wc.suggested_name}':", text=wc.suggested_name)
        if ok and new_name.strip():
            wc.suggested_name = new_name.strip()
            item.setText(0, new_name.strip())
            # Refresh structure label
            if self._selected_ns_id:
                self._show_details(self._selected_ns_id)
            # Refresh unsorted list display
            self._refresh_unsorted_display()

    # ─── Category management ──────────────────────────────────────

    def _create_category(self):
        name, ok = QInputDialog.getText(self, "New Category", "Category name:")
        if ok and name.strip():
            name = name.strip()
            if name in self.category_buckets:
                return
            if self.session:
                self.session.categories.append(name)
            self._add_category_widget(name)

    def _add_category_widget(self, name: str):
        bucket = CategoryBucket(name)
        bucket.itemsDropped.connect(self._on_items_dropped_to_category)
        bucket.itemSelected.connect(self._show_details)
        bucket.stageRequested.connect(self._stage_category)
        bucket.renameRequested.connect(self._rename_category)
        bucket.deleteRequested.connect(self._delete_category)
        self.cat_scroll_layout.addWidget(bucket)
        self.category_buckets[name] = bucket

    def _on_items_dropped_to_category(self, category_name: str, temp_ids: list):
        """Move items from unsorted (or another category) into the target category."""
        bucket = self.category_buckets.get(category_name)
        if not bucket:
            return

        for temp_id in temp_ids:
            ns = self._ns_map.get(temp_id)
            if not ns:
                continue

            # Remove from previous location
            if ns.category and ns.category in self.category_buckets:
                self.category_buckets[ns.category].remove_item(temp_id)
            else:
                # Remove from unsorted
                for i in range(self.unsorted_list.count()):
                    w = self.unsorted_list.item(i)
                    if w and w.data(Qt.ItemDataRole.UserRole) == temp_id:
                        self.unsorted_list.takeItem(i)
                        break

            ns.category = category_name
            bucket.add_item(temp_id, self._ns_display_text(ns))

    def _rename_category(self, old_name: str):
        new_name, ok = QInputDialog.getText(self, "Rename Category", "New name:", text=old_name)
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        new_name = new_name.strip()
        bucket = self.category_buckets.pop(old_name, None)
        if bucket:
            bucket.rename(new_name)
            self.category_buckets[new_name] = bucket
            # Update session categories
            if self.session:
                self.session.categories = [new_name if c == old_name else c for c in self.session.categories]
            # Update all namesets pointing to old category
            for ns in self._ns_map.values():
                if ns.category == old_name:
                    ns.category = new_name

    def _delete_category(self, name: str):
        bucket = self.category_buckets.pop(name, None)
        if not bucket:
            return
        # Move items back to unsorted
        for temp_id in bucket.get_all_ids():
            ns = self._ns_map.get(temp_id)
            if ns:
                ns.category = None
                self._add_to_unsorted(ns)
        bucket.setParent(None)
        bucket.deleteLater()
        if self.session and name in self.session.categories:
            self.session.categories.remove(name)

    def _stage_category(self, name: str):
        bucket = self.category_buckets.get(name)
        if not bucket:
            return
        for temp_id in list(bucket.get_all_ids()):
            ns = self._ns_map.get(temp_id)
            if ns:
                ns.staged = True
                ns.approved = True
                bucket.remove_item(temp_id)
        self._refresh_staging_tree()

    # ─── Staging ──────────────────────────────────────────────────

    def _stage_selected_items(self):
        items = self.unsorted_list.selectedItems()
        for item in items:
            temp_id = item.data(Qt.ItemDataRole.UserRole)
            ns = self._ns_map.get(temp_id)
            if ns:
                ns.staged = True
                ns.approved = True
        # Remove from unsorted
        for item in items:
            row = self.unsorted_list.row(item)
            self.unsorted_list.takeItem(row)
        self._refresh_staging_tree()

    def _unstage_selected(self):
        items = self.staging_tree.selectedItems()
        for item in items:
            temp_id = item.data(0, Qt.ItemDataRole.UserRole)
            ns = self._ns_map.get(temp_id)
            if ns:
                ns.staged = False
                ns.approved = False
                if ns.category and ns.category in self.category_buckets:
                    self.category_buckets[ns.category].add_item(temp_id, self._ns_display_text(ns))
                else:
                    self._add_to_unsorted(ns)
        self._refresh_staging_tree()

    def _refresh_staging_tree(self):
        self.staging_tree.clear()
        staged = [ns for ns in self._ns_map.values() if ns.staged]
        for ns in staged:
            # Build structure text
            parts = []
            field_names = []
            val_count = 0
            for part in ns.structure:
                if part["type"] == "literal":
                    parts.append(part["value"])
                else:
                    wc = self.session.candidate_wildcards.get(part["temp_id"]) if self.session else None
                    name = wc.suggested_name if wc else part["temp_id"]
                    parts.append(f"[{name}]")
                    field_names.append(name)
                    if wc:
                        val_count += len(wc.values)

            item = QTreeWidgetItem(self.staging_tree, [
                ns.suggested_name,
                "".join(parts),
                ", ".join(field_names),
                str(val_count),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, ns.temp_id)

        n = len(staged)
        self.staged_count_label.setText(f"{n} item{'s' if n != 1 else ''} staged")
        self.btn_commit.setEnabled(n > 0)

    # ─── Context menus ────────────────────────────────────────────

    def _unsorted_context_menu(self, pos: QPoint):
        items = self.unsorted_list.selectedItems()
        if not items:
            return
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1e1e2e; color: #ddd; } QMenu::item:selected { background-color: #3a3a5e; }")

        stage_act = menu.addAction("Stage Selected")
        rename_act = menu.addAction("Rename") if len(items) == 1 else None

        # Category sub-menu
        if self.category_buckets:
            cat_menu = menu.addMenu("Move to Category →")
            for cat_name in self.category_buckets:
                cat_menu.addAction(cat_name)

        menu.addSeparator()
        delete_act = menu.addAction("Discard Selected")

        action = menu.exec(self.unsorted_list.mapToGlobal(pos))
        if not action:
            return

        if action == stage_act:
            self._stage_selected_items()
        elif action == rename_act:
            temp_id = items[0].data(Qt.ItemDataRole.UserRole)
            ns = self._ns_map.get(temp_id)
            if ns:
                new_name, ok = QInputDialog.getText(self, "Rename", "New pattern name:", text=ns.suggested_name)
                if ok and new_name.strip():
                    ns.suggested_name = new_name.strip()
                    self._refresh_unsorted_display()
        elif action == delete_act:
            for item in items:
                temp_id = item.data(Qt.ItemDataRole.UserRole)
                if temp_id in self._ns_map:
                    del self._ns_map[temp_id]
                row = self.unsorted_list.row(item)
                self.unsorted_list.takeItem(row)
        elif action.parent() and isinstance(action.parent(), QMenu):
            # It's a category action
            cat_name = action.text()
            temp_ids = [item.data(Qt.ItemDataRole.UserRole) for item in items]
            self._on_items_dropped_to_category(cat_name, temp_ids)

    def _refresh_unsorted_display(self):
        """Refresh display text for all unsorted items."""
        for i in range(self.unsorted_list.count()):
            item = self.unsorted_list.item(i)
            temp_id = item.data(Qt.ItemDataRole.UserRole)
            ns = self._ns_map.get(temp_id)
            if ns:
                item.setText(self._ns_display_text(ns))

    # ─── Session persistence ──────────────────────────────────────

    def _save_session(self):
        if not self.session:
            QMessageBox.information(self, "No Session", "Nothing to save. Analyze files first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Session", "ingest_session.json", "JSON Files (*.json)")
        if not path:
            return
        try:
            self.engine.save_session(self.session, path)
            self.status_label.setText(f"Session saved to {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", f"Could not save session:\n{e}")

    # ─── Commit to project ────────────────────────────────────────

    def _on_commit(self):
        if not self.session:
            return

        staged = [ns for ns in self._ns_map.values() if ns.staged]
        if not staged:
            self.reject()
            return

        reply = QMessageBox.question(
            self, "Commit Patterns to Project",
            f"This will write {len(staged)} pattern(s) with their slots and values to the project dictionary.\n\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        wc_mapping = {}  # temp_id -> real_id

        def find_existing_value(name):
            for v in list(self.tax_manager.core_registry["values"].values()) + \
                      list(self.tax_manager.project_registry["values"].values()):
                if v.name.lower() == name.lower() or any(a.lower() == name.lower() for a in v.aliases):
                    return v
            return None

        for ns in staged:
            for part in ns.structure:
                if part['type'] == 'wildcard':
                    temp_id = part['temp_id']
                    if temp_id in wc_mapping:
                        continue

                    candidate_wc = self.session.candidate_wildcards[temp_id]
                    # Use the suggested name (user-edited) for the real ID
                    safe_name = candidate_wc.suggested_name.replace(" ", "_").lower()
                    real_wc_id = f"wc.proj.{safe_name}"

                    # Ensure uniqueness
                    counter = 2
                    base_id = real_wc_id
                    while self.tax_manager.get_wildcard(real_wc_id):
                        real_wc_id = f"{base_id}_{counter}"
                        counter += 1

                    wc_mapping[temp_id] = real_wc_id

                    self.tax_manager.add_item("project", Wildcard(id=real_wc_id, name=candidate_wc.suggested_name))

                    for cv in candidate_wc.values:
                        existing = find_existing_value(cv.name)
                        if existing:
                            if existing.name.lower() != cv.name.lower() and cv.name not in existing.aliases:
                                existing.aliases.append(cv.name)
                        else:
                            val_id = f"val.proj.{cv.name.lower()}"
                            # Ensure value ID uniqueness
                            base_val_id = val_id
                            counter = 2
                            while self.tax_manager.get_value(val_id):
                                val_id = f"{base_val_id}_{counter}"
                                counter += 1
                            self.tax_manager.add_item("project", Value(
                                id=val_id, name=cv.name, wildcard_id=real_wc_id
                            ))

        for ns in staged:
            new_structure = []
            for part in ns.structure:
                if part['type'] == 'literal':
                    new_structure.append(NameSetComponent(type="literal", value=part['value']))
                else:
                    new_structure.append(NameSetComponent(type="wildcard", id=wc_mapping[part['temp_id']]))

            safe_ns_name = ns.suggested_name.replace(" ", "_").lower()
            ns_id = f"ns.proj.{safe_ns_name}"
            # Ensure uniqueness
            base_ns_id = ns_id
            counter = 2
            while self.tax_manager.get_nameset(ns_id):
                ns_id = f"{base_ns_id}_{counter}"
                counter += 1

            self.tax_manager.add_item("project", NameSet(
                id=ns_id, name=ns.suggested_name, nameset_structure=new_structure
            ))

        self.tax_manager.save()
        self.status_label.setText(f"✅ Committed {len(staged)} patterns to project dictionary.")
        QMessageBox.information(self, "Success", f"Successfully committed {len(staged)} patterns to the project dictionary.")
        self.accept()
