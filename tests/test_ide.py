"""Tests for the IDE MCP client."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def test_ide_imports():
    """IDE module imports cleanly."""
    from keanu.hero.ide import IdeConnection, discover, get_ide, ide_context_string
    assert IdeConnection is not None


def test_ide_connection_init():
    """IdeConnection initializes with port and auth token."""
    from keanu.hero.ide import IdeConnection
    conn = IdeConnection(port=12345, auth_token="test-token", workspace_path="/tmp")
    assert conn.port == 12345
    assert conn.auth_token == "test-token"
    assert conn.workspace_path == "/tmp"
    assert conn.base_url == "http://127.0.0.1:12345"
    assert conn.session_id is None


def test_ide_connection_headers_no_session():
    """Headers without session ID."""
    from keanu.hero.ide import IdeConnection
    conn = IdeConnection(port=1, auth_token="tok")
    headers = conn._headers()
    assert headers["Authorization"] == "Bearer tok"
    assert "mcp-session-id" not in headers


def test_ide_connection_headers_with_session():
    """Headers include session ID when set."""
    from keanu.hero.ide import IdeConnection
    conn = IdeConnection(port=1, auth_token="tok")
    conn.session_id = "sess-123"
    headers = conn._headers()
    assert headers["mcp-session-id"] == "sess-123"


def test_ide_connection_connect_failure():
    """Connect returns False on connection error."""
    from keanu.hero.ide import IdeConnection
    conn = IdeConnection(port=1, auth_token="tok")
    assert conn.connect() is False


def test_ide_connection_call_tool_no_session():
    """call_tool returns None without session."""
    from keanu.hero.ide import IdeConnection
    conn = IdeConnection(port=1, auth_token="tok")
    assert conn.call_tool("openDiff", {}) is None


@patch("keanu.hero.ide.requests.post")
def test_ide_connection_connect_success(mock_post):
    """Connect succeeds with valid response."""
    from keanu.hero.ide import IdeConnection

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"mcp-session-id": "sess-abc"}
    mock_post.return_value = mock_resp

    conn = IdeConnection(port=9999, auth_token="tok")
    assert conn.connect() is True
    assert conn.session_id == "sess-abc"


@patch("keanu.hero.ide.requests.post")
def test_ide_open_diff(mock_post):
    """open_diff calls the tool."""
    from keanu.hero.ide import IdeConnection

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": {"content": []}}
    mock_post.return_value = mock_resp

    conn = IdeConnection(port=9999, auth_token="tok")
    conn.session_id = "sess-abc"

    assert conn.open_diff("/tmp/test.py", "print('hello')") is True


def test_discover_no_env_no_files():
    """discover returns None when no env vars or port files."""
    from keanu.hero.ide import discover

    with patch.dict(os.environ, {}, clear=True):
        # clear any keanu env vars
        for key in list(os.environ.keys()):
            if key.startswith("KEANU_IDE"):
                del os.environ[key]
        result = discover()
        assert result is None


def test_ide_context_string_no_connection():
    """ide_context_string returns empty when no IDE."""
    import keanu.hero.ide as ide_mod
    ide_mod._connection = None
    ide_mod._checked = True
    from keanu.hero.ide import ide_context_string
    assert ide_context_string() == ""


def test_ide_context_string_with_connection():
    """ide_context_string returns context when IDE connected."""
    import keanu.hero.ide as ide_mod
    from keanu.hero.ide import IdeConnection, ide_context_string

    conn = IdeConnection(port=1, auth_token="tok", workspace_path="/projects/foo")
    ide_mod._connection = conn
    ide_mod._checked = True

    ctx = ide_context_string()
    assert "IDE CONNECTED" in ctx
    assert "/projects/foo" in ctx

    # cleanup
    ide_mod._connection = None
    ide_mod._checked = False


def test_discover_port_file(tmp_path):
    """discover reads port files from tmpdir."""
    from keanu.hero.ide import IdeConnection

    port_dir = tmp_path / "keanu" / "ide"
    port_dir.mkdir(parents=True)
    port_file = port_dir / "keanu-ide-server-123-9999.json"
    port_file.write_text(json.dumps({
        "port": 9999,
        "authToken": "test-token",
        "workspacePath": "/test",
    }))

    with patch("keanu.hero.ide.tempfile") as mock_tempfile, \
         patch.dict(os.environ, {}, clear=True), \
         patch("keanu.hero.ide.IdeConnection") as MockConn:

        mock_tempfile.gettempdir.return_value = str(tmp_path)
        mock_conn = MagicMock()
        mock_conn.connect.return_value = True
        MockConn.return_value = mock_conn

        from keanu.hero.ide import discover
        # clear env vars
        for key in list(os.environ.keys()):
            if key.startswith("KEANU_IDE"):
                del os.environ[key]

        result = discover()
        assert result is mock_conn
        MockConn.assert_called_with(9999, "test-token", "/test")
