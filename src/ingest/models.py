"""
Data models for the taxonomy ingestion pipeline.
"""
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class ParsedAsset:
    original_path: str
    filename: str
    tokens: List[str]
    skipped: bool = False
    matched_nameset_id: Optional[str] = None
    skip_reason: Optional[str] = None
    confidence: float = 0.0


@dataclass
class CandidateValue:
    name: str
    confidence: float


@dataclass
class CandidateWildcard:
    temp_id: str
    suggested_name: str
    values: List[CandidateValue]
    confidence: float


@dataclass
class CandidateNameSet:
    temp_id: str
    suggested_name: str
    structure: List[Dict[str, str]]
    matched_assets: List[ParsedAsset]
    confidence: float
    category: Optional[str] = None  # UI-only category assignment
    staged: bool = False
    approved: bool = False


@dataclass
class DedupMatch:
    """Info about a filename that matched an existing NameSet."""
    filename: str
    matched_nameset_id: str
    matched_nameset_name: str


@dataclass
class StagingSession:
    """Intermediate representation that holds all work-in-progress before commit."""
    session_id: str = ""
    candidate_namesets: List[CandidateNameSet] = field(default_factory=list)
    candidate_wildcards: Dict[str, CandidateWildcard] = field(default_factory=dict)
    dedup_matches: List[DedupMatch] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    total_input_count: int = 0

    def __post_init__(self):
        if not self.session_id:
            self.session_id = str(uuid.uuid4())[:8]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "categories": self.categories,
            "total_input_count": self.total_input_count,
            "candidate_namesets": [
                {
                    "temp_id": ns.temp_id,
                    "suggested_name": ns.suggested_name,
                    "structure": ns.structure,
                    "matched_assets": [
                        {"filename": a.filename, "original_path": a.original_path}
                        for a in ns.matched_assets
                    ],
                    "confidence": ns.confidence,
                    "category": ns.category,
                    "staged": ns.staged,
                    "approved": ns.approved,
                }
                for ns in self.candidate_namesets
            ],
            "candidate_wildcards": {
                wc_id: {
                    "temp_id": wc.temp_id,
                    "suggested_name": wc.suggested_name,
                    "values": [{"name": v.name, "confidence": v.confidence} for v in wc.values],
                    "confidence": wc.confidence,
                }
                for wc_id, wc in self.candidate_wildcards.items()
            },
            "dedup_matches": [
                {"filename": m.filename, "matched_nameset_id": m.matched_nameset_id, "matched_nameset_name": m.matched_nameset_name}
                for m in self.dedup_matches
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StagingSession":
        session = cls(session_id=data.get("session_id", ""))
        session.categories = data.get("categories", [])
        session.total_input_count = data.get("total_input_count", 0)

        # Rebuild candidate wildcards first (needed for reference)
        for wc_id, wc_data in data.get("candidate_wildcards", {}).items():
            session.candidate_wildcards[wc_id] = CandidateWildcard(
                temp_id=wc_data["temp_id"],
                suggested_name=wc_data["suggested_name"],
                values=[CandidateValue(name=v["name"], confidence=v["confidence"]) for v in wc_data["values"]],
                confidence=wc_data["confidence"],
            )

        # Rebuild candidate namesets
        for ns_data in data.get("candidate_namesets", []):
            assets = [
                ParsedAsset(original_path=a.get("original_path", ""), filename=a["filename"], tokens=[])
                for a in ns_data.get("matched_assets", [])
            ]
            session.candidate_namesets.append(CandidateNameSet(
                temp_id=ns_data["temp_id"],
                suggested_name=ns_data["suggested_name"],
                structure=ns_data["structure"],
                matched_assets=assets,
                confidence=ns_data["confidence"],
                category=ns_data.get("category"),
                staged=ns_data.get("staged", False),
                approved=ns_data.get("approved", False),
            ))

        session.dedup_matches = [
            DedupMatch(filename=m["filename"], matched_nameset_id=m["matched_nameset_id"], matched_nameset_name=m["matched_nameset_name"])
            for m in data.get("dedup_matches", [])
        ]
        return session
