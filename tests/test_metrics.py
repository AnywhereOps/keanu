"""Tests for the convergence metrics system."""

import time
import pytest

from keanu.abilities.world.metrics import (
    record_fire, record_ash, record_forge,
    ratio, by_ability, by_legend, forges, dashboard,
    _dashboard_message,
)


@pytest.fixture(autouse=True)
def isolated_metrics(tmp_path, monkeypatch):
    """point metrics to temp files for every test."""
    fake_file = tmp_path / "metrics.jsonl"
    monkeypatch.setattr("keanu.abilities.world.metrics.METRICS_FILE", fake_file)
    return fake_file


class TestRecording:

    def test_record_fire(self, isolated_metrics):
        record_fire("test prompt", legend="creator", model="opus", tokens=500)
        from keanu.io import read_jsonl
        records = read_jsonl(isolated_metrics)
        assert len(records) == 1
        assert records[0]["type"] == "fire"
        assert records[0]["legend"] == "creator"
        assert records[0]["tokens"] == 500

    def test_record_ash(self, isolated_metrics):
        record_ash("read", success=True)
        from keanu.io import read_jsonl
        records = read_jsonl(isolated_metrics)
        assert len(records) == 1
        assert records[0]["type"] == "ash"
        assert records[0]["ability"] == "read"

    def test_record_forge(self, isolated_metrics):
        record_forge("new_ability")
        from keanu.io import read_jsonl
        records = read_jsonl(isolated_metrics)
        assert len(records) == 1
        assert records[0]["type"] == "forge"
        assert records[0]["ability"] == "new_ability"


class TestRatio:

    def test_empty(self):
        r = ratio()
        assert r["fire"] == 0
        assert r["ash"] == 0
        assert r["ratio"] == 0.0
        assert r["trend"] == "no data"

    def test_all_fire(self):
        for _ in range(5):
            record_fire("test")
        r = ratio()
        assert r["fire"] == 5
        assert r["ash"] == 0
        assert r["ratio"] == 0.0

    def test_all_ash(self):
        for _ in range(5):
            record_ash("read")
        r = ratio()
        assert r["fire"] == 0
        assert r["ash"] == 5
        assert r["ratio"] == 1.0

    def test_mixed(self):
        record_fire("a")
        record_fire("b")
        record_ash("read")
        record_ash("edit")
        record_ash("search")
        r = ratio()
        assert r["fire"] == 2
        assert r["ash"] == 3
        assert r["total"] == 5
        assert r["ratio"] == 0.6

    def test_first_period_trend(self):
        record_fire("test")
        record_ash("read")
        r = ratio()
        assert r["trend"] == "first period"


class TestByAbility:

    def test_empty(self):
        assert by_ability() == []

    def test_counts_abilities(self):
        record_ash("read")
        record_ash("read")
        record_ash("edit")
        result = by_ability()
        assert len(result) == 2
        assert result[0]["ability"] == "read"
        assert result[0]["count"] == 2

    def test_tracks_success_rate(self):
        record_ash("edit", success=True)
        record_ash("edit", success=True)
        record_ash("edit", success=False)
        result = by_ability()
        assert len(result) == 1
        assert result[0]["success_rate"] == 0.67


class TestByLegend:

    def test_empty(self):
        assert by_legend() == []

    def test_counts_legends(self):
        record_fire("a", legend="creator", tokens=100)
        record_fire("b", legend="creator", tokens=200)
        record_fire("c", legend="friend", tokens=50)
        result = by_legend()
        assert len(result) == 2
        assert result[0]["legend"] == "creator"
        assert result[0]["calls"] == 2
        assert result[0]["total_tokens"] == 300


class TestForges:

    def test_empty(self):
        assert forges() == []

    def test_lists_forges(self):
        record_forge("git")
        record_forge("test")
        result = forges()
        assert len(result) == 2


class TestDashboard:

    def test_empty_dashboard(self):
        d = dashboard()
        assert d["period_days"] == 7
        assert "no data" in d["message"]

    def test_populated_dashboard(self):
        record_fire("a")
        record_ash("read")
        record_ash("edit")
        record_forge("git")
        d = dashboard()
        assert d["fire_ash_ratio"]["total"] == 3
        assert len(d["by_ability"]) == 2
        assert d["forges_30d"] == 1


class TestDashboardMessage:

    def test_no_data(self):
        msg = _dashboard_message({"total": 0, "ratio": 0, "trend": "no data",
                                   "prev_ratio": 0, "fire": 0, "ash": 0})
        assert "no data" in msg

    def test_converging(self):
        msg = _dashboard_message({"total": 10, "ratio": 0.7, "trend": "converging",
                                   "prev_ratio": 0.5, "fire": 3, "ash": 7})
        assert "converging" in msg
        assert "70%" in msg

    def test_diverging(self):
        msg = _dashboard_message({"total": 10, "ratio": 0.3, "trend": "diverging",
                                   "prev_ratio": 0.5, "fire": 7, "ash": 3})
        assert "more fire" in msg

    def test_stable(self):
        msg = _dashboard_message({"total": 10, "ratio": 0.5, "trend": "stable",
                                   "prev_ratio": 0.5, "fire": 5, "ash": 5})
        assert "stable" in msg
