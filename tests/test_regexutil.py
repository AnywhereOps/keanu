"""Tests for regexutil.py - regex pattern analysis and testing."""

import re

from keanu.tools.regexutil import (
    MatchInfo,
    RegexMatch,
    common_patterns,
    escape_for_literal,
    explain_pattern,
    find_in_files,
    suggest_pattern,
    check_pattern,
    validate_pattern,
)


class TestTestPattern:
    def test_simple_match(self):
        r = check_pattern(r"\d+", "abc 123 def 456")
        assert len(r.matches) == 2
        assert r.matches[0].full_match == "123"
        assert r.matches[1].full_match == "456"

    def test_no_match(self):
        r = check_pattern(r"\d+", "no digits here")
        assert r.matches == []

    def test_groups(self):
        r = check_pattern(r"(\w+)@(\w+)", "user@host")
        assert r.matches[0].groups == ("user", "host")

    def test_named_groups(self):
        r = check_pattern(r"(?P<name>\w+)=(?P<val>\w+)", "key=value")
        m = r.matches[0]
        assert m.named_groups == {"name": "key", "val": "value"}

    def test_positions(self):
        r = check_pattern(r"cat", "the cat sat")
        m = r.matches[0]
        assert m.start == 4
        assert m.end == 7

    def test_multiline(self):
        text = "line one\nline two\nline three"
        r = check_pattern(r"line \w+", text)
        assert len(r.matches) == 3
        assert r.matches[0].line_number == 1
        assert r.matches[1].line_number == 2
        assert r.matches[2].line_number == 3

    def test_flags_case_insensitive(self):
        r = check_pattern(r"hello", "Hello HELLO hello", re.IGNORECASE)
        assert len(r.matches) == 3
        assert r.flags == re.IGNORECASE

    def test_result_stores_pattern_and_text(self):
        r = check_pattern(r"x", "x")
        assert r.pattern == "x"
        assert r.text == "x"


class TestExplainPattern:
    def test_dot(self):
        exps = explain_pattern(".")
        assert any("any character" in e for e in exps)

    def test_digit(self):
        exps = explain_pattern(r"\d+")
        assert any("digit" in e for e in exps)
        assert any("one or more" in e for e in exps)

    def test_anchor(self):
        exps = explain_pattern(r"^foo$")
        assert any("start" in e for e in exps)
        assert any("end" in e for e in exps)

    def test_named_group(self):
        exps = explain_pattern(r"(?P<id>\d+)")
        assert any("id" in e for e in exps)

    def test_lookahead(self):
        exps = explain_pattern(r"foo(?=bar)")
        assert any("lookahead" in e for e in exps)

    def test_lookbehind(self):
        exps = explain_pattern(r"(?<=x)y")
        assert any("lookbehind" in e for e in exps)

    def test_character_class(self):
        exps = explain_pattern(r"[abc]")
        assert any("abc" in e for e in exps)

    def test_negated_class(self):
        exps = explain_pattern(r"[^0-9]")
        assert any("NOT" in e for e in exps)

    def test_quantifier_range(self):
        exps = explain_pattern(r"a{2,5}")
        assert any("2" in e and "5" in e for e in exps)

    def test_alternation(self):
        exps = explain_pattern(r"cat|dog")
        assert any("OR" in e for e in exps)

    def test_word_boundary(self):
        exps = explain_pattern(r"\b")
        assert any("word boundary" in e for e in exps)

    def test_non_capturing(self):
        exps = explain_pattern(r"(?:abc)")
        assert any("non-capturing" in e for e in exps)

    def test_lazy_quantifier(self):
        exps = explain_pattern(r".*?")
        assert any("lazy" in e for e in exps)


class TestValidatePattern:
    def test_valid(self):
        ok, msg = validate_pattern(r"\d{3}-\d{4}")
        assert ok is True
        assert msg == ""

    def test_invalid_unbalanced(self):
        ok, msg = validate_pattern(r"(unclosed")
        assert ok is False
        assert msg  # has an error message

    def test_invalid_quantifier(self):
        ok, msg = validate_pattern(r"*bad")
        assert ok is False


class TestCommonPatterns:
    def test_all_patterns_compile(self):
        for name, pat in common_patterns().items():
            re.compile(pat)  # should not raise

    def test_email(self):
        assert re.search(common_patterns()["email"], "hi user@example.com bye")

    def test_url(self):
        assert re.search(common_patterns()["url"], "visit https://example.com/path")

    def test_ipv4(self):
        assert re.search(common_patterns()["ipv4"], "server at 192.168.1.1 ok")

    def test_date_iso(self):
        assert re.search(common_patterns()["date_iso"], "date: 2026-02-16")

    def test_uuid(self):
        assert re.search(
            common_patterns()["uuid"],
            "id: 550e8400-e29b-41d4-a716-446655440000",
        )

    def test_semver(self):
        assert re.search(common_patterns()["semver"], "version v1.2.3-beta")

    def test_phone(self):
        assert re.search(common_patterns()["phone_us"], "call 555-867-5309")


class TestSuggestPattern:
    def test_common_prefix_suffix(self):
        pat = suggest_pattern(["test_foo.py", "test_bar.py", "test_baz.py"])
        compiled = re.compile(f"^{pat}$")
        for ex in ["test_foo.py", "test_bar.py", "test_baz.py"]:
            assert compiled.match(ex), f"should match {ex}"

    def test_digits(self):
        pat = suggest_pattern(["id-001", "id-042", "id-999"])
        compiled = re.compile(f"^{pat}$")
        assert compiled.match("id-123")

    def test_empty_returns_wildcard(self):
        assert suggest_pattern([]) == ".*"

    def test_single_example(self):
        pat = suggest_pattern(["hello"])
        assert re.match(f"^{pat}$", "hello")


class TestFindInFiles:
    def test_finds_matches(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f1.write_text("foo 123\nbar 456\n")
        f2 = tmp_path / "b.txt"
        f2.write_text("no match here\n")
        f3 = tmp_path / "c.txt"
        f3.write_text("789 baz\n")

        results = find_in_files(r"\d+", [str(f1), str(f2), str(f3)])
        assert str(f1) in results
        assert str(f2) not in results
        assert str(f3) in results
        assert len(results[str(f1)]) == 2
        assert results[str(f1)][0].line_number == 1
        assert results[str(f1)][1].line_number == 2

    def test_missing_file_skipped(self, tmp_path):
        results = find_in_files(r"x", [str(tmp_path / "nope.txt")])
        assert results == {}


class TestEscapeForLiteral:
    def test_escapes_special_chars(self):
        text = "hello.world(1+2)"
        escaped = escape_for_literal(text)
        assert re.match(escaped, text)
        assert not re.match(escaped, "helloXworld(1+2)")

    def test_plain_text_unchanged_match(self):
        text = "simple"
        escaped = escape_for_literal(text)
        assert re.match(escaped, text)
