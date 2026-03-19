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
_console_lock = threading.Lock()


def get_console() -> Console:
    """Get the shared console instance."""
    return _console


@contextmanager
def progress_context(description: str) -> Iterator[Progress]:
    """Create a progress context that coordinates with other terminal output.

    Args:
        description: Initial description for the progress bar

    Yields:
        Progress: A Rich Progress instance for tracking tasks
    """
    with _console_lock:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=_console,
            transient=True,
        ) as progress:
            yield progress


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
        with _console.status(message, spinner=spinner) as status:
            yield status


def print_safe(*args: Any, **kwargs: Any) -> None:
    """Thread-safe print using the shared console."""
    with _console_lock:
        _console.print(*args, **kwargs)
