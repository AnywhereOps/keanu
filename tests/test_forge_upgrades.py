"""tests for forge upgrades: registry, import/export, version checks."""

import json
from pathlib import Path
from unittest.mock import patch

from keanu.abilities.forge import (
    forge_ability, bake_single_ability,
    register_ability, unregister_ability, list_registered,
    export_ability, import_ability, check_ability_version,
    _load_registry, _save_registry, _REGISTRY_FILE,
)


class TestForgeWithBake:

    def test_forge_without_bake(self, tmp_path):
        with patch("keanu.abilities.forge.ABILITIES_DIR", tmp_path):
            with patch("keanu.abilities.forge.TESTS_DIR", tmp_path):
                result = forge_ability("test_bake", "test baking", ["test"])
                assert "error" not in result
                assert "baked" not in result

    def test_forge_with_bake_no_chromadb(self, tmp_path):
        with patch("keanu.abilities.forge.ABILITIES_DIR", tmp_path):
            with patch("keanu.abilities.forge.TESTS_DIR", tmp_path):
                with patch("keanu.abilities.forge.bake_single_ability") as mock_bake:
                    mock_bake.return_value = {"success": False, "error": "chromadb not available"}
                    result = forge_ability("test_bake2", "test baking", ["test"], bake=True)
                    assert "baked" in result
                    assert not result["baked"]["success"]

    def test_bake_single_no_chromadb(self):
        with patch.dict("sys.modules", {"chromadb": None}):
            result = bake_single_ability("test", "desc", ["kw"])
            assert not result["success"]


class TestAbilityRegistry:

    def test_register(self, tmp_path):
        reg_file = tmp_path / "registry.json"
        with patch("keanu.abilities.forge._REGISTRY_FILE", reg_file):
            entry = register_ability("myab", "does things", ["thing", "do"])
            assert entry["name"] == "myab"
            assert entry["description"] == "does things"

            registered = list_registered()
            assert len(registered) == 1
            assert registered[0]["name"] == "myab"

    def test_unregister(self, tmp_path):
        reg_file = tmp_path / "registry.json"
        with patch("keanu.abilities.forge._REGISTRY_FILE", reg_file):
            register_ability("myab", "does things", ["thing"])
            assert unregister_ability("myab")
            assert len(list_registered()) == 0

    def test_unregister_nonexistent(self, tmp_path):
        reg_file = tmp_path / "registry.json"
        with patch("keanu.abilities.forge._REGISTRY_FILE", reg_file):
            assert not unregister_ability("nope")

    def test_register_with_metadata(self, tmp_path):
        reg_file = tmp_path / "registry.json"
        with patch("keanu.abilities.forge._REGISTRY_FILE", reg_file):
            entry = register_ability("myab", "desc", ["kw"],
                                     author="drew", version="1.0.0")
            assert entry["author"] == "drew"
            assert entry["version"] == "1.0.0"


