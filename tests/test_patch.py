"""tests for multi-file patch ability."""

from unittest.mock import patch

from keanu.abilities.hands.patch import (
    apply_patch, parse_patch_args, FileEdit, PatchResult, PatchAbility,
)


class TestFileEdit:

    def test_defaults(self):
        e = FileEdit(file_path="f.py", old_string="a", new_string="b")
        assert e.file_path == "f.py"


class TestApplyPatch:

    def test_single_edit(self, tmp_path):
        f = tmp_path / "foo.py"
        f.write_text("x = 1\ny = 2\n")
        edits = [FileEdit(str(f), "x = 1", "x = 10")]
        result = apply_patch(edits)
        assert result.success
        assert result.edits_applied == 1
        assert "x = 10" in f.read_text()

    def test_multi_file_edit(self, tmp_path):
        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("old_a")
        b.write_text("old_b")
        edits = [
            FileEdit(str(a), "old_a", "new_a"),
            FileEdit(str(b), "old_b", "new_b"),
        ]
        result = apply_patch(edits)
        assert result.success
        assert a.read_text() == "new_a"
        assert b.read_text() == "new_b"
        assert len(result.files_changed) == 2

    def test_multi_edit_same_file(self, tmp_path):
        f = tmp_path / "foo.py"
        f.write_text("aaa\nbbb\nccc\n")
        edits = [
            FileEdit(str(f), "aaa", "AAA"),
            FileEdit(str(f), "bbb", "BBB"),
        ]
        result = apply_patch(edits)
        assert result.success
        content = f.read_text()
        assert "AAA" in content
        assert "BBB" in content

    def test_rollback_on_missing_string(self, tmp_path):
        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("good")
        b.write_text("bad")
        edits = [
            FileEdit(str(a), "good", "changed"),
            FileEdit(str(b), "nonexistent", "nope"),
        ]
        result = apply_patch(edits)
        assert not result.success
        # a should NOT have been changed
        assert a.read_text() == "good"

    def test_rollback_on_duplicate_string(self, tmp_path):
        f = tmp_path / "foo.py"
        f.write_text("dup\ndup\n")
        edits = [FileEdit(str(f), "dup", "unique")]
        result = apply_patch(edits)
        assert not result.success
        assert "2 times" in result.errors[0]

    def test_dry_run(self, tmp_path):
        f = tmp_path / "foo.py"
        f.write_text("original")
        edits = [FileEdit(str(f), "original", "changed")]
        result = apply_patch(edits, dry_run=True)
        assert result.success
        assert result.edits_applied == 1
        # file should NOT be changed
        assert f.read_text() == "original"

    def test_empty_edits(self):
        result = apply_patch([])
        assert result.success

    def test_nonexistent_file(self):
        edits = [FileEdit("/nonexistent/file.py", "a", "b")]
        result = apply_patch(edits)
        assert not result.success
        assert "cannot read" in result.errors[0]


class TestParsePatchArgs:

    def test_parses_edits(self):
        args = {
            "edits": [
                {"file_path": "a.py", "old_string": "old", "new_string": "new"},
                {"file_path": "b.py", "old_string": "x", "new_string": "y"},
            ]
        }
        edits = parse_patch_args(args)
        assert len(edits) == 2
        assert edits[0].file_path == "a.py"

    def test_empty_args(self):
        assert parse_patch_args({}) == []

    def test_missing_fields(self):
        args = {"edits": [{"file_path": "a.py"}]}
        edits = parse_patch_args(args)
        assert len(edits) == 1
        assert edits[0].old_string == ""


class TestPatchAbility:

    def test_no_edits(self):
        ab = PatchAbility()
        result = ab.execute("", context={})
        assert not result["success"]

    def test_apply_edit(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("hello world")
        ab = PatchAbility()
        with patch("keanu.abilities.hands.hands._is_safe_path", return_value=True):
            result = ab.execute("", context={
                "edits": [
                    {"file_path": str(f), "old_string": "hello", "new_string": "goodbye"},
                ],
            })
        assert result["success"]
        assert f.read_text() == "goodbye world"

    def test_preview_mode(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("original")
        ab = PatchAbility()
        with patch("keanu.abilities.hands.hands._is_safe_path", return_value=True):
            result = ab.execute("", context={
                "preview": True,
                "edits": [
                    {"file_path": str(f), "old_string": "original", "new_string": "changed"},
                ],
            })
        assert result["success"]
        assert "preview" in result["result"]
        assert f.read_text() == "original"  # not changed
