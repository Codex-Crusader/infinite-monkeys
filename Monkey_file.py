#!/usr/bin/env python3
"""
Infinite Monkey Theorem Simulator - Optimized for Minimum Time Complexity

This implementation is near-optimal for Python because:
1. Uses true parallelism via multiprocessing (bypasses GIL)
2. Minimal synchronization: only a shared Event (lock-free read)
3. Hot loop uses local bindings to eliminate attribute lookups
4. Event checked every 10K iterations (balances responsiveness vs overhead)
5. ''.join(list) is the fastest string construction in CPython
6. randrange(n) is faster than choice() (avoids indexing overhead)

SAFE RUN NOTES:
- This will use 100% CPU on all workers (default: 50 processes)
- Recommended: Set MONKEY_COUNT = os.cpu_count() for optimal performance
- On a laptop, may generate heat - ensure adequate cooling
- Expected time: unpredictable (probability-based, could be seconds to hours+)
- Press Ctrl+C to stop safely
"""

import multiprocessing as mp
import os
from random import randrange
from time import perf_counter
from queue import Empty

# Configuration
TARGET = "Hello world!"
CHARSET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
MONKEY_COUNT = 50  # Recommended: os.cpu_count() or os.cpu_count() * 2
EVENT_CHECK_INTERVAL = 10000  # Check stop event every N attempts


def worker(worker_id, target, charset, stop_event, progress_counter):
    """
    Single worker process - generates random strings until match or stop.

    Optimizations:
    - All variables bound locally to avoid global/attribute lookups
    - randrange pre-bound as local function
    - Pre-calculated length, charset length
    - No I/O in hot loop
    - Event checked periodically, not every iteration
    - Progress updated only when checking stop event (minimal overhead)
    """
    # Local bindings for maximum speed
    rand = randrange
    length = len(target)
    chars = charset
    len_chars = len(charset)
    check_interval = EVENT_CHECK_INTERVAL

    attempts = 0
    local_check_counter = 0

    # Hot loop - optimized for speed
    while not stop_event.is_set():
        # Generate candidate string using list comprehension + join
        # This is faster than alternatives (+=, array, etc.)
        candidate = ''.join([chars[rand(len_chars)] for _ in range(length)])

        attempts += 1
        local_check_counter += 1

        # Check for match
        if candidate == target:
            stop_event.set()  # Signal all workers to stop
            # Update progress one last time
            with progress_counter.get_lock():
                progress_counter.value += local_check_counter
            return worker_id, attempts, candidate

        # Periodically check if another worker found it and update progress
        if local_check_counter >= check_interval:
            # Update shared progress counter (minimal synchronization overhead)
            with progress_counter.get_lock():
                progress_counter.value += check_interval

            local_check_counter = 0
            # is_set() is a fast, lock-free read
            if stop_event.is_set():
                return worker_id, attempts, None

    return worker_id, attempts, None


def worker_wrapper(worker_id, target, charset, stop_event, progress_counter, result_queue):
    """Wrapper to handle queue communication for worker results."""
    try:
        result = worker(worker_id, target, charset, stop_event, progress_counter)
        result_queue.put(result)
    except (KeyboardInterrupt, SystemExit):
        # Allow clean shutdown signals to propagate
        result_queue.put((worker_id, 0, None))
        raise
    except (ValueError, TypeError, RuntimeError):
        # Handle known exceptions that could occur during string generation
        result_queue.put((worker_id, 0, None))


