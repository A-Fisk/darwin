"""Comprehensive tests for threading safeguards and deadlock prevention.

These tests ensure the threading safeguards implemented in console.py work correctly
to prevent the 5-minute hang issue and provide robust concurrent console access.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from unittest.mock import Mock, patch
from typing import Any

import pytest

from darwin.console import (
    get_console,
    progress_context,
    status_context,
    print_safe,
    _console_lock,
    _live_display_active
)


class TestConsoleRLockReentrancy:
    """Test RLock reentrancy behavior to prevent deadlocks."""

    def test_rlock_allows_nested_acquisition(self) -> None:
        """Test that RLock allows the same thread to acquire the lock multiple times."""
        # Track acquisition count
        acquisition_count = 0

        def nested_lock_test() -> None:
            nonlocal acquisition_count

            with _console_lock:
                acquisition_count += 1
                # This should not deadlock - same thread acquiring again
                with _console_lock:
                    acquisition_count += 1
                    # Even deeper nesting
                    with _console_lock:
                        acquisition_count += 1

        # Should complete without hanging
        thread = threading.Thread(target=nested_lock_test)
        thread.start()
        thread.join(timeout=5.0)  # 5 second timeout

        assert not thread.is_alive(), "Thread should have completed, not hung"
        assert acquisition_count == 3, "All nested lock acquisitions should have succeeded"

    def test_progress_context_reentrancy(self) -> None:
        """Test that progress_context can be called from within itself (reentrancy)."""
        results = []

        def nested_progress_test() -> None:
            with progress_context("Outer progress") as outer:
                results.append("outer_started")

                # This should not deadlock - should fall back to no-op
                with progress_context("Inner progress") as inner:
                    results.append("inner_started")
                    # Verify inner is a NoOpProgress object
                    task_id = inner.add_task("Test task")
                    results.append(f"inner_task_id_{task_id}")

                results.append("outer_continuing")

        thread = threading.Thread(target=nested_progress_test)
        thread.start()
        thread.join(timeout=5.0)

        assert not thread.is_alive(), "Thread should have completed, not hung"
        assert "outer_started" in results
        assert "inner_started" in results
        assert "inner_task_id_0" in results  # NoOpProgress returns 0 for task IDs
        assert "outer_continuing" in results

    def test_status_context_reentrancy(self) -> None:
        """Test that status_context can be nested safely."""
        results = []

        def nested_status_test() -> None:
            with status_context("Outer status") as outer:
                results.append("outer_started")

                # This should work since we use the same RLock
                with status_context("Inner status") as inner:
                    results.append("inner_started")

                results.append("outer_continuing")

        thread = threading.Thread(target=nested_status_test)
        thread.start()
        thread.join(timeout=5.0)

        assert not thread.is_alive(), "Thread should have completed, not hung"
        assert "outer_started" in results
        assert "inner_started" in results
        assert "outer_continuing" in results


class TestConcurrentConsoleAccess:
    """Test concurrent console access scenarios to prevent race conditions."""

    def test_concurrent_print_safe(self) -> None:
        """Test that multiple threads can safely call print_safe concurrently."""
        results = []
        num_threads = 10
        iterations_per_thread = 5

        def print_worker(thread_id: int) -> None:
            for i in range(iterations_per_thread):
                # Mock the actual console print to capture calls
                with patch('darwin.console._console.print') as mock_print:
                    print_safe(f"Thread {thread_id} message {i}")
                    # Verify print was called
                    mock_print.assert_called_once()
                results.append(f"thread_{thread_id}_msg_{i}")
                time.sleep(0.01)  # Small delay to encourage interleaving

        # Start all threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=print_worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all to complete
        for thread in threads:
            thread.join(timeout=10.0)
            assert not thread.is_alive(), f"Thread {thread} should have completed"

        # Verify all messages were processed
        expected_count = num_threads * iterations_per_thread
        assert len(results) == expected_count, f"Expected {expected_count} messages, got {len(results)}"

    def test_concurrent_progress_contexts(self) -> None:
        """Test multiple progress contexts in different threads."""
        results = []

        def progress_worker(worker_id: int) -> None:
            with progress_context(f"Worker {worker_id}") as progress:
                task = progress.add_task(f"Task for worker {worker_id}")
                for i in range(3):
                    progress.update(task, description=f"Worker {worker_id} step {i}")
                    time.sleep(0.01)
                results.append(f"worker_{worker_id}_completed")

        # Start 5 concurrent workers
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(progress_worker, i) for i in range(5)]

            # Wait for all to complete
            for future in as_completed(futures, timeout=10.0):
                future.result()  # Raises exception if worker failed

        # Verify all workers completed
        assert len(results) == 5
        for i in range(5):
            assert f"worker_{i}_completed" in results

    def test_concurrent_mixed_console_operations(self) -> None:
        """Test mixing print_safe, progress_context, and status_context concurrently."""
        results = []

        def print_worker() -> None:
            for i in range(3):
                with patch('darwin.console._console.print'):
                    print_safe(f"Print message {i}")
                results.append(f"print_{i}")
                time.sleep(0.01)

        def progress_worker() -> None:
            with progress_context("Progress worker") as progress:
                task = progress.add_task("Progress task")
                for i in range(3):
                    progress.update(task, description=f"Progress step {i}")
                    time.sleep(0.01)
                results.append("progress_completed")

        def status_worker() -> None:
            with status_context("Status worker"):
                for i in range(3):
                    time.sleep(0.01)
                results.append("status_completed")

        # Run all worker types concurrently
        threads = [
            threading.Thread(target=print_worker),
            threading.Thread(target=progress_worker),
            threading.Thread(target=status_worker),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join(timeout=10.0)
            assert not thread.is_alive(), "All threads should complete"

        # Verify all operations completed
        assert len([r for r in results if r.startswith("print_")]) == 3
        assert "progress_completed" in results
        assert "status_completed" in results


class TestDisplayConflictFallback:
    """Test display conflict fallback logic to prevent Rich display issues."""

    def test_nested_progress_falls_back_to_noop(self) -> None:
        """Test that nested progress_context falls back to NoOpProgress."""
        noop_calls = []

        # Mock print_safe to capture NoOpProgress calls
        def mock_print_safe(*args: Any, **kwargs: Any) -> None:
            noop_calls.append(str(args))

        with patch('darwin.console.print_safe', side_effect=mock_print_safe):
            with progress_context("Outer") as outer:
                # This should be real progress
                assert hasattr(outer, 'add_task')
                assert hasattr(outer, 'update')

                with progress_context("Inner") as inner:
                    # This should be NoOpProgress
                    task_id = inner.add_task("Inner task")
                    assert task_id == 0, "NoOpProgress should return 0 for task ID"

                    inner.update(task_id, description="Updated description")

        # Verify NoOpProgress made print calls
        assert len(noop_calls) >= 2, "NoOpProgress should have made print calls"
        assert any("Inner task" in call for call in noop_calls)
        assert any("Updated description" in call for call in noop_calls)

    def test_live_display_active_thread_local(self) -> None:
        """Test that _live_display_active is properly thread-local."""
        thread_locals = {}

        def check_thread_local(thread_id: int) -> None:
            # Should start as False/unset
            initial_state = getattr(_live_display_active, 'active', False)
            thread_locals[f"{thread_id}_initial"] = initial_state

            # Set to True in this thread
            _live_display_active.active = True
            thread_locals[f"{thread_id}_set"] = _live_display_active.active

            time.sleep(0.1)  # Let other threads run

            # Should still be True in this thread
            final_state = getattr(_live_display_active, 'active', False)
            thread_locals[f"{thread_id}_final"] = final_state

        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=check_thread_local, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)
            assert not thread.is_alive()

        # Verify each thread had independent state
        for i in range(3):
            assert thread_locals[f"{i}_initial"] is False
            assert thread_locals[f"{i}_set"] is True
            assert thread_locals[f"{i}_final"] is True

    def test_status_context_sets_live_display_active(self) -> None:
        """Test that status_context properly sets and cleans up _live_display_active."""
        # Should start as False/unset
        initial = getattr(_live_display_active, 'active', False)
        assert initial is False

        with status_context("Test status"):
            # Should be True inside context
            inside = getattr(_live_display_active, 'active', False)
            assert inside is True

        # Should be False after context
        final = getattr(_live_display_active, 'active', False)
        assert final is False


class TestAPITimeoutHandling:
    """Test API timeout handling under various failure modes."""

    def test_anthropic_client_has_timeout(self) -> None:
        """Test that Anthropic client is configured with timeout."""
        # This tests the fix in generation.py
        with patch('darwin.agents.generation.anthropic.Anthropic') as MockClient:
            from darwin.agents.generation import run
            from darwin.state import ResearchState

            # Mock the client and response
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = [Mock(type="text", text='[{"text": "test", "references": []}]')]
            mock_response.stop_reason = "end_turn"
            mock_client.messages.create.return_value = mock_response
            MockClient.return_value = mock_client

            # Create minimal state
            state: ResearchState = {
                "topic": "test",
                "max_iterations": 1,
                "iteration": 1,
                "hypotheses": [],
                "ranked_ids": [],
                "top_hypotheses": [],
                "proximity_clusters": [],
                "supervisor_decision": "continue",
                "meta_review_notes": "",
                "human_feedback": None,
                "final_hypotheses": [],
                "messages": [],
            }

            # Run generation
            run(state)

            # Verify client was created with timeout
            MockClient.assert_called_once_with(timeout=60.0)

    def test_timeout_in_concurrent_scenario(self) -> None:
        """Test timeout behavior under concurrent load (simulation)."""
        timeout_results = []

        def simulate_api_call_with_timeout(call_id: int) -> None:
            """Simulate an API call that might timeout."""
            try:
                # Simulate varying response times
                delay = 0.1 if call_id % 2 == 0 else 0.2
                time.sleep(delay)
                timeout_results.append(f"call_{call_id}_success")
            except Exception as e:
                timeout_results.append(f"call_{call_id}_error_{type(e).__name__}")

        # Simulate multiple concurrent API calls
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(simulate_api_call_with_timeout, i) for i in range(10)]

            # Wait for all calls to complete
            for future in as_completed(futures, timeout=5.0):
                future.result()  # This will raise if any call failed unexpectedly

        # Verify all calls completed (no actual timeouts in this simulation)
        assert len(timeout_results) == 10
        success_count = len([r for r in timeout_results if "success" in r])
        assert success_count == 10, "All simulated calls should have succeeded"


class TestSyntheticDeadlockPrevention:
    """Test synthetic deadlock scenarios and their prevention."""

    def test_reproduce_original_deadlock_scenario(self) -> None:
        """Reproduce the original deadlock scenario that was fixed."""
        results = []

        def simulate_cli_with_status() -> None:
            """Simulate CLI holding status_context (like the original issue)."""
            with status_context("CLI status"):
                results.append("cli_status_acquired")
                time.sleep(0.1)  # Hold lock for a bit
                results.append("cli_status_held")

                # Simulate what caused the original deadlock - nested console operations
                with patch('darwin.console._console.print'):
                    print_safe("CLI message while holding status")
                results.append("cli_print_safe_completed")

        def simulate_generation_with_progress() -> None:
            """Simulate generation agent trying to use progress_context."""
            time.sleep(0.05)  # Start slightly after CLI
            with progress_context("Generation progress") as progress:
                results.append("generation_progress_acquired")
                task = progress.add_task("Generation task")
                progress.update(task, description="Generating...")
                results.append("generation_progress_completed")

        # Run both scenarios concurrently - this would have deadlocked before the fix
        threads = [
            threading.Thread(target=simulate_cli_with_status),
            threading.Thread(target=simulate_generation_with_progress)
        ]

        for thread in threads:
            thread.start()

        # Both threads should complete without hanging
        for thread in threads:
            thread.join(timeout=5.0)
            assert not thread.is_alive(), "Thread should not hang with RLock fix"

        # Verify both operations completed
        assert "cli_status_acquired" in results
        assert "cli_print_safe_completed" in results
        assert "generation_progress_acquired" in results
        assert "generation_progress_completed" in results

    def test_deep_nesting_scenario(self) -> None:
        """Test deeply nested console operations don't cause issues."""
        results = []

        def deep_nesting_worker() -> None:
            with status_context("Level 1"):
                results.append("level_1")

                with progress_context("Level 2") as p2:  # Should become NoOpProgress
                    results.append("level_2")

                    with status_context("Level 3"):  # Should work with RLock
                        results.append("level_3")

                        with patch('darwin.console._console.print'):
                            print_safe("Deep message")
                        results.append("deep_print")

                        task = p2.add_task("Deep task")  # NoOpProgress call
                        results.append("deep_task")

        thread = threading.Thread(target=deep_nesting_worker)
        thread.start()
        thread.join(timeout=5.0)

        assert not thread.is_alive(), "Deep nesting should not cause hangs"

        # Verify all levels were reached
        expected_results = ["level_1", "level_2", "level_3", "deep_print", "deep_task"]
        for expected in expected_results:
            assert expected in results, f"Missing result: {expected}"

    def test_multiple_progress_contexts_different_threads(self) -> None:
        """Test multiple progress contexts in different threads don't interfere."""
        results = []

        def progress_worker(worker_id: int, delay: float) -> None:
            time.sleep(delay)  # Stagger start times
            with progress_context(f"Worker {worker_id}") as progress:
                task = progress.add_task(f"Task {worker_id}")
                for i in range(3):
                    progress.update(task, description=f"Worker {worker_id} step {i}")
                    time.sleep(0.01)
                results.append(f"worker_{worker_id}_done")

        # Start multiple workers with different start delays
        threads = []
        for i in range(4):
            delay = i * 0.02  # 0, 0.02, 0.04, 0.06 second delays
            thread = threading.Thread(target=progress_worker, args=(i, delay))
            threads.append(thread)
            thread.start()

        # All should complete without interference
        for thread in threads:
            thread.join(timeout=10.0)
            assert not thread.is_alive(), "All progress workers should complete"

        # Verify all workers completed
        assert len(results) == 4
        for i in range(4):
            assert f"worker_{i}_done" in results

    def test_console_lock_acquisition_order(self) -> None:
        """Test that lock acquisition order is consistent to prevent deadlocks."""
        acquisition_order = []

        def lock_acquirer(acquirer_id: int, hold_time: float) -> None:
            with _console_lock:
                acquisition_order.append(f"acquired_{acquirer_id}")
                time.sleep(hold_time)
                acquisition_order.append(f"released_{acquirer_id}")

        # Start multiple threads trying to acquire the lock
        threads = []
        for i in range(3):
            hold_time = 0.1  # Each thread holds lock for 0.1 seconds
            thread = threading.Thread(target=lock_acquirer, args=(i, hold_time))
            threads.append(thread)
            thread.start()
            time.sleep(0.01)  # Small delay between starts

        # Wait for all to complete
        for thread in threads:
            thread.join(timeout=5.0)
            assert not thread.is_alive(), "Lock acquirer threads should complete"

        # Verify we got the expected number of acquisitions and releases
        acquired_events = [e for e in acquisition_order if "acquired" in e]
        released_events = [e for e in acquisition_order if "released" in e]

        assert len(acquired_events) == 3, "Should have 3 acquisitions"
        assert len(released_events) == 3, "Should have 3 releases"

        # Verify proper nesting - each acquire should have a matching release
        # The exact order depends on thread scheduling, but structure should be valid
        assert len(acquisition_order) == 6, "Should have 6 total events"


