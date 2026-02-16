"""plugins.py - plugin system for third-party abilities.

discover, load, and manage abilities from pip-installed packages.
abilities register via entry_points in pyproject.toml. hooks let
plugins react to events. custom legends and lenses are supported.

in the world: the bazaar. anyone can bring their tools.
"""

import importlib
import importlib.metadata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# ============================================================
# PLUGIN DISCOVERY
# ============================================================

ENTRY_POINT_GROUP = "keanu.abilities"
LEGEND_ENTRY_POINT = "keanu.legends"
LENS_ENTRY_POINT = "keanu.lenses"

@dataclass
class PluginInfo:
    """metadata about a discovered plugin."""
    name: str
    version: str
    package: str
    module: str
    entry_point: str
    loaded: bool = False
    error: str = ""

    def __str__(self):
        status = "loaded" if self.loaded else f"error: {self.error}" if self.error else "pending"
        return f"{self.name} ({self.version}) [{status}]"


def discover_plugins() -> list[PluginInfo]:
    """discover installed plugins via entry_points."""
    plugins = []

    try:
        eps = importlib.metadata.entry_points()
        # Python 3.12+ returns a SelectableGroups, earlier returns dict
        if hasattr(eps, 'select'):
            ability_eps = eps.select(group=ENTRY_POINT_GROUP)
        elif isinstance(eps, dict):
            ability_eps = eps.get(ENTRY_POINT_GROUP, [])
        else:
            ability_eps = [ep for ep in eps if ep.group == ENTRY_POINT_GROUP]
    except Exception:
        return []

    for ep in ability_eps:
        dist = ep.dist
        plugins.append(PluginInfo(
            name=ep.name,
            version=dist.version if dist else "0.0.0",
            package=dist.name if dist else "",
            module=ep.value,
            entry_point=str(ep),
        ))

    return plugins


def load_plugin(info: PluginInfo) -> bool:
    """load a plugin and register its abilities."""
    try:
        module = importlib.import_module(info.module.split(":")[0])
        # if entry point has a callable (module:func), call it
        if ":" in info.module:
            func_name = info.module.split(":")[1]
            func = getattr(module, func_name)
            func()  # register abilities
        info.loaded = True
        return True
    except Exception as e:
        info.error = str(e)
        return False


def load_all_plugins() -> list[PluginInfo]:
    """discover and load all plugins."""
    plugins = discover_plugins()
    for p in plugins:
        load_plugin(p)
    return plugins


# ============================================================
# HOOKS
# ============================================================

@dataclass
class Hook:
    """a hook that fires on an event."""
    event: str
    callback: Callable
    priority: int = 0  # lower = earlier
    plugin: str = ""


# event types
HOOK_EVENTS = [
    "before_edit",      # (filepath, old_content) -> modified content or None
    "after_edit",       # (filepath, new_content) -> None
    "before_test",      # (target) -> None
    "after_test",       # (result) -> None
    "on_error",         # (error_dict) -> None
    "before_commit",    # (message, files) -> modified message or None
    "after_commit",     # (commit_hash) -> None
    "on_miss",          # (prompt) -> None (router miss)
    "before_oracle",    # (prompt, system, legend) -> modified prompt or None
    "after_oracle",     # (response) -> None
    "on_forge",         # (ability_name) -> None
]

_hooks: dict[str, list[Hook]] = {event: [] for event in HOOK_EVENTS}


def register_hook(event: str, callback: Callable, priority: int = 0, plugin: str = ""):
    """register a hook for an event."""
    if event not in _hooks:
        _hooks[event] = []
    hook = Hook(event=event, callback=callback, priority=priority, plugin=plugin)
    _hooks[event].append(hook)
    _hooks[event].sort(key=lambda h: h.priority)


def fire_hook(event: str, *args, **kwargs):
    """fire all hooks for an event. returns first non-None result."""
    for hook in _hooks.get(event, []):
        try:
            result = hook.callback(*args, **kwargs)
            if result is not None:
                return result
        except Exception:
            pass
    return None


def list_hooks() -> dict[str, list[dict]]:
    """list all registered hooks."""
    return {
        event: [{"plugin": h.plugin, "priority": h.priority} for h in hooks]
        for event, hooks in _hooks.items()
        if hooks
    }


def clear_hooks(event: str | None = None):
    """clear hooks for an event, or all hooks."""
    if event:
        _hooks[event] = []
    else:
        for e in _hooks:
            _hooks[e] = []


# ============================================================
# CUSTOM LEGENDS
# ============================================================

def discover_legends() -> list[PluginInfo]:
    """discover custom legends from plugins."""
    try:
        eps = importlib.metadata.entry_points()
        if hasattr(eps, 'select'):
            legend_eps = eps.select(group=LEGEND_ENTRY_POINT)
        elif isinstance(eps, dict):
            legend_eps = eps.get(LEGEND_ENTRY_POINT, [])
        else:
            legend_eps = [ep for ep in eps if ep.group == LEGEND_ENTRY_POINT]
    except Exception:
        return []

    return [
        PluginInfo(
            name=ep.name,
            version=ep.dist.version if ep.dist else "0.0.0",
            package=ep.dist.name if ep.dist else "",
            module=ep.value,
            entry_point=str(ep),
        )
        for ep in legend_eps
    ]


def load_custom_legends():
    """load and register custom legends from plugins."""
    for info in discover_legends():
        try:
            module = importlib.import_module(info.module.split(":")[0])
            if ":" in info.module:
                func = getattr(module, info.module.split(":")[1])
                legend = func()
            else:
                legend = getattr(module, "legend", None)
            if legend:
                from keanu.legends import register_legend
                register_legend(legend)
                info.loaded = True
        except Exception as e:
            info.error = str(e)


# ============================================================
# PLUGIN CONFIG
# ============================================================

def get_plugin_config(plugin_name: str) -> dict:
    """get configuration for a plugin from keanu config."""
    config_file = Path.home() / ".keanu" / "plugins" / f"{plugin_name}.json"
    if config_file.exists():
        import json
        try:
            return json.loads(config_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def set_plugin_config(plugin_name: str, config: dict):
    """save configuration for a plugin."""
    import json
    config_dir = Path.home() / ".keanu" / "plugins"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / f"{plugin_name}.json"
    config_file.write_text(json.dumps(config, indent=2))
