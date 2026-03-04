import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Union
import itertools

@dataclass
class Trigger:
    id: str
    delimiter: str

@dataclass
class Value:
    id: str
    name: str
    wildcard_id: str
    status: str = "approved"
    tags: List[str] = field(default_factory=list)
    triggers: List[Trigger] = field(default_factory=list)

    @classmethod
    def from_dict(cls, id: str, data: dict):
        triggers = [Trigger(**t) for t in data.get("triggers", [])]
        return cls(
            id=id,
            name=data["name"],
            wildcard_id=data["wildcard_id"],
            status=data.get("status", "approved"),
            tags=data.get("tags", []),
            triggers=triggers
        )
    
    def to_dict(self):
        d = {
            "name": self.name,
            "status": self.status,
            "wildcard_id": self.wildcard_id
        }
        if self.tags:
            d["tags"] = self.tags
        if self.triggers:
            d["triggers"] = [{"id": t.id, "delimiter": t.delimiter} for t in self.triggers]
        return d

@dataclass
class Wildcard:
    id: str
    name: str

    @classmethod
    def from_dict(cls, id: str, data: dict):
        return cls(id=id, name=data.get("name", id))

    def to_dict(self):
        return {"name": self.name}

@dataclass
class NameSetComponent:
    type: str  # "wildcard" or "literal"
    id: Optional[str] = None
    value: Optional[str] = None

    def to_dict(self):
        if self.type == "wildcard":
            return {"type": "wildcard", "id": self.id}
        elif self.type == "literal":
            return {"type": "literal", "value": self.value}
        return {"type": self.type}

@dataclass
class NameSet:
    id: str
    name: str
    nameset_structure: List[NameSetComponent]

    @classmethod
    def from_dict(cls, id: str, data: dict):
        structure = [NameSetComponent(**c) for c in data.get("nameset_structure", [])]
        return cls(
            id=id,
            name=data["name"],
            nameset_structure=structure
        )

    def to_dict(self):
        return {
            "name": self.name,
            "nameset_structure": [comp.to_dict() for comp in self.nameset_structure]
        }

class TaxonomyManager:
    def __init__(self, core_path: str = None, project_path: str = None):
        if core_path is None or project_path is None:
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(root_dir, "data")
            if core_path is None:
                core_path = os.path.join(data_dir, "dictionary_core.json")
            if project_path is None:
                project_path = os.path.join(data_dir, "dictionary_project.json")
                
        self.core_path = core_path
        self.project_path = project_path
        
        self.core_registry = {"wildcards": {}, "values": {}, "namesets": {}}
        self.project_registry = {"wildcards": {}, "values": {}, "namesets": {}}
        
    def load(self):
        if os.path.exists(self.core_path):
            with open(self.core_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._parse_data("core", data)
                
        if os.path.exists(self.project_path):
            with open(self.project_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._parse_data("project", data)
                
    def _parse_data(self, source: str, data: dict):
        registry = self.core_registry if source == "core" else self.project_registry
        for key, value in data.items():
            if key.startswith("wc."):
                registry["wildcards"][key] = Wildcard.from_dict(key, value)
            elif key.startswith("val."):
                registry["values"][key] = Value.from_dict(key, value)
            elif key.startswith("ns."):
                registry["namesets"][key] = NameSet.from_dict(key, value)
                
    def add_item(self, source: str, item: Union[Wildcard, Value, NameSet]):
        registry = self.core_registry if source == "core" else self.project_registry
        if isinstance(item, Wildcard):
            registry["wildcards"][item.id] = item
        elif isinstance(item, Value):
            registry["values"][item.id] = item
        elif isinstance(item, NameSet):
            registry["namesets"][item.id] = item

    def get_value(self, id: str) -> Optional[Value]:
        return self.core_registry["values"].get(id) or self.project_registry["values"].get(id)
        
    def get_wildcard(self, id: str) -> Optional[Wildcard]:
        return self.core_registry["wildcards"].get(id) or self.project_registry["wildcards"].get(id)
        
    def get_nameset(self, id: str) -> Optional[NameSet]:
        return self.core_registry["namesets"].get(id) or self.project_registry["namesets"].get(id)

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
        """Generates all permutations of asset names based on a NameSet and user selections."""
        nameset = self.get_nameset(nameset_id)
        if not nameset:
            raise ValueError(f"NameSet '{nameset_id}' not found.")
            
        component_results = []
        
        for comp in nameset.nameset_structure:
            if comp.type == "literal":
                component_results.append([comp.value])
            elif comp.type == "wildcard":
                res = self.resolve_wildcard(comp.id, selections)
                component_results.append(res if res else [""])
                
        combinations = list(itertools.product(*component_results))
        return ["".join(combo) for combo in combinations]
