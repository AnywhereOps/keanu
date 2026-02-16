"""tests for git hook management."""

import os
import stat

from keanu.data.githooks import (
    list_hooks, install_hook, uninstall_hook, install_all,
    validate_commit_message, suggest_commit_type,
    is_git_repo, hooks_dir, HOOK_TYPES,
    HookConfig, HookResult,
)


class TestIsGitRepo:

    def test_is_repo(self, tmp_path):
        (tmp_path / ".git").mkdir()
        assert is_git_repo(str(tmp_path))

    def test_not_repo(self, tmp_path):
        assert not is_git_repo(str(tmp_path))


class TestListHooks:

    def test_empty(self, tmp_path):
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        assert list_hooks(str(tmp_path)) == []

    def test_finds_hooks(self, tmp_path):
        hdir = tmp_path / ".git" / "hooks"
        hdir.mkdir(parents=True)
        hook = hdir / "pre-commit"
        hook.write_text("#!/bin/sh\n# keanu pre-commit\necho hi\n")
        hook.chmod(hook.stat().st_mode | stat.S_IEXEC)

        hooks = list_hooks(str(tmp_path))
        assert len(hooks) == 1
        assert hooks[0]["type"] == "pre-commit"
        assert hooks[0]["keanu_managed"]

    def test_skips_samples(self, tmp_path):
        hdir = tmp_path / ".git" / "hooks"
        hdir.mkdir(parents=True)
        (hdir / "pre-commit.sample").write_text("# sample\n")
        assert list_hooks(str(tmp_path)) == []


class TestInstallHook:

    def test_install_pre_commit(self, tmp_path):
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        path = install_hook("pre-commit", str(tmp_path))
        assert os.path.exists(path)
        content = open(path).read()
        assert "keanu" in content
        assert os.access(path, os.X_OK)

    def test_install_commit_msg(self, tmp_path):
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        path = install_hook("commit-msg", str(tmp_path))
        content = open(path).read()
        assert "conventional" in content.lower()

    def test_install_pre_push(self, tmp_path):
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        path = install_hook("pre-push", str(tmp_path))
        content = open(path).read()
        assert "pytest" in content

    def test_custom_commands(self, tmp_path):
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        path = install_hook("pre-commit", str(tmp_path),
                           commands=["echo 'custom check'"])
        content = open(path).read()
        assert "custom check" in content

    def test_refuses_non_git(self, tmp_path):
        try:
            install_hook("pre-commit", str(tmp_path))
            assert False
        except ValueError:
            pass

    def test_refuses_unknown_type(self, tmp_path):
        (tmp_path / ".git").mkdir()
        try:
            install_hook("unknown-hook", str(tmp_path))
            assert False
        except ValueError:
            pass

    def test_refuses_overwrite_non_keanu(self, tmp_path):
        hdir = tmp_path / ".git" / "hooks"
        hdir.mkdir(parents=True)
        (hdir / "pre-commit").write_text("#!/bin/sh\necho 'external hook'\n")
        try:
            install_hook("pre-commit", str(tmp_path))
            assert False
        except FileExistsError:
            pass

    def test_force_overwrite(self, tmp_path):
        hdir = tmp_path / ".git" / "hooks"
        hdir.mkdir(parents=True)
        (hdir / "pre-commit").write_text("#!/bin/sh\necho 'external hook'\n")
        path = install_hook("pre-commit", str(tmp_path), force=True)
        content = open(path).read()
        assert "keanu" in content


class TestUninstallHook:

    def test_uninstall(self, tmp_path):
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        install_hook("pre-commit", str(tmp_path))
        assert uninstall_hook("pre-commit", str(tmp_path))

    def test_uninstall_nonexistent(self, tmp_path):
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        assert not uninstall_hook("pre-commit", str(tmp_path))

    def test_refuses_non_keanu(self, tmp_path):
        hdir = tmp_path / ".git" / "hooks"
        hdir.mkdir(parents=True)
        (hdir / "pre-commit").write_text("#!/bin/sh\necho 'external hook'\n")
        assert not uninstall_hook("pre-commit", str(tmp_path))


class TestInstallAll:

    def test_installs_recommended(self, tmp_path):
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        paths = install_all(str(tmp_path))
        assert len(paths) == 3  # pre-commit, commit-msg, pre-push


class TestValidateCommitMessage:

    def test_valid_feat(self):
        ok, err = validate_commit_message("feat: add login")
        assert ok

    def test_valid_fix_with_scope(self):
        ok, err = validate_commit_message("fix(auth): repair token refresh")
        assert ok

    def test_valid_breaking(self):
        ok, err = validate_commit_message("feat!: remove old API")
        assert ok

    def test_invalid_no_type(self):
        ok, err = validate_commit_message("add login feature")
        assert not ok

    def test_invalid_empty(self):
        ok, err = validate_commit_message("")
        assert not ok

    def test_too_long(self):
        ok, err = validate_commit_message("feat: " + "x" * 70)
        assert not ok
        assert "too long" in err

    def test_all_types(self):
        types = ["feat", "fix", "docs", "style", "refactor", "perf",
                 "test", "chore", "ci", "build", "revert"]
        for t in types:
            ok, _ = validate_commit_message(f"{t}: test message")
            assert ok, f"type '{t}' should be valid"


class TestSuggestCommitType:

    def test_test(self):
        assert suggest_commit_type("add test for login") == "test"

    def test_docs(self):
        assert suggest_commit_type("update README") == "docs"

    def test_fix(self):
        assert suggest_commit_type("fix login bug") == "fix"

    def test_refactor(self):
        assert suggest_commit_type("refactor auth module") == "refactor"

    def test_default(self):
        assert suggest_commit_type("add new stuff") == "feat"
