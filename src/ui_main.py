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
    QToolButton, QSizePolicy, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QAction

from logic import TaxonomyManager, Element, Pattern, Wildcard, PatternComponent, Trigger


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
        
        self._action_element_map = {}
        
        self.menu.triggered.connect(self._on_action_triggered)
        self.setStyleSheet("text-align: left;")

    def add_element(self, element: Element):
        action = QAction(element.name, self.menu)
        action.setCheckable(True)
        self.menu.addAction(action)
        self._action_element_map[action] = element

    def clear(self):
        self.menu.clear()
        self._action_element_map.clear()
        self.setText(self.title_base)

    def _on_action_triggered(self, action: QAction):
        self.menu.show() # keep open
        self.update_title()
        self.selectionChanged.emit()

    def update_title(self):
        selected = self.get_selected_elements()
        if not selected:
            self.setText(self.title_base)
        elif len(selected) == 1:
            self.setText(f"{self.title_base}: {selected[0].name}")
        else:
            self.setText(f"{self.title_base}: [ {len(selected)} selected ]")

    def get_selected_elements(self):
        return [self._action_element_map[act] for act, el in self._action_element_map.items() if act.isChecked()]


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


class PatternWidget(QFrame):
    sequenceChanged = pyqtSignal()
    
    def __init__(self, pattern: Pattern, tax_manager: TaxonomyManager, parent=None):
        super().__init__(parent)
        self.base_pattern = pattern
        self.tax_manager = tax_manager
        
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("PatternWidget { background-color: #2b2b2b; border: 1px solid #444; border-radius: 3px; }")
        
        self.slots = []
        for c in pattern.filename_structure:
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
        header_layout.addWidget(QLabel(f"<b>Pattern component: {pattern.name}</b>"))
        
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
        self.add_pattern_btn = QPushButton("+ Add Pattern")
        self.add_pattern_btn.clicked.connect(self.on_add_pattern)
        
        self.header_layout.addWidget(self.header_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.add_pattern_btn)
        self.main_layout.addLayout(self.header_layout)
        
        self.collapsible_box = CollapsibleBox(title="Variables (Expand to lock/select)")
        self.main_layout.addWidget(self.collapsible_box)
        
        self.patterns_layout = QVBoxLayout()
        self.patterns_layout.setSpacing(10)
        self.main_layout.addLayout(self.patterns_layout)
        
        self.patterns = []
        self.wildcard_combos = {}
        self.base_wildcards = set()

    def on_add_pattern(self):
        pat = self.tax_manager.get_pattern("pat.combat.melee")
        if pat:
            self.add_pattern(pat)

    def add_pattern(self, pattern):
        pw = PatternWidget(pattern, self.tax_manager, self)
        pw.sequenceChanged.connect(self.update_base_wildcards)
        self.patterns_layout.addWidget(pw)
        self.patterns.append(pw)
        self.update_base_wildcards()

    def update_base_wildcards(self):
        new_base = set()
        for pw in self.patterns:
            for slot in pw.slots:
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
                selected = self.wildcard_combos[curr_id].get_selected_elements()
                for el in selected:
                    for t in el.triggers:
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
        
        all_elements = list(self.tax_manager.core_registry["elements"].values()) + list(self.tax_manager.project_registry["elements"].values())
        for el in all_elements:
            if el.wildcard_id == wildcard_id:
                combo.add_element(el)
                
        combo.selectionChanged.connect(self.on_selection_changed)
        self.wildcard_combos[wildcard_id] = combo
        self.collapsible_box.content_layout.addWidget(combo)
        return combo

    def on_selection_changed(self):
        self.sync_combos()

    def get_selections(self):
        return {w_id: combo.get_selected_elements() for w_id, combo in self.wildcard_combos.items()}

    def regenerate_all_matrices(self):
        selections = self.get_selections()
        for pw in self.patterns:
            pw.generate_and_preview(selections)
        self.globalMatrixUpdated.emit()

    def get_all_global_matrices(self):
        global_matrix = []
        for pw in self.patterns:
            global_matrix.extend(pw.last_generated_names)
        return global_matrix



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
        
        self.create_menu_bar()
        
        self.current_matrix = []

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("&File")
        
        exit_action = QAction("&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit Menu
        edit_menu = menubar.addMenu("&Edit")
        # Placeholder for future edit actions
        
        # Window Menu
        window_menu = menubar.addMenu("&Window")
        
        # Toggle docks visibility
        window_menu.addAction(self.left_dock.toggleViewAction())
        window_menu.addAction(self.right_dock.toggleViewAction())
        
        # Help Menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def show_about(self):
        QMessageBox.about(self, "About Ludexicon", 
            "<b>Ludexicon</b><br><br>"
            "Game Asset Taxonomy Engine.<br>"
            "A tool for standardizing naming conventions.<br><br>"
            "Version 0.1")

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



def setup_dummy_data(manager: TaxonomyManager):
    """Populates the manager with some initial data so the UI isn't empty."""
    # Core
    manager.add_item("core", Wildcard("wc.entity_class", "Entity Class"))
    manager.add_item("core", Wildcard("wc.action", "Action"))
    manager.add_item("core", Wildcard("wc.mob_id", "Mob ID"))
    
    manager.add_item("core", Element(id="el.class.mob", name="Mob", wildcard_id="wc.entity_class", triggers=[Trigger(id="wc.mob_id", delimiter="_")]))
    manager.add_item("core", Element(id="el.action.melee", name="Melee", wildcard_id="wc.action"))
    manager.add_item("core", Element(id="el.action.ranged", name="Ranged", wildcard_id="wc.action"))
    manager.add_item("core", Element(id="el.action.impact", name="Impact", wildcard_id="wc.action"))
    manager.add_item("core", Element(id="el.action.walk", name="Walk", wildcard_id="wc.action"))
    
    # Project
    # Note: to properly show "Mob ID" in the taxonomy tree we should technically register it in project wildcards if it's purely project side,
    # but since it's triggered from core, we registered it in core wildcards.
    manager.add_item("project", Element(id="el.mob.saltdevil", name="SaltDevil", wildcard_id="wc.mob_id"))
    manager.add_item("project", Element(id="el.mob.firefiend", name="FireFiend", wildcard_id="wc.mob_id"))
    
    manager.add_item("project", Pattern(
        id="pat.combat.melee",
        name="Entity Attack",
        filename_structure=[
            PatternComponent(type="wildcard", id="wc.entity_class"),
            PatternComponent(type="literal", value="_"),
            PatternComponent(type="wildcard", id="wc.action")
        ]
    ))
    
    manager.save()

def main():
    app = QApplication(sys.argv)
    
    # Standard dense styling
    app.setStyleSheet("""
        QMainWindow { background-color: #2b2b2b; color: #e0e0e0; }
        QWidget { background-color: #2b2b2b; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
        QDockWidget { border: 1px solid #444; }
        QDockWidget::title { background: #3c3f41; padding: 4px; text-align: center; }
        QPushButton { background-color: #3c3f41; border: 1px solid #555; padding: 4px; border-radius: 2px; }
        QPushButton:hover { background-color: #4b4d4f; }
        QPushButton:checked { background-color: #5b5d5f; }
        QLineEdit, QTreeView, QListWidget, QScrollArea { background-color: #1e1e1e; border: 1px solid #3c3f41; }
        QHeaderView::section { background-color: #3c3f41; padding: 4px; border: 1px solid #333; }
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
