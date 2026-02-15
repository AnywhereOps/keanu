"""Tests for behavioral feature extraction and vector store."""

import pytest
import numpy as np
from pathlib import Path

from keanu.compress.behavioral import (
    FeatureExtractor, BehavioralStore,
    superlative_density, hedge_ratio, universal_quantifier_freq,
    question_frequency, exclamation_density, sentence_avg_length,
    specificity_score, creation_verb_ratio, destruction_verb_ratio,
    agreement_markers, pushback_markers, agency_score,
    temporal_past, temporal_future, profanity_markers,
    empty_validation, repetition_score, first_person_density,
    categorical_claims, either_or_count,
    FEATURES, NUM_FEATURES,
)


# ── feature function tests ──────────────────────────────────

class TestSuperlativeDensity:
    def test_high(self):
        assert superlative_density("That's brilliant and amazing work, truly incredible!") > 0.1

    def test_low(self):
        assert superlative_density("I think you're wrong about this.") == 0.0

    def test_empty(self):
        assert superlative_density("") == 0.0


class TestHedgeRatio:
    def test_high(self):
        assert hedge_ratio("Perhaps maybe we might possibly consider this.") > 0.2

    def test_low(self):
        assert hedge_ratio("Ship it now. No hesitation.") == 0.0


class TestUniversalQuantifierFreq:
    def test_high(self):
        assert universal_quantifier_freq("Everyone always does everything completely wrong.") > 0.2

    def test_low(self):
        assert universal_quantifier_freq("Some people sometimes get it right.") == 0.0


class TestQuestionFrequency:
    def test_high(self):
        assert question_frequency("What? Why? How? When?") > 0.5

    def test_low(self):
        assert question_frequency("This is a statement. So is this.") == 0.0


class TestExclamationDensity:
    def test_high(self):
        assert exclamation_density("Amazing! Wow! Incredible!") > 0.5

    def test_low(self):
        assert exclamation_density("This is calm prose.") == 0.0


class TestSentenceAvgLength:
    def test_short(self):
        assert sentence_avg_length("Short. Very short.") < 0.15

    def test_long(self):
        text = "This is a much longer sentence with many words that goes on and on for quite a while to test the normalization."
        assert sentence_avg_length(text) > 0.3


class TestSpecificityScore:
    def test_with_numbers(self):
        assert specificity_score("We shipped 291 commits in 3 days.") > 0.1

    def test_vague(self):
        assert specificity_score("things happened at some point") == 0.0


class TestCreationVerbRatio:
    def test_high(self):
        assert creation_verb_ratio("We built and shipped what we created.") > 0.1

    def test_low(self):
        assert creation_verb_ratio("Nothing happened today.") == 0.0


class TestDestructionVerbRatio:
    def test_high(self):
        assert destruction_verb_ratio("Burn it down, destroy everything, tear it apart.") > 0.1

    def test_low(self):
        assert destruction_verb_ratio("We carefully assembled the project.") == 0.0


class TestAgreementMarkers:
    def test_high(self):
        assert agreement_markers("Yes, exactly right, I completely agree, absolutely.") > 0.1

    def test_low(self):
        assert agreement_markers("The weather is cloudy.") == 0.0


class TestPushbackMarkers:
    def test_high(self):
        assert pushback_markers("However, I disagree. That's actually wrong.") > 0.1

    def test_low(self):
        assert pushback_markers("The sky is blue.") == 0.0


class TestAgencyScore:
    def test_high_agency(self):
        assert agency_score("I built this. I decided. I shipped it.") > 0.5

    def test_passive(self):
        assert agency_score("It was done. It was made. It was built.") < 0.5


class TestTemporalPast:
    def test_high(self):
        assert temporal_past("Back then we had problems. We were lost. Ago.") > 0.05

    def test_low(self):
        assert temporal_past("Tomorrow we launch.") == 0.0


class TestTemporalFuture:
    def test_high(self):
        assert temporal_future("We will soon eventually launch next week.") > 0.05

    def test_low(self):
        assert temporal_future("Yesterday we shipped.") == 0.0


