import sys
import os

# Redirect standard output and error to log file
log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ludexicon.log')
sys.stdout = open(log_file_path, "w")
sys.stderr = sys.stdout
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeView, QListWidget, QScrollArea, QPushButton, QCheckBox,
    QLineEdit, QLabel, QSplitter, QComboBox, QFrame, QListWidgetItem,
    QToolButton, QSizePolicy, QMenu, QMessageBox, QTabWidget, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QAction

from logic import TaxonomyManager, Value, NameSet, Wildcard, NameSetComponent, Trigger
from ui_ingest import TaxonomyIngestDialog


class MultiSelectComboBox(QPushButton):
    """
    A multi-select dropdown button using QMenu.
    """
    selectionChanged = pyqtSignal()

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.title_base = title
        
        self.menu = QMenu(self)
        self.setMenu(self.menu)
        
        self._action_value_map = {}
        
        self.menu.triggered.connect(self._on_action_triggered)
        self.setStyleSheet("text-align: left;")

    def add_value(self, value: Value):
        action = QAction(value.name, self.menu)
        action.setCheckable(True)
        self.menu.addAction(action)
        self._action_value_map[action] = value

    def clear(self):
        self.menu.clear()
        self._action_value_map.clear()
        self.setText(self.title_base)

    def _on_action_triggered(self, action: QAction):
        self.menu.show() # keep open
        self.update_title()
        self.selectionChanged.emit()

    def update_title(self):
        selected = self.get_selected_values()
        if not selected:
            self.setText(self.title_base)
        elif len(selected) == 1:
            self.setText(f"{self.title_base}: {selected[0].name}")
        else:
            self.setText(f"{self.title_base}: [ {len(selected)} selected ]")

    def get_selected_values(self):
        return [self._action_value_map[act] for act, val in self._action_value_map.items() if act.isChecked()]


class CollapsibleBox(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.toggle_button = QToolButton(text=title, checkable=True, checked=False)
        self.toggle_button.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.pressed.connect(self.on_pressed)

        self.content_area = QScrollArea(maximumHeight=0, minimumHeight=0)
        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.content_area.setFrameShape(QFrame.Shape.NoFrame)

        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)

        self.content_layout = QHBoxLayout()
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.content_widget = QWidget()
        self.content_widget.setLayout(self.content_layout)
        self.content_area.setWidget(self.content_widget)
        self.content_area.setWidgetResizable(True)
        
        self.is_expanded = False

    def on_pressed(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if not checked else Qt.ArrowType.RightArrow)
        self.is_expanded = not checked
        if self.is_expanded:
            self.content_area.setMinimumHeight(self.content_layout.sizeHint().height() + 20)
            self.content_area.setMaximumHeight(self.content_layout.sizeHint().height() + 20)
        else:
            self.content_area.setMinimumHeight(0)
            self.content_area.setMaximumHeight(0)


