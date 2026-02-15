"""Tests for the interactive REPL."""

from unittest.mock import patch, MagicMock

import pytest


def test_repl_imports():
    """REPL module imports cleanly."""
    from keanu.hero.repl import Repl, run_repl
    assert Repl is not None
    assert run_repl is not None


def test_repl_init_defaults():
    """REPL starts with the creator legend and no specific model.
    The creator is the default AI persona (Claude today, DeepSeek tomorrow)."""
    from keanu.hero.repl import Repl
    repl = Repl()
    assert repl.legend == "creator"
    assert repl.model is None


def test_repl_init_custom():
    """REPL accepts a custom legend (AI persona) and model override.
    The architect legend talks like Drew's partner, not a generic assistant."""
    from keanu.hero.repl import Repl
    repl = Repl(legend="architect", model="llama3")
    assert repl.legend == "architect"
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


def test_slash_legend_set():
    """Switching legends changes which AI persona answers.
    /legend architect tells the oracle to answer as the architect."""
    from keanu.hero.repl import Repl
    repl = Repl(legend="creator")
    repl._handle_slash("/legend architect")
    assert repl.legend == "architect"


def test_slash_legend_invalid():
    """An unknown legend name is rejected, current legend stays.
    Only registered legends (creator, friend, architect) are valid."""
    from keanu.hero.repl import Repl
    repl = Repl(legend="creator")
    repl._handle_slash("/legend invalid")
    assert repl.legend == "creator"


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
