"""
Core data models for the Ludexicon taxonomy system.
"""
from dataclasses import dataclass, field
from typing import List, Optional


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
    aliases: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, id: str, data: dict):
        triggers = [Trigger(**t) for t in data.get("triggers", [])]
        return cls(
            id=id,
            name=data["name"],
            wildcard_id=data["wildcard_id"],
            status=data.get("status", "approved"),
            tags=data.get("tags", []),
            triggers=triggers,
            aliases=data.get("aliases", [])
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
        if self.aliases:
            d["aliases"] = self.aliases
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