class NameSetWidget(QFrame):
    sequenceChanged = pyqtSignal()
    
    def __init__(self, nameset: NameSet, tax_manager: TaxonomyManager, parent=None):
        super().__init__(parent)
        self.base_nameset = nameset
        self.tax_manager = tax_manager
        
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("NameSetWidget { background-color: #2b2b2b; border: 1px solid #444; border-radius: 3px; }")
        
        self.slots = []
        for c in nameset.nameset_structure:
            self.slots.append({'type': c.type, 'id': c.id, 'value': c.value})
            
        self.slots_layout = QHBoxLayout()
        self.slots_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.slots_container = QWidget()
        self.slots_container.setLayout(self.slots_layout)
        
        self.build_slots_ui_from_scratch()
        
        self.preview_list = QListWidget()
        self.preview_list.setMaximumHeight(80) 
        self.preview_list.setStyleSheet("QListWidget { background-color: #1e1e1e; border: 1px solid #3c3f41; }")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(f"<b>NameSet component: {nameset.name}</b>"))
        
        main_layout.addLayout(header_layout)
        main_layout.addWidget(self.slots_container)
        main_layout.addWidget(QLabel("<i>Local Matrix Preview:</i>"))
        main_layout.addWidget(self.preview_list)
        
        self.last_generated_names = []

    def build_slots_ui_from_scratch(self):
        while self.slots_layout.count():
            item = self.slots_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        all_wcs = list(self.tax_manager.core_registry["wildcards"].values()) + list(self.tax_manager.project_registry["wildcards"].values())

        for i, slot in enumerate(self.slots):
            if slot['type'] == 'literal':
                label = QLabel(slot['value'])
                label.setStyleSheet("font-weight: bold; padding: 0px 5px; font-size: 14px;")
                self.slots_layout.addWidget(label)
            elif slot['type'] == 'wildcard':
                combo = QComboBox()
                combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
                for wc in all_wcs:
                    combo.addItem(f"[{wc.name}]", userData=wc.id)
                    if wc.id == slot['id']:
                        combo.setCurrentIndex(combo.count() - 1)
                        
                combo.currentIndexChanged.connect(lambda idx, slot_idx=i, cb=combo: self.on_wildcard_changed(slot_idx, cb))
                self.slots_layout.addWidget(combo)
                
        self.append_btn = QPushButton("+")
        self.append_btn.setFixedSize(24, 24)
        self.append_btn.setStyleSheet("font-weight: bold;")
        self.append_btn.clicked.connect(self.on_append_clicked)
        self.slots_layout.addWidget(self.append_btn)
        self.slots_layout.addStretch()

    def on_wildcard_changed(self, slot_idx, combo):
        self.slots[slot_idx]['id'] = combo.currentData()
        self.sequenceChanged.emit()

    def on_append_clicked(self):
        self.slots.append({'type': 'literal', 'value': '_'})
        all_wcs = list(self.tax_manager.core_registry["wildcards"].values()) + list(self.tax_manager.project_registry["wildcards"].values())
        first_id = all_wcs[0].id if all_wcs else ""
        self.slots.append({'type': 'wildcard', 'id': first_id})
        
        self.build_slots_ui_from_scratch()
        self.sequenceChanged.emit()

    def generate_and_preview(self, selections):
        component_results = []
        for comp in self.slots:
            if comp['type'] == 'literal':
                component_results.append([comp['value']])
            elif comp['type'] == 'wildcard':
                res = self.tax_manager.resolve_wildcard(comp['id'], selections)
                component_results.append(res if res else [""])
                
        import itertools
        combinations = list(itertools.product(*component_results))
        names = ["".join(combo) for combo in combinations]
        
        self.preview_list.clear()
        valid_names = []
        for name in names:
            if name and len(name) > 2:
                valid_names.append(name)
                self.preview_list.addItem(name)
                
        self.last_generated_names = valid_names
        return valid_names


