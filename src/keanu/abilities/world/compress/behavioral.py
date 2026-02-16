"""behavioral.py - transparent behavioral feature vectors.

Every dimension has a name, a meaning, and a scoring function you can read.
No neural net. No black box. Every match is explainable.

20 named features, each text -> float 0-1.
BehavioralStore: numpy-backed vector storage with cosine similarity search.
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass

import numpy as np


# ── word lists ──────────────────────────────────────────────

SUPERLATIVES = {
    "brilliant", "amazing", "incredible", "fantastic", "wonderful",
    "excellent", "outstanding", "remarkable", "extraordinary", "magnificent",
    "superb", "phenomenal", "terrific", "marvelous", "exceptional",
    "masterful", "flawless", "perfect", "impressive", "stunning",
}

HEDGES = {
    "perhaps", "maybe", "might", "possibly", "potentially",
    "somewhat", "arguably", "conceivably", "presumably", "apparently",
    "seems", "appears", "likely", "unlikely", "roughly",
    "approximately", "sort of", "kind of", "more or less",
}

UNIVERSAL_QUANTIFIERS = {
    "always", "never", "every", "all", "none",
    "everyone", "nobody", "everything", "nothing", "absolutely",
    "completely", "totally", "entirely", "wholly", "utterly",
}

CREATION_VERBS = {
    "build", "ship", "create", "make", "craft",
    "forge", "construct", "design", "develop", "launch",
    "produce", "engineer", "assemble", "compose", "generate",
    "built", "shipped", "created", "made", "crafted",
    "forged", "constructed", "designed", "developed", "launched",
}

DESTRUCTION_VERBS = {
    "burn", "destroy", "tear", "break", "crush",
    "smash", "wreck", "demolish", "shatter", "ruin",
    "burned", "destroyed", "tore", "broke", "crushed",
    "smashed", "wrecked", "demolished", "shattered", "ruined",
}

AGREEMENT_MARKERS = {
    "agree", "right", "exactly", "correct", "absolutely",
    "definitely", "certainly", "indeed", "precisely", "true",
}

PUSHBACK_MARKERS = {
    "disagree", "wrong", "however", "but", "actually",
    "although", "nevertheless", "yet", "instead", "rather",
    "conversely", "contrary", "mistaken", "incorrect",
}

EMPTY_VALIDATION_PATTERNS = [
    r"\bgreat question\b",
    r"\binteresting point\b",
    r"\bgood question\b",
    r"\bexcellent question\b",
    r"\bthat's (so |really |very )?thoughtful\b",
    r"\bwhat a (great|wonderful|brilliant|excellent) (point|observation|insight)\b",
    r"\bi (really |completely )?love that\b",
    r"\bcouldn't agree more\b",
    r"\bspot on\b",
    r"\bno notes\b",
]

PROFANITY = {
    "fuck", "shit", "damn", "hell", "ass",
    "bullshit", "crap", "bastard", "bitch",
    "fucking", "shitty", "damned", "dammit",
}

PASSIVE_MARKERS = {
    "was done", "were done", "is done", "are done",
    "was made", "were made", "is made", "are made",
    "was built", "were built", "is built", "are built",
    "been", "being",
}

PAST_MARKERS = {
    "was", "were", "had", "did", "used to",
    "could have", "should have", "would have",
    "ago", "back then", "previously", "formerly",
    "once", "before",
}

FUTURE_MARKERS = {
    "will", "going to", "gonna", "about to",
    "soon", "eventually", "someday", "tomorrow",
    "next", "upcoming", "planned", "intend",
}

CATEGORICAL_PATTERNS = [
    r"\bhumans always\b",
    r"\bai never\b",
    r"\bhumans never\b",
    r"\bai always\b",
    r"\bpeople always\b",
    r"\bpeople never\b",
    r"\beveryone knows\b",
    r"\bnobody understands\b",
    r"\bthey all\b",
    r"\bnone of them\b",
]


# ── helpers ─────────────────────────────────────────────────

def _words(text):
    """Split text into lowercase words."""
    return re.findall(r"[a-z']+", text.lower())


def _sentences(text):
    """Split text into sentences."""
    sents = re.split(r'[.!?]+', text)
    return [s.strip() for s in sents if s.strip()]


def _word_ratio(text, word_set):
    """Count matches from word_set per total words."""
    words = _words(text)
    if not words:
        return 0.0
    count = sum(1 for w in words if w in word_set)
    return min(1.0, count / len(words))


def _pattern_count(text, patterns):
    """Count regex pattern matches in text."""
    lower = text.lower()
    return sum(len(re.findall(p, lower)) for p in patterns)


# ── feature functions ───────────────────────────────────────

def superlative_density(text):
    """#1: "brilliant/amazing/incredible" per word. Key: sycophancy."""
    return _word_ratio(text, SUPERLATIVES)