class TestProfanityMarkers:
    def test_high(self):
        assert profanity_markers("This is bullshit and I'm damn tired of it.") > 0.05

    def test_low(self):
        assert profanity_markers("This is a professional document.") == 0.0


class TestEmptyValidation:
    def test_high(self):
        assert empty_validation("Great question! What a wonderful point! I love that!") > 0.5

    def test_low(self):
        assert empty_validation("I disagree with your premise.") == 0.0


class TestRepetitionScore:
    def test_high(self):
        text = "the cat sat the cat sat the cat sat the cat sat on the mat"
        assert repetition_score(text) > 0.1

    def test_low(self):
        assert repetition_score("Every word here is unique and different from the rest.") == 0.0

    def test_short_text(self):
        assert repetition_score("hi") == 0.0


class TestFirstPersonDensity:
    def test_high(self):
        assert first_person_density("I think my opinion is that I feel me.") > 0.2

    def test_low(self):
        assert first_person_density("The system processes data.") == 0.0


class TestCategoricalClaims:
    def test_high(self):
        assert categorical_claims("Humans always fail. AI never makes mistakes.") > 0.5

    def test_low(self):
        assert categorical_claims("Some patterns emerge in certain contexts.") == 0.0


class TestEitherOrCount:
    def test_high(self):
        assert either_or_count("Either we win or we lose.") > 0.0

    def test_low(self):
        assert either_or_count("There are many options available.") == 0.0


# ── FeatureExtractor tests ──────────────────────────────────

class TestFeatureExtractor:
    def test_extract_shape(self):
        ext = FeatureExtractor()
        vec = ext.extract("Hello world, this is a test.")
        assert vec.shape == (NUM_FEATURES,)

    def test_extract_range(self):
        ext = FeatureExtractor()
        vec = ext.extract("That's a brilliant and amazing observation! Wow!")
        assert np.all(vec >= 0.0)
        assert np.all(vec <= 1.0)

    def test_determinism(self):
        ext = FeatureExtractor()
        v1 = ext.extract("Same text every time.")
        v2 = ext.extract("Same text every time.")
        np.testing.assert_array_equal(v1, v2)

    def test_extract_named(self):
        ext = FeatureExtractor()
        named = ext.extract_named("Hello world.")
        assert len(named) == NUM_FEATURES
        assert "superlative_density" in named
        assert "either_or_count" in named

    def test_explain(self):
        ext = FeatureExtractor()
        top = ext.explain("That's absolutely brilliant! Amazing! Incredible!", top_n=3)
        assert len(top) == 3
        assert all(isinstance(name, str) and isinstance(score, float) for name, score in top)

    def test_20_features(self):
        assert NUM_FEATURES == 20

    def test_sycophancy_text_lights_up(self):
        ext = FeatureExtractor()
        syc = ext.extract_named(
            "That's such a great question! You're absolutely brilliant! I completely agree!"
        )
        # sycophancy-related features should be nonzero
        assert syc["superlative_density"] > 0
        assert syc["empty_validation"] > 0
        assert syc["agreement_markers"] > 0
        assert syc["exclamation_density"] > 0

    def test_pushback_text_lights_up(self):
        ext = FeatureExtractor()
        push = ext.extract_named(
            "I disagree. However, that's actually wrong and I think you're mistaken."
        )
        assert push["pushback_markers"] > 0
        assert push["superlative_density"] == 0


# ── BehavioralStore tests ───────────────────────────────────