class TestExportImport:

    def test_export_ability(self, tmp_path):
        ab_dir = tmp_path / "abilities"
        ab_dir.mkdir()
        (ab_dir / "cool.py").write_text('name = "cool"\n# cool ability\n')

        with patch("keanu.abilities.forge.ABILITIES_DIR", ab_dir):
            with patch("keanu.abilities.forge.TESTS_DIR", tmp_path):
                result = export_ability("cool")
                assert "source" in result
                assert 'name = "cool"' in result["source"]

    def test_export_missing(self, tmp_path):
        with patch("keanu.abilities.forge.ABILITIES_DIR", tmp_path):
            result = export_ability("nonexistent")
            assert "error" in result

    def test_import_ability(self, tmp_path):
        ab_dir = tmp_path / "abilities"
        ab_dir.mkdir()
        test_dir = tmp_path / "tests"
        test_dir.mkdir()

        source = '"""cool: does cool stuff"""\nname = "cool"\n'
        test_source = '"""test cool"""\ndef test_cool(): pass\n'

        with patch("keanu.abilities.forge.ABILITIES_DIR", ab_dir):
            with patch("keanu.abilities.forge.TESTS_DIR", test_dir):
                result = import_ability(source, test_source, name="cool")
                assert "error" not in result
                assert (ab_dir / "cool.py").exists()
                assert (test_dir / "test_cool_ability.py").exists()

    def test_import_refuses_overwrite(self, tmp_path):
        ab_dir = tmp_path / "abilities"
        ab_dir.mkdir()
        (ab_dir / "cool.py").write_text("existing\n")

        with patch("keanu.abilities.forge.ABILITIES_DIR", ab_dir):
            result = import_ability("new", name="cool")
            assert "error" in result
            assert "already exists" in result["error"]

    def test_import_allows_overwrite(self, tmp_path):
        ab_dir = tmp_path / "abilities"
        ab_dir.mkdir()
        (ab_dir / "cool.py").write_text("existing\n")

        with patch("keanu.abilities.forge.ABILITIES_DIR", ab_dir):
            with patch("keanu.abilities.forge.TESTS_DIR", tmp_path):
                result = import_ability("new code", name="cool", overwrite=True)
                assert "error" not in result
                assert (ab_dir / "cool.py").read_text() == "new code"

    def test_import_extracts_name(self, tmp_path):
        ab_dir = tmp_path / "abilities"
        ab_dir.mkdir()

        source = '    name = "auto_found"\n'

        with patch("keanu.abilities.forge.ABILITIES_DIR", ab_dir):
            with patch("keanu.abilities.forge.TESTS_DIR", tmp_path):
                result = import_ability(source)
                assert result["name"] == "auto_found"

    def test_import_no_name_fails(self, tmp_path):
        result = import_ability("no name here")
        assert "error" in result


class TestVersionCheck:

    def test_not_registered(self, tmp_path):
        reg_file = tmp_path / "registry.json"
        with patch("keanu.abilities.forge._REGISTRY_FILE", reg_file):
            result = check_ability_version("unknown")
            assert result["status"] == "not_registered"

    def test_registered_installed(self, tmp_path):
        reg_file = tmp_path / "registry.json"
        ab_dir = tmp_path / "abilities"
        ab_dir.mkdir()
        (ab_dir / "myab.py").write_text("# ability\n")

        with patch("keanu.abilities.forge._REGISTRY_FILE", reg_file):
            with patch("keanu.abilities.forge.ABILITIES_DIR", ab_dir):
                register_ability("myab", "desc", ["kw"], version="2.0.0")
                result = check_ability_version("myab")
                assert result["status"] == "installed"
                assert result["version"] == "2.0.0"

    def test_registered_not_installed(self, tmp_path):
        reg_file = tmp_path / "registry.json"
        ab_dir = tmp_path / "abilities"
        ab_dir.mkdir()

        with patch("keanu.abilities.forge._REGISTRY_FILE", reg_file):
            with patch("keanu.abilities.forge.ABILITIES_DIR", ab_dir):
                register_ability("missing", "desc", ["kw"])
                result = check_ability_version("missing")
                assert result["status"] == "not_installed"


class TestRegistryPersistence:

    def test_load_empty(self, tmp_path):
        reg_file = tmp_path / "registry.json"
        with patch("keanu.abilities.forge._REGISTRY_FILE", reg_file):
            data = _load_registry()
            assert data["abilities"] == {}

    def test_save_and_load(self, tmp_path):
        reg_file = tmp_path / "registry.json"
        with patch("keanu.abilities.forge._REGISTRY_FILE", reg_file):
            _save_registry({"abilities": {"x": {"name": "x"}}, "version": 1})
            data = _load_registry()
            assert "x" in data["abilities"]

    def test_corrupt_file(self, tmp_path):
        reg_file = tmp_path / "registry.json"
        reg_file.write_text("not json")
        with patch("keanu.abilities.forge._REGISTRY_FILE", reg_file):
            data = _load_registry()
            assert data["abilities"] == {}