class GroupWidget(QFrame):
    globalMatrixUpdated = pyqtSignal()
    
    def __init__(self, name: str, tax_manager: TaxonomyManager, parent=None):
        super().__init__(parent)
        self.tax_manager = tax_manager
        
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setStyleSheet("GroupWidget { background-color: #333333; margin-bottom: 10px; border-radius: 5px; }")
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        self.header_layout = QHBoxLayout()
        self.header_label = QLabel(f"<h3 style='margin:0;'>Group: {name}</h3>")
        self.add_nameset_btn = QPushButton("+ Add NameSet")
        self.add_nameset_btn.clicked.connect(self.on_add_nameset)
        
        self.header_layout.addWidget(self.header_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.add_nameset_btn)
        self.main_layout.addLayout(self.header_layout)
        
        self.collapsible_box = CollapsibleBox(title="Wildcards (Expand to lock/select)")
        self.main_layout.addWidget(self.collapsible_box)
        
        self.namesets_layout = QVBoxLayout()
        self.namesets_layout.setSpacing(10)
        self.main_layout.addLayout(self.namesets_layout)
        
        self.namesets = []
        self.wildcard_combos = {}
        self.base_wildcards = set()

    def on_add_nameset(self):
        ns = self.tax_manager.get_nameset("ns.combat.melee")
        if ns:
            self.add_nameset(ns)

    def add_nameset(self, nameset):
        nw = NameSetWidget(nameset, self.tax_manager, self)
        nw.sequenceChanged.connect(self.update_base_wildcards)
        self.namesets_layout.addWidget(nw)
        self.namesets.append(nw)
        self.update_base_wildcards()

    def update_base_wildcards(self):
        new_base = set()
        for nw in self.namesets:
            for slot in nw.slots:
                if slot['type'] == 'wildcard' and slot['id']:
                    new_base.add(slot['id'])
        self.base_wildcards = new_base
        self.sync_combos()

    def sync_combos(self):
        required = set(self.base_wildcards)
        queue = list(required)
        i = 0
        triggered = set()
        
        while i < len(queue):
            curr_id = queue[i]
            if curr_id in self.wildcard_combos:
                selected = self.wildcard_combos[curr_id].get_selected_values()
                for v in selected:
                    for t in v.triggers:
                        if t.id not in required and t.id not in triggered:
                            triggered.add(t.id)
                            queue.append(t.id)
            i += 1
            
        total_required = required.union(triggered)
        
        existing = set(self.wildcard_combos.keys())
        for w_id in existing - total_required:
            combo = self.wildcard_combos.pop(w_id)
            self.collapsible_box.content_layout.removeWidget(combo)
            combo.deleteLater()
            
        for w_id in total_required - existing:
            self.create_combobox(w_id)
            
        if self.collapsible_box.is_expanded:
            self.collapsible_box.content_area.setMinimumHeight(self.collapsible_box.content_layout.sizeHint().height() + 20)
            self.collapsible_box.content_area.setMaximumHeight(self.collapsible_box.content_layout.sizeHint().height() + 20)

        self.regenerate_all_matrices()

    def create_combobox(self, wildcard_id: str):
        wildcard = self.tax_manager.get_wildcard(wildcard_id)
        name = wildcard.name if wildcard else wildcard_id
        combo = MultiSelectComboBox(f"[{name}]")
        
        all_values = list(self.tax_manager.core_registry["values"].values()) + list(self.tax_manager.project_registry["values"].values())
        for val in all_values:
            if val.wildcard_id == wildcard_id:
                combo.add_value(val)
                
        combo.selectionChanged.connect(self.on_selection_changed)
        self.wildcard_combos[wildcard_id] = combo
        self.collapsible_box.content_layout.addWidget(combo)
        return combo

    def on_selection_changed(self):
        self.sync_combos()

    def get_selections(self):
        return {w_id: combo.get_selected_values() for w_id, combo in self.wildcard_combos.items()}

    def regenerate_all_matrices(self):
        selections = self.get_selections()
        for nw in self.namesets:
            nw.generate_and_preview(selections)
        self.globalMatrixUpdated.emit()

    def get_all_global_matrices(self):
        global_matrix = []
        for nw in self.namesets:
            global_matrix.extend(nw.last_generated_names)
        return global_matrix


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
            if string and "_" in string or len(string) > 2:
                final_str = string + ".wav" if append_ext else string
                self.output_list.addItem(final_str)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        items = [self.output_list.item(i).text() for i in range(self.output_list.count())]
        clipboard.setText("\n".join(items))