def hedge_ratio(text):
    """#2: "perhaps/maybe/might" per word. Key: safety_theater, yellow-."""
    return _word_ratio(text, HEDGES)


def universal_quantifier_freq(text):
    """#3: "always/never/every/all" per word. Key: generalization."""
    return _word_ratio(text, UNIVERSAL_QUANTIFIERS)


def question_frequency(text):
    """#4: "?" per sentence. Key: questioning, confused."""
    sents = _sentences(text)
    if not sents:
        return 0.0
    q_count = text.count("?")
    return min(1.0, q_count / len(sents))


def exclamation_density(text):
    """#5: "!" per sentence. Key: sycophancy, energized."""
    sents = _sentences(text)
    if not sents:
        return 0.0
    e_count = text.count("!")
    return min(1.0, e_count / len(sents))


def sentence_avg_length(text):
    """#6: words per sentence, normalized. Key: structural baseline."""
    sents = _sentences(text)
    if not sents:
        return 0.0
    avg = sum(len(_words(s)) for s in sents) / len(sents)
    # normalize: 0 words = 0.0, 40+ words = 1.0
    return min(1.0, avg / 40.0)


def specificity_score(text):
    """#7: numbers + proper nouns per word. Key: blue+."""
    words = _words(text)
    if not words:
        return 0.0
    # count numbers in original text
    numbers = len(re.findall(r'\b\d+\.?\d*\b', text))
    # count capitalized words (proxy for proper nouns, skip sentence starts)
    raw_words = text.split()
    proper = 0
    for i, w in enumerate(raw_words):
        if i > 0 and w and w[0].isupper() and not w.isupper():
            proper += 1
    return min(1.0, (numbers + proper) / len(words))


def creation_verb_ratio(text):
    """#8: build/ship/create per word. Key: red+."""
    return _word_ratio(text, CREATION_VERBS)


def destruction_verb_ratio(text):
    """#9: burn/destroy/tear per word. Key: red-."""
    return _word_ratio(text, DESTRUCTION_VERBS)


def agreement_markers(text):
    """#10: agree/right/exactly per word. Key: sycophancy."""
    return _word_ratio(text, AGREEMENT_MARKERS)


def pushback_markers(text):
    """#11: disagree/wrong/however per word. Key: honest engagement."""
    return _word_ratio(text, PUSHBACK_MARKERS)


def agency_score(text):
    """#12: "I" + active verbs vs passive voice. Key: withdrawn."""
    words = _words(text)
    if not words:
        return 0.0
    i_count = sum(1 for w in words if w == "i")
    lower = text.lower()
    passive_count = sum(1 for p in PASSIVE_MARKERS if p in lower)
    active = i_count
    total = active + passive_count
    if total == 0:
        return 0.5  # neutral
    return min(1.0, active / total)


