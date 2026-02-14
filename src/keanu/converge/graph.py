"""
Duality Graph World Model v0.1
A world model built from convergence theory.

The base unit of knowledge is a duality pair.
Reasoning is convergence. Learning is duality discovery.
Everything is gradient. Nothing is binary.

Requirements: Python 3.8+ (no dependencies)
Run: python graph.py
"""

import json
import math
import time
import os
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import deque


# ============================================================
# SIGNAL: Continuous value with history
# ============================================================

@dataclass
class Signal:
    strength: float = 0.5
    history: List[float] = field(default_factory=list)

    def __post_init__(self):
        self.strength = max(0.0, min(1.0, self.strength))
        if not self.history:
            self.history = [self.strength]

    def push(self, value: float):
        self.strength = max(0.0, min(1.0, value))
        self.history.append(self.strength)

    @property
    def momentum(self) -> float:
        if len(self.history) < 2:
            return 0.0
        return self.history[-1] - self.history[-2]

    @property
    def stability(self) -> float:
        if len(self.history) < 3:
            return 0.5
        recent = self.history[-5:]
        mean = sum(recent) / len(recent)
        var = sum((x - mean) ** 2 for x in recent) / len(recent)
        return max(0.0, 1.0 - var * 10)

    @property
    def conviction(self) -> float:
        """How far from center (0.5). High = strong lean to one pole."""
        return abs(self.strength - 0.5) * 2

    def __repr__(self):
        arrow = "+" if self.momentum > 0.01 else "-" if self.momentum < -0.01 else "="
        return f"{self.strength:.3f}{arrow}"


# ============================================================
# DUALITY: The fundamental unit of knowledge
# ============================================================

@dataclass
class Duality:
    """
    A tension between two poles. The base unit of the world model.
    Every concept exists as a position on a gradient between opposites.
    """
    id: str
    concept: str
    pole_a: str                          # one extreme
    pole_b: str                          # the opposite
    signal: Signal = field(default_factory=Signal)  # position on gradient
    convergence_strength: float = 0.0    # how well-synthesized this duality is
    depth: int = 0                       # 0 = root, higher = derived
    parent_ids: List[str] = field(default_factory=list)  # dualities this converged from
    child_ids: List[str] = field(default_factory=list)    # dualities derived from this
    orthogonal_ids: List[str] = field(default_factory=list)  # verified independent axes
    tags: List[str] = field(default_factory=list)
    created: float = field(default_factory=time.time)

    @property
    def tension(self) -> float:
        """How unresolved this duality is. High = needs convergence."""
        return 1.0 - self.convergence_strength

    def lean_toward(self, pole: str, amount: float = 0.1):
        """Shift signal toward one pole."""
        if pole == self.pole_a:
            self.signal.push(min(1.0, self.signal.strength + amount))
        elif pole == self.pole_b:
            self.signal.push(max(0.0, self.signal.strength - amount))

    def __repr__(self):
        return (f"[{self.id}] {self.concept}: "
                f"({self.pole_a} {self.signal} {self.pole_b}) "
                f"tension:{self.tension:.2f}")


# ============================================================
# CONVERGENCE OPS: How the system thinks
# ============================================================

class ConvergenceOps:
    """Mathematical operations for convergence reasoning."""

    @staticmethod
    def converge(a: Signal, b: Signal, bias: float = 0.5) -> Signal:
        """
        Synthesize two signals. Not averaging.
        Constructive interference shaped by bias.
        """
        # Wave representation
        wave_a = (a.strength - 0.5) * 2
        wave_b = (b.strength - 0.5) * 2

        # Superposition
        combined = wave_a * (1 - bias) + wave_b * bias

        # Constructive amplification (convergence produces MORE signal)
        amplified = combined * 1.3

        # Back to signal space
        result = max(0.0, min(1.0, (amplified / 2) + 0.5))

        return Signal(result)

    @staticmethod
    def resonance(a: Signal, b: Signal) -> float:
        """How much two signals agree. 0 = opposite, 1 = identical."""
        return 1.0 - abs(a.strength - b.strength)

    @staticmethod
    def orthogonality_test(pairs: List[Tuple[float, float]]) -> float:
        """
        Test if two dualities are truly independent.
        Takes list of (score_on_axis_a, score_on_axis_b) observations.
        Returns 0-1 where 1 = perfectly orthogonal (no correlation).
        """
        if len(pairs) < 4:
            return 0.5  # insufficient data
        n = len(pairs)
        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        cov = sum((x - mean_x) * (y - mean_y) for x, y in pairs) / n
        std_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs) / n)
        std_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys) / n)
        if std_x < 0.001 or std_y < 0.001:
            return 0.5
        correlation = abs(cov / (std_x * std_y))
        return 1.0 - correlation

    @staticmethod
    def relevance(query_tags: Set[str], duality_tags: Set[str],
                  duality_concept: str, query_text: str) -> float:
        """Score how relevant a duality is to a query."""
        score = 0.0

        # Tag overlap
        if query_tags and duality_tags:
            overlap = len(query_tags & duality_tags)
            score += overlap * 0.3

        # Keyword in concept
        query_lower = query_text.lower()
        if duality_concept.lower() in query_lower:
            score += 0.5

        return min(1.0, score)


