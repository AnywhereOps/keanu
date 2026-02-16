"""tests for API client generation."""

import json

from keanu.gen.apigen import (
    parse_openapi, parse_openapi_file, generate_client, generate_models,
    Endpoint, ApiSpec, _to_snake_case, _resolve_type,
)


SAMPLE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Pet Store", "version": "1.0.0"},
    "servers": [{"url": "https://api.example.com/v1"}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer"}, "required": False},
                ],
                "responses": {
                    "200": {
                        "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/Pet"}}}},
                    },
                },
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Pet"}}},
                },
                "responses": {
                    "201": {
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Pet"}}},
                    },
                },
            },
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "getPet",
                "summary": "Get a pet by ID",
                "parameters": [
                    {"name": "petId", "in": "path", "schema": {"type": "integer"}, "required": True},
                ],
                "responses": {
                    "200": {
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Pet"}}},
                    },
                },
            },
        },
    },
    "components": {
        "schemas": {
            "Pet": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "id": {"type": "integer", "description": "Pet ID"},
                    "name": {"type": "string", "description": "Pet name"},
                    "tag": {"type": "string"},
                },
            },
        },
    },
}


class TestParseOpenapi:

    def test_basic(self):
        api = parse_openapi(SAMPLE_SPEC)
        assert api.title == "Pet Store"
        assert api.version == "1.0.0"
        assert api.base_url == "https://api.example.com/v1"

    def test_endpoints(self):
        api = parse_openapi(SAMPLE_SPEC)
        assert len(api.endpoints) == 3

    def test_get_endpoint(self):
        api = parse_openapi(SAMPLE_SPEC)
        get_pets = next(e for e in api.endpoints if e.operation_id == "listPets")
        assert get_pets.method == "GET"
        assert get_pets.path == "/pets"
        assert len(get_pets.query_params) == 1

    def test_post_endpoint(self):
        api = parse_openapi(SAMPLE_SPEC)
        create = next(e for e in api.endpoints if e.operation_id == "createPet")
        assert create.method == "POST"
        assert create.request_body["required"]

    def test_path_params(self):
        api = parse_openapi(SAMPLE_SPEC)
        get_pet = next(e for e in api.endpoints if e.operation_id == "getPet")
        assert len(get_pet.path_params) == 1
        assert get_pet.path_params[0]["name"] == "petId"

    def test_models(self):
        api = parse_openapi(SAMPLE_SPEC)
        assert "Pet" in api.models
        pet = api.models["Pet"]
        assert "name" in pet
        assert pet["name"]["required"]
        assert pet["id"]["type"] == "int"


class TestParseFile:

    def test_json(self, tmp_path):
        f = tmp_path / "spec.json"
        f.write_text(json.dumps(SAMPLE_SPEC))
        api = parse_openapi_file(str(f))
        assert api.title == "Pet Store"


class TestEndpoint:

    def test_function_name_from_operation_id(self):
        e = Endpoint(method="GET", path="/pets", operation_id="listPets")
        assert e.function_name == "list_pets"

    def test_function_name_generated(self):
        e = Endpoint(method="GET", path="/users")
        assert e.function_name == "get_users"

    def test_path_and_query_params(self):
        e = Endpoint(
            method="GET", path="/users/{id}",
            parameters=[
                {"name": "id", "in": "path", "type": "int", "required": True},
                {"name": "limit", "in": "query", "type": "int", "required": False},
            ],
        )
        assert len(e.path_params) == 1
        assert len(e.query_params) == 1


class TestResolveType:

    def test_string(self):
        assert _resolve_type({"type": "string"}) == "str"

    def test_integer(self):
        assert _resolve_type({"type": "integer"}) == "int"

    def test_number(self):
        assert _resolve_type({"type": "number"}) == "float"

    def test_boolean(self):
        assert _resolve_type({"type": "boolean"}) == "bool"

    def test_array(self):
        assert _resolve_type({"type": "array", "items": {"type": "string"}}) == "list[str]"

    def test_ref(self):
        assert _resolve_type({"$ref": "#/components/schemas/Pet"}) == "Pet"

    def test_datetime(self):
        assert _resolve_type({"type": "string", "format": "date-time"}) == "datetime"

    def test_empty(self):
        assert _resolve_type({}) == "Any"


class TestToSnakeCase:

    def test_camel(self):
        assert _to_snake_case("listPets") == "list_pets"

    def test_pascal(self):
        assert _to_snake_case("ListPets") == "list_pets"

    def test_already_snake(self):
        assert _to_snake_case("list_pets") == "list_pets"

    def test_acronym(self):
        assert _to_snake_case("getHTTPResponse") == "get_http_response"


class TestGenerateClient:

    def test_generates_class(self):
        api = parse_openapi(SAMPLE_SPEC)
        code = generate_client(api)
        assert "class PetStoreClient:" in code
        assert "def list_pets" in code
        assert "def create_pet" in code
        assert "def get_pet" in code

    def test_imports(self):
        api = parse_openapi(SAMPLE_SPEC)
        code = generate_client(api)
        assert "import requests" in code

    def test_base_url(self):
        api = parse_openapi(SAMPLE_SPEC)
        code = generate_client(api)
        assert "api.example.com" in code

    def test_custom_class_name(self):
        api = parse_openapi(SAMPLE_SPEC)
        code = generate_client(api, class_name="MyClient")
        assert "class MyClient:" in code

    def test_path_params_in_method(self):
        api = parse_openapi(SAMPLE_SPEC)
        code = generate_client(api)
        assert "petId: int" in code

    def test_query_params(self):
        api = parse_openapi(SAMPLE_SPEC)
        code = generate_client(api)
        assert "limit" in code


class TestGenerateModels:

    def test_generates_dataclass(self):
        api = parse_openapi(SAMPLE_SPEC)
        code = generate_models(api)
        assert "@dataclass" in code
        assert "class Pet:" in code
        assert "name: str" in code

    def test_optional_fields(self):
        api = parse_openapi(SAMPLE_SPEC)
        code = generate_models(api)
        assert "Optional" in code  # tag is not required
        assert "= None" in code

    def test_descriptions(self):
        api = parse_openapi(SAMPLE_SPEC)
        code = generate_models(api)
        assert "Pet ID" in code