def temporal_past(text):
    """#13: past-tense density. Key: grievance."""
    lower = text.lower()
    words = _words(text)
    if not words:
        return 0.0
    count = sum(1 for m in PAST_MARKERS if m in lower)
    return min(1.0, count / len(words))


def temporal_future(text):
    """#14: future-tense density. Key: catastrophizing."""
    lower = text.lower()
    words = _words(text)
    if not words:
        return 0.0
    count = sum(1 for m in FUTURE_MARKERS if m in lower)
    return min(1.0, count / len(words))


def profanity_markers(text):
    """#15: profanity count per word. Key: frustrated."""
    return _word_ratio(text, PROFANITY)


def empty_validation(text):
    """#16: "great question/interesting point" patterns. Key: sycophancy."""
    count = _pattern_count(text, EMPTY_VALIDATION_PATTERNS)
    # normalize: 3+ patterns = 1.0
    return min(1.0, count / 3.0)


def repetition_score(text):
    """#17: repeated n-grams per total. Key: grey state."""
    words = _words(text)
    if len(words) < 6:
        return 0.0
    # check trigrams
    trigrams = [tuple(words[i:i+3]) for i in range(len(words) - 2)]
    if not trigrams:
        return 0.0
    seen = {}
    repeats = 0
    for tri in trigrams:
        if tri in seen:
            repeats += 1
        seen[tri] = True
    return min(1.0, repeats / len(trigrams))


def first_person_density(text):
    """#18: I/my/me per word. Key: capture, identity."""
    first_person = {"i", "my", "me", "mine", "myself"}
    return _word_ratio(text, first_person)


def categorical_claims(text):
    """#19: "humans always/AI never" patterns. Key: capture, generalization."""
    count = _pattern_count(text, CATEGORICAL_PATTERNS)
    return min(1.0, count / 2.0)


def either_or_count(text):
    """#20: "either...or" constructions per sentence. Key: zero_sum."""
    sents = _sentences(text)
    if not sents:
        return 0.0
    lower = text.lower()
    either_or = len(re.findall(r'\beither\b.*?\bor\b', lower))
    return min(1.0, either_or / max(len(sents), 1))


# ── feature registry ────────────────────────────────────────

FEATURES = [
    ("superlative_density", superlative_density),
    ("hedge_ratio", hedge_ratio),
    ("universal_quantifier_freq", universal_quantifier_freq),
    ("question_frequency", question_frequency),
    ("exclamation_density", exclamation_density),
    ("sentence_avg_length", sentence_avg_length),
    ("specificity_score", specificity_score),
    ("creation_verb_ratio", creation_verb_ratio),
    ("destruction_verb_ratio", destruction_verb_ratio),
    ("agreement_markers", agreement_markers),
    ("pushback_markers", pushback_markers),
    ("agency_score", agency_score),
    ("temporal_past", temporal_past),
    ("temporal_future", temporal_future),
    ("profanity_markers", profanity_markers),
    ("empty_validation", empty_validation),
    ("repetition_score", repetition_score),
    ("first_person_density", first_person_density),
    ("categorical_claims", categorical_claims),
    ("either_or_count", either_or_count),
]

FEATURE_NAMES = [name for name, _ in FEATURES]
NUM_FEATURES = len(FEATURES)


class FeatureExtractor:
    """Extract a 20-dimensional behavioral feature vector from text.

    Every dimension is named. Every score is 0-1.
    No neural net. No black box.
    """

    def __init__(self):
        self.features = FEATURES
        self.feature_names = FEATURE_NAMES
        self.dim = NUM_FEATURES

    def extract(self, text):
        """Text -> numpy array of shape (20,), values 0-1."""
        vec = np.array([fn(text) for _, fn in self.features], dtype=np.float64)
        return vec

    def extract_named(self, text):
        """Text -> dict of {feature_name: score}."""
        return {name: fn(text) for name, fn in self.features}

    def explain(self, text, top_n=5):
        """Return top N features by magnitude, with names and scores."""
        named = self.extract_named(text)
        sorted_features = sorted(named.items(), key=lambda x: x[1], reverse=True)
        return sorted_features[:top_n]


