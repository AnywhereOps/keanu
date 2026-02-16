"""tests for changelog generation."""

from unittest.mock import patch, MagicMock

from keanu.data.changelog import (
    CommitInfo, _guess_type,
    get_commits, get_tags, generate_changelog,
    generate_release_notes, commits_since_tag,
)


class TestCommitInfo:

    def test_conventional_commit(self):
        c = CommitInfo(hash="abc", short_hash="abc", subject="feat(auth): add login")
        assert c.commit_type == "feat"
        assert c.scope == "auth"
        assert c.subject == "add login"

    def test_breaking_bang(self):
        c = CommitInfo(hash="abc", short_hash="abc", subject="feat!: remove old api")
        assert c.breaking
        assert c.commit_type == "feat"

    def test_breaking_body(self):
        c = CommitInfo(hash="abc", short_hash="abc", subject="fix: update schema",
                       body="BREAKING CHANGE: field renamed")
        assert c.breaking

    def test_pr_number(self):
        c = CommitInfo(hash="abc", short_hash="abc", subject="feat: add auth #42")
        assert c.pr_number == "42"

    def test_no_conventional(self):
        c = CommitInfo(hash="abc", short_hash="abc", subject="add new feature")
        assert c.commit_type == "feat"

    def test_fix_detection(self):
        c = CommitInfo(hash="abc", short_hash="abc", subject="fix bug in login")
        assert c.commit_type == "fix"

    def test_scope_only(self):
        c = CommitInfo(hash="abc", short_hash="abc", subject="refactor(core): simplify loop")
        assert c.scope == "core"
        assert c.commit_type == "refactor"


class TestGuessType:

    def test_fix(self):
        assert _guess_type("fix broken test") == "fix"
        assert _guess_type("bugfix for login") == "fix"

    def test_feat(self):
        assert _guess_type("add new feature") == "feat"
        assert _guess_type("implement auth") == "feat"

    def test_docs(self):
        assert _guess_type("update README") == "docs"

    def test_test(self):
        assert _guess_type("test coverage for parser") == "test"

    def test_refactor(self):
        assert _guess_type("refactor login module") == "refactor"

    def test_build(self):
        assert _guess_type("bump dep versions") == "build"

    def test_unknown(self):
        assert _guess_type("misc stuff") == "chore"


class TestGetCommits:

    def test_with_mock(self, tmp_path):
        output = "abc123\nabc\nfeat: add login\n\nDrew\n2024-01-01 00:00:00\n---END---\n"
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout=output)
            commits = get_commits(str(tmp_path))
            assert len(commits) >= 1
            assert commits[0].subject == "add login"

    def test_empty(self, tmp_path):
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="")
            commits = get_commits(str(tmp_path))
            assert commits == []

    def test_error(self, tmp_path):
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=1, stdout="")
            commits = get_commits(str(tmp_path))
            assert commits == []


class TestGetTags:

    def test_with_mock(self, tmp_path):
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="v1.0.0 2024-01-01\nv0.9.0 2023-12-01\n")
            tags = get_tags(str(tmp_path))
            assert len(tags) == 2
            assert tags[0]["name"] == "v1.0.0"

    def test_no_tags(self, tmp_path):
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="")
            tags = get_tags(str(tmp_path))
            assert tags == []


class TestGenerateChangelog:

    def test_groups_by_type(self):
        commits = [
            CommitInfo(hash="a", short_hash="a1", subject="feat: add login"),
            CommitInfo(hash="b", short_hash="b1", subject="fix: repair logout"),
            CommitInfo(hash="c", short_hash="c1", subject="docs: update README"),
        ]
        with patch("keanu.data.changelog.get_commits", return_value=commits):
            md = generate_changelog()
            assert "## Features" in md
            assert "## Bug Fixes" in md
            assert "## Documentation" in md
            assert "add login" in md

    def test_breaking_section(self):
        commits = [
            CommitInfo(hash="a", short_hash="a1", subject="feat!: remove old api"),
        ]
        with patch("keanu.data.changelog.get_commits", return_value=commits):
            md = generate_changelog()
            assert "BREAKING CHANGES" in md

    def test_empty(self):
        with patch("keanu.data.changelog.get_commits", return_value=[]):
            md = generate_changelog()
            assert "No commits" in md

    def test_custom_title(self):
        commits = [
            CommitInfo(hash="a", short_hash="a1", subject="feat: stuff"),
        ]
        with patch("keanu.data.changelog.get_commits", return_value=commits):
            md = generate_changelog(title="v2.0.0")
            assert "# v2.0.0" in md

    def test_scoped_commits(self):
        commits = [
            CommitInfo(hash="a", short_hash="a1", subject="feat(auth): add oauth"),
        ]
        with patch("keanu.data.changelog.get_commits", return_value=commits):
            md = generate_changelog()
            assert "**auth**" in md

    def test_pr_references(self):
        commits = [
            CommitInfo(hash="a", short_hash="a1", subject="fix: login bug #123"),
        ]
        with patch("keanu.data.changelog.get_commits", return_value=commits):
            md = generate_changelog()
            assert "#123" in md


class TestReleaseNotes:

    def test_basic(self):
        commits = [
            CommitInfo(hash="a", short_hash="a1", subject="feat: new thing"),
        ]
        with patch("keanu.data.changelog.get_commits", return_value=commits):
            with patch("subprocess.run") as mock:
                mock.return_value = MagicMock(returncode=0, stdout="2024-01-01\n")
                md = generate_release_notes(from_tag="v1.0.0", to_tag="v2.0.0")
                assert "Release v2.0.0" in md


class TestCommitsSinceTag:

    def test_no_tags(self):
        with patch("keanu.data.changelog.get_tags", return_value=[]):
            with patch("keanu.data.changelog.get_commits") as mock:
                mock.return_value = []
                commits_since_tag()
                mock.assert_called_once()
