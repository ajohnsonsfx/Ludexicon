import os
import re
import json
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from pathlib import Path


# ─── Data Classes ────────────────────────────────────────────────────

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


# ─── Heuristic Wildcard Namer ────────────────────────────────────────

class WildcardNamer:
    """Uses a heuristic dictionary to suggest meaningful names for wildcard slots."""

    def __init__(self, heuristics_path: str = None):
        if heuristics_path is None:
            heuristics_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "naming_heuristics.json")
        self.heuristics_path = heuristics_path
        self.categories: Dict[str, dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.heuristics_path):
            with open(self.heuristics_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.categories = data.get("categories", {})
            self.fallback_names = data.get("fallback_position_names", {})
        else:
            self.categories = {}
            self.fallback_names = {}

    def suggest_name(self, values: List[str], token_position: int, total_tokens: int, used_names: Set[str]) -> Tuple[str, float]:
        """
        Given a list of values at a wildcard slot, suggest a semantic name.
        Returns (suggested_name, confidence_score).
        """
        if not values:
            return self._fallback_name(token_position, total_tokens, used_names), 0.0

        # Normalize values for comparison
        normalized = {v.lower() for v in values}

        best_name = None
        best_score = 0.0

        for cat_name, cat_data in self.categories.items():
            examples_lower = {e.lower() for e in cat_data.get("examples", [])}
            if not examples_lower:
                continue

            # Calculate overlap: how many of our values match examples in this category
            overlap = normalized & examples_lower
            if not overlap:
                continue

            # Score = fraction of our values that match this category
            coverage = len(overlap) / len(normalized)
            # Bonus for position bias matching
            bias = cat_data.get("position_bias", "any")
            position_bonus = 0.0
            if bias == "early" and token_position <= total_tokens // 3:
                position_bonus = 0.1
            elif bias == "late" and token_position >= (total_tokens * 2) // 3:
                position_bonus = 0.1
            elif bias == "any":
                position_bonus = 0.05

            score = coverage + position_bonus

            if score > best_score:
                best_score = score
                best_name = cat_name

        # Require at least 15% coverage to use a category name
        if best_name and best_score >= 0.15:
            # Ensure uniqueness
            final_name = best_name
            counter = 2
            while final_name in used_names:
                final_name = f"{best_name}{counter}"
                counter += 1
            return final_name, min(best_score * 100, 100.0)

        return self._fallback_name(token_position, total_tokens, used_names), 0.0

    def _fallback_name(self, position: int, total: int, used_names: Set[str]) -> str:
        """Generate a positional fallback name like 'Slot_1'."""
        # Try positional fallback names first
        pos_key = str(position) if position < total // 2 else str(position - total)
        if pos_key in self.fallback_names:
            name = self.fallback_names[pos_key]
            if name not in used_names:
                return name

        # Generic numbered fallback
        base = f"Slot_{position + 1}"
        name = base
        counter = 2
        while name in used_names:
            name = f"{base}_{counter}"
            counter += 1
        return name


# ─── Ingest Engine ───────────────────────────────────────────────────

class TaxonomyIngestEngine:
    """
    Handles the full ingestion pipeline:
    - Phase 1: Parse and deduplicate filenames
    - Phase 2: Run inference to find patterns and name wildcards
    - Phase 3: Store results in a StagingSession for user review
    """
    def __init__(self, taxonomy_manager):
        self.tax_mgr = taxonomy_manager
        self.pending_assets: List[ParsedAsset] = []
        self.namer = WildcardNamer()

        self.ignore_variations = False
        self.ignore_versions = False
        self.ignore_dates = False

        # Pre-compute known name cache for dedup
        self._known_names: Dict[str, Tuple[str, str]] = self._build_known_names_cache()

    def clean_name(self, name: str) -> str:
        changed = True
        while changed:
            changed = False

            if self.ignore_dates:
                date_match = re.search(r'([_\-]?(?:\d{8}|\d{6}|\d{4}-\d{2}-\d{2}))$', name)
                if date_match and date_match.start() > 0:
                    name = name[:date_match.start()]
                    changed = True
                    continue

            if self.ignore_versions:
                ver_match = re.search(r'([_\-]?v\d+(?:\.\d+)?)$', name, re.IGNORECASE)
                if ver_match and ver_match.start() > 0:
                    name = name[:ver_match.start()]
                    changed = True
                    continue

            if self.ignore_variations:
                var_match = re.search(r'([_\-]?\d+)$', name)
                if var_match and var_match.start() > 0:
                    name = name[:var_match.start()]
                    changed = True
                    continue

        return name

    def _build_known_names_cache(self) -> Dict[str, Tuple[str, str]]:
        """
        Generates every possible valid name from the dictionaries.
        Returns a dict mapping name -> (nameset_id, nameset_name) for dedup info.
        """
        known = {}

        all_namesets = list(self.tax_mgr.core_registry["namesets"].values()) + \
                       list(self.tax_mgr.project_registry["namesets"].values())
        all_values = list(self.tax_mgr.core_registry["values"].values()) + \
                     list(self.tax_mgr.project_registry["values"].values())

        # Group values by wildcard_id
        val_map = {}
        for v in all_values:
            if v.wildcard_id not in val_map:
                val_map[v.wildcard_id] = []
            val_map[v.wildcard_id].append(v)

        for ns in all_namesets:
            try:
                names = self._generate_all_possible_names_with_aliases(ns, val_map)
                for name in names:
                    known[name] = (ns.id, ns.name)
            except Exception as e:
                print(f"Warning: Could not pre-cache NameSet {ns.id}: {e}")

        return known

    def _generate_all_possible_names_with_aliases(self, nameset, val_map) -> List[str]:
        import itertools

        def resolve_wc(wc_id: str) -> List[str]:
            results = []
            for val in val_map.get(wc_id, []):
                base_names = [val.name] + val.aliases
                if not val.triggers:
                    results.extend(base_names)
                else:
                    current_strings = base_names
                    for t in val.triggers:
                        sub_results = resolve_wc(t.id)
                        next_strings = []
                        for cs in current_strings:
                            for sub in sub_results:
                                if sub:
                                    next_strings.append(f"{cs}{t.delimiter}{sub}")
                                else:
                                    next_strings.append(cs)
                        current_strings = next_strings
                    results.extend(current_strings)
            return results if results else [""]

        component_results = []
        for comp in nameset.nameset_structure:
            if comp.type == "literal":
                component_results.append([comp.value])
            elif comp.type == "wildcard":
                res = resolve_wc(comp.id)
                component_results.append(res)

        combinations = list(itertools.product(*component_results))
        return ["".join(combo) for combo in combinations]

    def split_into_tokens(self, filename: str) -> List[str]:
        """
        Splits a string by underscores, hyphens, and camelCase transitions.
        Retains delimiters so we can build structural patterns from them.
        """
        raw_tokens = re.split(r'([_\-])', filename)

        final_tokens = []
        for token in raw_tokens:
            if not token:
                continue
            if token in ['_', '-']:
                final_tokens.append(token)
                continue
            # Split camelCase/PascalCase
            camel_split = re.sub(r'([a-z])([A-Z])', r'\1 \2', token).split(' ')
            for part in camel_split:
                if part:
                    final_tokens.append(part)

        return final_tokens

    def process_raw_names(self, source_name: str, names: List[str]):
        """Processes raw names, deduplicating known ones and tokenizing unknowns."""
        for name in names:
            name = name.strip()
            if not name:
                continue

            if '.' in name:
                name_no_ext, _ = os.path.splitext(name)
            else:
                name_no_ext = name

            name_no_ext = self.clean_name(name_no_ext)
            if not name_no_ext:
                continue

            match_info = self._known_names.get(name_no_ext)

            if match_info:
                ns_id, ns_name = match_info
                self.pending_assets.append(ParsedAsset(
                    original_path=f"[{source_name}] {name}",
                    filename=name_no_ext,
                    tokens=[],
                    skipped=True,
                    matched_nameset_id=ns_id,
                    skip_reason=f"Matched '{ns_name}' ({ns_id})",
                ))
            else:
                tokens = self.split_into_tokens(name_no_ext)
                self.pending_assets.append(ParsedAsset(
                    original_path=f"[{source_name}] {name}",
                    filename=name_no_ext,
                    tokens=tokens,
                    skipped=False,
                ))

    def get_unknown_assets(self) -> List[ParsedAsset]:
        return [a for a in self.pending_assets if not a.skipped]

    def get_dedup_matches(self) -> List[DedupMatch]:
        """Returns detailed info about all filenames that matched existing entries."""
        matches = []
        for a in self.pending_assets:
            if a.skipped and a.matched_nameset_id:
                match_info = self._known_names.get(a.filename)
                if match_info:
                    ns_id, ns_name = match_info
                    matches.append(DedupMatch(
                        filename=a.filename,
                        matched_nameset_id=ns_id,
                        matched_nameset_name=ns_name,
                    ))
        return matches

    def run_inference(self) -> StagingSession:
        """
        Full inference pipeline. Groups unknowns by token pattern,
        names wildcards heuristically, and returns a StagingSession.
        """
        unknowns = self.get_unknown_assets()

        # 1. Deduplicate unknown filenames (keep unique only)
        seen_filenames = set()
        unique_unknowns = []
        for a in unknowns:
            if a.filename not in seen_filenames:
                seen_filenames.add(a.filename)
                unique_unknowns.append(a)

        # 2. Group by token length
        length_groups: Dict[int, List[ParsedAsset]] = {}
        for a in unique_unknowns:
            length = len(a.tokens)
            if length not in length_groups:
                length_groups[length] = []
            length_groups[length].append(a)

        candidate_namesets = []
        candidate_wildcards = {}
        wc_counter = 1
        ns_counter = 1
        used_wc_names: Set[str] = set()

        # 3. Process each group
        for length, assets in sorted(length_groups.items()):
            if not assets:
                continue

            group_size = len(assets)

            # Analyze frequencies at each token index
            frequency_map: List[Dict[str, int]] = [{} for _ in range(length)]
            for a in assets:
                for i, token in enumerate(a.tokens):
                    frequency_map[i][token] = frequency_map[i].get(token, 0) + 1

            # Build structure and wildcards
            structure = []
            non_delimiter_index = 0  # Track position among meaningful (non-delimiter) slots
            total_non_delimiters = sum(
                1 for freq in frequency_map
                if not all(t in ['_', '-'] for t in freq.keys())
            )

            for i, freq in enumerate(frequency_map):
                unique_tokens = list(freq.keys())
                is_delimiter = all(t in ['_', '-'] for t in unique_tokens)

                if is_delimiter or (len(unique_tokens) == 1 and group_size > 1):
                    if is_delimiter:
                        literal_val = max(freq.items(), key=lambda x: x[1])[0]
                    else:
                        literal_val = unique_tokens[0]
                    structure.append({"type": "literal", "value": literal_val})
                else:
                    # It's a wildcard slot — name it heuristically
                    temp_id = f"wc_temp_{wc_counter}"
                    wc_counter += 1

                    # Get suggested name from heuristic engine
                    value_names = list(freq.keys())
                    suggested_name, name_confidence = self.namer.suggest_name(
                        value_names, non_delimiter_index, total_non_delimiters, used_wc_names
                    )
                    used_wc_names.add(suggested_name)

                    structure.append({"type": "wildcard", "temp_id": temp_id})

                    # Create CandidateValues
                    c_values = []
                    for val_name, count in freq.items():
                        val_conf = (count / group_size) * 100.0
                        c_values.append(CandidateValue(name=val_name, confidence=val_conf))

                    wc_conf = min(100.0, group_size * 5.0)
                    candidate_wildcards[temp_id] = CandidateWildcard(
                        temp_id=temp_id,
                        suggested_name=suggested_name,
                        values=c_values,
                        confidence=wc_conf,
                    )

                if not is_delimiter:
                    non_delimiter_index += 1

            # Build CandidateNameSet with a descriptive name
            temp_ns_id = f"ns_temp_{ns_counter}"
            ns_counter += 1
            ns_conf = min(100.0, group_size * 10.0)

            # Build suggested NameSet name from pattern
            ns_name_parts = []
            for part in structure:
                if part["type"] == "literal":
                    pass  # Skip delimiters in the display name
                elif part["type"] == "wildcard":
                    wc = candidate_wildcards[part["temp_id"]]
                    ns_name_parts.append(f"[{wc.suggested_name}]")
            suggested_ns_name = " ".join(ns_name_parts) if ns_name_parts else f"Pattern {ns_counter}"

            ns = CandidateNameSet(
                temp_id=temp_ns_id,
                suggested_name=suggested_ns_name,
                structure=structure,
                matched_assets=assets,
                confidence=ns_conf,
            )

            for a in assets:
                a.matched_nameset_id = temp_ns_id
                a.confidence = ns_conf

            candidate_namesets.append(ns)

        # Build session
        session = StagingSession(
            candidate_namesets=candidate_namesets,
            candidate_wildcards=candidate_wildcards,
            dedup_matches=self.get_dedup_matches(),
            total_input_count=len(self.pending_assets),
        )

        return session

    def save_session(self, session: StagingSession, path: str):
        """Save staging session to a JSON file for later resumption."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2)

    def load_session(self, path: str) -> StagingSession:
        """Load a previously saved staging session."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return StagingSession.from_dict(data)