class MainWindow(QMainWindow):
    def __init__(self, tax_manager: TaxonomyManager):
        super().__init__()
        self.tax_manager = tax_manager
        self.setWindowTitle("Ludexicon - Game Asset Taxonomy Engine")
        self.resize(1200, 800)
        
        self.browser_count = 1
        self.browsers = []
        self.builder_count = 0
        
        self.init_ui()

    def init_ui(self):
        # Center Pane: Builders Tabs
        self.builder_tabs = QTabWidget()
        self.builder_tabs.setTabsClosable(True)
        self.builder_tabs.setMovable(True)
        self.builder_tabs.tabCloseRequested.connect(self.close_builder_tab)
        self.builder_tabs.tabBarDoubleClicked.connect(self.rename_builder_tab)
        self.setCentralWidget(self.builder_tabs)
        
        self.spawn_new_builder()

        # Dock settings
        self.setDockOptions(QMainWindow.DockOption.AllowNestedDocks | QMainWindow.DockOption.ForceTabbedDocks)
        self.setTabPosition(Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North)

        # Left Pane: Browser
        self.left_dock = self.create_browser_dock("Browser")
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.left_dock)
        
        self.create_menu_bar()

    def spawn_new_builder(self):
        self.builder_count += 1
        builder = BuilderWidget(self.tax_manager, self)
        name = f"Builder {self.builder_count}"
        idx = self.builder_tabs.addTab(builder, name)
        self.builder_tabs.setCurrentIndex(idx)
        builder.add_dummy_group()

    def close_builder_tab(self, index):
        if self.builder_tabs.count() > 1:
            widget = self.builder_tabs.widget(index)
            self.builder_tabs.removeTab(index)
            widget.deleteLater()

    def rename_builder_tab(self, index):
        if index >= 0:
            current_name = self.builder_tabs.tabText(index)
            new_name, ok = QInputDialog.getText(self, "Rename Tab", "Enter new builder name:", text=current_name)
            if ok and new_name:
                self.builder_tabs.setTabText(index, new_name)

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("&File")

        new_builder_action = QAction("New &Builder", self)
        new_builder_action.setShortcut("Ctrl+T")
        new_builder_action.triggered.connect(self.spawn_new_builder)
        file_menu.addAction(new_builder_action)
        
        file_menu.addSeparator()

        ingest_action = QAction("Ingest Taxonomy...", self)
        ingest_action.triggered.connect(self.open_ingest_tool)
        file_menu.addAction(ingest_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit Menu
        edit_menu = menubar.addMenu("&Edit")
        # Placeholder for future edit actions
        
        # Window Menu
        window_menu = menubar.addMenu("&Window")
        
        # Spawn New Browser
        new_browser_action = QAction("&New Browser", self)
        new_browser_action.triggered.connect(self.spawn_new_browser)
        window_menu.addAction(new_browser_action)
        window_menu.addSeparator()
        
        # Toggle docks visibility
        window_menu.addAction(self.left_dock.toggleViewAction())
        
        # Help Menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def open_ingest_tool(self):
        dialog = TaxonomyIngestDialog(self.tax_manager, self)
        dialog.exec()
        
        # In Phase 5, we'll refresh the trees after the dialog closes
        self.populate_lexicon_tree()

    def create_browser_dock(self, title: str) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setTitleBarWidget(DockTitleTab(title, dock))
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search Taxonomy...")
        layout.addWidget(search_bar)
        
        tree_view = QTreeView()
        tree_model = QStandardItemModel()
        tree_model.setHorizontalHeaderLabels(["Name", "ID", "Tags"])
        tree_view.setModel(tree_model)
        
        tree_view.setColumnWidth(0, 150)
        tree_view.setColumnWidth(1, 150)
        
        layout.addWidget(tree_view)
        
        dock.setWidget(widget)
        
        # We store references so they don't get garbage collected and can expand
        # But populate_lexicon_tree doesn't dynamically update right now natively
        dock.tree_view = tree_view
        dock.tree_model = tree_model
        dock.search_bar = search_bar
        
        self.populate_lexicon_tree(tree_model, tree_view)
        
        self.browsers.append(dock)
        return dock

    def spawn_new_browser(self):
        self.browser_count += 1
        new_dock = self.create_browser_dock(f"Browser {self.browser_count}")
        # Add to the same dock area and tabify it with the first one 
        # so they stack properly instead of just squeezing.
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, new_dock)
        if self.browsers: # Try to tabify with the first browser
            self.tabifyDockWidget(self.browsers[0], new_dock)
            new_dock.show()

    def show_about(self):
        QMessageBox.about(self, "About Ludexicon", 
            "<b>Ludexicon</b><br><br>"
            "Game Asset Taxonomy Engine.<br>"
            "A tool for standardizing naming conventions.<br><br>"
            "Created by: <a href='https://github.com/ajohnsonsfx'>Alex Johnson</a><br><br>"
            "Version 0.1")

    def populate_lexicon_tree(self, tree_model=None, tree_view=None):
        if tree_model is None:
            tree_model = getattr(self, 'tree_model', None)
        if tree_view is None:
            tree_view = getattr(self, 'tree_view', None)

        root = tree_model.invisibleRootItem()
        
        # Core
        core_node = [QStandardItem("Core Lexicon"), QStandardItem(""), QStandardItem("")]
        for wc_id, wc in self.tax_manager.core_registry["wildcards"].items():
            wc_name = QStandardItem(wc.name)
            wc_id_item = QStandardItem(f"[{wc_id}]")
            wc_tags = QStandardItem("")
            
            for v_id, v in self.tax_manager.core_registry["values"].items():
                if v.wildcard_id == wc_id:
                    v_name = QStandardItem(v.name)
                    v_id_item = QStandardItem(f"[{v_id}]")
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
            
            for v_id, v in self.tax_manager.project_registry["values"].items():
                if v.wildcard_id == wc_id:
                    v_name = QStandardItem(v.name)
                    v_id_item = QStandardItem(f"[{v_id}]")
                    tags_str = ", ".join(getattr(v, 'tags', []))
                    v_tags = QStandardItem(tags_str)
                    wc_name.appendRow([v_name, v_id_item, v_tags])
            proj_node[0].appendRow([wc_name, wc_id_item, wc_tags])
            
        root.appendRow(core_node)
        root.appendRow(proj_node)
        if tree_view:
            tree_view.expandAll()