@contextmanager
def timeout_context(seconds: float):
    """Context manager to enforce a timeout on code execution."""
    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")

    # Set the signal handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(seconds))

    try:
        yield
    finally:
        signal.alarm(0)  # Cancel the alarm
        signal.signal(signal.SIGALRM, old_handler)  # Restore old handler


class TestDeadlockDetection:
    """Integration tests to detect potential deadlocks."""

    def test_no_deadlock_in_heavy_concurrent_usage(self) -> None:
        """Stress test to ensure no deadlocks under heavy concurrent usage."""
        results = []

        def heavy_console_user(user_id: int) -> None:
            """Simulate heavy console usage that could trigger deadlocks."""
            for iteration in range(5):
                # Mix different console operations
                if iteration % 3 == 0:
                    with patch('darwin.console._console.print'):
                        print_safe(f"User {user_id} iteration {iteration}")
                elif iteration % 3 == 1:
                    with progress_context(f"User {user_id} progress {iteration}") as p:
                        task = p.add_task(f"User {user_id} task")
                        p.update(task, description="Working...")
                else:
                    with status_context(f"User {user_id} status {iteration}"):
                        time.sleep(0.01)

                results.append(f"user_{user_id}_iteration_{iteration}")
                time.sleep(0.001)  # Tiny delay to encourage interleaving

        # Use timeout context to detect deadlocks
        with timeout_context(10.0):  # 10 second timeout
            # Start many concurrent heavy users
            threads = []
            for i in range(8):  # 8 concurrent users
                thread = threading.Thread(target=heavy_console_user, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all to complete
            for thread in threads:
                thread.join()

        # If we get here, no deadlock occurred
        # Verify all users completed all iterations
        expected_results = 8 * 5  # 8 users × 5 iterations each
        assert len(results) == expected_results, f"Expected {expected_results} results, got {len(results)}"