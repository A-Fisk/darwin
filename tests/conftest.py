"""Pytest configuration and fixtures for the darwin test suite."""
import pytest


@pytest.fixture(autouse=True)
def reset_debug_mode():
    """Reset debug mode to default state before each test for proper isolation."""
    from darwin.debug_modes import reset_debug_mode

    # Reset before test
    reset_debug_mode()

    yield

    # Reset after test (cleanup)
    reset_debug_mode()