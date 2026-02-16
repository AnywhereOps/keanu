"""Tests for fixtures.py - fake data generation."""

import json
import os
import re
import tempfile
from datetime import date

from keanu.gen.fixtures import (
    Fixture,
    fake_address,
    fake_bool,
    fake_choice,
    fake_csv,
    fake_date,
    fake_email,
    fake_int,
    fake_json,
    fake_name,
    fake_phone,
    fake_sql_inserts,
    fake_text,
    fake_uuid,
    load_fixture,
    save_fixture,
    seed,
)


class TestSeed:
    def test_reproducible(self):
        seed(99)
        a = fake_name()
        seed(99)
        b = fake_name()
        assert a == b

    def test_different_seeds_differ(self):
        seed(1)
        a = fake_name()
        seed(2)
        b = fake_name()
        assert a != b


class TestFakeName:
    def test_returns_string(self):
        assert isinstance(fake_name(), str)

    def test_has_two_parts(self):
        parts = fake_name().split()
        assert len(parts) == 2


class TestFakeEmail:
    def test_has_at_sign(self):
        assert "@" in fake_email()

    def test_from_name(self):
        email = fake_email("John Doe")
        assert email.startswith("john.doe@")

    def test_random_when_no_name(self):
        email = fake_email()
        assert "@" in email
        assert "." in email.split("@")[0]


class TestFakePhone:
    def test_format(self):
        phone = fake_phone()
        assert re.match(r"\(\d{3}\) \d{3}-\d{4}", phone)


class TestFakeAddress:
    def test_keys(self):
        addr = fake_address()
        assert set(addr.keys()) == {"street", "city", "state", "zip"}

    def test_zip_is_5_digits(self):
        addr = fake_address()
        assert re.match(r"\d{5}", addr["zip"])


class TestFakeUuid:
    def test_format(self):
        u = fake_uuid()
        assert re.match(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}",
            u,
        )


class TestFakeDate:
    def test_within_range(self):
        d = fake_date("2023-01-01", "2023-12-31")
        parsed = date.fromisoformat(d)
        assert date(2023, 1, 1) <= parsed <= date(2023, 12, 31)

    def test_default_range(self):
        d = fake_date()
        parsed = date.fromisoformat(d)
        assert date(2020, 1, 1) <= parsed <= date(2026, 12, 31)

    def test_same_start_end(self):
        d = fake_date("2023-06-15", "2023-06-15")
        assert d == "2023-06-15"


class TestFakeText:
    def test_word_count(self):
        t = fake_text(5)
        # ends with period, strip it
        words = t.rstrip(".").split()
        assert len(words) == 5

    def test_capitalized(self):
        t = fake_text(3)
        assert t[0].isupper()

    def test_ends_with_period(self):
        assert fake_text().endswith(".")


class TestFakeInt:
    def test_in_range(self):
        for _ in range(50):
            v = fake_int(10, 20)
            assert 10 <= v <= 20


class TestFakeChoice:
    def test_from_list(self):
        options = ["a", "b", "c"]
        assert fake_choice(options) in options


class TestFakeBool:
    def test_returns_bool(self):
        assert isinstance(fake_bool(), bool)

    def test_always_true(self):
        for _ in range(20):
            assert fake_bool(true_pct=1.0) is True

    def test_always_false(self):
        for _ in range(20):
            assert fake_bool(true_pct=0.0) is False


class TestFakeJson:
    def test_flat_schema(self):
        schema = {"id": "int", "name": "name", "email": "email"}
        result = fake_json(schema)
        assert isinstance(result["id"], int)
        assert isinstance(result["name"], str)
        assert "@" in result["email"]

    def test_nested_schema(self):
        schema = {
            "user": {"name": "name", "age": "int"},
            "active": "bool",
        }
        result = fake_json(schema)
        assert isinstance(result["user"], dict)
        assert isinstance(result["user"]["name"], str)
        assert isinstance(result["user"]["age"], int)
        assert isinstance(result["active"], bool)

    def test_list_schema(self):
        schema = {"tags": ["string"], "scores": ["int"]}
        result = fake_json(schema)
        assert isinstance(result["tags"], list)
        assert all(isinstance(t, str) for t in result["tags"])
        assert isinstance(result["scores"], list)
        assert all(isinstance(s, int) for s in result["scores"])


class TestFakeCsv:
    def test_row_count(self):
        cols = [{"name": "id", "type": "int"}, {"name": "name", "type": "name"}]
        output = fake_csv(cols, rows=5)
        lines = output.strip().split("\n")
        assert len(lines) == 6  # header + 5 rows

    def test_header(self):
        cols = [{"name": "x", "type": "int"}, {"name": "y", "type": "string"}]
        output = fake_csv(cols, rows=1)
        header = output.strip().split("\n")[0]
        assert "x" in header and "y" in header


class TestFakeSqlInserts:
    def test_count(self):
        cols = [{"name": "id", "type": "int"}]
        output = fake_sql_inserts("users", cols, rows=3)
        lines = output.strip().split("\n")
        assert len(lines) == 3

    def test_table_name(self):
        cols = [{"name": "val", "type": "string"}]
        output = fake_sql_inserts("items", cols, rows=1)
        assert "INSERT INTO items" in output

    def test_values_present(self):
        cols = [{"name": "id", "type": "int"}, {"name": "name", "type": "name"}]
        output = fake_sql_inserts("t", cols, rows=1)
        assert "VALUES" in output
        assert ";" in output


class TestFixtureSaveLoad:
    def test_json_roundtrip(self):
        fix = Fixture(
            name="test",
            columns=["id", "name"],
            data=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_fixture(fix, path, fmt="json")
            loaded = load_fixture(path)
            assert loaded.name == "test"
            assert loaded.columns == ["id", "name"]
            assert loaded.data == fix.data
        finally:
            os.unlink(path)

    def test_csv_roundtrip(self):
        fix = Fixture(
            name="test",
            columns=["id", "name"],
            data=[{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}],
        )
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            save_fixture(fix, path, fmt="csv")
            loaded = load_fixture(path)
            assert loaded.columns == ["id", "name"]
            assert len(loaded.data) == 2
            assert loaded.data[0]["name"] == "Alice"
        finally:
            os.unlink(path)