def setup_dummy_data(manager: TaxonomyManager):
    """Populates the manager with some initial data so the UI isn't empty."""
    # Core
    manager.add_item("core", Wildcard("wc.entity_class", "Entity Class"))
    manager.add_item("core", Wildcard("wc.action", "Action"))
    manager.add_item("core", Wildcard("wc.mob_id", "Mob ID"))
    
    manager.add_item("core", Value(id="val.class.mob", name="Mob", wildcard_id="wc.entity_class", triggers=[Trigger(id="wc.mob_id", delimiter="_")]))
    manager.add_item("core", Value(id="val.action.melee", name="Melee", wildcard_id="wc.action"))
    manager.add_item("core", Value(id="val.action.ranged", name="Ranged", wildcard_id="wc.action"))
    manager.add_item("core", Value(id="val.action.impact", name="Impact", wildcard_id="wc.action"))
    manager.add_item("core", Value(id="val.action.walk", name="Walk", wildcard_id="wc.action"))
    
    # Project
    # Note: to properly show "Mob ID" in the taxonomy tree we should technically register it in project wildcards if it's purely project side,
    # but since it's triggered from core, we registered it in core wildcards.
    manager.add_item("project", Value(id="val.mob.saltdevil", name="SaltDevil", wildcard_id="wc.mob_id"))
    manager.add_item("project", Value(id="val.mob.firefiend", name="FireFiend", wildcard_id="wc.mob_id"))
    
    manager.add_item("project", NameSet(
        id="ns.combat.melee",
        name="Entity Attack",
        nameset_structure=[
            NameSetComponent(type="wildcard", id="wc.entity_class"),
            NameSetComponent(type="literal", value="_"),
            NameSetComponent(type="wildcard", id="wc.action")
        ]
    ))
    
    manager.save()

def main():
    app = QApplication(sys.argv)
    
    # Standard dense styling
    app.setStyleSheet("""
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
    """)
    
    manager = TaxonomyManager()
    setup_dummy_data(manager) # populate basic stuff for UX pass
    manager.load()
    
    window = MainWindow(manager)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
