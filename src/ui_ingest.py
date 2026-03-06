from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSplitter, 
    QTreeWidget, QTreeWidgetItem, QPushButton, QFrame, 
    QScrollArea, QWidget, QCheckBox, QMenu, QInputDialog, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QAction
import os

from ingest_logic import TaxonomyIngestEngine, CandidateNameSet, CandidateWildcard
from logic import NameSet, Wildcard, Value, NameSetComponent

class IngestInputArea(QTextEdit):
    filesDropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText("Paste names here, or drag & drop folders/.txt/.csv files here...")
        self.setStyleSheet("""
            QTextEdit { 
                background-color: #1e1e1e; 
                border: 2px dashed #444; 
                border-radius: 5px; 
                padding: 10px;
                font-family: monospace;
            }
            QTextEdit:hover {
                border-color: #4b6eaf;
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
            # Handle standard text drop
            super().dropEvent(event)


class TaxonomyIngestDialog(QDialog):
    def __init__(self, tax_manager, parent=None):
        super().__init__(parent)
        self.tax_manager = tax_manager
        self.engine = TaxonomyIngestEngine(tax_manager)
        
        self.setWindowTitle("Taxonomy Ingest Tool")
        self.resize(1000, 700)
        
        self.init_ui()
        
    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        
        # 1. Input Area
        self.input_layout = QVBoxLayout()
        self.input_area = IngestInputArea()
        self.input_area.filesDropped.connect(self.on_files_dropped)
        self.input_area.setMaximumHeight(150)
        self.input_layout.addWidget(self.input_area)
        
        self.options_layout = QHBoxLayout()
        self.options_layout.addWidget(QLabel("Ignore Suffixes:"))
        self.chk_ignore_vars = QCheckBox("Variations (e.g. _01, 02)")
        self.chk_ignore_versions = QCheckBox("Versions (e.g. _v01, v2.0)")
        self.chk_ignore_dates = QCheckBox("Dates (e.g. _20240101)")
        self.options_layout.addWidget(self.chk_ignore_vars)
        self.options_layout.addWidget(self.chk_ignore_versions)
        self.options_layout.addWidget(self.chk_ignore_dates)
        self.options_layout.addStretch()
        self.input_layout.addLayout(self.options_layout)

        self.analyze_btn = QPushButton("Analyze Input")
        self.analyze_btn.clicked.connect(self.on_analyze_clicked)
        self.analyze_btn.setStyleSheet("background-color: #48669c; font-weight: bold; padding: 5px;")
        self.input_layout.addWidget(self.analyze_btn)
        
        self.main_layout.addLayout(self.input_layout)
        
        # 2. Main content splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Candidate NameSets
        self.ns_tree = QTreeWidget()
        self.ns_tree.setHeaderLabels(["Candidate NameSet Structure", "Count", "Confidence"])
        self.ns_tree.setColumnWidth(0, 400)
        self.ns_tree.itemClicked.connect(self.on_nameset_selected)
        
        # Right: Details (Wildcards / Assets)
        self.details_widget = QWidget()
        self.details_layout = QVBoxLayout(self.details_widget)
        
        self.details_label = QLabel("Select a NameSet to review details")
        self.details_label.setStyleSheet("font-weight: bold;")
        self.details_layout.addWidget(self.details_label)
        
        self.wc_tree = QTreeWidget()
        self.wc_tree.setHeaderLabels(["Wildcard Tokens", "Confidence"])
        self.details_layout.addWidget(self.wc_tree)
        
        self.asset_list = QTreeWidget()
        self.asset_list.setHeaderLabels(["Example Assets"])
        self.details_layout.addWidget(self.asset_list)
        
        self.splitter.addWidget(self.ns_tree)
        self.splitter.addWidget(self.details_widget)
        self.splitter.setSizes([600, 400])
        
        self.main_layout.addWidget(self.splitter)
        
        # 3. Bottom Buttons
        self.button_layout = QHBoxLayout()
        
        self.status_label = QLabel("Ready")
        self.button_layout.addWidget(self.status_label)
        self.button_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.button_layout.addWidget(self.btn_cancel)
        
        self.btn_submit = QPushButton("Submit Selected (Inject to Project)")
        self.btn_submit.setStyleSheet("background-color: #2d5a27; font-weight: bold;")
        self.btn_submit.setEnabled(False)
        self.btn_submit.clicked.connect(self.on_submit_clicked)
        self.button_layout.addWidget(self.btn_submit)
        
        self.main_layout.addLayout(self.button_layout)

    def on_files_dropped(self, paths):
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
            self.status_label.setText(f"{len(extracted_names)} names loaded. Click 'Analyze Input' to continue.")

    def on_analyze_clicked(self):
        text = self.input_area.toPlainText().strip()
        if not text:
            return
            
        names = []
        for line in text.split('\n'):
            for part in line.split(','):
                cleaned = part.strip()
                if cleaned:
                    names.append(cleaned)
                    
        if names:
            self.engine.ignore_variations = self.chk_ignore_vars.isChecked()
            self.engine.ignore_versions = self.chk_ignore_versions.isChecked()
            self.engine.ignore_dates = self.chk_ignore_dates.isChecked()

            self.status_label.setText("Processing input...")
            self.engine.pending_assets.clear()
            self.engine.process_raw_names("Input Box", names)
            self._run_inference_and_update()

    def _run_inference_and_update(self):
        unknowns = self.engine.get_unknown_assets()
        skipped = len(self.engine.pending_assets) - len(unknowns)
        
        self.status_label.setText(f"Found {len(unknowns)} unknowns ({skipped} skipped). Running inference...")
        
        self.candidate_ns, self.candidate_wcs = self.engine.run_inference()
        self.update_results_tree()
        self.btn_submit.setEnabled(True)
        self.status_label.setText(f"Inference complete. {len(self.candidate_ns)} NameSet candidates found.")

    def update_results_tree(self):
        self.ns_tree.clear()
        
        # Group by confidence for UX
        high = []
        low = []
        for ns in self.candidate_ns:
            if ns.confidence >= 70:
                high.append(ns)
            else:
                low.append(ns)
        
        if high:
            parent = QTreeWidgetItem(self.ns_tree, ["High Confidence Suggestions"])
            parent.setExpanded(True)
            for ns in high:
                self.add_ns_to_tree(parent, ns)
                
        if low:
            parent = QTreeWidgetItem(self.ns_tree, ["Low Confidence Suggestions (Review Carefully)"])
            parent.setExpanded(True)
            for ns in low:
                self.add_ns_to_tree(parent, ns)

    def add_ns_to_tree(self, parent, ns):
        struct_str = ""
        for part in ns.structure:
            if part['type'] == 'literal':
                struct_str += part['value']
            else:
                struct_str += f"[{part['temp_id']}]"
                
        item = QTreeWidgetItem(parent, [struct_str, str(len(ns.matched_assets)), f"{ns.confidence:.0f}%"])
        item.setData(0, Qt.ItemDataRole.UserRole, ns)
        
        # Color coding
        if ns.confidence >= 90:
            item.setForeground(2, QBrush(QColor("#5cb85c"))) # Green
        elif ns.confidence >= 50:
            item.setForeground(2, QBrush(QColor("#f0ad4e"))) # Orange
        else:
            item.setForeground(2, QBrush(QColor("#d9534f"))) # Red
            
        item.setCheckState(0, Qt.CheckState.Checked if ns.confidence >= 70 else Qt.CheckState.Unchecked)

    def on_nameset_selected(self, item, column):
        ns = item.data(0, Qt.ItemDataRole.UserRole)
        if not ns: return
        
        self.details_label.setText(f"NameSet: {item.text(0)}")
        
        # Update Wildcard details
        self.wc_tree.clear()
        for part in ns.structure:
            if part['type'] == 'wildcard':
                wc_id = part['temp_id']
                wc = self.candidate_wcs.get(wc_id)
                if wc:
                    wc_item = QTreeWidgetItem(self.wc_tree, [f"Wildcard {wc_id}", f"{wc.confidence:.0f}%"])
                    wc_item.setExpanded(True)
                    for val in sorted(wc.values, key=lambda x: x.confidence, reverse=True):
                        QTreeWidgetItem(wc_item, [val.name, f"{val.confidence:.0f}%"])
        
        # Update Asset Examples (limit to 20 for performance)
        self.asset_list.clear()
        for asset in ns.matched_assets[:20]:
            QTreeWidgetItem(self.asset_list, [asset.filename])

    def on_submit_clicked(self):
        root = self.ns_tree.invisibleRootItem()
        approved_ns = []
        for i in range(root.childCount()):
            group = root.child(i)
            for j in range(group.childCount()):
                item = group.child(j)
                if item.checkState(0) == Qt.CheckState.Checked:
                    approved_ns.append(item.data(0, Qt.ItemDataRole.UserRole))
        
        if not approved_ns:
            self.reject()
            return

        # Phase 5: Mapping & Injection
        wc_mapping = {} # temp_id -> real_id
        
        def find_existing_value(name):
            for v in list(self.tax_manager.core_registry["values"].values()) + list(self.tax_manager.project_registry["values"].values()):
                if v.name.lower() == name.lower() or any(a.lower() == name.lower() for a in v.aliases):
                    return v
            return None

        for ns in approved_ns:
            for part in ns.structure:
                if part['type'] == 'wildcard':
                    temp_id = part['temp_id']
                    if temp_id in wc_mapping:
                        continue
                        
                    candidate_wc = self.candidate_wcs[temp_id]
                    real_wc_id = f"wc.proj.{candidate_wc.temp_id}"
                    wc_mapping[temp_id] = real_wc_id
                    
                    self.tax_manager.add_item("project", Wildcard(id=real_wc_id, name=candidate_wc.temp_id))
                    
                    for cv in candidate_wc.values:
                        existing = find_existing_value(cv.name)
                        if existing:
                            if existing.name.lower() != cv.name.lower() and cv.name not in existing.aliases:
                                existing.aliases.append(cv.name)
                        else:
                            val_id = f"val.proj.{cv.name.lower()}"
                            self.tax_manager.add_item("project", Value(id=val_id, name=cv.name, wildcard_id=real_wc_id))

        for ns in approved_ns:
            new_structure = []
            for part in ns.structure:
                if part['type'] == 'literal':
                    new_structure.append(NameSetComponent(type="literal", value=part['value']))
                else:
                    new_structure.append(NameSetComponent(type="wildcard", id=wc_mapping[part['temp_id']]))
            
            ns_id = f"ns.proj.{ns.temp_id}"
            self.tax_manager.add_item("project", NameSet(id=ns_id, name=f"Ingested {ns.temp_id}", nameset_structure=new_structure))

        self.tax_manager.save()
        self.accept()
