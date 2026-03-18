"""Test that __main__.py exposes the correct entry point."""
from __future__ import annotations

import importlib


def test_main_module_callable() -> None:
    """darwin.__main__ should be importable without error."""
    mod = importlib.import_module("darwin.__main__")
    assert hasattr(mod, "main")
