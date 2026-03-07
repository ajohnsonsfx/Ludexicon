"""
MainWindow — the primary application window for Ludexicon.

Houses the tabbed builder workspace, dockable browser panels,
and the application menu bar.
"""
import logging
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QInputDialog, QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from core.taxonomy_manager import TaxonomyManager
from ui.builder.builder_widget import BuilderWidget
from ui.browser.browser_dock import BrowserDock
from ui.ingest.ingest_dialog import TaxonomyIngestDialog

logger = logging.getLogger("ludexicon.ui")


class MainWindow(QMainWindow):
    def __init__(self, tax_manager: TaxonomyManager):
        super().__init__()
        self.tax_manager = tax_manager
        self.setWindowTitle("Ludexicon - Game Asset Taxonomy Engine")
        self.resize(1800, 900)

        self.browser_count = 1
        self.browsers = []
        self.builder_count = 0

        self.init_ui()

        # Connect to the event bus for automatic browser refresh
        self.tax_manager.events.data_changed.connect(self._on_data_changed)

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
        self.left_dock = BrowserDock("Browser", self.tax_manager, self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.left_dock)
        self.browsers.append(self.left_dock)

        # Ensure the browser dock is significantly wider by default
        self.resizeDocks([self.left_dock], [700], Qt.Orientation.Horizontal)

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

        new_builder_action = QAction("New &Builder", self)
        new_builder_action.setShortcut("Ctrl+T")
        new_builder_action.triggered.connect(self.spawn_new_builder)
        window_menu.addAction(new_builder_action)

        window_menu.addSeparator()

        new_browser_action = QAction("&New Browser", self)
        new_browser_action.triggered.connect(self.spawn_new_browser)
        window_menu.addAction(new_browser_action)
        window_menu.addSeparator()

        window_menu.addAction(self.left_dock.toggleViewAction())

        # Help Menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def open_ingest_tool(self):
        dialog = TaxonomyIngestDialog(self.tax_manager, self)
        dialog.exec()
        # Refresh all browsers after ingest dialog closes
        self._refresh_all_browsers()

    def spawn_new_browser(self):
        self.browser_count += 1
        new_dock = BrowserDock(f"Browser {self.browser_count}", self.tax_manager, self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, new_dock)
        if self.browsers:
            self.tabifyDockWidget(self.browsers[0], new_dock)
            new_dock.show()
        self.browsers.append(new_dock)

    def show_about(self):
        QMessageBox.about(self, "About Ludexicon",
            "<b>Ludexicon</b><br><br>"
            "Game Asset Taxonomy Engine.<br>"
            "A tool for standardizing naming conventions.<br><br>"
            "Created by: <a href='https://github.com/ajohnsonsfx'>Alex Johnson</a><br><br>"
            "Version 0.2")

    def _on_data_changed(self):
        """Called when the taxonomy data changes via the event bus."""
        self._refresh_all_browsers()

    def _refresh_all_browsers(self):
        """Refreshes all open browser docks with the latest taxonomy data."""
        for dock in self.browsers:
            dock.populate()
