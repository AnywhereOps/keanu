"""tests for structured diff analysis."""

from keanu.tools.diff import (
    parse_diff, diff_stats, find_moved_code, classify_change,
    format_diff_summary, FileDiff, Hunk, DiffStats,
)


SAMPLE_DIFF = """diff --git a/main.py b/main.py
--- a/main.py
+++ b/main.py
@@ -1,5 +1,6 @@ def main():
-    print("hello")
+    print("hello world")
+    print("goodbye")
"""

MULTI_FILE_DIFF = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,3 +1,4 @@
 x = 1
+y = 2
 z = 3
diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1,3 @@
+def hello():
+    pass
+
diff --git a/old.py b/old.py
deleted file mode 100644
--- a/old.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def goodbye():
-    pass
"""


class TestParseDiff:

    def test_basic(self):
        files = parse_diff(SAMPLE_DIFF)
        assert len(files) == 1
        assert files[0].path == "main.py"
        assert files[0].additions == 2
        assert files[0].deletions == 1

    def test_multi_file(self):
        files = parse_diff(MULTI_FILE_DIFF)
        assert len(files) == 3

    def test_new_file(self):
        files = parse_diff(MULTI_FILE_DIFF)
        new = next(f for f in files if f.path == "new.py")
        assert new.status == "added"
        assert new.additions == 3

    def test_deleted_file(self):
        files = parse_diff(MULTI_FILE_DIFF)
        old = next(f for f in files if f.path == "old.py")
        assert old.status == "deleted"
        assert old.deletions == 2

    def test_hunks(self):
        files = parse_diff(SAMPLE_DIFF)
        assert len(files[0].hunks) == 1
        hunk = files[0].hunks[0]
        assert len(hunk.added_lines) == 2
        assert len(hunk.removed_lines) == 1

    def test_rename(self):
        diff = """diff --git a/old.py b/new.py
rename from old.py
rename to new.py
"""
        files = parse_diff(diff)
        assert len(files) == 1
        assert files[0].is_rename
        assert files[0].path == "new.py"
        assert files[0].old_path == "old.py"

    def test_empty(self):
        assert parse_diff("") == []


class TestDiffStats:

    def test_basic(self):
        files = parse_diff(MULTI_FILE_DIFF)
        stats = diff_stats(files)
        assert stats.files_changed == 3
        assert stats.files_added == 1
        assert stats.files_deleted == 1
        assert stats.files_modified == 1

    def test_totals(self):
        files = parse_diff(SAMPLE_DIFF)
        stats = diff_stats(files)
        assert stats.additions == 2
        assert stats.deletions == 1
        assert stats.total_changes == 3

    def test_summary(self):
        files = parse_diff(SAMPLE_DIFF)
        stats = diff_stats(files)
        summary = stats.summary()
        assert "1 files changed" in summary
        assert "insertions" in summary


class TestFindMovedCode:

    def test_detects_move(self):
        files = [
            FileDiff(
                path="old.py",
                status="modified",
                hunks=[Hunk(
                    old_start=1, old_count=5, new_start=1, new_count=0,
                    removed_lines=["def foo():", "    return 1", "    # done", ""],
                )],
                deletions=4,
            ),
            FileDiff(
                path="new.py",
                status="modified",
                hunks=[Hunk(
                    old_start=1, old_count=0, new_start=1, new_count=5,
                    added_lines=["def foo():", "    return 1", "    # done", ""],
                )],
                additions=4,
            ),
        ]
        moves = find_moved_code(files)
        assert len(moves) >= 1
        assert moves[0]["from"] == "old.py"
        assert moves[0]["to"] == "new.py"

    def test_no_moves(self):
        files = [
            FileDiff(
                path="a.py",
                hunks=[Hunk(old_start=1, old_count=1, new_start=1, new_count=1,
                            added_lines=["x = 1"])],
                additions=1,
            ),
        ]
        moves = find_moved_code(files)
        assert len(moves) == 0


class TestClassifyChange:

    def test_new_feature(self):
        f = FileDiff(path="feature.py", status="added")
        assert classify_change(f) == "new_feature"

    def test_test(self):
        f = FileDiff(path="tests/test_foo.py", status="modified", additions=5, deletions=2)
        assert classify_change(f) == "test"

    def test_docs(self):
        f = FileDiff(path="README.md", status="modified", additions=3, deletions=1)
        assert classify_change(f) == "docs"

    def test_config(self):
        f = FileDiff(path="config.yaml", status="modified", additions=1, deletions=1)
        assert classify_change(f) == "config"

    def test_removal(self):
        f = FileDiff(path="old.py", status="deleted")
        assert classify_change(f) == "removal"

    def test_pure_addition(self):
        f = FileDiff(path="new_code.py", status="modified", additions=10, deletions=0)
        assert classify_change(f) == "new_feature"

    def test_refactor(self):
        f = FileDiff(
            path="module.py", status="modified", additions=10, deletions=10,
            hunks=[Hunk(old_start=1, old_count=10, new_start=1, new_count=10,
                        added_lines=["# refactored"], removed_lines=["# old"])],
        )
        assert classify_change(f) == "refactor"


class TestFormatSummary:

    def test_basic(self):
        files = parse_diff(SAMPLE_DIFF)
        summary = format_diff_summary(files)
        assert "main.py" in summary
        assert "+2" in summary

    def test_multi(self):
        files = parse_diff(MULTI_FILE_DIFF)
        summary = format_diff_summary(files)
        assert "3 files changed" in summary
