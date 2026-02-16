"""tests for ability protocol upgrade: schemas and chains."""

from unittest.mock import MagicMock

from keanu.abilities.schema import (
    ParamSchema, AbilitySchema, ChainStep, ChainResult,
    get_schema, execute_chain, SCHEMAS,
    _type_check,
)


class TestParamSchema:

    def test_defaults(self):
        p = ParamSchema("name")
        assert p.type == "string"
        assert p.required


class TestAbilitySchema:

    def test_validate_input_ok(self):
        schema = AbilitySchema(
            name="test",
            inputs=[ParamSchema("file_path", "string", required=True)],
        )
        assert schema.validate_input({"file_path": "test.py"}) == []

    def test_validate_missing_required(self):
        schema = AbilitySchema(
            name="test",
            inputs=[ParamSchema("file_path", "string", required=True)],
        )
        errors = schema.validate_input({})
        assert len(errors) == 1
        assert "missing" in errors[0]

    def test_validate_wrong_type(self):
        schema = AbilitySchema(
            name="test",
            inputs=[ParamSchema("count", "int", required=True)],
        )
        errors = schema.validate_input({"count": "not_an_int"})
        assert len(errors) == 1
        assert "expected int" in errors[0]

    def test_validate_optional_missing_ok(self):
        schema = AbilitySchema(
            name="test",
            inputs=[ParamSchema("path", "string", required=False)],
        )
        assert schema.validate_input({}) == []

    def test_signature(self):
        schema = AbilitySchema(
            name="edit",
            inputs=[
                ParamSchema("file_path", "path"),
                ParamSchema("old_string", "string"),
                ParamSchema("preview", "bool", required=False),
            ],
        )
        sig = schema.signature()
        assert "edit(" in sig
        assert "file_path: path" in sig
        assert "preview: bool?" in sig


class TestBuiltInSchemas:

    def test_read_schema_exists(self):
        assert "read" in SCHEMAS

    def test_write_schema_exists(self):
        assert "write" in SCHEMAS

    def test_edit_schema(self):
        schema = SCHEMAS["edit"]
        assert schema.name == "edit"
        required = [p.name for p in schema.inputs if p.required]
        assert "file_path" in required
        assert "old_string" in required

    def test_get_schema(self):
        assert get_schema("read") is not None
        assert get_schema("nonexistent") is None

    def test_run_requires_confirmation(self):
        assert SCHEMAS["run"].requires_confirmation


class TestChainExecution:

    def _make_registry(self, abilities: dict[str, dict]):
        """make a mock registry from name -> execute_result mappings."""
        registry = {}
        for name, result in abilities.items():
            mock_ab = MagicMock()
            mock_ab.execute.return_value = result
            registry[name] = mock_ab
        return registry

    def test_simple_chain(self):
        registry = self._make_registry({
            "read": {"success": True, "result": "file contents", "data": {}},
            "edit": {"success": True, "result": "edited", "data": {}},
        })

        steps = [
            ChainStep("read", {"file_path": "test.py"}),
            ChainStep("edit", {"file_path": "test.py", "old_string": "a", "new_string": "b"}),
        ]

        result = execute_chain(steps, registry)
        assert result.success
        assert result.steps_completed == 2

    def test_chain_stop_on_failure(self):
        registry = self._make_registry({
            "read": {"success": False, "result": "not found", "data": {}},
            "edit": {"success": True, "result": "edited", "data": {}},
        })

        steps = [
            ChainStep("read", {"file_path": "missing.py"}, on_fail="stop"),
            ChainStep("edit", {}),
        ]

        result = execute_chain(steps, registry)
        assert not result.success
        assert result.steps_completed == 0

    def test_chain_skip_on_failure(self):
        registry = self._make_registry({
            "read": {"success": False, "result": "not found", "data": {}},
            "edit": {"success": True, "result": "edited", "data": {}},
        })

        steps = [
            ChainStep("read", {"file_path": "missing.py"}, on_fail="skip"),
            ChainStep("edit", {"file_path": "f.py", "old_string": "a", "new_string": "b"}),
        ]

        result = execute_chain(steps, registry)
        assert result.success
        assert result.steps_completed == 2

    def test_chain_unknown_ability(self):
        result = execute_chain(
            [ChainStep("nonexistent", {})],
            {},
        )
        assert not result.success
        assert "unknown" in result.errors[0]

    def test_dry_run(self):
        registry = self._make_registry({
            "read": {"success": True, "result": "x", "data": {}},
        })

        result = execute_chain(
            [ChainStep("read", {"file_path": "f.py"})],
            registry,
            dry_run=True,
        )
        assert result.success
        assert "dry run" in result.results[0]["result"]
        # ability should NOT have been called
        registry["read"].execute.assert_not_called()

    def test_chain_rollback(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("original")

        # first ability succeeds (write), second fails
        write_ab = MagicMock()
        def fake_write(prompt, context):
            f.write_text(context.get("content", ""))
            return {"success": True, "result": "written", "data": {}}
        write_ab.execute.side_effect = fake_write

        fail_ab = MagicMock()
        fail_ab.execute.return_value = {"success": False, "result": "boom", "data": {}}

        registry = {"write": write_ab, "test": fail_ab}

        steps = [
            ChainStep("write", {"file_path": str(f), "content": "changed"}),
            ChainStep("test", {"op": "run"}, on_fail="rollback"),
        ]

        result = execute_chain(steps, registry)
        assert not result.success
        assert result.rolled_back
        # file should be restored to original
        assert f.read_text() == "original"

    def test_validation_failure(self):
        registry = self._make_registry({
            "read": {"success": True, "result": "x", "data": {}},
        })

        # read requires file_path
        steps = [ChainStep("read", {})]
        result = execute_chain(steps, registry)
        assert not result.success
        assert "missing" in result.errors[0]


class TestTypeCheck:

    def test_string(self):
        assert _type_check("hello", "string")
        assert not _type_check(123, "string")

    def test_int(self):
        assert _type_check(42, "int")
        assert not _type_check("42", "int")

    def test_bool(self):
        assert _type_check(True, "bool")

    def test_list(self):
        assert _type_check([1, 2], "list")
        assert not _type_check("not a list", "list")

    def test_unknown_type(self):
        assert _type_check("anything", "unknown_type")

    def test_path(self):
        assert _type_check("/foo/bar", "path")
