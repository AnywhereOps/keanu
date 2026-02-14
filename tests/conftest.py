"""Shared test fixtures."""

import pytest
from unittest.mock import patch

from keanu.memory.memberberry import MemberberryStore


@pytest.fixture
def temp_store(tmp_path):
    with patch("keanu.memory.memberberry.MEMBERBERRY_DIR", tmp_path), \
         patch("keanu.memory.memberberry.MEMORIES_FILE", tmp_path / "memories.json"), \
         patch("keanu.memory.memberberry.PLANS_FILE", tmp_path / "plans.json"), \
         patch("keanu.memory.memberberry.CONFIG_FILE", tmp_path / "config.json"):
        yield MemberberryStore()
