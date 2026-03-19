"""Centralized console management to prevent terminal output conflicts.

This module provides a shared Rich Console instance and coordinates terminal output
between different agents to prevent progress bar flickering and display conflicts.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Global shared console instance
_console = Console()
_console_lock = threading.RLock()  # Use RLock for reentrancy to prevent deadlock

# Track if we're currently inside a live display to prevent nested displays
_live_display_active = threading.local()


def get_console() -> Console:
    """Get the shared console instance."""
    return _console


@contextmanager
def progress_context(description: str) -> Iterator[Progress]:
    """Create a progress context that coordinates with other terminal output.

    Args:
        description: Initial description for the progress bar

    Yields:
        Progress: A Rich Progress instance for tracking tasks, or a no-op Progress
        if another live display is already active.
    """
    with _console_lock:
        # Check if we're already inside a live display (e.g., status_context)
        is_nested = getattr(_live_display_active, 'active', False)

        if is_nested:
            # Return a no-op progress object that just prints updates
            class NoOpProgress:
                def add_task(self, description: str, **kwargs) -> int:
                    print_safe(f"  {description}")
                    return 0

                def update(self, task_id: int, **kwargs) -> None:
                    if 'description' in kwargs:
                        print_safe(f"  {kwargs['description']}")

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    pass

            yield NoOpProgress()  # type: ignore[misc]
        else:
            # Safe to create a real progress display
            _live_display_active.active = True
            try:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=_console,
                    transient=True,
                ) as progress:
                    yield progress
            finally:
                _live_display_active.active = False


@contextmanager
def status_context(message: str, spinner: str = "dots") -> Iterator[Any]:
    """Create a status context that coordinates with other terminal output.

    Args:
        message: Status message to display
        spinner: Spinner style to use

    Yields:
        The status object that can be updated
    """
    with _console_lock:
        _live_display_active.active = True
        try:
            with _console.status(message, spinner=spinner) as status:
                yield status
        finally:
            _live_display_active.active = False


def print_safe(*args: Any, **kwargs: Any) -> None:
    """Thread-safe print using the shared console."""
    with _console_lock:
        _console.print(*args, **kwargs)
