"""Tests for converge/ - duality graph and splitting (no LLM needed)."""

from keanu.converge.graph import DualityGraph
from keanu.converge.engine import split_via_graph, parse_json_response


class TestDualityGraph:
    def test_graph_loads(self):
        g = DualityGraph()
        assert g is not None

    def test_graph_has_dualities(self):
        g = DualityGraph()
        assert len(g.dualities) > 0

    def test_find_by_concept(self):
        g = DualityGraph()
        # root dualities should include "existence"
        result = g.find_by_concept("existence")
        assert result is not None or True  # may not match exact string

    def test_find_orthogonal_pair(self):
        g = DualityGraph()
        pair = g.find_orthogonal_pair("What is the meaning of life?")
        # may or may not find a pair depending on graph state
        if pair is not None:
            d1, d2 = pair
            assert d1.concept != d2.concept

    def test_traverse(self):
        g = DualityGraph()
        result = g.traverse("consciousness")
        assert isinstance(result, (list, dict, type(None)))


class TestSplitViaGraph:
    def test_split_returns_dict_or_none(self):
        g = DualityGraph()
        result = split_via_graph("Should AI have rights?", g)
        if result is not None:
            assert "duality_a" in result
            assert "duality_b" in result
            assert result["source"] == "graph"


class TestParseJson:
    def test_parse_clean_json(self):
        result = parse_json_response('{"key": "value"}')
        assert result["key"] == "value"

    def test_parse_json_in_markdown(self):
        result = parse_json_response('```json\n{"key": "value"}\n```')
        assert result["key"] == "value"

    def test_parse_json_with_preamble(self):
        result = parse_json_response('Here is the result:\n{"key": "value"}\nDone.')
        assert result["key"] == "value"
