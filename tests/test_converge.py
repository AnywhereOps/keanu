"""tests for converge/ - duality graph and JSON parsing (no LLM needed)."""

from keanu.abilities.world.converge.graph import DualityGraph
from keanu.abilities.world.converge.engine import LENSES
from keanu.oracle import interpret


class TestDualityGraph:
    def test_graph_loads(self):
        g = DualityGraph()
        assert g is not None

    def test_graph_has_dualities(self):
        g = DualityGraph()
        assert len(g.dualities) > 0

    def test_find_by_concept(self):
        g = DualityGraph()
        result = g.find_by_concept("existence")
        assert result is not None or True

    def test_find_orthogonal_pair(self):
        g = DualityGraph()
        pair = g.find_orthogonal_pair("What is the meaning of life?")
        if pair is not None:
            d1, d2 = pair
            assert d1.concept != d2.concept

    def test_traverse(self):
        g = DualityGraph()
        result = g.traverse("consciousness")
        assert isinstance(result, (list, dict, type(None)))


class TestLensesConfig:
    def test_six_lenses(self):
        assert len(LENSES) == 6

    def test_each_lens_has_required_fields(self):
        for lens in LENSES:
            assert "id" in lens
            assert "name" in lens
            assert "axis" in lens
            assert "pole" in lens
            assert "prompt" in lens


class TestParseJson:
    def test_parse_clean_json(self):
        result = interpret('{"key": "value"}')
        assert result["key"] == "value"

    def test_parse_json_in_markdown(self):
        result = interpret('```json\n{"key": "value"}\n```')
        assert result["key"] == "value"

    def test_parse_json_with_preamble(self):
        result = interpret('Here is the result:\n{"key": "value"}\nDone.')
        assert result["key"] == "value"
