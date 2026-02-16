"""tests for REPL session save/restore."""

from unittest.mock import patch

from keanu.hero.sessions import (
    SessionState, save_session, load_session, delete_session,
    list_sessions, get_latest_session, auto_save, auto_restore,
)


class TestSessionState:

    def test_defaults(self):
        s = SessionState()
        assert s.mode == "do"
        assert s.legend == "creator"
        assert s.created_at > 0

    def test_to_dict(self):
        s = SessionState(name="test", mode="craft", legend="friend")
        d = s.to_dict()
        assert d["name"] == "test"
        assert d["mode"] == "craft"
        assert d["legend"] == "friend"

    def test_from_dict(self):
        d = {"name": "x", "mode": "prove", "legend": "architect", "model": "opus"}
        s = SessionState.from_dict(d)
        assert s.name == "x"
        assert s.mode == "prove"
        assert s.model == "opus"

    def test_history_cap(self):
        s = SessionState(history=[{"role": "user", "content": f"msg{i}"} for i in range(200)])
        d = s.to_dict()
        assert len(d["history"]) == 100

    def test_roundtrip(self):
        s = SessionState(name="rt", mode="craft", context={"files": ["a.py"]})
        d = s.to_dict()
        s2 = SessionState.from_dict(d)
        assert s2.name == "rt"
        assert s2.mode == "craft"
        assert s2.context == {"files": ["a.py"]}


class TestSaveLoad:

    def test_save_and_load(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        with patch("keanu.hero.sessions._SESSIONS_DIR", sessions_dir):
            state = SessionState(mode="craft", legend="friend")
            name = save_session(state, name="my_session")
            assert name == "my_session"

            loaded = load_session("my_session")
            assert loaded.mode == "craft"
            assert loaded.legend == "friend"

    def test_save_auto_name(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        with patch("keanu.hero.sessions._SESSIONS_DIR", sessions_dir):
            state = SessionState()
            name = save_session(state)
            assert name.startswith("session_")

    def test_load_missing(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        with patch("keanu.hero.sessions._SESSIONS_DIR", sessions_dir):
            try:
                load_session("nonexistent")
                assert False, "should have raised"
            except FileNotFoundError:
                pass

    def test_delete(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        with patch("keanu.hero.sessions._SESSIONS_DIR", sessions_dir):
            state = SessionState()
            save_session(state, name="deleteme")
            assert delete_session("deleteme")
            assert not delete_session("deleteme")

    def test_delete_nonexistent(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        with patch("keanu.hero.sessions._SESSIONS_DIR", sessions_dir):
            assert not delete_session("nope")


class TestListSessions:

    def test_empty(self, tmp_path):
        with patch("keanu.hero.sessions._SESSIONS_DIR", tmp_path / "sessions"):
            assert list_sessions() == []

    def test_lists_saved(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        with patch("keanu.hero.sessions._SESSIONS_DIR", sessions_dir):
            save_session(SessionState(mode="do"), name="s1")
            save_session(SessionState(mode="craft"), name="s2")
            sessions = list_sessions()
            assert len(sessions) == 2
            names = [s["name"] for s in sessions]
            assert "s1" in names
            assert "s2" in names


class TestAutoSaveRestore:

    def test_auto_save(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        with patch("keanu.hero.sessions._SESSIONS_DIR", sessions_dir):
            state = SessionState(mode="prove")
            name = auto_save(state)
            assert name == "autosave"

    def test_auto_restore(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        with patch("keanu.hero.sessions._SESSIONS_DIR", sessions_dir):
            auto_save(SessionState(mode="craft", legend="architect"))
            restored = auto_restore()
            assert restored is not None
            assert restored.mode == "craft"
            assert restored.legend == "architect"

    def test_auto_restore_none(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        with patch("keanu.hero.sessions._SESSIONS_DIR", sessions_dir):
            assert auto_restore() is None


class TestGetLatest:

    def test_no_sessions(self, tmp_path):
        with patch("keanu.hero.sessions._SESSIONS_DIR", tmp_path / "sessions"):
            assert get_latest_session() is None

    def test_gets_latest(self, tmp_path):
        import time
        sessions_dir = tmp_path / "sessions"
        with patch("keanu.hero.sessions._SESSIONS_DIR", sessions_dir):
            save_session(SessionState(mode="do"), name="old")
            time.sleep(0.01)
            save_session(SessionState(mode="craft"), name="new")
            latest = get_latest_session()
            assert latest is not None
            assert latest.name == "new"
