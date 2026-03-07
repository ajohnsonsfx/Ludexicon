"""
TaxonomyIngestDialog — full ingestion workspace dialog.

Redesigned layout:
  Left sidebar: Import controls + source tree
  Center: Three-tab workflow (Patterns / Slots / Values)
  Right sidebar: Progress tracker
  Bottom: Staging area + commit
"""
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSplitter,
    QTreeWidget, QTreeWidgetItem, QPushButton, QFrame,
    QScrollArea, QWidget, QCheckBox, QMenu, QInputDialog,
    QListWidget, QListWidgetItem, QAbstractItemView,
    QLineEdit, QMessageBox, QFileDialog, QTabWidget, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QMimeData
from PyQt6.QtGui import QColor, QBrush, QDrag, QAction

from core.models import NameSet, Wildcard, Value, NameSetComponent
from ingest.engine import TaxonomyIngestEngine
from ingest.models import CandidateNameSet, StagingSession
from ui.ingest.input_area import IngestInputArea
from ui.ingest.category_bucket import DraggableNameSetList, CategoryBucket
from ui.ingest.source_tree import ImportSourceTree


class TaxonomyIngestDialog(QDialog):
    def __init__(self, tax_manager, parent=None):
        super().__init__(parent)
        self.tax_manager = tax_manager
        self.engine = TaxonomyIngestEngine(tax_manager)

        self.setWindowTitle("Ingestion Workspace")
        self.resize(1500, 900)

        self.session: StagingSession = None
        self.category_buckets: dict = {}  # name -> CategoryBucket

        self.setAcceptDrops(True)

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
            QTabWidget::pane {
                border: 1px solid #333;
                background-color: #1a1a2e;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #1e1e2e;
                color: #aaa;
                padding: 8px 20px;
                border: 1px solid #333;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #1a1a2e;
                color: #8ab4f8;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #2a2a4e;
            }
        """)

        # ═══════════════════════════════════════════════════════════════
        #  MAIN HORIZONTAL LAYOUT: Left sidebar | Center workspace | Right sidebar
        # ═══════════════════════════════════════════════════════════════
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ─── LEFT SIDEBAR: Import ─────────────────────────────────────
        left_sidebar = QFrame()
        left_sidebar.setMinimumWidth(260)
        left_sidebar.setMaximumWidth(360)
        left_sidebar.setStyleSheet("QFrame { background-color: #151520; border-radius: 6px; }")
        left_layout = QVBoxLayout(left_sidebar)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        import_header = QLabel("① Import Files")
        import_header.setStyleSheet("font-size: 14px; font-weight: bold; color: #8ab4f8;")
        left_layout.addWidget(import_header)

        import_help = QLabel(
            "Drop folders, CSV files, or paste filenames anywhere in this window.\n"
            "The tool will extract and analyze asset names."
        )
        import_help.setStyleSheet("color: #777; font-size: 10px; padding: 2px;")
        import_help.setWordWrap(True)
        left_layout.addWidget(import_help)

        self.input_area = IngestInputArea()
        self.input_area.filesDropped.connect(self._on_files_dropped)
        self.input_area.setMaximumHeight(80)
        self.input_area.setMinimumHeight(60)
        left_layout.addWidget(self.input_area)

        # Options
        options_frame = QFrame()
        options_layout = QVBoxLayout(options_frame)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(2)
        strip_label = QLabel("Strip suffixes:")
        strip_label.setStyleSheet("color: #999; font-size: 11px;")
        options_layout.addWidget(strip_label)
        self.chk_ignore_vars = QCheckBox("Variations (_01, 02)")
        self.chk_ignore_versions = QCheckBox("Versions (_v01)")
        self.chk_ignore_dates = QCheckBox("Dates (_20240101)")
        self.chk_ignore_vars.setChecked(True)
        for chk in (self.chk_ignore_vars, self.chk_ignore_versions, self.chk_ignore_dates):
            chk.setStyleSheet("QCheckBox { color: #bbb; font-size: 11px; }")
            options_layout.addWidget(chk)
        left_layout.addWidget(options_frame)

        # Buttons row
        btn_row = QVBoxLayout()
        self.btn_analyze = QPushButton("⚡ Analyze")
        self.btn_analyze.setStyleSheet("background-color: #1a5276; font-weight: bold; padding: 8px;")
        self.btn_analyze.clicked.connect(self._on_analyze)
        btn_row.addWidget(self.btn_analyze)

        self.btn_load_session = QPushButton("📂 Load Session")
        self.btn_load_session.clicked.connect(self._on_load_session)
        btn_row.addWidget(self.btn_load_session)
        left_layout.addLayout(btn_row)

        # Dedup summary (hidden until results)
        self.dedup_frame = QFrame()
        self.dedup_frame.setStyleSheet("QFrame { background-color: #1a3a2e; border-radius: 4px; padding: 4px; }")
        self.dedup_frame.setVisible(False)
        dedup_layout = QVBoxLayout(self.dedup_frame)
        dedup_layout.setContentsMargins(6, 4, 6, 4)
        self.dedup_label = QLabel()
        self.dedup_label.setStyleSheet("color: #8bc34a; font-size: 11px; font-weight: bold;")
        self.dedup_label.setWordWrap(True)
        dedup_layout.addWidget(self.dedup_label)
        self.btn_show_matches = QPushButton("Show Matches ▾")
        self.btn_show_matches.setStyleSheet("background-color: transparent; color: #8bc34a; border: none; text-decoration: underline; font-size: 11px;")
        self.btn_show_matches.clicked.connect(self._toggle_match_details)
        dedup_layout.addWidget(self.btn_show_matches)
        self.match_details_tree = QTreeWidget()
        self.match_details_tree.setHeaderLabels(["Matched Filename", "Matched Pattern"])
        self.match_details_tree.setVisible(False)
        self.match_details_tree.setMaximumHeight(120)
        dedup_layout.addWidget(self.match_details_tree)
        left_layout.addWidget(self.dedup_frame)

        # Source tree
        tree_splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.source_tree = ImportSourceTree(title="📂 Imported")
        tree_splitter.addWidget(self.source_tree)
        
        self.ingested_tree = ImportSourceTree(title="✅ Ingested")
        tree_splitter.addWidget(self.ingested_tree)
        
        tree_splitter.setSizes([300, 300])
        left_layout.addWidget(tree_splitter, stretch=1)

        main_splitter.addWidget(left_sidebar)

        # ─── CENTER: Tab Workspace ────────────────────────────────────
        center_frame = QFrame()
        center_layout = QVBoxLayout(center_frame)
        center_layout.setContentsMargins(4, 4, 4, 4)
        center_layout.setSpacing(4)

        self.workspace_tabs = QTabWidget()

        # --- Patterns Tab ---
        patterns_widget = QWidget()
        patterns_layout = QVBoxLayout(patterns_widget)
        patterns_layout.setContentsMargins(8, 8, 8, 8)
        patterns_layout.setSpacing(4)

        patterns_help = QLabel(
            "🔍 Patterns represent naming structures found in your files. "
            "Each pattern shows how filenames are composed of literal text and variable slots.\n\n"
            "• Select a pattern to see its details on the right\n"
            "• Right-click for more options (rename, stage, discard)\n"
            "• Stage patterns when you're satisfied with their structure"
        )
        patterns_help.setStyleSheet("color: #888; font-size: 11px; padding: 6px; background-color: #1a1a2e; border-radius: 4px;")
        patterns_help.setWordWrap(True)
        patterns_layout.addWidget(patterns_help)

        patterns_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Unsorted patterns list
        unsorted_frame = QFrame()
        unsorted_layout = QVBoxLayout(unsorted_frame)
        unsorted_layout.setContentsMargins(0, 0, 0, 0)
        unsorted_header = QLabel("Discovered Patterns")
        unsorted_header.setStyleSheet("font-size: 12px; font-weight: bold; color: #f0ad4e;")
        unsorted_layout.addWidget(unsorted_header)
        self.unsorted_list = DraggableNameSetList()
        self.unsorted_list.itemClicked.connect(self._on_item_selected)
        self.unsorted_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.unsorted_list.customContextMenuRequested.connect(self._unsorted_context_menu)
        unsorted_layout.addWidget(self.unsorted_list)

        unsorted_btn_row = QHBoxLayout()
        self.btn_stage_selected = QPushButton("Stage Selected ▸")
        self.btn_stage_selected.setStyleSheet("background-color: #2d5a27; font-weight: bold;")
        self.btn_stage_selected.clicked.connect(self._stage_selected_items)
        unsorted_btn_row.addWidget(self.btn_stage_selected)
        unsorted_btn_row.addStretch()
        unsorted_layout.addLayout(unsorted_btn_row)

        patterns_splitter.addWidget(unsorted_frame)

        # Right: Pattern detail panel
        detail_frame = QFrame()
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(4, 0, 0, 0)
        detail_header = QLabel("Pattern Details")
        detail_header.setStyleSheet("font-size: 12px; font-weight: bold; color: #bb86fc;")
        detail_layout.addWidget(detail_header)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        self.ns_name_edit = QLineEdit()
        self.ns_name_edit.setPlaceholderText("Select a pattern to see details")
        self.ns_name_edit.editingFinished.connect(self._on_ns_name_edited)
        name_row.addWidget(self.ns_name_edit)
        detail_layout.addLayout(name_row)

        self.structure_label = QLabel("Structure: —")
        self.structure_label.setStyleSheet("color: #aaa; font-family: monospace; padding: 4px;")
        detail_layout.addWidget(self.structure_label)

        wc_label = QLabel("Slots:")
        wc_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
        detail_layout.addWidget(wc_label)
        self.wc_tree = QTreeWidget()
        self.wc_tree.setHeaderLabels(["Slot Name", "Values", "Confidence"])
        self.wc_tree.setColumnWidth(0, 150)
        self.wc_tree.setColumnWidth(1, 120)
        self.wc_tree.itemDoubleClicked.connect(self._on_wc_tree_double_click)
        detail_layout.addWidget(self.wc_tree)

        ex_label = QLabel("Example filenames:")
        ex_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
        detail_layout.addWidget(ex_label)
        self.example_list = QListWidget()
        self.example_list.setMaximumHeight(100)
        self.example_list.setStyleSheet("""
            QListWidget { background-color: #1a1a2e; border: 1px solid #333; border-radius: 3px; }
            QListWidget::item { color: #aaa; padding: 2px 6px; font-family: monospace; font-size: 11px; }
        """)
        detail_layout.addWidget(self.example_list)

        patterns_splitter.addWidget(detail_frame)
        patterns_splitter.setSizes([350, 400])

        # --- Categories Section (Bottom of Left Column in Patterns Tab) ---
        cat_frame = QFrame()
        cat_layout = QVBoxLayout(cat_frame)
        cat_layout.setContentsMargins(0, 10, 0, 0)
        
        cat_header_row = QHBoxLayout()
        cat_label = QLabel("📁 Categories")
        cat_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #8ab4f8;")
        cat_header_row.addWidget(cat_label)
        cat_header_row.addStretch()
        self.btn_new_category = QPushButton("+ New")
        self.btn_new_category.setStyleSheet("background-color: #1a5276; font-size: 10px; padding: 2px 8px;")
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
        
        unsorted_layout.addWidget(cat_frame, stretch=1)

        patterns_layout.addWidget(patterns_splitter)
        self.workspace_tabs.addTab(patterns_widget, "🔍 Patterns")

        # --- Slots & Values Tab ---
        slots_widget = QWidget()
        slots_layout = QVBoxLayout(slots_widget)
        slots_layout.setContentsMargins(8, 8, 8, 8)
        slots_layout.setSpacing(4)

        slots_help = QLabel(
            "🎰 Slots & Values: Manage the variable parts of your naming structure.\n\n"
            "• **Rename Slot**: Double-click a blue slot name\n"
            "• **Rename Value**: Double-click a gray value\n"
            "• **Move Values**: Drag selected values (Ctrl/Shift+Click) to a different slot\n"
            "• **Reorganize**: Right-click for more options"
        )
        slots_help.setStyleSheet("color: #888; font-size: 11px; padding: 6px; background-color: #1a1a2e; border-radius: 4px;")
        slots_help.setWordWrap(True)
        slots_layout.addWidget(slots_help)

        self.slots_tree = QTreeWidget()
        self.slots_tree.setHeaderLabels(["Slot / Value", "Detail", "Confidence", "Used In"])
        self.slots_tree.setColumnWidth(0, 220)
        self.slots_tree.setColumnWidth(1, 100)
        self.slots_tree.setColumnWidth(2, 80)
        self.slots_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.slots_tree.setDragEnabled(True)
        self.slots_tree.setAcceptDrops(True)
        self.slots_tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.slots_tree.itemDoubleClicked.connect(self._on_slots_tree_double_click)
        self.slots_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.slots_tree.customContextMenuRequested.connect(self._slots_context_menu)
        
        # Override drop event for custom move logic
        self.slots_tree.dropEvent = self._on_slots_tree_drop
        
        self.slots_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1a1a2e;
                border: 1px solid #333;
                border-radius: 4px;
                font-size: 12px;
            }
            QTreeWidget::item { padding: 4px; color: #ddd; }
            QTreeWidget::item:selected { background-color: #3a3a5e; }
        """)
        slots_layout.addWidget(self.slots_tree)
        self.workspace_tabs.addTab(slots_widget, "🎰 Slots")

        center_layout.addWidget(self.workspace_tabs, stretch=1)

        # ─── STAGING AREA (bottom of center) ──────────────────────────
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
        self.staging_tree.setMaximumHeight(140)
        self.staging_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        staging_layout.addWidget(self.staging_tree)

        center_layout.addWidget(staging_frame)

        main_splitter.addWidget(center_frame)

        main_splitter.setSizes([350, 1150])
        root.addWidget(main_splitter, stretch=1)

        # ─── Status bar ───────────────────────────────────────────────
        status_row = QHBoxLayout()
        self.status_label = QLabel("Ready. Drop files in the left panel to begin.")
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

    # ─── File import handlers ─────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = []
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    paths.append(url.toLocalFile())
        if paths:
            self._on_files_dropped(paths)
        elif event.mimeData().hasText():
            text = event.mimeData().text()
            current_text = self.input_area.toPlainText().strip()
            new_text = text.strip()
            if current_text:
                self.input_area.setPlainText(current_text + "\n" + new_text)
            else:
                self.input_area.setPlainText(new_text)
        event.acceptProposedAction()

    def _on_files_dropped(self, paths):
        extracted = {}  # source_label -> [names]
        for path in paths:
            if os.path.isdir(path):
                label = os.path.basename(path) + "/"
                names = []
                for dirpath, dirnames, filenames in os.walk(path):
                    for f in filenames:
                        name, _ = os.path.splitext(f)
                        names.append(name)
                if names:
                    extracted[label] = names
            elif os.path.isfile(path) and path.lower().endswith(('.csv', '.txt')):
                label = os.path.basename(path)
                names = []
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        for part in line.split(','):
                            cleaned = part.strip()
                            if cleaned:
                                names.append(cleaned)
                if names:
                    extracted[label] = names

        if extracted:
            all_names = []
            for label, names in extracted.items():
                all_names.extend(names)
            current_text = self.input_area.toPlainText().strip()
            new_text = "\n".join(all_names)
            if current_text:
                self.input_area.setPlainText(current_text + "\n" + new_text)
            else:
                self.input_area.setPlainText(new_text)
            total = sum(len(v) for v in extracted.values())
            sources = ", ".join(extracted.keys())
            self.status_label.setText(f"{total} names loaded from {sources}. Click 'Analyze' to process.")

    def _on_analyze(self):
        text = self.input_area.toPlainText().strip()
        if not text:
            return

        # Try to parse source labels from the input
        # For pasted text, use "Pasted Text" as the source label
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
        try:
            self._populate_from_session()
        except Exception as e:
            QMessageBox.critical(self, "Analysis Failed", f"A crash occurred during UI population:\n{e}\n\nPlease check the logs.")
            import traceback
            traceback.print_exc()

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
                f"✓ {dedup_count} of {total} filenames already exist. "
                f"{unknowns} new items."
            )
            self.dedup_frame.setVisible(True)
            self._populate_match_details()
        else:
            self.dedup_frame.setVisible(False)

        # Unsorted list (Patterns tab — non-staged, non-categorized items)
        self.unsorted_list.clear()
        for ns in self.session.candidate_namesets:
            if not ns.staged and not ns.category:
                self._add_to_unsorted(ns)

        # Clear and rebuild categories
        # First, remove all existing category bucket widgets
        for bucket in self.category_buckets.values():
            bucket.setParent(None)
            bucket.deleteLater()
        self.category_buckets.clear()

        # Rebuild categories from session
        for cat_name in self.session.categories:
            self._add_category_widget(cat_name)

        # Put categorized items in their buckets
        for ns in self.session.candidate_namesets:
            if ns.category and not ns.staged:
                if ns.category in self.category_buckets:
                    self.category_buckets[ns.category].add_item(ns.temp_id, self._ns_display_text(ns))

        # Populate Slots and Values tab
        self._refresh_slots_tab()

        # Staging tree
        self._refresh_staging_tree()

        # Progress panel
        self._refresh_progress()

        ns_count = len([ns for ns in self.session.candidate_namesets if not ns.staged])
        self.status_label.setText(
            f"Analysis complete. {ns_count} patterns found, {dedup_count} duplicates filtered."
        )

    def _add_to_unsorted(self, ns: CandidateNameSet):
        from PyQt6.QtWidgets import QListWidgetItem
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

    # ─── Dedup details ─────────────────────────────────────────────────

    def _populate_match_details(self):
        self.match_details_tree.clear()
        if not self.session:
            return
        groups = {}
        for m in self.session.dedup_matches:
            key = m.matched_nameset_name
            if key not in groups:
                groups[key] = []
            groups[key].append(m)

        for ns_name, matches in sorted(groups.items()):
            parent = QTreeWidgetItem(self.match_details_tree, [f"{ns_name} ({len(matches)} matches)", ""])
            parent.setForeground(0, QBrush(QColor("#8bc34a")))
            for m in matches[:50]:
                QTreeWidgetItem(parent, [m.filename, m.matched_nameset_name])

    def _toggle_match_details(self):
        vis = not self.match_details_tree.isVisible()
        self.match_details_tree.setVisible(vis)
        self.btn_show_matches.setText("Hide Matches ▴" if vis else "Show Matches ▾")

    # ─── Item selection / detail panel ─────────────────────────────────

    def _on_item_selected(self, item):
        temp_id = item.data(Qt.ItemDataRole.UserRole)
        self._show_details(temp_id)

    def _show_details(self, temp_id: str):
        if not self.session or temp_id not in self._ns_map:
            return
        self._selected_ns_id = temp_id
        ns = self._ns_map[temp_id]

        self.ns_name_edit.setText(ns.suggested_name)

        parts = []
        for part in ns.structure:
            if part["type"] == "literal":
                parts.append(part["value"])
            else:
                wc = self.session.candidate_wildcards.get(part["temp_id"])
                name = wc.suggested_name if wc else part["temp_id"]
                parts.append(f"[{name}]")
        self.structure_label.setText(f"Structure: {''.join(parts)}")

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

        self.example_list.clear()
        for asset in ns.matched_assets[:30]:
            self.example_list.addItem(asset.filename)

        # Switch to Patterns tab to show details
        self.workspace_tabs.setCurrentIndex(0)

    def _on_ns_name_edited(self):
        if self._selected_ns_id and self._selected_ns_id in self._ns_map:
            new_name = self.ns_name_edit.text().strip()
            if new_name:
                self._ns_map[self._selected_ns_id].suggested_name = new_name

    # ─── Slots & Values tab ────────────────────────────────────────────

    def _refresh_slots_tab(self):
        """Populate the Slots & Values combined tree."""
        self.slots_tree.clear()
        if not self.session:
            return

        for wc_id, wc in self.session.candidate_wildcards.items():
            # Find patterns using this slot
            used_in = []
            for ns in self.session.candidate_namesets:
                for part in ns.structure:
                    if part.get("temp_id") == wc_id:
                        used_in.append(ns.suggested_name)
                        break

            slot_node = QTreeWidgetItem(self.slots_tree, [
                wc.suggested_name,
                f"{len(wc.values)} values",
                f"{wc.confidence:.0f}%",
                ", ".join(used_in) if used_in else "—"
            ])
            slot_node.setData(0, Qt.ItemDataRole.UserRole, wc_id)
            slot_node.setData(0, Qt.ItemDataRole.UserRole + 1, "slot")
            slot_node.setForeground(0, QBrush(QColor("#8ab4f8")))
            slot_node.setFlags(slot_node.flags() | Qt.ItemFlag.ItemIsDropEnabled)
            slot_node.setExpanded(True)

            for val in sorted(wc.values, key=lambda x: x.confidence, reverse=True):
                val_node = QTreeWidgetItem(slot_node, [
                    val.name,
                    "",
                    f"{val.confidence:.0f}%",
                    ""
                ])
                val_node.setData(0, Qt.ItemDataRole.UserRole, val.name)  # value name is the ID
                val_node.setData(0, Qt.ItemDataRole.UserRole + 1, "value")
                val_node.setData(0, Qt.ItemDataRole.UserRole + 2, wc_id) # parent slot ID
                val_node.setForeground(0, QBrush(QColor("#ccc")))
                val_node.setFlags(val_node.flags() & ~Qt.ItemFlag.ItemIsDropEnabled | Qt.ItemFlag.ItemIsDragEnabled)

    def _on_slots_tree_double_click(self, item, column):
        """Handle renaming for both slots and values in the main Slots tab."""
        etype = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if etype == "slot":
            self._handle_slot_rename(item)
        elif etype == "value":
            self._handle_value_rename(item)

    def _on_wc_tree_double_click(self, item, column):
        """Handle renaming for slots in the Pattern Details panel."""
        # Only slots are top-level here, children are just values for display
        if item.parent(): # It's a value
            self._handle_value_rename_display_only(item)
        else: # It's a slot
            self._handle_slot_rename(item)

    def _handle_value_rename_display_only(self, item):
        """Renaming a value shown in the pattern details list."""
        old_val_name = item.text(0)
        parent = item.parent()
        if not parent: return
        wc_id = parent.data(0, Qt.ItemDataRole.UserRole)
        wc = self.session.candidate_wildcards.get(wc_id)
        if not wc: return

        new_name, ok = QInputDialog.getText(self, "Rename Value", "New name:", text=old_val_name)
        if ok and new_name.strip():
            new_name = new_name.strip()
            for val in wc.values:
                if val.name == old_val_name:
                    val.name = new_name
                    break
            self._refresh_slots_tab()
            if self._selected_ns_id:
                self._show_details(self._selected_ns_id)

    def _handle_slot_rename(self, item):
        wc_id = item.data(0, Qt.ItemDataRole.UserRole)
        wc = self.session.candidate_wildcards.get(wc_id)
        if not wc: return
        
        new_name, ok = QInputDialog.getText(self, "Rename Slot", "New name:", text=wc.suggested_name)
        if ok and new_name.strip():
            wc.suggested_name = new_name.strip()
            self._refresh_slots_tab()
            self._refresh_unsorted_display()
            if self._selected_ns_id:
                self._show_details(self._selected_ns_id)

    def _handle_value_rename(self, item):
        old_val_name = item.data(0, Qt.ItemDataRole.UserRole)
        wc_id = item.data(0, Qt.ItemDataRole.UserRole + 2)
        wc = self.session.candidate_wildcards.get(wc_id)
        if not wc: return
        
        new_name, ok = QInputDialog.getText(self, "Rename Value", "New name:", text=old_val_name)
        if ok and new_name.strip():
            new_name = new_name.strip()
            # Update value name in the model
            for val in wc.values:
                if val.name == old_val_name:
                    val.name = new_name
                    break
            self._refresh_slots_tab()

    def _slots_context_menu(self, pos: QPoint):
        items = self.slots_tree.selectedItems()
        if not items: return
        
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1e1e2e; color: #ddd; } QMenu::item:selected { background-color: #3a3a5e; }")
        
        # Only show move if values are selected
        values = [i for i in items if i.data(0, Qt.ItemDataRole.UserRole + 1) == "value"]
        
        if len(items) == 1:
            menu.addAction("Rename", lambda: self._on_slots_tree_double_click(items[0], 0))
        
        if values:
            move_menu = menu.addMenu("Move to Slot →")
            for wc_id, wc in sorted(self.session.candidate_wildcards.items(), key=lambda x: x[1].suggested_name):
                act = move_menu.addAction(wc.suggested_name)
                act.setData(wc_id)
                act.triggered.connect(lambda checked, target_id=wc_id: self._move_values_to_slot(values, target_id))

        menu.exec(self.slots_tree.mapToGlobal(pos))

    def _move_values_to_slot(self, items, target_wc_id):
        """Logic to move values from one wildcard to another in the session model."""
        target_wc = self.session.candidate_wildcards.get(target_wc_id)
        if not target_wc: return
        
        for item in items:
            source_wc_id = item.data(0, Qt.ItemDataRole.UserRole + 2)
            val_name = item.data(0, Qt.ItemDataRole.UserRole)
            
            if source_wc_id == target_wc_id: continue
            
            source_wc = self.session.candidate_wildcards.get(source_wc_id)
            if not source_wc: continue
            
            # Find and move the candidate value object
            found_val = None
            for val in source_wc.values:
                if val.name == val_name:
                    found_val = val
                    break
            
            if found_val:
                source_wc.values.remove(found_val)
                # Check if exists in target, if so merge confidence? (Simple move for now)
                target_wc.values.append(found_val)
        
        self._refresh_slots_tab()

    def _on_slots_tree_drop(self, event):
        """Custom drop handler for moving values between slots."""
        target_item = self.slots_tree.itemAt(event.position().toPoint())
        if not target_item:
            event.ignore()
            return
        
        # Determine target slot
        target_wc_id = None
        if target_item.data(0, Qt.ItemDataRole.UserRole + 1) == "slot":
            target_wc_id = target_item.data(0, Qt.ItemDataRole.UserRole)
        elif target_item.data(0, Qt.ItemDataRole.UserRole + 1) == "value":
            target_wc_id = target_item.data(0, Qt.ItemDataRole.UserRole + 2)
        
        if not target_wc_id:
            event.ignore()
            return

        selected_items = self.slots_tree.selectedItems()
        values_to_move = [i for i in selected_items if i.data(0, Qt.ItemDataRole.UserRole + 1) == "value"]
        
        if values_to_move:
            self._move_values_to_slot(values_to_move, target_wc_id)
            event.accept()
        else:
            event.ignore()

    def _on_slot_rename(self, item, column):
        # Redundant now, replaced by _on_slots_tree_double_click
        pass

    # (Deleting the old _refresh_values_tab)


    # ─── Progress / Ingested panel ───────────────────────────────────────────────

    def _refresh_imported_tree(self):
        """Update the Imported sidebar to exclude understood/staged items."""
        if not self.session:
            self.source_tree.clear()
            return

        imported_groups = {}
        
        # Add files that are NOT staged
        for ns in self._ns_map.values():
            if not ns.staged:
                for a in ns.matched_assets:
                    label = getattr(a, 'source_label', "Unknown")
                    if label not in imported_groups:
                        imported_groups[label] = []
                    if a.filename not in imported_groups[label]:
                        imported_groups[label].append(a.filename)

        self.source_tree.populate_from_session(imported_groups)

    def _refresh_progress(self):
        """Update the Ingested sidebar with understood/staged items."""
        if not self.session:
            self.ingested_tree.clear()
            return

        ingested_groups = {}
        
        # Add deduplicated files (already understood by dictionary)
        for m in self.session.dedup_matches:
            label = m.source_label or "Unknown"
            if label not in ingested_groups:
                ingested_groups[label] = []
            if m.filename not in ingested_groups[label]:
                ingested_groups[label].append(m.filename)

        # Add files from currently staged namesets
        for ns in self._ns_map.values():
            if ns.staged:
                for a in ns.matched_assets:
                    label = getattr(a, 'source_label', "Unknown")
                    if label not in ingested_groups:
                        ingested_groups[label] = []
                    if a.filename not in ingested_groups[label]:
                        ingested_groups[label].append(a.filename)

        self.ingested_tree.populate_from_session(ingested_groups)
        self._refresh_imported_tree()

    # ─── Category management ──────────────────────────────────────────

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

            if ns.category and ns.category in self.category_buckets:
                self.category_buckets[ns.category].remove_item(temp_id)
            else:
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
            if self.session:
                self.session.categories = [new_name if c == old_name else c for c in self.session.categories]
            for ns in self._ns_map.values():
                if ns.category == old_name:
                    ns.category = new_name

    def _delete_category(self, name: str):
        bucket = self.category_buckets.pop(name, None)
        if not bucket:
            return
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
        self._refresh_progress()

    # ─── Staging ──────────────────────────────────────────────────────

    def _stage_selected_items(self):
        items = self.unsorted_list.selectedItems()
        for item in items:
            temp_id = item.data(Qt.ItemDataRole.UserRole)
            ns = self._ns_map.get(temp_id)
            if ns:
                ns.staged = True
                ns.approved = True
        for item in items:
            row = self.unsorted_list.row(item)
            self.unsorted_list.takeItem(row)
        self._refresh_staging_tree()
        self._refresh_progress()

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
        self._refresh_progress()

    def _refresh_staging_tree(self):
        self.staging_tree.clear()
        staged = [ns for ns in self._ns_map.values() if ns.staged]
        for ns in staged:
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

    # ─── Context menus ────────────────────────────────────────────────

    def _unsorted_context_menu(self, pos: QPoint):
        items = self.unsorted_list.selectedItems()
        if not items:
            return
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1e1e2e; color: #ddd; } QMenu::item:selected { background-color: #3a3a5e; }")

        stage_act = menu.addAction("Stage Selected")
        rename_act = menu.addAction("Rename") if len(items) == 1 else None

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

    # ─── Session persistence ──────────────────────────────────────────

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

    # ─── Commit to project ────────────────────────────────────────────

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
            for v in self.tax_manager.get_all_values():
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
                    safe_name = candidate_wc.suggested_name.replace(" ", "_").lower()
                    real_wc_id = f"wc.proj.{safe_name}"

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
