"""Tests for the git ability."""

import subprocess
import pytest
from unittest.mock import patch, MagicMock

from keanu.abilities.hands.git import (
    GitAbility, _git,
    _op_status, _op_diff, _op_log, _op_blame,
    _op_branch, _op_stash, _op_add, _op_commit, _op_show,
)


# ============================================================
# REGISTRATION
# ============================================================

class TestGitRegistration:

    def test_registered(self):
        from keanu.abilities import _REGISTRY
        assert "git" in _REGISTRY

    def test_can_handle_returns_false(self):
        ab = GitAbility()
        can, conf = ab.can_handle("git status")
        assert can is False

    def test_has_cast_line(self):
        ab = GitAbility()
        assert ab.cast_line.endswith("...")


# ============================================================
# _git helper
# ============================================================

class TestGitHelper:

    @patch("keanu.abilities.hands.git.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="main\n", stderr=""
        )
        ok, out = _git("branch", "--show-current")
        assert ok is True
        assert out == "main"

    @patch("keanu.abilities.hands.git.subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="fatal: not a git repo"
        )
        ok, out = _git("status")
        assert ok is False
        assert "not a git repo" in out

    @patch("keanu.abilities.hands.git.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=15)
        ok, out = _git("log")
        assert ok is False
        assert "timed out" in out

    @patch("keanu.abilities.hands.git.subprocess.run")
    def test_git_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        ok, out = _git("status")
        assert ok is False
        assert "not found" in out


# ============================================================
# STATUS
# ============================================================

class TestGitStatus:

    @patch("keanu.abilities.hands.git._git")
    def test_clean(self, mock_git):
        mock_git.side_effect = [
            (True, ""),           # status --short
            (True, "main"),       # branch --show-current
        ]
        result = _op_status({})
        assert result["success"] is True
        assert "clean" in result["result"]
        assert result["data"]["branch"] == "main"
        assert result["data"]["clean"] is True

    @patch("keanu.abilities.hands.git._git")
    def test_dirty(self, mock_git):
        mock_git.side_effect = [
            (True, " M src/foo.py\n?? new.py"),
            (True, "feature"),
        ]
        result = _op_status({})
        assert result["success"] is True
        assert "feature" in result["result"]
        assert "foo.py" in result["result"]
        assert result["data"]["clean"] is False

    @patch("keanu.abilities.hands.git._git")
    def test_status_error(self, mock_git):
        mock_git.return_value = (False, "fatal: not a git repo")
        result = _op_status({})
        assert result["success"] is False


# ============================================================
# DIFF
# ============================================================

class TestGitDiff:

    @patch("keanu.abilities.hands.git._git")
    def test_no_changes(self, mock_git):
        mock_git.return_value = (True, "")
        result = _op_diff({})
        assert result["success"] is True
        assert "no unstaged" in result["result"]
        assert result["data"]["empty"] is True

    @patch("keanu.abilities.hands.git._git")
    def test_staged(self, mock_git):
        mock_git.return_value = (True, "")
        result = _op_diff({"staged": True})
        assert "no staged" in result["result"]

    @patch("keanu.abilities.hands.git._git")
    def test_with_changes(self, mock_git):
        mock_git.return_value = (True, "+new line\n-old line")
        result = _op_diff({})
        assert result["success"] is True
        assert "+new line" in result["result"]

    @patch("keanu.abilities.hands.git._git")
    def test_specific_file(self, mock_git):
        mock_git.return_value = (True, "+changed")
        _op_diff({"file": "foo.py"})
        mock_git.assert_called_with("diff", "--", "foo.py")

    @patch("keanu.abilities.hands.git._git")
    def test_truncates_large_diff(self, mock_git):
        mock_git.return_value = (True, "x" * 10000)
        result = _op_diff({})
        assert "truncated" in result["result"]


# ============================================================
# LOG
# ============================================================

class TestGitLog:

    @patch("keanu.abilities.hands.git._git")
    def test_default(self, mock_git):
        mock_git.return_value = (True, "abc123 some commit (drew, 2h ago)")
        result = _op_log({})
        assert result["success"] is True
        assert "abc123" in result["result"]

    @patch("keanu.abilities.hands.git._git")
    def test_custom_count(self, mock_git):
        mock_git.return_value = (True, "log output")
        result = _op_log({"n": 5})
        assert result["data"]["count"] == 5


# ============================================================
# BLAME
# ============================================================

class TestGitBlame:

    def test_no_file(self):
        result = _op_blame({})
        assert result["success"] is False
        assert "No file" in result["result"]

    @patch("keanu.abilities.hands.git._git")
    def test_blame_file(self, mock_git):
        mock_git.return_value = (True, "abc123 (drew 2024-01-01) line 1")
        result = _op_blame({"file": "foo.py"})
        assert result["success"] is True
        assert result["data"]["file"] == "foo.py"


# ============================================================
# BRANCH
# ============================================================

class TestGitBranch:

    @patch("keanu.abilities.hands.git._git")
    def test_list(self, mock_git):
        mock_git.return_value = (True, "* main\n  feature")
        result = _op_branch({"sub": "list"})
        assert result["success"] is True
        assert "main" in result["result"]

    @patch("keanu.abilities.hands.git._git")
    def test_create(self, mock_git):
        mock_git.return_value = (True, "")
        result = _op_branch({"sub": "create", "name": "feat/new"})
        assert result["success"] is True
        assert "feat/new" in result["result"]

    def test_create_no_name(self):
        result = _op_branch({"sub": "create"})
        assert result["success"] is False

    @patch("keanu.abilities.hands.git._git")
    def test_switch(self, mock_git):
        mock_git.return_value = (True, "")
        result = _op_branch({"sub": "switch", "name": "main"})
        assert result["success"] is True

    def test_unknown_sub(self):
        result = _op_branch({"sub": "nope"})
        assert result["success"] is False


# ============================================================
# STASH
# ============================================================

class TestGitStash:

    @patch("keanu.abilities.hands.git._git")
    def test_save(self, mock_git):
        mock_git.return_value = (True, "Saved working directory")
        result = _op_stash({"sub": "save"})
        assert result["success"] is True

    @patch("keanu.abilities.hands.git._git")
    def test_save_with_message(self, mock_git):
        mock_git.return_value = (True, "")
        _op_stash({"sub": "save", "message": "wip"})
        mock_git.assert_called_with("stash", "push", "-m", "wip")

    @patch("keanu.abilities.hands.git._git")
    def test_pop(self, mock_git):
        mock_git.return_value = (True, "")
        result = _op_stash({"sub": "pop"})
        assert result["success"] is True

    @patch("keanu.abilities.hands.git._git")
    def test_list(self, mock_git):
        mock_git.return_value = (True, "")
        result = _op_stash({"sub": "list"})
        assert "no stashes" in result["result"]


# ============================================================
# ADD + COMMIT
# ============================================================

class TestGitAddCommit:

    def test_add_no_files(self):
        result = _op_add({})
        assert result["success"] is False

    @patch("keanu.abilities.hands.git._git")
    def test_add_files(self, mock_git):
        mock_git.return_value = (True, "")
        result = _op_add({"files": ["a.py", "b.py"]})
        assert result["success"] is True
        assert "a.py" in result["result"]

    def test_commit_no_message(self):
        result = _op_commit({})
        assert result["success"] is False

    @patch("keanu.abilities.hands.git._git")
    def test_commit(self, mock_git):
        mock_git.return_value = (True, "[main abc123] fix bug")
        result = _op_commit({"message": "fix bug"})
        assert result["success"] is True


# ============================================================
# SHOW
# ============================================================

class TestGitShow:

    @patch("keanu.abilities.hands.git._git")
    def test_show_head(self, mock_git):
        mock_git.return_value = (True, "commit abc123\nAuthor: drew")
        result = _op_show({})
        assert result["success"] is True
        assert result["data"]["ref"] == "HEAD"


# ============================================================
# EXECUTE DISPATCH
# ============================================================

class TestGitExecute:

    @patch("keanu.abilities.hands.git._git")
    def test_dispatches_status(self, mock_git):
        mock_git.side_effect = [(True, ""), (True, "main")]
        ab = GitAbility()
        result = ab.execute("", {"op": "status"})
        assert result["success"] is True
        assert "main" in result["result"]

    def test_unknown_op(self):
        ab = GitAbility()
        result = ab.execute("", {"op": "rebase"})
        assert result["success"] is False
        assert "Unknown git op" in result["result"]

    @patch("keanu.abilities.hands.git._git")
    def test_default_op_is_status(self, mock_git):
        mock_git.side_effect = [(True, ""), (True, "main")]
        ab = GitAbility()
        result = ab.execute("", {})
        assert result["success"] is True
        assert "main" in result["result"]
