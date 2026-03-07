"""
IngestInputArea — drag-and-drop text area for file ingestion input.
"""
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import pyqtSignal


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
