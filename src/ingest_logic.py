import os
import re
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Set
from pathlib import Path

@dataclass
class ParsedAsset:
    original_path: str
    filename: str
    tokens: List[str]
    skipped: bool = False
    matched_nameset_id: Optional[str] = None
    confidence: float = 0.0

@dataclass
class CandidateValue:
    name: str
    confidence: float

@dataclass
class CandidateWildcard:
    temp_id: str
    values: List[CandidateValue]
    confidence: float

@dataclass
class CandidateNameSet:
    temp_id: str
    structure: List[Dict[str, str]] # e.g. [{"type": "wildcard", "temp_id": "wc_0"}, {"type": "literal", "value": "_"}]
    matched_assets: List[ParsedAsset]
    confidence: float

class TaxonomyIngestEngine:
    """
    Handles Phase 2 & 3 of the Taxonomy Ingest process.
    Reads files, tokenizes names, skips known assets, and calculates confidence.
    """
    def __init__(self, taxonomy_manager):
        self.tax_mgr = taxonomy_manager
        self.pending_assets: List[ParsedAsset] = []
        
        # Pre-compute all known valid string permutations to accelerate the 'skip' check
        self._known_names = self._build_known_names_cache()

    def _build_known_names_cache(self) -> Set[str]:
        """
        Generates every possible valid name from the core and project dictionaries,
        including all aliases, to perform O(1) lookups during ingestion.
        """
        known = set()
        
        # We need a custom generator that respects aliases
        # This is essentially what `generate_names` does, but we must inject aliases as valid substitute Values
        all_namesets = list(self.tax_mgr.core_registry["namesets"].values()) + list(self.tax_mgr.project_registry["namesets"].values())
        
        # For each nameset, resolve its wildcards, expanding both core 'name' and any 'aliases'
        # To do this correctly, we simulate a 'selection' dict containing ALL values
        all_values = list(self.tax_mgr.core_registry["values"].values()) + list(self.tax_mgr.project_registry["values"].values())
        
        # Group values by wildcard_id
        val_map = {}
        for v in all_values:
            if v.wildcard_id not in val_map:
                val_map[v.wildcard_id] = []
            val_map[v.wildcard_id].append(v)

        for ns in all_namesets:
            try:
                # We need a specialized resolution that accounts for aliases
                names = self._generate_all_possible_names_with_aliases(ns, val_map)
                known.update(names)
            except Exception as e:
                print(f"Warning: Could not pre-cache NameSet {ns.id}: {e}")
                
        return known

    def _generate_all_possible_names_with_aliases(self, nameset, val_map) -> List[str]:
        import itertools
        
        def resolve_wc(wc_id: str) -> List[str]:
            results = []
            for val in val_map.get(wc_id, []):
                # Standard name
                base_names = [val.name] + val.aliases
                
                # Triggers (simplification: if a value has triggers, we append them)
                # Note: Full trigger-with-alias expansion is complex, but for pre-filtering, 
                # we do our best effort.
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
        Splits a string by underscores, hyphens, and transitions from lowercase to Uppercase (camelCase).
        Retains the delimiters so we can build structural NameSets from them.
        """
        # 1. Split by delimiters, keeping the delimiters in the list
        raw_tokens = re.split(r'([_\-])', filename)
        
        final_tokens = []
        for token in raw_tokens:
            if not token:
                continue
            
            if token in ['_', '-']:
                final_tokens.append(token)
                continue
                
            # 2. Split camelCase/PascalCase (e.g., 'jumpAttack' -> 'jump', 'Attack')
            camel_split = re.sub(r'([a-z])([A-Z])', r'\1 \2', token).split(' ')
            
            for part in camel_split:
                if part:
                    final_tokens.append(part)
                    
        return final_tokens

    def process_raw_names(self, source_name: str, names: List[str]):
        """
        Processes a list of raw string names, checking for knowns and tokenizing unknowns.
        """
        for name in names:
            name = name.strip()
            if not name:
                continue
                
            # Strip extension if it looks like a filename (just in case they pasted filenames)
            if '.' in name:
                name_no_ext, _ = os.path.splitext(name)
            else:
                name_no_ext = name

            is_known = name_no_ext in self._known_names
            
            if is_known:
                self.pending_assets.append(ParsedAsset(
                    original_path=f"[{source_name}] {name}",
                    filename=name_no_ext,
                    tokens=[],
                    skipped=True
                ))
            else:
                tokens = self.split_into_tokens(name_no_ext)
                self.pending_assets.append(ParsedAsset(
                    original_path=f"[{source_name}] {name}",
                    filename=name_no_ext,
                    tokens=tokens,
                    skipped=False
                ))

    def process_directory(self, dir_path: str):
        """
        Scans a directory (non-recursive for now, top-level files only), 
        checks if they are known, and tokenizes unknown files.
        """
        self.pending_assets.clear()
        
        if not os.path.isdir(dir_path):
            return
            
        names_to_process = []
        for file in os.listdir(dir_path):
            full_path = os.path.join(dir_path, file)
            if os.path.isfile(full_path):
                names_to_process.append(file)
                
        self.process_raw_names(f"Dir: {os.path.basename(dir_path)}", names_to_process)

    def process_file(self, file_path: str):
        """
        Scans a text or CSV file for a list of names.
        """
        self.pending_assets.clear()
        
        if not os.path.isfile(file_path):
            return
            
        names_to_process = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Basic comma separation logic 
                # (If it's a CSV, we assume it's just a comma-separated list of names. 
                # For robust CSV, the user should provide names in the first column or just single names.)
                for part in line.split(','):
                    cleaned = part.strip()
                    if cleaned:
                        names_to_process.append(cleaned)
                        
        self.process_raw_names(f"File: {os.path.basename(file_path)}", names_to_process)

    def get_unknown_assets(self) -> List[ParsedAsset]:
        return [a for a in self.pending_assets if not a.skipped]

    def run_inference(self) -> Tuple[List[CandidateNameSet], Dict[str, CandidateWildcard]]:
        """
        Phase 3 Algorithm: Groups unknown assets by token count and structure.
        Generates Candidate NameSets, Wildcards, and Values with confidence scores.
        """
        unknowns = self.get_unknown_assets()
        
        # 1. Group by token length
        length_groups: Dict[int, List[ParsedAsset]] = {}
        for a in unknowns:
            length = len(a.tokens)
            if length not in length_groups:
                length_groups[length] = []
            length_groups[length].append(a)
            
        candidate_namesets = []
        candidate_wildcards = {}
        wc_counter = 1
        ns_counter = 1
        
        # 2. Process each group
        for length, assets in length_groups.items():
            if not assets:
                continue
                
            group_size = len(assets)
            
            # 3. Analyze frequencies at each index
            # frequency_map[index] = { "token1": count, "token2": count }
            frequency_map: List[Dict[str, int]] = [{} for _ in range(length)]
            for a in assets:
                for i, token in enumerate(a.tokens):
                    frequency_map[i][token] = frequency_map[i].get(token, 0) + 1
                    
            # 4. Build Structure and Wildcards
            structure = []
            for i, freq in enumerate(frequency_map):
                unique_tokens = list(freq.keys())
                
                # If ALL unique tokens in this slot are delimiters, treat it as a LITERAL.
                is_delimiter = all(t in ['_', '-'] for t in unique_tokens)
                
                # Strict literals: exactly 1 token across all files, OR it's a delimiter slot
                if len(unique_tokens) == 1 or is_delimiter:
                    # If it's a messy delimiter slot, pick the most common delimiter
                    if is_delimiter:
                        literal_val = max(freq.items(), key=lambda x: x[1])[0]
                    else:
                        literal_val = unique_tokens[0]
                        
                    structure.append({"type": "literal", "value": literal_val})
                else:
                    # It's a Wildcard! There is variance at this index.
                    temp_id = f"wc_temp_{wc_counter}"
                    wc_counter += 1
                    
                    structure.append({"type": "wildcard", "temp_id": temp_id})
                    
                    # Create CandidateValues for this Wildcard
                    c_values = []
                    for val_name, count in freq.items():
                        # Confidence for a single value: (how often it appears at this slot) / (total files in group)
                        val_conf = (count / group_size) * 100.0
                        c_values.append(CandidateValue(name=val_name, confidence=val_conf))
                        
                    # Confidence for the Wildcard itself:
                    # If it has many unique values, but they're well distributed, high confidence.
                    # If there's 50 files and 49 have "A" and 1 has "B" - could be a typo. Let's start with a base formula:
                    # Confidence based on group size (more files sharing same structure = higher confidence)
                    wc_conf = min(100.0, group_size * 5.0) # E.g. 20 files = 100% confidence it's a real wildcard slot
                    
                    candidate_wildcards[temp_id] = CandidateWildcard(
                        temp_id=temp_id, 
                        values=c_values,
                        confidence=wc_conf
                    )
            
            # 5. Build CandidateNameSet
            temp_ns_id = f"ns_temp_{ns_counter}"
            ns_counter += 1
            
            # NameSet confidence: scale by how many files follow this exact structure
            ns_conf = min(100.0, group_size * 10.0) # E.g. 10 files = 100% confidence
            
            ns = CandidateNameSet(
                temp_id=temp_ns_id,
                structure=structure,
                matched_assets=assets,
                confidence=ns_conf
            )
            
            # Associate the assets to this candidateset
            for a in assets:
                a.matched_nameset_id = temp_ns_id
                a.confidence = ns_conf
                
            candidate_namesets.append(ns)
            
        return candidate_namesets, candidate_wildcards
