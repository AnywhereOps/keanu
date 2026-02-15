"""Tests for the interactive REPL."""

from unittest.mock import patch, MagicMock

import pytest


def test_repl_imports():
    """REPL module imports cleanly."""
    from keanu.hero.repl import Repl, run_repl
    assert Repl is not None
    assert run_repl is not None


def test_repl_init_defaults():
    """REPL initializes with default backend and model."""
    from keanu.hero.repl import Repl
    repl = Repl()
    assert repl.backend == "claude"
    assert repl.model is None


def test_repl_init_custom():
    """REPL accepts custom backend and model."""
    from keanu.hero.repl import Repl
    repl = Repl(backend="ollama", model="llama3")
    assert repl.backend == "ollama"
    assert repl.model == "llama3"


def test_slash_quit():
    """Slash quit returns True (should exit)."""
    from keanu.hero.repl import Repl
    repl = Repl()
    assert repl._handle_slash("/quit") is True
    assert repl._handle_slash("/q") is True
    assert repl._handle_slash("/exit") is True


def test_slash_help():
    """Slash help returns False (don't exit)."""
    from keanu.hero.repl import Repl
    repl = Repl()
    assert repl._handle_slash("/help") is False


def test_slash_model_show():
    """Slash model with no arg shows current model."""
    from keanu.hero.repl import Repl
    repl = Repl(model="test-model")
    assert repl._handle_slash("/model") is False
    assert repl.model == "test-model"


def test_slash_model_set():
    """Slash model with arg changes model."""
    from keanu.hero.repl import Repl
    repl = Repl()
    repl._handle_slash("/model gpt-4")
    assert repl.model == "gpt-4"


def test_slash_backend_set():
    """Slash backend with valid arg changes backend."""
    from keanu.hero.repl import Repl
    repl = Repl(backend="claude")
    repl._handle_slash("/backend ollama")
    assert repl.backend == "ollama"


def test_slash_backend_invalid():
    """Slash backend with invalid arg does not change backend."""
    from keanu.hero.repl import Repl
    repl = Repl(backend="claude")
    repl._handle_slash("/backend invalid")
    assert repl.backend == "claude"


def test_slash_unknown():
    """Unknown slash command returns False."""
    from keanu.hero.repl import Repl
    repl = Repl()
    assert repl._handle_slash("/unknown") is False


def test_slash_abilities():
    """Slash abilities returns False (lists abilities)."""
    from keanu.hero.repl import Repl
    repl = Repl()
    assert repl._handle_slash("/abilities") is False
