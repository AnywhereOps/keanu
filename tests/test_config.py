"""tests for configuration management."""

import json
import os
from unittest.mock import patch

from keanu.abilities.world.config import (
    Config, DEFAULTS,
    load_global, save_global, load_project, save_project,
    load_config, get_value, set_global_value, set_project_value,
    list_config, init_project_config,
    _env_overrides,
)


class TestConfig:

    def test_defaults(self):
        c = Config()
        assert c.get("model") == DEFAULTS["model"]
        assert c.get("max_turns") == DEFAULTS["max_turns"]

    def test_override(self):
        c = Config(values={"model": "custom"})
        assert c.get("model") == "custom"

    def test_missing_key(self):
        c = Config()
        assert c.get("nonexistent", "fallback") == "fallback"

    def test_contains(self):
        c = Config()
        assert "model" in c
        assert "nonexistent" not in c

    def test_getitem(self):
        c = Config(values={"model": "test"})
        assert c["model"] == "test"

    def test_to_dict(self):
        c = Config(values={"model": "custom"})
        d = c.to_dict()
        assert d["model"] == "custom"
        assert "max_turns" in d  # defaults included


class TestGlobalConfig:

    def test_load_empty(self, tmp_path):
        with patch("keanu.abilities.world.config._GLOBAL_CONFIG", tmp_path / "config.json"):
            assert load_global() == {}

    def test_save_and_load(self, tmp_path):
        config_file = tmp_path / "config.json"
        with patch("keanu.abilities.world.config._GLOBAL_CONFIG", config_file):
            save_global({"model": "opus", "max_turns": 50})
            loaded = load_global()
            assert loaded["model"] == "opus"
            assert loaded["max_turns"] == 50

    def test_corrupt_file(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text("not json")
        with patch("keanu.abilities.world.config._GLOBAL_CONFIG", config_file):
            assert load_global() == {}


class TestProjectConfig:

    def test_load_empty(self, tmp_path):
        assert load_project(str(tmp_path)) == {}

    def test_save_and_load(self, tmp_path):
        save_project({"legend": "friend"}, str(tmp_path))
        loaded = load_project(str(tmp_path))
        assert loaded["legend"] == "friend"

    def test_file_location(self, tmp_path):
        save_project({"x": 1}, str(tmp_path))
        assert (tmp_path / ".keanu.json").exists()


class TestLoadConfig:

    def test_defaults_only(self, tmp_path):
        with patch("keanu.abilities.world.config._GLOBAL_CONFIG", tmp_path / "global.json"):
            config = load_config(str(tmp_path))
            assert config.get("model") == DEFAULTS["model"]
            assert config.source == "defaults"

    def test_global_override(self, tmp_path):
        global_file = tmp_path / "global.json"
        global_file.write_text(json.dumps({"model": "opus"}))
        with patch("keanu.abilities.world.config._GLOBAL_CONFIG", global_file):
            config = load_config(str(tmp_path))
            assert config.get("model") == "opus"
            assert config.source == "global"

    def test_project_overrides_global(self, tmp_path):
        global_file = tmp_path / "global.json"
        global_file.write_text(json.dumps({"model": "opus"}))

        project = tmp_path / "project"
        project.mkdir()
        save_project({"model": "haiku"}, str(project))

        with patch("keanu.abilities.world.config._GLOBAL_CONFIG", global_file):
            config = load_config(str(project))
            assert config.get("model") == "haiku"
            assert config.source == "project"

    def test_env_overrides_all(self, tmp_path):
        global_file = tmp_path / "global.json"
        global_file.write_text(json.dumps({"model": "opus"}))

        with patch("keanu.abilities.world.config._GLOBAL_CONFIG", global_file):
            with patch.dict(os.environ, {"KEANU_MODEL": "env-model"}):
                config = load_config(str(tmp_path))
                assert config.get("model") == "env-model"
                assert config.source == "env"


class TestEnvOverrides:

    def test_string_override(self):
        with patch.dict(os.environ, {"KEANU_MODEL": "test-model"}):
            overrides = _env_overrides()
            assert overrides["model"] == "test-model"

    def test_int_override(self):
        with patch.dict(os.environ, {"KEANU_MAX_TURNS": "50"}):
            overrides = _env_overrides()
            assert overrides["max_turns"] == 50

    def test_bool_override(self):
        with patch.dict(os.environ, {"KEANU_PREFER_LOCAL": "true"}):
            overrides = _env_overrides()
            assert overrides["prefer_local"] is True

    def test_no_overrides(self):
        # Clear relevant env vars
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("KEANU_")}
        with patch.dict(os.environ, env, clear=True):
            overrides = _env_overrides()
            assert overrides == {}


class TestHelpers:

    def test_get_value(self, tmp_path):
        with patch("keanu.abilities.world.config._GLOBAL_CONFIG", tmp_path / "g.json"):
            val = get_value("model", str(tmp_path))
            assert val == DEFAULTS["model"]

    def test_set_global_value(self, tmp_path):
        with patch("keanu.abilities.world.config._GLOBAL_CONFIG", tmp_path / "g.json"):
            set_global_value("model", "opus")
            assert load_global()["model"] == "opus"

    def test_set_project_value(self, tmp_path):
        set_project_value("legend", "architect", str(tmp_path))
        assert load_project(str(tmp_path))["legend"] == "architect"

    def test_list_config(self, tmp_path):
        global_file = tmp_path / "g.json"
        global_file.write_text(json.dumps({"model": "opus"}))
        with patch("keanu.abilities.world.config._GLOBAL_CONFIG", global_file):
            listing = list_config(str(tmp_path))
            assert listing["model"]["value"] == "opus"
            assert listing["model"]["source"] == "global"
            assert listing["max_turns"]["source"] == "default"

    def test_init_project_config(self, tmp_path):
        path = init_project_config(str(tmp_path))
        assert ".keanu.json" in path
        loaded = load_project(str(tmp_path))
        assert "legend" in loaded

    def test_init_existing(self, tmp_path):
        save_project({"custom": True}, str(tmp_path))
        init_project_config(str(tmp_path))
        # should not overwrite
        loaded = load_project(str(tmp_path))
        assert loaded.get("custom") is True
