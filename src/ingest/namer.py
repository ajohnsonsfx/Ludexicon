"""
Heuristic-based wildcard naming engine.

Uses a JSON dictionary of known game-dev categories to suggest meaningful
names for wildcard slots during taxonomy ingestion.
"""
import json
import os
import logging
from typing import List, Dict, Tuple, Set

logger = logging.getLogger("ludexicon.ingest.namer")


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
            logger.warning("Heuristics file not found: %s", self.heuristics_path)

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
