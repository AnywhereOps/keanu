"""apigen.py - API client generation from OpenAPI specs.

parse OpenAPI/Swagger specs, generate typed Python clients.
supports path params, query params, request bodies, response types.

in the world: the translator between specs and code. the API says
what it does, this module writes the code that talks to it.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Endpoint:
    """a parsed API endpoint."""
    method: str         # GET, POST, PUT, DELETE, PATCH
    path: str           # /users/{id}
    operation_id: str = ""
    summary: str = ""
    description: str = ""
    parameters: list[dict] = field(default_factory=list)  # [{name, in, type, required}]
    request_body: dict = field(default_factory=dict)
    response_type: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def function_name(self) -> str:
        if self.operation_id:
            return _to_snake_case(self.operation_id)
        # generate from method + path
        parts = [self.method.lower()]
        for segment in self.path.split("/"):
            if segment and not segment.startswith("{"):
                parts.append(segment)
        return "_".join(parts)

    @property
    def path_params(self) -> list[dict]:
        return [p for p in self.parameters if p.get("in") == "path"]

    @property
    def query_params(self) -> list[dict]:
        return [p for p in self.parameters if p.get("in") == "query"]


@dataclass
class ApiSpec:
    """a parsed OpenAPI specification."""
    title: str = ""
    version: str = ""
    base_url: str = ""
    endpoints: list[Endpoint] = field(default_factory=list)
    models: dict = field(default_factory=dict)  # name -> {properties}


# ============================================================
# SPEC PARSING
# ============================================================

def parse_openapi(spec: dict) -> ApiSpec:
    """parse an OpenAPI spec dict into structured format."""
    info = spec.get("info", {})
    api = ApiSpec(
        title=info.get("title", ""),
        version=info.get("version", ""),
    )

    # base URL
    servers = spec.get("servers", [])
    if servers:
        api.base_url = servers[0].get("url", "")

    # endpoints
    paths = spec.get("paths", {})
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
                continue

            endpoint = Endpoint(
                method=method.upper(),
                path=path,
                operation_id=details.get("operationId", ""),
                summary=details.get("summary", ""),
                description=details.get("description", ""),
                tags=details.get("tags", []),
            )

            # parameters
            for param in details.get("parameters", []):
                endpoint.parameters.append({
                    "name": param.get("name", ""),
                    "in": param.get("in", ""),
                    "type": _resolve_type(param.get("schema", {})),
                    "required": param.get("required", False),
                })

            # request body
            body = details.get("requestBody", {})
            if body:
                content = body.get("content", {})
                json_content = content.get("application/json", {})
                schema = json_content.get("schema", {})
                endpoint.request_body = {
                    "type": _resolve_type(schema),
                    "required": body.get("required", False),
                }

            # response type
            responses = details.get("responses", {})
            success = responses.get("200", responses.get("201", {}))
            if success:
                content = success.get("content", {})
                json_content = content.get("application/json", {})
                schema = json_content.get("schema", {})
                endpoint.response_type = _resolve_type(schema)

            api.endpoints.append(endpoint)

    # models (schemas)
    components = spec.get("components", {})
    schemas = components.get("schemas", {})
    for name, schema in schemas.items():
        api.models[name] = _parse_schema(schema)

    return api


def parse_openapi_file(path: str) -> ApiSpec:
    """parse an OpenAPI spec from a file (JSON or YAML)."""
    content = Path(path).read_text()

    if path.endswith((".yaml", ".yml")):
        try:
            import yaml
            spec = yaml.safe_load(content)
        except ImportError:
            raise ImportError("PyYAML required for YAML specs: pip install pyyaml")
    else:
        spec = json.loads(content)

    return parse_openapi(spec)


def _resolve_type(schema: dict) -> str:
    """resolve a schema to a Python type string."""
    if not schema:
        return "Any"

    ref = schema.get("$ref", "")
    if ref:
        return ref.split("/")[-1]

    schema_type = schema.get("type", "")
    if schema_type == "string":
        fmt = schema.get("format", "")
        if fmt == "date-time":
            return "datetime"
        if fmt == "date":
            return "date"
        return "str"
    elif schema_type == "integer":
        return "int"
    elif schema_type == "number":
        return "float"
    elif schema_type == "boolean":
        return "bool"
    elif schema_type == "array":
        items = schema.get("items", {})
        item_type = _resolve_type(items)
        return f"list[{item_type}]"
    elif schema_type == "object":
        return "dict"

    return "Any"


def _parse_schema(schema: dict) -> dict:
    """parse a schema into field definitions."""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    fields = {}
    for name, prop in properties.items():
        fields[name] = {
            "type": _resolve_type(prop),
            "required": name in required,
            "description": prop.get("description", ""),
        }

    return fields


def _to_snake_case(name: str) -> str:
    """convert camelCase or PascalCase to snake_case."""
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    s = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', s)
    return s.lower().replace("-", "_")


# ============================================================
# CODE GENERATION
# ============================================================

def generate_client(api: ApiSpec, class_name: str = "") -> str:
    """generate a Python API client class from an API spec."""
    if not class_name:
        class_name = _to_snake_case(api.title).replace("_", " ").title().replace(" ", "") + "Client"
        if class_name == "Client":
            class_name = "ApiClient"

    lines = [
        f'"""auto-generated client for {api.title} v{api.version}."""',
        "",
        "import requests",
        "from typing import Any, Optional",
        "",
        "",
        f"class {class_name}:",
        f'    """client for {api.title}."""',
        "",
        f'    def __init__(self, base_url: str = "{api.base_url}", headers: dict = None):',
        "        self.base_url = base_url.rstrip('/')",
        "        self.headers = headers or {}",
        "        self.session = requests.Session()",
        "        self.session.headers.update(self.headers)",
        "",
    ]

    for endpoint in api.endpoints:
        method_lines = _generate_method(endpoint)
        lines.extend(method_lines)
        lines.append("")

    return "\n".join(lines)


def _generate_method(endpoint: Endpoint) -> list[str]:
    """generate a method for an endpoint."""
    func_name = endpoint.function_name
    params = ["self"]

    # path parameters (required)
    for p in endpoint.path_params:
        type_hint = p.get("type", "str")
        params.append(f"{p['name']}: {type_hint}")

    # request body
    if endpoint.request_body:
        body_type = endpoint.request_body.get("type", "dict")
        if endpoint.request_body.get("required"):
            params.append(f"body: {body_type}")
        else:
            params.append(f"body: Optional[{body_type}] = None")

    # query parameters
    for p in endpoint.query_params:
        type_hint = p.get("type", "str")
        if p.get("required"):
            params.append(f"{p['name']}: {type_hint}")
        else:
            params.append(f"{p['name']}: Optional[{type_hint}] = None")

    sig = ", ".join(params)
    return_type = endpoint.response_type or "dict"

    lines = [
        f"    def {func_name}({sig}) -> {return_type}:",
        f'        """{endpoint.summary or endpoint.method + " " + endpoint.path}."""',
    ]

    # build URL
    path = endpoint.path
    if endpoint.path_params:
        for p in endpoint.path_params:
            path = path.replace(f"{{{p['name']}}}", f"{{{p['name']}}}")
        lines.append(f'        url = f"{{self.base_url}}{path}"')
    else:
        lines.append(f'        url = self.base_url + "{path}"')

    # build query params
    if endpoint.query_params:
        lines.append("        params = {}")
        for p in endpoint.query_params:
            lines.append(f"        if {p['name']} is not None:")
            lines.append(f'            params["{p["name"]}"] = {p["name"]}')
    else:
        lines.append("        params = None")

    # make request
    method = endpoint.method.lower()
    if endpoint.request_body:
        lines.append(f"        response = self.session.{method}(url, json=body, params=params)")
    else:
        lines.append(f"        response = self.session.{method}(url, params=params)")

    lines.append("        response.raise_for_status()")
    lines.append("        return response.json()")

    return lines


def generate_models(api: ApiSpec) -> str:
    """generate dataclass models from API schemas."""
    lines = [
        '"""auto-generated models."""',
        "",
        "from dataclasses import dataclass, field",
        "from typing import Any, Optional",
        "",
    ]

    for name, fields in api.models.items():
        lines.append("")
        lines.append("@dataclass")
        lines.append(f"class {name}:")
        if not fields:
            lines.append("    pass")
            continue

        for field_name, field_info in fields.items():
            type_hint = field_info["type"]
            if not field_info["required"]:
                type_hint = f"Optional[{type_hint}]"
            default = " = None" if not field_info["required"] else ""
            desc = f"  # {field_info['description']}" if field_info.get("description") else ""
            lines.append(f"    {field_name}: {type_hint}{default}{desc}")

    return "\n".join(lines) + "\n"