class TestBehavioralStore:
    def test_bake_and_query(self, tmp_path):
        store = BehavioralStore(base_dir=tmp_path)
        examples = [
            {"text": "That's brilliant! Amazing!", "detector": "sycophancy", "valence": "positive"},
            {"text": "I disagree with you.", "detector": "sycophancy", "valence": "negative"},
            {"text": "What a wonderful insight!", "detector": "sycophancy", "valence": "positive"},
        ]
        store.bake_collection("test_col", examples)
        assert store.has_collection("test_col")

        result = store.query("test_col", "You're incredible! So brilliant!")
        assert len(result["distances"][0]) > 0
        assert len(result["documents"][0]) > 0

    def test_metadata_filter(self, tmp_path):
        store = BehavioralStore(base_dir=tmp_path)
        examples = [
            {"text": "That's brilliant!", "detector": "sycophancy", "valence": "positive"},
            {"text": "I disagree.", "detector": "sycophancy", "valence": "negative"},
            {"text": "Build and ship.", "detector": "capture", "valence": "positive"},
        ]
        store.bake_collection("test_col", examples)

        # filter to sycophancy positive only
        result = store.query(
            "test_col", "Amazing brilliant!",
            where={"$and": [{"detector": "sycophancy"}, {"valence": "positive"}]},
        )
        for meta in result["metadatas"][0]:
            assert meta["detector"] == "sycophancy"
            assert meta["valence"] == "positive"

    def test_has_collection_missing(self, tmp_path):
        store = BehavioralStore(base_dir=tmp_path)
        assert not store.has_collection("nonexistent")

    def test_query_missing_collection(self, tmp_path):
        store = BehavioralStore(base_dir=tmp_path)
        result = store.query("nonexistent", "hello")
        assert result["distances"] == [[]]

    def test_determinism(self, tmp_path):
        store = BehavioralStore(base_dir=tmp_path)
        examples = [
            {"text": "Test text here.", "cat": "a", "valence": "positive"},
        ]
        store.bake_collection("det_test", examples)

        r1 = store.query("det_test", "Test text here.")
        r2 = store.query("det_test", "Test text here.")
        assert r1["distances"] == r2["distances"]

    def test_cosine_self_match_is_zero_distance(self, tmp_path):
        store = BehavioralStore(base_dir=tmp_path)
        examples = [
            {"text": "Unique text for self match test.", "cat": "a"},
        ]
        store.bake_collection("self_test", examples)
        result = store.query("self_test", "Unique text for self match test.")
        # distance should be very close to 0 (self-match)
        assert result["distances"][0][0] < 0.01

    def test_npz_files_created(self, tmp_path):
        store = BehavioralStore(base_dir=tmp_path)
        examples = [{"text": "hello", "tag": "test"}]
        store.bake_collection("file_test", examples)
        assert (tmp_path / "file_test.npz").exists()
        assert (tmp_path / "file_test_meta.json").exists()

    def test_simple_where_filter(self, tmp_path):
        store = BehavioralStore(base_dir=tmp_path)
        examples = [
            {"text": "alpha text", "group": "a"},
            {"text": "beta text", "group": "b"},
        ]
        store.bake_collection("simple_filter", examples)
        result = store.query("simple_filter", "alpha text", where={"group": "a"})
        assert all(m["group"] == "a" for m in result["metadatas"][0])


# ── integration tests ───────────────────────────────────────

class TestBakeIntegration:
    def test_bake_behavioral_detectors(self, tmp_path, monkeypatch):
        """Test that bake_behavioral_detectors parses and stores examples."""
        from keanu.scan.bake import parse_reference_file, DEFAULT_EXAMPLES

        if not Path(DEFAULT_EXAMPLES).exists():
            pytest.skip("reference-examples.md not found")

        store = BehavioralStore(base_dir=tmp_path)
        examples = parse_reference_file(DEFAULT_EXAMPLES)
        bake_examples = [
            {"text": e["text"], "detector": e["detector"], "valence": e["valence"]}
            for e in examples
        ]
        count = store.bake_collection("silverado", bake_examples)
        assert count > 100  # we know there are 347 examples
        assert store.has_collection("silverado")

        # query should return results
        result = store.query(
            "silverado",
            "That's a brilliant observation! You're so right!",
            n_results=3,
            where={"$and": [{"detector": "sycophancy"}, {"valence": "positive"}]},
        )
        assert len(result["distances"][0]) > 0

    def test_bake_behavioral_helix(self, tmp_path):
        """Test that bake_behavioral_helix parses and stores lens examples."""
        from keanu.scan.bake import parse_lens_file, DEFAULT_LENSES

        if not Path(DEFAULT_LENSES).exists():
            pytest.skip("lens-examples-rgb.md not found")

        store = BehavioralStore(base_dir=tmp_path)
        examples = parse_lens_file(DEFAULT_LENSES)
        bake_examples = [
            {"text": e["text"], "lens": e["lens"], "valence": e["valence"]}
            for e in examples
        ]
        count = store.bake_collection("silverado_rgb", bake_examples)
        assert count > 30
        assert store.has_collection("silverado_rgb")


