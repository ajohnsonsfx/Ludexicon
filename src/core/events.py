"""
Lightweight signal bus for taxonomy data change notifications.
"""
from PyQt6.QtCore import QObject, pyqtSignal


class TaxonomyEvents(QObject):
    """Emitted by TaxonomyManager when data changes occur."""
    data_changed = pyqtSignal()          # general refresh signal
    wildcard_added = pyqtSignal(str)     # wildcard_id
    value_added = pyqtSignal(str)        # value_id
    nameset_added = pyqtSignal(str)      # nameset_id
    item_deleted = pyqtSignal(str)       # item_id
