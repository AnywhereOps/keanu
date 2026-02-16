"""tests for MCP server."""

import json
from unittest.mock import patch, MagicMock

from keanu.infra.mcp_server import (
    list_tools, call_tool, list_resources, read_resource,
    MCPServer, _mcp_type,
)


class TestListTools:

    def test_returns_list(self):
        tools = list_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_tool_has_name(self):
        tools = list_tools()
        names = [t["name"] for t in tools]
        assert any("keanu_read" == n for n in names)

    def test_tool_has_schema(self):
        tools = list_tools()
        for tool in tools:
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"

    def test_tool_description(self):
        tools = list_tools()
        read_tool = next(t for t in tools if t["name"] == "keanu_read")
        assert read_tool["description"]


class TestCallTool:

    def test_call_unknown_tool(self):
        result = call_tool("keanu_nonexistent", {})
        assert result["isError"]

    def test_call_strips_prefix(self):
        # "read" should work with or without keanu_ prefix
        with patch("keanu.infra.mcp_server._REGISTRY") as mock_reg:
            mock_ab = MagicMock()
            mock_ab.execute.return_value = {"success": True, "result": "ok"}
            mock_reg.get.return_value = mock_ab

            result = call_tool("keanu_read", {"file_path": "test.py"})

        mock_reg.get.assert_called_with("read")

    def test_call_returns_content(self):
        with patch("keanu.infra.mcp_server._REGISTRY") as mock_reg:
            mock_ab = MagicMock()
            mock_ab.execute.return_value = {"success": True, "result": "file contents here"}
            mock_reg.get.return_value = mock_ab

            result = call_tool("keanu_read", {"file_path": "test.py"})

        assert not result["isError"]
        assert "file contents here" in result["content"][0]["text"]

    def test_call_handles_exception(self):
        with patch("keanu.infra.mcp_server._REGISTRY") as mock_reg:
            mock_ab = MagicMock()
            mock_ab.execute.side_effect = RuntimeError("boom")
            mock_reg.get.return_value = mock_ab

            result = call_tool("keanu_test", {"op": "run"})

        assert result["isError"]
        assert "boom" in result["content"][0]["text"]


class TestListResources:

    def test_returns_resources(self):
        resources = list_resources()
        assert len(resources) >= 3

    def test_pulse_resource(self):
        resources = list_resources()
        uris = [r["uri"] for r in resources]
        assert "keanu://pulse" in uris

    def test_abilities_resource(self):
        resources = list_resources()
        uris = [r["uri"] for r in resources]
        assert "keanu://abilities" in uris


class TestReadResource:

    def test_read_abilities(self):
        result = read_resource("keanu://abilities")
        assert "contents" in result
        text = result["contents"][0]["text"]
        data = json.loads(text)
        assert isinstance(data, list)

    def test_read_unknown(self):
        result = read_resource("keanu://nonexistent")
        assert "Unknown" in result["contents"][0]["text"]

    def test_read_cost(self):
        result = read_resource("keanu://cost")
        assert "contents" in result
        text = result["contents"][0]["text"]
        data = json.loads(text)
        assert "calls" in data


class TestMCPServer:

    def test_initialize(self):
        server = MCPServer()
        response = server.handle_message({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })
        assert response["result"]["protocolVersion"]
        assert "tools" in response["result"]["capabilities"]

    def test_tools_list(self):
        server = MCPServer()
        response = server.handle_message({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })
        assert "tools" in response["result"]

    def test_resources_list(self):
        server = MCPServer()
        response = server.handle_message({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/list",
            "params": {},
        })
        assert "resources" in response["result"]

    def test_resources_read(self):
        server = MCPServer()
        response = server.handle_message({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/read",
            "params": {"uri": "keanu://abilities"},
        })
        assert "contents" in response["result"]

    def test_ping(self):
        server = MCPServer()
        response = server.handle_message({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "ping",
            "params": {},
        })
        assert response["id"] == 5

    def test_notification_no_response(self):
        server = MCPServer()
        response = server.handle_message({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        })
        assert response is None

    def test_unknown_method(self):
        server = MCPServer()
        response = server.handle_message({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "nonexistent/method",
            "params": {},
        })
        assert "error" in response


class TestMcpType:

    def test_string(self):
        assert _mcp_type("string") == "string"

    def test_int(self):
        assert _mcp_type("int") == "integer"

    def test_bool(self):
        assert _mcp_type("bool") == "boolean"

    def test_unknown(self):
        assert _mcp_type("custom") == "string"