def main():
    """Main execution - spawns workers and coordinates results."""
    print(f"{'=' * 70}")
    print(f"INFINITE MONKEY THEOREM SIMULATOR")
    print(f"{'=' * 70}")
    print(f"Target string: '{TARGET}'")
    print(f"Length: {len(TARGET)} characters")
    print(f"Character set size: {len(CHARSET)}")
    print(f"Search space: {len(CHARSET)}^{len(TARGET)} = {len(CHARSET) ** len(TARGET):.2e} possibilities")
    print(f"Workers: {MONKEY_COUNT}")
    print(f"CPU cores available: {os.cpu_count()}")
    print(f"{'=' * 70}")
    print(f"\n⚠️  WARNING: This will use 100% CPU on {MONKEY_COUNT} processes!")
    print(f"⚠️  Recommended setting: MONKEY_COUNT = {os.cpu_count()} (your CPU count)")
    print(f"\nStarting workers... Press Ctrl+C to stop.\n")

    # Use 'spawn' for clean process isolation (required on macOS/Windows, best on Linux)
    ctx = mp.get_context('spawn')

    # Create shared objects that can be inherited by child processes
    stop_event = ctx.Event()
    progress_counter = ctx.Value('L', 0)  # 'L' = unsigned long
    result_queue = ctx.Queue()

    start_time = perf_counter()
    last_progress_time = start_time

    # Launch workers using Process instead of Pool for Windows compatibility
    processes = []

    try:
        # Start all worker processes
        for i in range(MONKEY_COUNT):
            p = ctx.Process(target=worker_wrapper,
                            args=(i, TARGET, CHARSET, stop_event, progress_counter, result_queue))
            p.start()
            processes.append(p)

        # Wait for first completion (match found or Ctrl+C) and show progress
        while not stop_event.is_set():
            # Check if any results are available
            while not result_queue.empty():
                result = result_queue.get()
                if result[2] is not None:  # Match found
                    stop_event.set()
                    break

            # Print progress every 2 seconds
            current_time = perf_counter()
            if current_time - last_progress_time >= 2.0:
                elapsed = current_time - start_time
                current_attempts = progress_counter.value
                rate = current_attempts / elapsed if elapsed > 0 else 0

                print(f"⏱️  Progress: {current_attempts:,} attempts | "
                      f"{elapsed:.1f}s elapsed | "
                      f"{rate:,.0f} attempts/sec | "
                      f"{MONKEY_COUNT} workers active")

                last_progress_time = current_time

            # Small sleep to avoid busy-waiting
            if not stop_event.is_set():
                import time
                time.sleep(0.1)

        # Signal all workers to stop
        stop_event.set()

        # Wait for all processes to finish
        for p in processes:
            p.join(timeout=2)
            if p.is_alive():
                p.terminate()
                p.join()

        # Collect all results from queue
        all_results = []
        while not result_queue.empty():
            try:
                all_results.append(result_queue.get_nowait())
            except Empty:
                # Queue is empty, no more results to collect
                break

        elapsed = perf_counter() - start_time

        # Find winner and calculate stats
        winner = None
        total_attempts = progress_counter.value

        for worker_id, attempts, match in all_results:
            if match is not None:
                winner = (worker_id, attempts, match)

        # Display results
        print(f"\n{'=' * 70}")
        print(f"RESULT")
        print(f"{'=' * 70}")

        if winner:
            w_id, w_attempts, w_match = winner
            print(f"✓ MATCH FOUND!")
            print(f"  Worker #{w_id} found: '{w_match}'")
            print(f"  Worker attempts: {w_attempts:,}")
            print(f"  Total attempts (all workers): {total_attempts:,}")
            print(f"  Time elapsed: {elapsed:.2f} seconds")
            print(f"  Rate: {total_attempts / elapsed:,.0f} attempts/second")
            print(f"  Theoretical probability: 1 in {len(CHARSET) ** len(TARGET):.2e}")
        else:
            print(f"✗ No match found (interrupted)")
            print(f"  Total attempts: {total_attempts:,}")
            print(f"  Time elapsed: {elapsed:.2f} seconds")

        print(f"{'=' * 70}")

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Interrupted by user. Stopping workers...")
        stop_event.set()
        for p in processes:
            p.terminate()
            p.join()
        print(f"✓ All workers stopped.")


if __name__ == "__main__":
    # Ensure proper multiprocessing on Windows/macOS
    mp.freeze_support()
    main()