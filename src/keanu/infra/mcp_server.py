"""mcp_server.py - expose keanu abilities as MCP tools.

allows any MCP client (Claude Desktop, other agents) to use keanu's
abilities. scan, detect, converge, alive, and all hands abilities
exposed as MCP tools. memory exposed as MCP resources.

in the world: the embassy. keanu speaks MCP so anyone can call.

this implements a minimal MCP server that speaks JSON-RPC over stdio.
no external MCP library required.
"""

import json
import sys
from typing import Any

from keanu.abilities import _REGISTRY, list_abilities
from keanu.abilities.schema import SCHEMAS, get_schema


# ============================================================
# MCP TOOL DEFINITIONS
# ============================================================

def list_tools() -> list[dict]:
    """generate MCP tool definitions from registered abilities."""
    tools = []

    for ab in _REGISTRY.values():
        schema = get_schema(ab.name)

        # build input schema from AbilitySchema if available
        properties = {}
        required = []

        if schema:
            for param in schema.inputs:
                prop = {"type": _mcp_type(param.type)}
                if param.description:
                    prop["description"] = param.description
                if param.default is not None:
                    prop["default"] = param.default
                properties[param.name] = prop
                if param.required:
                    required.append(param.name)
        else:
            # fallback: generic prompt parameter
            properties = {
                "prompt": {"type": "string", "description": "What to do"},
            }

        tool = {
            "name": f"keanu_{ab.name}",
            "description": ab.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }
        tools.append(tool)

    return tools


def call_tool(name: str, arguments: dict) -> dict:
    """call a keanu ability via MCP tool name."""
    # strip keanu_ prefix
    ability_name = name
    if ability_name.startswith("keanu_"):
        ability_name = ability_name[6:]

    ab = _REGISTRY.get(ability_name)
    if ab is None:
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
            "isError": True,
        }

    try:
        result = ab.execute(
            prompt=arguments.get("prompt", ""),
            context=arguments,
        )
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e}"}],
            "isError": True,
        }

    return {
        "content": [{"type": "text", "text": result.get("result", "")}],
        "isError": not result.get("success", False),
    }


# ============================================================
# MCP RESOURCE DEFINITIONS
# ============================================================

def list_resources() -> list[dict]:
    """expose keanu state as MCP resources."""
    resources = []

    # pulse state
    resources.append({
        "uri": "keanu://pulse",
        "name": "Keanu Pulse State",
        "description": "Current ALIVE/GREY/BLACK state",
        "mimeType": "application/json",
    })

    # abilities list
    resources.append({
        "uri": "keanu://abilities",
        "name": "Keanu Abilities",
        "description": "All registered abilities and their descriptions",
        "mimeType": "application/json",
    })

    # session cost
    resources.append({
        "uri": "keanu://cost",
        "name": "Session Cost",
        "description": "Token usage and cost tracking for current session",
        "mimeType": "application/json",
    })

    return resources


def read_resource(uri: str) -> dict:
    """read an MCP resource by URI."""
    if uri == "keanu://pulse":
        try:
            from keanu.alive import check as alive_check
            state = alive_check("system check")
            return {"contents": [{"uri": uri, "text": json.dumps({"state": state.name})}]}
        except Exception:
            return {"contents": [{"uri": uri, "text": json.dumps({"state": "unknown"})}]}

    elif uri == "keanu://abilities":
        abilities = list_abilities()
        return {"contents": [{"uri": uri, "text": json.dumps(abilities)}]}

    elif uri == "keanu://cost":
        try:
            from keanu.oracle import get_session_cost
            cost = get_session_cost()
            return {"contents": [{"uri": uri, "text": json.dumps({
                "calls": cost.calls,
                "total_tokens": cost.total_input_tokens + cost.total_output_tokens,
                "cost": cost.total_cost,
                "by_model": cost.by_model,
            })}]}
        except Exception:
            return {"contents": [{"uri": uri, "text": "{}"}]}

    return {"contents": [{"uri": uri, "text": f"Unknown resource: {uri}"}]}


# ============================================================
# JSON-RPC SERVER
# ============================================================

class MCPServer:
    """minimal MCP server over stdio.

    implements the MCP protocol (JSON-RPC 2.0) for tool listing,
    tool calling, resource listing, and resource reading.
    """

    def __init__(self):
        self.running = False

    def handle_message(self, message: dict) -> dict | None:
        """handle a single JSON-RPC message. returns a response or None."""
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        if method == "initialize":
            return self._response(msg_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                },
                "serverInfo": {"name": "keanu", "version": "0.1.0"},
            })

        elif method == "tools/list":
            return self._response(msg_id, {"tools": list_tools()})

        elif method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments", {})
            result = call_tool(name, args)
            return self._response(msg_id, result)

        elif method == "resources/list":
            return self._response(msg_id, {"resources": list_resources()})

        elif method == "resources/read":
            uri = params.get("uri", "")
            result = read_resource(uri)
            return self._response(msg_id, result)

        elif method == "notifications/initialized":
            return None  # notification, no response

        elif method == "ping":
            return self._response(msg_id, {})

        else:
            return self._error(msg_id, -32601, f"Method not found: {method}")

    def _response(self, msg_id, result):
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _error(self, msg_id, code, message):
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

    def run_stdio(self):
        """run the server over stdin/stdout. blocking."""
        self.running = True
        while self.running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                message = json.loads(line)
                response = self.handle_message(message)
                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError:
                continue
            except (EOFError, KeyboardInterrupt):
                break


# ============================================================
# HELPERS
# ============================================================

def _mcp_type(schema_type: str) -> str:
    """convert ability schema type to JSON schema type."""
    type_map = {
        "string": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "list": "array",
        "dict": "object",
        "path": "string",
    }
    return type_map.get(schema_type, "string")