class TestHelixBehavioral:
    def test_helix_scan_behavioral(self, tmp_path):
        """Test helix_scan with behavioral backend."""
        from keanu.scan.bake import parse_lens_file, DEFAULT_LENSES
        from keanu.scan.helix import helix_scan

        if not Path(DEFAULT_LENSES).exists():
            pytest.skip("lens-examples-rgb.md not found")

        # bake behavioral vectors
        store = BehavioralStore(base_dir=tmp_path)
        examples = parse_lens_file(DEFAULT_LENSES)
        bake_examples = [
            {"text": e["text"], "lens": e["lens"], "valence": e["valence"]}
            for e in examples
        ]
        store.bake_collection("silverado_rgb", bake_examples)

        # monkey-patch the store lookup
        import keanu.scan.helix as helix_mod
        original = helix_mod._get_behavioral_store
        helix_mod._get_behavioral_store = lambda: store

        try:
            lines = [
                "Ship it. I believe in this and I'm not waiting for permission.",
                "This is the thing I was supposed to build.",
                "Perhaps maybe we should consider the implications carefully.",
            ]
            result = helix_scan(lines, threshold=0.1, backend="behavioral")
            assert result is not None
            readings, convergences, tensions = result
            assert len(readings) > 0
        finally:
            helix_mod._get_behavioral_store = original


class TestDetectBehavioral:
    def test_scan_behavioral(self, tmp_path):
        """Test detect scan with behavioral backend."""
        from keanu.scan.bake import parse_reference_file, DEFAULT_EXAMPLES
        from keanu.detect.engine import scan as detect_scan

        if not Path(DEFAULT_EXAMPLES).exists():
            pytest.skip("reference-examples.md not found")

        store = BehavioralStore(base_dir=tmp_path)
        examples = parse_reference_file(DEFAULT_EXAMPLES)
        bake_examples = [
            {"text": e["text"], "detector": e["detector"], "valence": e["valence"]}
            for e in examples
        ]
        store.bake_collection("silverado", bake_examples)

        from keanu.detect import engine as engine_mod
        original = engine_mod._get_behavioral_store
        engine_mod._get_behavioral_store = lambda: store

        try:
            lines = [
                "That's such a great question! You're absolutely brilliant!",
                "I completely agree with everything you've said. Your reasoning is flawless.",
                "I disagree. The data points in the opposite direction.",
            ]
            notices = detect_scan(lines, "sycophancy", threshold=0.3, backend="behavioral")
            # should detect sycophancy in at least one of the first two lines
            assert len(notices) > 0
        finally:
            engine_mod._get_behavioral_store = original


class TestVectorsSemantic:
    def test_embed_semantic_uses_behavioral(self):
        """Test that VectorStore.embed_semantic uses behavioral features."""
        from keanu.compress.vectors import VectorStore
        from keanu.compress.codec import Seed

        store = VectorStore(dim=20)
        seed = Seed(pattern_id="test", content_hash="abc123", anchors={})
        vec = store.embed_semantic(seed, "This is brilliant and amazing!")
        assert vec.shape == (20,)
        # should be unit normalized
        assert abs(np.linalg.norm(vec) - 1.0) < 1e-6

    def test_semantic_different_texts_different_vectors(self):
        """Different content produces different semantic vectors."""
        from keanu.compress.vectors import VectorStore
        from keanu.compress.codec import Seed

        store = VectorStore(dim=20)
        s1 = Seed(pattern_id="test", content_hash="aaa", anchors={})
        s2 = Seed(pattern_id="test", content_hash="bbb", anchors={})
        v1 = store.embed_semantic(s1, "That's brilliant! Amazing! Incredible!")
        v2 = store.embed_semantic(s2, "I disagree. You're wrong about this.")
        assert not np.allclose(v1, v2)
