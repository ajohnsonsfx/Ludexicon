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
class Element:
    id: str
    name: str
    wildcard_id: str
    status: str = "approved"
    triggers: List[Trigger] = field(default_factory=list)

    @classmethod
    def from_dict(cls, id: str, data: dict):
        triggers = [Trigger(**t) for t in data.get("triggers", [])]
        return cls(
            id=id,
            name=data["name"],
            wildcard_id=data["wildcard_id"],
            status=data.get("status", "approved"),
            triggers=triggers
        )
    
    def to_dict(self):
        d = {
            "name": self.name,
            "status": self.status,
            "wildcard_id": self.wildcard_id
        }
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
class PatternComponent:
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
class Pattern:
    id: str
    name: str
    filename_structure: List[PatternComponent]

    @classmethod
    def from_dict(cls, id: str, data: dict):
        structure = [PatternComponent(**c) for c in data.get("filename_structure", [])]
        return cls(
            id=id,
            name=data["name"],
            filename_structure=structure
        )

    def to_dict(self):
        return {
            "name": self.name,
            "filename_structure": [comp.to_dict() for comp in self.filename_structure]
        }

class TaxonomyManager:
    def __init__(self, core_path: str = "data/dictionary_core.json", project_path: str = "data/dictionary_project.json"):
        self.core_path = core_path
        self.project_path = project_path
        
        self.core_registry = {"wildcards": {}, "elements": {}, "patterns": {}}
        self.project_registry = {"wildcards": {}, "elements": {}, "patterns": {}}
        
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
            elif key.startswith("el."):
                registry["elements"][key] = Element.from_dict(key, value)
            elif key.startswith("pat."):
                registry["patterns"][key] = Pattern.from_dict(key, value)
                
    def add_item(self, source: str, item: Union[Wildcard, Element, Pattern]):
        registry = self.core_registry if source == "core" else self.project_registry
        if isinstance(item, Wildcard):
            registry["wildcards"][item.id] = item
        elif isinstance(item, Element):
            registry["elements"][item.id] = item
        elif isinstance(item, Pattern):
            registry["patterns"][item.id] = item

    def get_element(self, id: str) -> Optional[Element]:
        return self.core_registry["elements"].get(id) or self.project_registry["elements"].get(id)
        
    def get_wildcard(self, id: str) -> Optional[Wildcard]:
        return self.core_registry["wildcards"].get(id) or self.project_registry["wildcards"].get(id)
        
    def get_pattern(self, id: str) -> Optional[Pattern]:
        return self.core_registry["patterns"].get(id) or self.project_registry["patterns"].get(id)

    def save(self):
        core_out = {}
        for category in ["wildcards", "elements", "patterns"]:
            for k, v in self.core_registry[category].items():
                core_out[k] = v.to_dict()
                
        project_out = {}
        for category in ["wildcards", "elements", "patterns"]:
            for k, v in self.project_registry[category].items():
                project_out[k] = v.to_dict()
                
        # Save keeping deterministic format: 4-space indent, keys sorted alphabetically
        with open(self.core_path, 'w', encoding='utf-8') as f:
            json.dump(core_out, f, indent=4, sort_keys=True)
            
        with open(self.project_path, 'w', encoding='utf-8') as f:
            json.dump(project_out, f, indent=4, sort_keys=True)

    def resolve_wildcard(self, wildcard_id: str, selections: Dict[str, List[Element]]) -> List[str]:
        """Recursively resolves a wildcard slot into its final list of strings, including triggered associations."""
        results = []
        selected_elements = selections.get(wildcard_id, [])
        if not selected_elements:
            return [""]
            
        for element in selected_elements:
            base_str = element.name
            
            if not element.triggers:
                results.append(base_str)
            else:
                current_strings = [base_str]
                for trigger in element.triggers:
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

    def generate_names(self, pattern_id: str, selections: Dict[str, List[Element]]) -> List[str]:
        """Generates all permutations of asset names based on a pattern and user selections."""
        pattern = self.get_pattern(pattern_id)
        if not pattern:
            raise ValueError(f"Pattern '{pattern_id}' not found.")
            
        component_results = []
        
        for comp in pattern.filename_structure:
            if comp.type == "literal":
                component_results.append([comp.value])
            elif comp.type == "wildcard":
                res = self.resolve_wildcard(comp.id, selections)
                component_results.append(res if res else [""])
                
        combinations = list(itertools.product(*component_results))
        return ["".join(combo) for combo in combinations]