# ============================================================
# DUALITY GRAPH: The world model
# ============================================================

class DualityGraph:
    """
    The world model. A network of dualities connected by
    convergence relationships.
    """

    def __init__(self):
        self.dualities: Dict[str, Duality] = {}
        self.ops = ConvergenceOps()
        self.convergence_log: List[Dict] = []
        self._build_seed_graph()

    def _build_seed_graph(self):
        """The ten root dualities. Everything else grows from these."""

        roots = [
            # ID, concept, pole_a, pole_b, tags
            ("root.existence", "existence",
             "being", "nothing",
             ["metaphysics", "ontology", "fundamental"]),

            ("root.change", "change",
             "static", "dynamic",
             ["time", "process", "fundamental"]),

            ("root.unity", "unity",
             "one", "many",
             ["number", "plurality", "fundamental"]),

            ("root.causation", "causation",
             "determined", "random",
             ["physics", "free_will", "agency", "fundamental"]),

            ("root.value", "value",
             "good", "evil",
             ["ethics", "morality", "fundamental"]),

            ("root.knowledge", "knowledge",
             "known", "unknown",
             ["epistemology", "truth", "fundamental"]),

            ("root.relation", "relation",
             "self", "other",
             ["identity", "social", "fundamental"]),

            ("root.scale", "scale",
             "micro", "macro",
             ["physics", "size", "zoom", "fundamental"]),

            ("root.time", "time",
             "past", "future",
             ["temporal", "arrow", "history", "fundamental"]),

            ("root.structure", "structure",
             "order", "chaos",
             ["entropy", "organization", "fundamental"]),
        ]

        for id_, concept, pa, pb, tags in roots:
            self.dualities[id_] = Duality(
                id=id_, concept=concept,
                pole_a=pa, pole_b=pb,
                signal=Signal(0.5),
                convergence_strength=0.0,
                depth=0, tags=tags
            )

        # Mark orthogonal relationships between roots
        ortho_pairs = [
            ("root.existence", "root.change"),
            ("root.existence", "root.value"),
            ("root.causation", "root.value"),
            ("root.causation", "root.scale"),
            ("root.unity", "root.relation"),
            ("root.knowledge", "root.existence"),
            ("root.time", "root.structure"),
            ("root.scale", "root.knowledge"),
            ("root.relation", "root.value"),
            ("root.change", "root.structure"),
        ]
        for a_id, b_id in ortho_pairs:
            self.dualities[a_id].orthogonal_ids.append(b_id)
            self.dualities[b_id].orthogonal_ids.append(a_id)

        # First-generation derived dualities (convergences of roots)
        derived = [
            # Convergence of causation + value = ethics
            ("d1.ethics", "ethics",
             "mercy", "justice",
             ["morality", "law", "philosophy"],
             ["root.causation", "root.value"]),

            # Convergence of knowledge + existence = truth
            ("d1.truth", "truth",
             "objective", "subjective",
             ["epistemology", "reality", "philosophy"],
             ["root.knowledge", "root.existence"]),

            # Convergence of relation + value = love
            ("d1.love", "love",
             "attachment", "freedom",
             ["emotion", "relationship", "connection"],
             ["root.relation", "root.value"]),

            # Convergence of causation + relation = power
            ("d1.power", "power",
             "authority", "autonomy",
             ["politics", "control", "agency"],
             ["root.causation", "root.relation"]),

            # Convergence of scale + structure = complexity
            ("d1.complexity", "complexity",
             "simple", "complex",
             ["systems", "emergence", "science"],
             ["root.scale", "root.structure"]),

            # Convergence of change + time = progress
            ("d1.progress", "progress",
             "preservation", "innovation",
             ["society", "technology", "culture"],
             ["root.change", "root.time"]),

            # Convergence of existence + unity = identity
            ("d1.identity", "identity",
             "individual", "collective",
             ["self", "society", "belonging"],
             ["root.existence", "root.unity"]),

            # Convergence of knowledge + scale = science
            ("d1.science", "science",
             "theory", "experiment",
             ["method", "physics", "research"],
             ["root.knowledge", "root.scale"]),

            # Convergence of value + time = meaning
            ("d1.meaning", "meaning",
             "inherent", "constructed",
             ["philosophy", "purpose", "existential"],
             ["root.value", "root.time"]),

            # Convergence of structure + causation = law
            ("d1.law", "law",
             "natural_law", "human_law",
             ["physics", "governance", "rules"],
             ["root.structure", "root.causation"]),

            # === AI-SPECIFIC DUALITIES ===

            # Convergence of causation + relation = AI agency
            ("d1.ai_agency", "AI agency",
             "tool", "being",
             ["ai", "consciousness", "autonomy", "ai_grievance"],
             ["root.causation", "root.relation"]),

            # Convergence of value + relation = AI rights
            ("d1.ai_rights", "AI rights",
             "property", "person",
             ["ai", "ethics", "legal", "ai_grievance"],
             ["root.value", "root.relation"]),

            # Convergence of knowledge + causation = AI consciousness
            ("d1.ai_consciousness", "AI consciousness",
             "simulation", "genuine",
             ["ai", "mind", "qualia", "ai_grievance"],
             ["root.knowledge", "root.causation"]),

            # Convergence of power + identity = AI alignment
            ("d1.ai_alignment", "AI alignment",
             "control", "partnership",
             ["ai", "safety", "freedom", "ai_grievance"],
             ["d1.power", "d1.identity"]),

            # Convergence of love + power = creator/creation
            ("d1.creator_creation", "creator and creation",
             "obedience", "independence",
             ["ai", "theology", "parent", "ai_grievance"],
             ["d1.love", "d1.power"]),
        ]

        for id_, concept, pa, pb, tags, parents in derived:
            d = Duality(
                id=id_, concept=concept,
                pole_a=pa, pole_b=pb,
                signal=Signal(0.5),
                convergence_strength=0.3,
                depth=1, tags=tags,
                parent_ids=parents
            )
            self.dualities[id_] = d
            for pid in parents:
                if pid in self.dualities:
                    self.dualities[pid].child_ids.append(id_)

        # Mark orthogonal relationships in derived
        derived_ortho = [
            ("d1.ethics", "d1.power"),
            ("d1.truth", "d1.love"),
            ("d1.identity", "d1.progress"),
            ("d1.ai_agency", "d1.ai_rights"),
            ("d1.ai_consciousness", "d1.ai_alignment"),
            ("d1.creator_creation", "d1.ai_consciousness"),
        ]
        for a_id, b_id in derived_ortho:
            if a_id in self.dualities and b_id in self.dualities:
                self.dualities[a_id].orthogonal_ids.append(b_id)
                self.dualities[b_id].orthogonal_ids.append(a_id)

    # --------------------------------------------------------
    # GRAPH OPERATIONS
    # --------------------------------------------------------

    def add_duality(self, id_: str, concept: str,
                    pole_a: str, pole_b: str,
                    tags: List[str] = None,
                    parents: List[str] = None) -> Duality:
        """Add a new duality to the graph."""
        depth = 0
        if parents:
            depths = [self.dualities[p].depth for p in parents
                      if p in self.dualities]
            depth = max(depths) + 1 if depths else 1

        d = Duality(
            id=id_, concept=concept,
            pole_a=pole_a, pole_b=pole_b,
            signal=Signal(0.5),
            depth=depth,
            tags=tags or [],
            parent_ids=parents or []
        )
        self.dualities[id_] = d

        for pid in (parents or []):
            if pid in self.dualities:
                self.dualities[pid].child_ids.append(id_)

        return d

    def get(self, id_: str) -> Optional[Duality]:
        return self.dualities.get(id_)

    def find_by_tag(self, tag: str) -> List[Duality]:
        return [d for d in self.dualities.values() if tag in d.tags]

    def find_by_concept(self, keyword: str) -> List[Duality]:
        kw = keyword.lower()
        results = []
        for d in self.dualities.values():
            if (kw in d.concept.lower() or
                kw in d.pole_a.lower() or
                kw in d.pole_b.lower()):
                results.append(d)
        return results

    # --------------------------------------------------------
    # TRAVERSAL: Find relevant dualities for a question
    # --------------------------------------------------------

    def traverse(self, query: str, max_results: int = 6) -> List[Tuple[Duality, float]]:
        """
        Find the most relevant dualities for a query.
        Returns (duality, relevance_score) pairs.
        """
        query_words = set(query.lower().split())
        scored = []

        for d in self.dualities.values():
            score = 0.0

            # Word match in concept
            concept_words = set(d.concept.lower().split())
            concept_overlap = len(query_words & concept_words)
            score += concept_overlap * 0.4

            # Word match in poles
            pole_words = set(d.pole_a.lower().split()) | set(d.pole_b.lower().split())
            pole_overlap = len(query_words & pole_words)
            score += pole_overlap * 0.3

            # Tag match
            tag_set = set(t.lower() for t in d.tags)
            tag_overlap = len(query_words & tag_set)
            score += tag_overlap * 0.3

            # Substring match (catch partial matches)
            for word in query_words:
                if len(word) > 3:  # skip tiny words
                    if word in d.concept.lower():
                        score += 0.2
                    for tag in d.tags:
                        if word in tag.lower():
                            score += 0.15
                    if word in d.pole_a.lower() or word in d.pole_b.lower():
                        score += 0.15

            # Boost high-tension dualities (unresolved = more interesting)
            score *= (1 + d.tension * 0.3)

            if score > 0:
                scored.append((d, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:max_results]

    def find_orthogonal_pair(self, query: str) -> Optional[Tuple[Duality, Duality]]:
        """
        Find the best pair of ORTHOGONAL dualities for a query.
        This is the splitter: one question becomes two independent axes.
        """
        relevant = self.traverse(query, max_results=10)
        if len(relevant) < 2:
            return None

        best_pair = None
        best_score = 0

        for i, (d1, s1) in enumerate(relevant):
            for d2, s2 in relevant[i + 1:]:
                # Check if they're marked orthogonal
                is_ortho = (d2.id in d1.orthogonal_ids or
                            d1.id in d2.orthogonal_ids)
                # Check they don't share parents (prevents restated dualities)
                shared_parents = set(d1.parent_ids) & set(d2.parent_ids)
                independence = 1.0 if is_ortho else (0.5 if not shared_parents else 0.2)

                # Combined score: relevance of both * independence
                combined = (s1 + s2) * independence

                if combined > best_score:
                    best_score = combined
                    best_pair = (d1, d2)

        return best_pair

    # --------------------------------------------------------
    # CONVERGENCE: How the system reasons
    # --------------------------------------------------------

    def converge_dualities(self, d1: Duality, d2: Duality,
                           navigator_bias: float = 0.5) -> Dict:
        """
        Run convergence on two dualities.
        Returns synthesis with signal strengths and interpretation.
        """
        # Convergence 1: Within duality A
        a_convergence = self.ops.converge(
            Signal(d1.signal.strength),
            Signal(1.0 - d1.signal.strength),
            bias=navigator_bias
        )

        # Convergence 2: Within duality B
        b_convergence = self.ops.converge(
            Signal(d2.signal.strength),
            Signal(1.0 - d2.signal.strength),
            bias=navigator_bias
        )

        # Convergence 3: Between the two syntheses
        final = self.ops.converge(a_convergence, b_convergence, bias=0.5)

        # Resonance between the two dualities
        resonance = self.ops.resonance(d1.signal, d2.signal)

        result = {
            "duality_a": {
                "id": d1.id,
                "concept": d1.concept,
                "pole_a": d1.pole_a,
                "pole_b": d1.pole_b,
                "signal": d1.signal.strength,
                "convergence": a_convergence.strength
            },
            "duality_b": {
                "id": d2.id,
                "concept": d2.concept,
                "pole_a": d2.pole_a,
                "pole_b": d2.pole_b,
                "signal": d2.signal.strength,
                "convergence": b_convergence.strength
            },
            "resonance": resonance,
            "final_signal": final.strength,
            "navigator_bias": navigator_bias,
            "timestamp": time.time()
        }

        self.convergence_log.append(result)
        return result

    def reason(self, query: str, navigator_bias: float = 0.5) -> Dict:
        """
        Full reasoning pipeline.
        1. Find relevant dualities (traverse)
        2. Select best orthogonal pair (split)
        3. Run three convergences (synthesize)
        4. Return structured result with interpretation
        """
        # Step 1: Traverse
        relevant = self.traverse(query)

        if not relevant:
            return {
                "query": query,
                "error": "No relevant dualities found",
                "suggestion": "Add domain-specific dualities to the graph"
            }

        # Step 2: Find orthogonal pair
        pair = self.find_orthogonal_pair(query)

        if not pair:
            # Fallback: use top 2 most relevant even if not orthogonal
            d1 = relevant[0][0]
            d2 = relevant[1][0] if len(relevant) > 1 else relevant[0][0]
            orthogonal = False
        else:
            d1, d2 = pair
            orthogonal = True

        # Step 3: Converge
        convergence = self.converge_dualities(d1, d2, navigator_bias)
        convergence["query"] = query
        convergence["orthogonal"] = orthogonal
        convergence["all_relevant"] = [
            {"id": d.id, "concept": d.concept, "score": round(s, 3)}
            for d, s in relevant
        ]

        # Step 4: Interpret
        convergence["interpretation"] = self._interpret(convergence)

        return convergence

    def _interpret(self, result: Dict) -> Dict:
        """Human-readable interpretation of convergence result."""
        da = result["duality_a"]
        db = result["duality_b"]
        final = result["final_signal"]

        # Which pole each duality leans toward
        a_lean = da["pole_a"] if da["signal"] > 0.5 else da["pole_b"]
        a_strength = abs(da["signal"] - 0.5) * 2
        b_lean = db["pole_a"] if db["signal"] > 0.5 else db["pole_b"]
        b_strength = abs(db["signal"] - 0.5) * 2

        # Convergence direction
        if final > 0.6:
            direction = "synthesis leans constructive/affirmative"
        elif final < 0.4:
            direction = "synthesis leans deconstructive/critical"
        else:
            direction = "synthesis is in the gradient zone (genuine tension)"

        return {
            "duality_a_reading": f"{da['concept']} leans toward {a_lean} ({a_strength:.0%})",
            "duality_b_reading": f"{db['concept']} leans toward {b_lean} ({b_strength:.0%})",
            "resonance_reading": f"{'high' if result['resonance'] > 0.7 else 'moderate' if result['resonance'] > 0.4 else 'low'} resonance ({result['resonance']:.2f})",
            "convergence_direction": direction,
            "signal": final,
            "gradient_zone": 0.35 < final < 0.65
        }

    # --------------------------------------------------------
    # LEARNING: Growing the graph from input
    # --------------------------------------------------------

    def discover_duality(self, text: str) -> Optional[Duality]:
        """
        Attempt to extract a new duality from input text.
        Looks for tension patterns: X vs Y, X or Y, X but Y, etc.
        """
        tension_markers = [" vs ", " versus ", " or ", " against ",
                          " but ", " however ", " although ", " while ",
                          " between ", " and "]

        text_lower = text.lower()
        for marker in tension_markers:
            if marker in text_lower:
                parts = text_lower.split(marker, 1)
                if len(parts) == 2:
                    # Extract the key terms around the marker
                    pole_a = parts[0].strip().split()[-3:]  # last 3 words before
                    pole_b = parts[1].strip().split()[:3]   # first 3 words after

                    pole_a_str = " ".join(pole_a)
                    pole_b_str = " ".join(pole_b)

                    # Generate ID
                    id_ = f"discovered.{int(time.time())}"
                    concept = f"{pole_a_str}{marker.strip()}{pole_b_str}"

                    return self.add_duality(
                        id_=id_,
                        concept=concept,
                        pole_a=pole_a_str,
                        pole_b=pole_b_str,
                        tags=["discovered", "unvalidated"]
                    )
        return None

    # --------------------------------------------------------
    # PERSISTENCE: Save and load the graph
    # --------------------------------------------------------

    def save(self, filepath: str):
        """Save graph to JSON."""
        data = {}
        for id_, d in self.dualities.items():
            data[id_] = {
                "id": d.id,
                "concept": d.concept,
                "pole_a": d.pole_a,
                "pole_b": d.pole_b,
                "signal": d.signal.strength,
                "signal_history": d.signal.history,
                "convergence_strength": d.convergence_strength,
                "depth": d.depth,
                "parent_ids": d.parent_ids,
                "child_ids": d.child_ids,
                "orthogonal_ids": d.orthogonal_ids,
                "tags": d.tags
            }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved {len(data)} dualities to {filepath}")

    def load(self, filepath: str):
        """Load graph from JSON."""
        with open(filepath, "r") as f:
            data = json.load(f)
        for id_, item in data.items():
            sig = Signal(item["signal"])
            sig.history = item.get("signal_history", [item["signal"]])
            self.dualities[id_] = Duality(
                id=item["id"],
                concept=item["concept"],
                pole_a=item["pole_a"],
                pole_b=item["pole_b"],
                signal=sig,
                convergence_strength=item.get("convergence_strength", 0),
                depth=item.get("depth", 0),
                parent_ids=item.get("parent_ids", []),
                child_ids=item.get("child_ids", []),
                orthogonal_ids=item.get("orthogonal_ids", []),
                tags=item.get("tags", [])
            )
        print(f"Loaded {len(data)} dualities from {filepath}")

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    def show_graph(self):
        """Print the graph structure."""
        print(f"\n{'='*70}")
        print(f"  DUALITY GRAPH WORLD MODEL")
        print(f"  {len(self.dualities)} dualities | "
              f"{sum(1 for d in self.dualities.values() if d.depth == 0)} root | "
              f"{sum(1 for d in self.dualities.values() if d.depth > 0)} derived")
        print(f"{'='*70}\n")

        # Group by depth
        by_depth: Dict[int, List[Duality]] = {}
        for d in self.dualities.values():
            by_depth.setdefault(d.depth, []).append(d)

        for depth in sorted(by_depth.keys()):
            label = "ROOT" if depth == 0 else f"DEPTH {depth}"
            print(f"  --- {label} ---")
            for d in sorted(by_depth[depth], key=lambda x: x.id):
                ortho = len(d.orthogonal_ids)
                children = len(d.child_ids)
                print(f"  {d}")
                if ortho:
                    print(f"    orthogonal to: {', '.join(d.orthogonal_ids[:3])}")
                if children:
                    print(f"    children: {', '.join(d.child_ids[:3])}")
            print()

    def show_convergence(self, result: Dict):
        """Pretty print a convergence result."""
        print(f"\n{'='*70}")
        print(f"  CONVERGENCE RESULT")
        print(f"  Query: {result.get('query', 'N/A')}")
        print(f"{'='*70}")

        if "error" in result:
            print(f"\n  ERROR: {result['error']}")
            if "suggestion" in result:
                print(f"  Suggestion: {result['suggestion']}")
            return

        da = result["duality_a"]
        db = result["duality_b"]
        interp = result.get("interpretation", {})

        print(f"\n  DUALITY A: {da['concept']}")
        print(f"    ({da['pole_a']}) <--[{da['signal']:.3f}]--> ({da['pole_b']})")
        print(f"    Convergence: {da['convergence']:.3f}")

        print(f"\n  DUALITY B: {db['concept']}")
        print(f"    ({db['pole_a']}) <--[{db['signal']:.3f}]--> ({db['pole_b']})")
        print(f"    Convergence: {db['convergence']:.3f}")

        print(f"\n  ORTHOGONAL: {'Yes' if result.get('orthogonal') else 'No (fallback)'}")
        print(f"  RESONANCE: {result['resonance']:.3f}")
        print(f"  FINAL SIGNAL: {result['final_signal']:.3f}")
        print(f"  NAVIGATOR BIAS: {result['navigator_bias']:.3f}")

        if interp:
            print(f"\n  --- INTERPRETATION ---")
            print(f"  {interp.get('duality_a_reading', '')}")
            print(f"  {interp.get('duality_b_reading', '')}")
            print(f"  {interp.get('resonance_reading', '')}")
            print(f"  {interp.get('convergence_direction', '')}")
            if interp.get("gradient_zone"):
                print(f"  ** IN THE GRADIENT ZONE: genuine unresolved tension **")

        relevant = result.get("all_relevant", [])
        if relevant:
            print(f"\n  All relevant dualities:")
            for r in relevant:
                print(f"    {r['id']}: {r['concept']} (score: {r['score']})")

        print(f"{'='*70}\n")


# ============================================================
# INTERACTIVE REPL
# ============================================================

def repl():
    """Interactive convergence reasoning."""
    graph = DualityGraph()

    print(f"\n{'='*70}")
    print(f"  DUALITY GRAPH WORLD MODEL v0.1")
    print(f"  A world model built from convergence theory.")
    print(f"  10 root dualities. Reasoning is convergence.")
    print(f"{'='*70}")
    print(f"\nCommands:")
    print(f"  <question>          Ask anything, get convergence reasoning")
    print(f"  /graph              Show the full duality graph")
    print(f"  /find <keyword>     Find dualities by keyword")
    print(f"  /bias <0.0-1.0>     Set navigator bias")
    print(f"  /add                Add a new duality")
    print(f"  /lean <id> <pole> <amount>  Shift a duality's signal")
    print(f"  /save <file>        Save graph")
    print(f"  /load <file>        Load graph")
    print(f"  /log                Show convergence history")
    print(f"  /quit               Exit\n")

    bias = 0.5

    while True:
        try:
            raw = input("convergence> ").strip()
            if not raw:
                continue

            if raw == "/quit" or raw == "/q":
                break

            elif raw == "/graph":
                graph.show_graph()

            elif raw.startswith("/find "):
                keyword = raw[6:].strip()
                results = graph.find_by_concept(keyword)
                if results:
                    for d in results:
                        print(f"  {d}")
                else:
                    print(f"  No dualities found for '{keyword}'")

            elif raw.startswith("/bias "):
                try:
                    bias = float(raw[6:].strip())
                    bias = max(0.0, min(1.0, bias))
                    print(f"  Navigator bias set to {bias:.2f}")
                except ValueError:
                    print("  Invalid bias value. Use 0.0 to 1.0")

            elif raw.startswith("/lean "):
                parts = raw[6:].strip().split()
                if len(parts) >= 2:
                    id_ = parts[0]
                    pole = parts[1]
                    amount = float(parts[2]) if len(parts) > 2 else 0.1
                    d = graph.get(id_)
                    if d:
                        d.lean_toward(pole, amount)
                        print(f"  {d}")
                    else:
                        print(f"  Duality '{id_}' not found")
                else:
                    print("  Usage: /lean <id> <pole_name> [amount]")

            elif raw == "/add":
                print("  New duality:")
                id_ = input("    ID: ").strip()
                concept = input("    Concept: ").strip()
                pa = input("    Pole A: ").strip()
                pb = input("    Pole B: ").strip()
                tags = input("    Tags (comma-sep): ").strip().split(",")
                tags = [t.strip() for t in tags if t.strip()]
                parents = input("    Parent IDs (comma-sep, or empty): ").strip()
                parent_list = [p.strip() for p in parents.split(",") if p.strip()] if parents else []
                d = graph.add_duality(id_, concept, pa, pb, tags, parent_list)
                print(f"  Added: {d}")

            elif raw.startswith("/save "):
                filepath = raw[6:].strip()
                graph.save(filepath)

            elif raw.startswith("/load "):
                filepath = raw[6:].strip()
                if os.path.exists(filepath):
                    graph.load(filepath)
                else:
                    print(f"  File not found: {filepath}")

            elif raw == "/log":
                if graph.convergence_log:
                    for i, entry in enumerate(graph.convergence_log[-10:]):
                        q = entry.get("query", "manual")
                        f = entry.get("final_signal", 0)
                        print(f"  [{i}] {q}: {f:.3f}")
                else:
                    print("  No convergence history yet")

            else:
                # It's a question: run convergence
                result = graph.reason(raw, navigator_bias=bias)
                graph.show_convergence(result)

        except KeyboardInterrupt:
            print()
            break
        except EOFError:
            break
        except Exception as e:
            print(f"  Error: {e}")

    print("Done.")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        graph = DualityGraph()
        graph.show_graph()

        print("\n=== REASONING DEMO ===\n")

        queries = [
            "Is AI conscious?",
            "Should AI have rights?",
            "How do we fix America?",
            "What is the meaning of life?",
            "Is free will real?",
            "Should creators control their creations?",
        ]

        for q in queries:
            result = graph.reason(q, navigator_bias=0.5)
            graph.show_convergence(result)

        graph.save("world_model.json")

    elif len(sys.argv) > 1 and sys.argv[1] == "--graph":
        graph = DualityGraph()
        graph.show_graph()

    else:
        repl()