"""tests for code review."""

from keanu.review import (
    review_diff, review_file, ReviewResult, Issue,
    _parse_diff, _check_line,
)


class TestParseDiff:

    def test_simple_diff(self):
        diff = """diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 x = 1
+y = 2
 z = 3
"""
        hunks = _parse_diff(diff)
        assert len(hunks) == 1
        assert hunks[0]["file"] == "foo.py"
        assert len(hunks[0]["additions"]) == 1
        assert hunks[0]["additions"][0][0] == "y = 2"

    def test_multi_file_diff(self):
        diff = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1 +1,2 @@
 x = 1
+y = 2
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -1 +1,2 @@
 a = 1
+b = 2
"""
        hunks = _parse_diff(diff)
        assert len(hunks) == 2
        assert hunks[0]["file"] == "a.py"
        assert hunks[1]["file"] == "b.py"


class TestCheckLine:

    def test_eval_security(self):
        issues = _check_line("result = eval(user_input)", "foo.py", 1)
        assert any(i.category == "security" for i in issues)
        assert any(i.severity == "critical" for i in issues)

    def test_os_system(self):
        issues = _check_line("os.system('rm -rf /')", "foo.py", 1)
        assert any("os.system" in i.message for i in issues)

    def test_hardcoded_password(self):
        issues = _check_line('password = "hunter2"', "foo.py", 1)
        assert any("password" in i.message.lower() for i in issues)

    def test_range_len(self):
        issues = _check_line("for i in range(len(items)):", "foo.py", 1)
        assert any(i.category == "performance" for i in issues)

    def test_bare_except(self):
        issues = _check_line("except:", "foo.py", 1)
        assert any(i.category == "performance" for i in issues)

    def test_none_comparison(self):
        issues = _check_line("if x == None:", "foo.py", 1)
        assert any(i.category == "logic" for i in issues)

    def test_print_statement(self):
        issues = _check_line('print("debug")', "foo.py", 1)
        assert any(i.category == "style" for i in issues)

    def test_breakpoint(self):
        issues = _check_line("breakpoint()", "foo.py", 1)
        assert any(i.category == "style" for i in issues)

    def test_clean_line(self):
        issues = _check_line("x = calculate_result(data)", "foo.py", 1)
        assert len(issues) == 0

    def test_todo_comment(self):
        issues = _check_line("# TODO: fix this later", "foo.py", 1)
        assert any("TODO" in i.message for i in issues)


class TestReviewDiff:

    def test_finds_issues(self):
        diff = """diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,5 @@
 x = 1
+result = eval(data)
+password = "secret123"
 z = 3
"""
        result = review_diff(diff)
        assert len(result.issues) >= 2
        assert not result.ok  # has critical issues

    def test_clean_diff(self):
        diff = """diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 x = 1
+y = calculate(x)
 z = 3
"""
        result = review_diff(diff)
        assert result.ok


class TestReviewFile:

    def test_reviews_file(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("import os\nresult = eval(input())\npassword = 'secret'\n")
        result = review_file(str(f))
        assert len(result.issues) >= 2

    def test_clean_file(self, tmp_path):
        f = tmp_path / "good.py"
        f.write_text("x = 1\ny = x + 2\n")
        result = review_file(str(f))
        assert result.ok

    def test_nonexistent_file(self):
        result = review_file("/nonexistent/file.py")
        assert "could not read" in result.summary


class TestReviewResult:

    def test_ok_when_no_critical(self):
        r = ReviewResult(issues=[
            Issue(severity="warning", category="style", file="f", line=1, message="x"),
        ])
        assert r.ok

    def test_not_ok_when_critical(self):
        r = ReviewResult(issues=[
            Issue(severity="critical", category="security", file="f", line=1, message="x"),
        ])
        assert not r.ok

    def test_counts(self):
        r = ReviewResult(issues=[
            Issue(severity="critical", category="security", file="f", line=1, message="a"),
            Issue(severity="warning", category="logic", file="f", line=2, message="b"),
            Issue(severity="warning", category="perf", file="f", line=3, message="c"),
        ])
        assert r.critical_count == 1
        assert r.warning_count == 2
