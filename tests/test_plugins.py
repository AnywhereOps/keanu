"""tests for plugin system."""

from unittest.mock import patch, MagicMock

from keanu.abilities.world.plugins import (
    discover_plugins, load_plugin, load_all_plugins,
    register_hook, fire_hook, list_hooks, clear_hooks,
    get_plugin_config, set_plugin_config,
    PluginInfo, Hook, HOOK_EVENTS,
)


class TestPluginDiscovery:

    def test_discover_returns_list(self):
        # may return empty list if no plugins installed
        plugins = discover_plugins()
        assert isinstance(plugins, list)

    def test_load_plugin_bad_module(self):
        info = PluginInfo(
            name="bad", version="0.1", package="bad-plugin",
            module="nonexistent.module:register",
            entry_point="bad = nonexistent.module:register",
        )
        result = load_plugin(info)
        assert not result
        assert info.error

    def test_plugin_info_str(self):
        info = PluginInfo(name="test", version="1.0", package="test-pkg",
                          module="test_mod", entry_point="test")
        assert "test" in str(info)
        assert "pending" in str(info)

    def test_plugin_info_loaded(self):
        info = PluginInfo(name="test", version="1.0", package="test-pkg",
                          module="test_mod", entry_point="test", loaded=True)
        assert "loaded" in str(info)

    def test_plugin_info_error(self):
        info = PluginInfo(name="test", version="1.0", package="test-pkg",
                          module="test_mod", entry_point="test", error="boom")
        assert "error" in str(info)


class TestHooks:

    def setup_method(self):
        clear_hooks()

    def test_register_and_fire(self):
        results = []
        register_hook("on_error", lambda e: results.append(e))
        fire_hook("on_error", {"type": "test"})
        assert len(results) == 1
        assert results[0]["type"] == "test"

    def test_priority_ordering(self):
        order = []
        register_hook("on_error", lambda e: order.append("second"), priority=10)
        register_hook("on_error", lambda e: order.append("first"), priority=1)
        fire_hook("on_error", {})
        assert order == ["first", "second"]

    def test_fire_returns_first_result(self):
        register_hook("before_edit", lambda f, c: "modified")
        register_hook("before_edit", lambda f, c: "ignored")
        result = fire_hook("before_edit", "file.py", "content")
        assert result == "modified"

    def test_fire_returns_none_when_no_result(self):
        register_hook("after_edit", lambda f, c: None)
        result = fire_hook("after_edit", "file.py", "content")
        assert result is None

    def test_fire_unknown_event(self):
        result = fire_hook("nonexistent_event")
        assert result is None

    def test_list_hooks(self):
        register_hook("on_error", lambda e: None, plugin="test-plugin")
        hooks = list_hooks()
        assert "on_error" in hooks
        assert hooks["on_error"][0]["plugin"] == "test-plugin"

    def test_clear_specific_event(self):
        register_hook("on_error", lambda e: None)
        register_hook("on_miss", lambda p: None)
        clear_hooks("on_error")
        hooks = list_hooks()
        assert "on_error" not in hooks
        assert "on_miss" in hooks

    def test_clear_all(self):
        register_hook("on_error", lambda e: None)
        register_hook("on_miss", lambda p: None)
        clear_hooks()
        assert list_hooks() == {}

    def test_hook_exception_doesnt_crash(self):
        register_hook("on_error", lambda e: 1/0)
        register_hook("on_error", lambda e: "ok")
        # should not raise, and second hook still fires
        result = fire_hook("on_error", {})
        assert result == "ok"

    def test_all_events_defined(self):
        assert len(HOOK_EVENTS) >= 10


class TestPluginConfig:

    def test_get_nonexistent(self, tmp_path):
        with patch("keanu.abilities.world.plugins.Path") as mock_path:
            mock_path.home.return_value = tmp_path
            config = get_plugin_config("nonexistent")
        assert config == {}

    def test_set_and_get(self, tmp_path):
        config_dir = tmp_path / ".keanu" / "plugins"
        config_dir.mkdir(parents=True)

        with patch("keanu.abilities.world.plugins.Path") as mock_path:
            mock_path.home.return_value = tmp_path
            set_plugin_config("test", {"key": "value"})
            config = get_plugin_config("test")

        assert config == {"key": "value"}
