"""ide.py - MCP client for the Keanu IDE Companion extension.

discovers the VSCode extension's MCP server and talks to it.
provides openDiff/closeDiff and IDE context for the agent loop.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

import requests

from keanu.log import info, warn, debug


class IdeConnection:
    """Connection to the Keanu IDE Companion MCP server."""

    def __init__(self, port: int, auth_token: str, workspace_path: str = ""):
        self.port = port
        self.auth_token = auth_token
        self.workspace_path = workspace_path
        self.base_url = f"http://127.0.0.1:{port}"
        self.session_id: Optional[str] = None
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        return headers

    def connect(self) -> bool:
        """Initialize MCP session."""
        try:
            resp = requests.post(
                f"{self.base_url}/mcp",
                headers=self._headers(),
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "keanu", "version": "0.1.0"},
                    },
                    "id": self._next_id(),
                },
                timeout=5,
            )
            if resp.status_code == 200:
                self.session_id = resp.headers.get("mcp-session-id")
                if self.session_id:
                    # Send initialized notification
                    requests.post(
                        f"{self.base_url}/mcp",
                        headers=self._headers(),
                        json={
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized",
                        },
                        timeout=5,
                    )
                    info("ide", f"connected to IDE on port {self.port}")
                    return True
            return False
        except (requests.ConnectionError, requests.Timeout):
            return False

    def call_tool(self, name: str, arguments: dict) -> Optional[dict]:
        """Call an MCP tool on the IDE server."""
        if not self.session_id:
            return None
        try:
            resp = requests.post(
                f"{self.base_url}/mcp",
                headers=self._headers(),
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                    "id": self._next_id(),
                },
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("result", {})
            return None
        except (requests.ConnectionError, requests.Timeout):
            warn("ide", f"tool call {name} failed (connection)")
            return None

    def open_diff(self, file_path: str, new_content: str) -> bool:
        """Show a diff view in the IDE."""
        result = self.call_tool("openDiff", {
            "filePath": file_path,
            "newContent": new_content,
        })
        return result is not None

    def close_diff(self, file_path: str) -> Optional[str]:
        """Close a diff view and get the final content."""
        result = self.call_tool("closeDiff", {"filePath": file_path})
        if result and result.get("content"):
            for item in result["content"]:
                if item.get("type") == "text":
                    try:
                        data = json.loads(item["text"])
                        return data.get("content")
                    except (json.JSONDecodeError, KeyError):
                        pass
        return None


def discover() -> Optional[IdeConnection]:
    """Discover the IDE companion extension.

    Checks:
    1. KEANU_IDE_SERVER_PORT env var (set by extension in VSCode terminal)
    2. Port files in $TMPDIR/keanu/ide/
    """
    # check env var first (most reliable, set by extension)
    port_str = os.environ.get("KEANU_IDE_SERVER_PORT")
    auth_token = os.environ.get("KEANU_IDE_AUTH_TOKEN", "")
    workspace = os.environ.get("KEANU_IDE_WORKSPACE_PATH", "")

    if port_str and auth_token:
        try:
            port = int(port_str)
            conn = IdeConnection(port, auth_token, workspace)
            if conn.connect():
                return conn
        except (ValueError, TypeError):
            pass

    # fallback: scan port files
    port_dir = Path(tempfile.gettempdir()) / "keanu" / "ide"
    if port_dir.exists():
        for port_file in sorted(port_dir.glob("keanu-ide-server-*.json"),
                                key=lambda p: p.stat().st_mtime,
                                reverse=True):
            try:
                data = json.loads(port_file.read_text())
                port = data["port"]
                token = data["authToken"]
                ws = data.get("workspacePath", "")
                conn = IdeConnection(port, token, ws)
                if conn.connect():
                    return conn
            except (json.JSONDecodeError, KeyError, OSError):
                continue

    return None


# module-level cached connection
_connection: Optional[IdeConnection] = None
_checked = False


def get_ide() -> Optional[IdeConnection]:
    """Get the IDE connection (cached, lazy discovery)."""
    global _connection, _checked
    if not _checked:
        _checked = True
        _connection = discover()
        if _connection:
            info("ide", "IDE connected")
        else:
            debug("ide", "no IDE detected")
    return _connection


def ide_context_string() -> str:
    """Get IDE context as a string for system prompts. Empty if no IDE."""
    conn = get_ide()
    if not conn:
        return ""

    parts = ["\n\nIDE CONNECTED (VSCode):"]
    if conn.workspace_path:
        parts.append(f"  Workspace: {conn.workspace_path}")
    parts.append("  The write ability will open diffs in the IDE for review.")
    return "\n".join(parts)
