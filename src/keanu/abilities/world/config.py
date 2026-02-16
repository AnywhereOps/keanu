"""config.py - configuration management.

layered config: defaults -> global (~/.keanu/config.json) -> project (.keanu.json).
handles model selection, API keys, default legend, feature flags.

in the world: the settings panel. each project can override the
global defaults. the hierarchy flows like water: deep to shallow.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from keanu.paths import keanu_home


_GLOBAL_CONFIG = keanu_home() / "config.json"
_PROJECT_CONFIG_NAME = ".keanu.json"


# ============================================================
# DEFAULTS
# ============================================================

DEFAULTS = {
    "model": "claude-sonnet-4-5-20250929",
    "local_model": "llama3.2",
    "legend": "creator",
    "max_turns": 0,
    "temperature": 0.7,
    "prefer_local": False,
    "auto_bake": True,
    "auto_test": False,
    "auto_lint": False,
    "auto_format": False,
    "streaming": True,
    "color_output": True,
    "history_size": 1000,
    "rag_chunk_size": 50,
    "ops_interval_hours": 24,
}


@dataclass
class Config:
    """merged configuration from all layers."""
    values: dict = field(default_factory=dict)
    source: str = ""  # which layer provided the final values

    def get(self, key: str, default=None):
        return self.values.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value):
        self.values[key] = value

    def __getitem__(self, key: str):
        return self.get(key)

    def __contains__(self, key: str):
        return key in self.values or key in DEFAULTS

    def to_dict(self) -> dict:
        merged = dict(DEFAULTS)
        merged.update(self.values)
        return merged


# ============================================================
# CONFIG LOADING
# ============================================================

def load_global() -> dict:
    """load global config from ~/.keanu/config.json."""
    if not _GLOBAL_CONFIG.exists():
        return {}
    try:
        return json.loads(_GLOBAL_CONFIG.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_global(config: dict):
    """save global config."""
    _GLOBAL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    _GLOBAL_CONFIG.write_text(json.dumps(config, indent=2) + "\n")


def load_project(root: str = ".") -> dict:
    """load project config from .keanu.json in project root."""
    config_path = Path(root) / _PROJECT_CONFIG_NAME
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_project(config: dict, root: str = "."):
    """save project config to .keanu.json."""
    config_path = Path(root) / _PROJECT_CONFIG_NAME
    config_path.write_text(json.dumps(config, indent=2) + "\n")


def load_config(root: str = ".") -> Config:
    """load merged config: defaults -> global -> project -> env."""
    merged = dict(DEFAULTS)

    # layer 1: global
    global_config = load_global()
    merged.update(global_config)

    # layer 2: project
    project_config = load_project(root)
    merged.update(project_config)

    # layer 3: environment overrides
    env_overrides = _env_overrides()
    merged.update(env_overrides)

    source = "defaults"
    if env_overrides:
        source = "env"
    elif project_config:
        source = "project"
    elif global_config:
        source = "global"

    return Config(values=merged, source=source)


def _env_overrides() -> dict:
    """extract config overrides from environment variables."""
    overrides = {}

    env_map = {
        "KEANU_MODEL": "model",
        "KEANU_LOCAL_MODEL": "local_model",
        "KEANU_LEGEND": "legend",
        "KEANU_MAX_TURNS": "max_turns",
        "KEANU_PREFER_LOCAL": "prefer_local",
        "KEANU_STREAMING": "streaming",
    }

    for env_key, config_key in env_map.items():
        value = os.environ.get(env_key)
        if value is not None:
            # type coercion
            if config_key in ("max_turns",):
                try:
                    overrides[config_key] = int(value)
                except ValueError:
                    pass
            elif config_key in ("prefer_local", "streaming"):
                overrides[config_key] = value.lower() in ("true", "1", "yes")
            else:
                overrides[config_key] = value

    return overrides


# ============================================================
# CONFIG HELPERS
# ============================================================

def get_value(key: str, root: str = ".") -> object:
    """get a single config value (merged)."""
    config = load_config(root)
    return config.get(key)


def set_global_value(key: str, value):
    """set a value in the global config."""
    config = load_global()
    config[key] = value
    save_global(config)


def set_project_value(key: str, value, root: str = "."):
    """set a value in the project config."""
    config = load_project(root)
    config[key] = value
    save_project(config, root)


def list_config(root: str = ".") -> dict:
    """list all config values with their sources."""
    global_config = load_global()
    project_config = load_project(root)
    env = _env_overrides()

    result = {}
    for key in DEFAULTS:
        source = "default"
        value = DEFAULTS[key]

        if key in global_config:
            source = "global"
            value = global_config[key]
        if key in project_config:
            source = "project"
            value = project_config[key]
        if key in env:
            source = "env"
            value = env[key]

        result[key] = {"value": value, "source": source}

    return result


def init_project_config(root: str = ".") -> str:
    """initialize a .keanu.json in the project root with defaults."""
    config_path = Path(root) / _PROJECT_CONFIG_NAME
    if config_path.exists():
        return str(config_path)

    default_project = {
        "legend": "creator",
        "max_turns": 0,
    }
    save_project(default_project, root)
    return str(config_path)