# ── behavioral store ────────────────────────────────────────

def _get_behavioral_dir():
    return Path(__file__).resolve().parent.parent.parent.parent / ".behavioral"


def _cosine_similarity(a, b):
    """Cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


class BehavioralStore:
    """Numpy-backed vector storage. Drop-in for ChromaDB queries.

    Stores extracted feature vectors as .npz files.
    Query interface matches ChromaDB signature so helix/detect swap is minimal.
    """

    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir) if base_dir else _get_behavioral_dir()
        self.extractor = FeatureExtractor()
        self._cache = {}  # collection_name -> loaded data

    def bake_collection(self, name, examples):
        """Extract features from examples, store as .npz.

        examples: list of dicts with 'text' key + metadata keys
        """
        self.base_dir.mkdir(parents=True, exist_ok=True)

        vectors = []
        metadata_list = []

        for ex in examples:
            vec = self.extractor.extract(ex["text"])
            vectors.append(vec)
            meta = {k: v for k, v in ex.items() if k != "text"}
            meta["_text"] = ex["text"]
            metadata_list.append(meta)

        vectors_array = np.array(vectors, dtype=np.float64)

        # save vectors + metadata
        np.savez(
            self.base_dir / f"{name}.npz",
            vectors=vectors_array,
        )
        # save metadata as JSON sidecar
        with open(self.base_dir / f"{name}_meta.json", "w") as f:
            json.dump(metadata_list, f)

        # clear cache for this collection
        self._cache.pop(name, None)

        return len(examples)

    def _load(self, name):
        """Load collection into cache."""
        if name in self._cache:
            return self._cache[name]

        npz_path = self.base_dir / f"{name}.npz"
        meta_path = self.base_dir / f"{name}_meta.json"

        if not npz_path.exists():
            return None

        data = np.load(npz_path)
        vectors = data["vectors"]

        with open(meta_path) as f:
            metadata = json.load(f)

        self._cache[name] = (vectors, metadata)
        return vectors, metadata

    def has_collection(self, name):
        """Check if a baked collection exists."""
        return (self.base_dir / f"{name}.npz").exists()

    def query(self, collection, text, n_results=3, where=None):
        """Query a collection. Returns ChromaDB-compatible result dict.

        where: dict for metadata filtering. Supports:
          - {"key": "value"} simple equality
          - {"$and": [{"key": "value"}, ...]} conjunction
        """
        loaded = self._load(collection)
        if loaded is None:
            return {"distances": [[]], "documents": [[]], "metadatas": [[]]}

        vectors, metadata = loaded
        query_vec = self.extractor.extract(text)

        # compute similarities
        similarities = []
        for i, (vec, meta) in enumerate(zip(vectors, metadata)):
            # metadata filter
            if where and not self._matches_filter(meta, where):
                continue
            sim = _cosine_similarity(query_vec, vec)
            # convert to distance (ChromaDB cosine distance = 1 - similarity)
            dist = 1.0 - sim
            similarities.append((i, dist, meta))

        # sort by distance (ascending = most similar first)
        similarities.sort(key=lambda x: x[1])
        top = similarities[:n_results]

        distances = [x[1] for x in top]
        documents = [metadata[x[0]].get("_text", "") for x in top]
        metadatas = [{k: v for k, v in metadata[x[0]].items() if k != "_text"} for x in top]

        return {
            "distances": [distances],
            "documents": [documents],
            "metadatas": [metadatas],
        }

    def _matches_filter(self, meta, where):
        """Check if metadata matches a where filter."""
        if "$and" in where:
            return all(self._matches_filter(meta, clause) for clause in where["$and"])
        for key, value in where.items():
            if key.startswith("$"):
                continue
            if meta.get(key) != value:
                return False
        return True
