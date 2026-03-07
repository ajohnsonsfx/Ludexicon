"""
TaxonomyManager — the central data engine for Ludexicon.

Handles loading, saving, querying, and name generation for the
core and project taxonomy registries.
"""
import json
import os
import shutil
import itertools
import logging
from typing import List, Dict, Optional, Union

from core.models import Value, Wildcard, NameSet, NameSetComponent, Trigger
from core.events import TaxonomyEvents

logger = logging.getLogger("ludexicon.core")


class TaxonomyManager:
    def __init__(self, core_path: str = None, project_path: str = None):
        if core_path is None or project_path is None:
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_dir = os.path.join(root_dir, "data")
            if core_path is None:
                core_path = os.path.join(data_dir, "dictionary_core.json")
            if project_path is None:
                project_path = os.path.join(data_dir, "dictionary_project.json")

        self.core_path = core_path
        self.project_path = project_path

        self.core_registry = {"wildcards": {}, "values": {}, "namesets": {}}
        self.project_registry = {"wildcards": {}, "values": {}, "namesets": {}}

        # Event bus — UI components can connect to these signals
        self.events = TaxonomyEvents()

        # Seed data folder from defaults/ if it's missing files
        self._seed_data_dir()

    # ─── Data Seeding ────────────────────────────────────────────────

    def _seed_data_dir(self):
        """Copies default JSON files into the data directory if they don't exist yet.
        This allows data/ to be .gitignored while still working out of the box."""
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        defaults_dir = os.path.join(root_dir, "defaults")
        if not os.path.isdir(defaults_dir):
            return
        data_dir = os.path.dirname(self.core_path)
        os.makedirs(data_dir, exist_ok=True)
        for filename in os.listdir(defaults_dir):
            dest = os.path.join(data_dir, filename)
            if not os.path.exists(dest):
                shutil.copy2(os.path.join(defaults_dir, filename), dest)
                logger.info("Seeded default file: %s", filename)

    # ─── Load / Save ─────────────────────────────────────────────────

    def load(self):
        if os.path.exists(self.core_path):
            with open(self.core_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._parse_data("core", data)

        if os.path.exists(self.project_path):
            with open(self.project_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._parse_data("project", data)

        logger.info("Loaded taxonomy: %d wildcards, %d values, %d namesets",
                     len(self.get_all_wildcards()),
                     len(self.get_all_values()),
                     len(self.get_all_namesets()))

    def _parse_data(self, source: str, data: dict):
        registry = self.core_registry if source == "core" else self.project_registry
        for key, value in data.items():
            if key.startswith("wc."):
                registry["wildcards"][key] = Wildcard.from_dict(key, value)
            elif key.startswith("val."):
                registry["values"][key] = Value.from_dict(key, value)
            elif key.startswith("ns."):
                registry["namesets"][key] = NameSet.from_dict(key, value)

    def save(self):
        core_out = {}
        for category in ["wildcards", "values", "namesets"]:
            for k, v in self.core_registry[category].items():
                core_out[k] = v.to_dict()

        project_out = {}
        for category in ["wildcards", "values", "namesets"]:
            for k, v in self.project_registry[category].items():
                project_out[k] = v.to_dict()

        # Save keeping deterministic format: 4-space indent, keys sorted alphabetically
        with open(self.core_path, 'w', encoding='utf-8') as f:
            json.dump(core_out, f, indent=4, sort_keys=True)

        with open(self.project_path, 'w', encoding='utf-8') as f:
            json.dump(project_out, f, indent=4, sort_keys=True)

        logger.info("Saved taxonomy files.")

    # ─── CRUD ────────────────────────────────────────────────────────

    def add_item(self, source: str, item: Union[Wildcard, Value, NameSet]):
        registry = self.core_registry if source == "core" else self.project_registry
        if isinstance(item, Wildcard):
            registry["wildcards"][item.id] = item
            self.events.wildcard_added.emit(item.id)
        elif isinstance(item, Value):
            registry["values"][item.id] = item
            self.events.value_added.emit(item.id)
        elif isinstance(item, NameSet):
            registry["namesets"][item.id] = item
            self.events.nameset_added.emit(item.id)
        self.events.data_changed.emit()

    # ─── Query API ───────────────────────────────────────────────────

    def get_value(self, id: str) -> Optional[Value]:
        return self.core_registry["values"].get(id) or self.project_registry["values"].get(id)

    def get_wildcard(self, id: str) -> Optional[Wildcard]:
        return self.core_registry["wildcards"].get(id) or self.project_registry["wildcards"].get(id)

    def get_nameset(self, id: str) -> Optional[NameSet]:
        return self.core_registry["namesets"].get(id) or self.project_registry["namesets"].get(id)

    def get_all_wildcards(self) -> List[Wildcard]:
        """Returns all wildcards across core and project registries."""
        return list(self.core_registry["wildcards"].values()) + list(self.project_registry["wildcards"].values())

    def get_all_values(self) -> List[Value]:
        """Returns all values across core and project registries."""
        return list(self.core_registry["values"].values()) + list(self.project_registry["values"].values())

    def get_all_namesets(self) -> List[NameSet]:
        """Returns all namesets across core and project registries."""
        return list(self.core_registry["namesets"].values()) + list(self.project_registry["namesets"].values())

    def get_values_for_wildcard(self, wildcard_id: str) -> List[Value]:
        """Returns all values that belong to a specific wildcard."""
        return [v for v in self.get_all_values() if v.wildcard_id == wildcard_id]

    # ─── Name Generation ─────────────────────────────────────────────

    def resolve_wildcard(self, wildcard_id: str, selections: Dict[str, List[Value]]) -> List[str]:
        """Recursively resolves a wildcard slot into its final list of strings, including triggered associations."""
        results = []
        selected_values = selections.get(wildcard_id, [])
        if not selected_values:
            return [""]

        for val in selected_values:
            base_str = val.name

            if not val.triggers:
                results.append(base_str)
            else:
                current_strings = [base_str]
                for trigger in val.triggers:
                    sub_results = self.resolve_wildcard(trigger.id, selections)
                    next_strings = []
                    for cs in current_strings:
                        for sub in sub_results:
                            if sub:
                                next_strings.append(f"{cs}{trigger.delimiter}{sub}")
                            else:
                                next_strings.append(cs)
                    current_strings = next_strings
                results.extend(current_strings)
        return results

    def generate_names(self, nameset_id: str, selections: Dict[str, List[Value]]) -> List[str]:
        """Generates all permutations of asset names based on a NameSet ID and user selections."""
        nameset = self.get_nameset(nameset_id)
        if not nameset:
            raise ValueError(f"NameSet '{nameset_id}' not found.")
        return self.generate_names_from_ns(nameset, selections)

    def generate_names_from_ns(self, nameset: NameSet, selections: Dict[str, List[Value]]) -> List[str]:
        """Generates all permutations of asset names from a NameSet object and user selections."""
        component_results = []

        for comp in nameset.nameset_structure:
            if comp.type == "literal":
                component_results.append([comp.value])
            elif comp.type == "wildcard":
                res = self.resolve_wildcard(comp.id, selections)
                component_results.append(res if res else [""])

        combinations = list(itertools.product(*component_results))
        return ["".join(combo) for combo in combinations]
