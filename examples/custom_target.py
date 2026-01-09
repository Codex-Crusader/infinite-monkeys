#!/usr/bin/env python3
"""
Custom Target Example

Shows how to customize the simulation:
- Different target strings
- Custom character sets
- Adjusted worker counts

Try these targets (from easiest to hardest):
- "OK" - seconds
- "Yes!" - minutes
- "Hello" - could be hours
- "Hello world!" - potentially never!
"""

import multiprocessing as mp
import os
from random import randrange
from time import perf_counter
from queue import Empty

# ============================================================================
# CUSTOMIZE THESE SETTINGS
# ============================================================================

# Target string to find
TARGET = "Code!"  # Try: "OK", "Yes!", "Hello", "Python", etc.

# Character set options:
# 1. Letters only (faster)
# CHARSET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

# 2. Letters + numbers (medium)
# CHARSET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

# 3. Full ASCII (slowest, but matches any printable character)
CHARSET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"

# Number of worker processes
MONKEY_COUNT = os.cpu_count()  # Use all CPU cores

# How often to check for stop signal (lower = more responsive, slightly slower)
EVENT_CHECK_INTERVAL = 10000


# ============================================================================


def worker(worker_id, target, charset, stop_event, progress_counter):
    """Generate random strings until match."""
    rand = randrange
    length = len(target)
    chars = charset
    len_chars = len(charset)
    check_interval = EVENT_CHECK_INTERVAL

    attempts = 0
    local_check_counter = 0

    while not stop_event.is_set():
        candidate = ''.join([chars[rand(len_chars)] for _ in range(length)])
        attempts += 1
        local_check_counter += 1

        if candidate == target:
            stop_event.set()
            with progress_counter.get_lock():
                progress_counter.value += local_check_counter
            return worker_id, attempts, candidate

        if local_check_counter >= check_interval:
            with progress_counter.get_lock():
                progress_counter.value += check_interval
            local_check_counter = 0
            if stop_event.is_set():
                return worker_id, attempts, None

    return worker_id, attempts, None


def worker_wrapper(worker_id, target, charset, stop_event, progress_counter, result_queue):
    try:
        result = worker(worker_id, target, charset, stop_event, progress_counter)
        result_queue.put(result)
    except (KeyboardInterrupt, SystemExit):
        result_queue.put((worker_id, 0, None))
        raise
    except (ValueError, TypeError, RuntimeError):
        result_queue.put((worker_id, 0, None))


def main():
    # Calculate difficulty
    search_space = len(CHARSET) ** len(TARGET)

    print("=" * 70)
    print("CUSTOM TARGET - Infinite Monkey Theorem")
    print("=" * 70)
    print(f"Target: '{TARGET}'")
    print(f"Length: {len(TARGET)} characters")
    print(f"Character set size: {len(CHARSET)}")
    print(f"Search space: {len(CHARSET)}^{len(TARGET)} = {search_space:.2e} possibilities")
    print(f"Workers: {MONKEY_COUNT}")
    print(f"CPU cores: {os.cpu_count()}")

    # Estimate difficulty
    if search_space < 1_000_000:
        print(f"\n💚 EASY - Should complete in seconds!")
    elif search_space < 100_000_000:
        print(f"\n💛 MEDIUM - Could take minutes to hours")
    elif search_space < 10_000_000_000:
        print(f"\n🧡 HARD - Could take hours to days")
    else:
        print(f"\n❤️  VERY HARD - Could take days/weeks or never complete!")

    print("\nPress Ctrl+C to stop anytime.\n")

    ctx = mp.get_context('spawn')
    stop_event = ctx.Event()
    progress_counter = ctx.Value('L', 0)
    result_queue = ctx.Queue()

    start_time = perf_counter()
    last_progress = start_time
    processes = []

    try:
        for i in range(MONKEY_COUNT):
            p = ctx.Process(target=worker_wrapper,
                            args=(i, TARGET, CHARSET, stop_event, progress_counter, result_queue))
            p.start()
            processes.append(p)

        # Progress loop
        while not stop_event.is_set():
            while not result_queue.empty():
                result = result_queue.get()
                if result[2] is not None:
                    stop_event.set()
                    break

            # Print progress every 2 seconds
            current_time = perf_counter()
            if current_time - last_progress >= 2.0:
                elapsed = current_time - start_time
                attempts = progress_counter.value
                rate = attempts / elapsed if elapsed > 0 else 0
                print(f"⏱️  {attempts:,} attempts | {elapsed:.1f}s | {rate:,.0f}/sec")
                last_progress = current_time

            if not stop_event.is_set():
                import time
                time.sleep(0.1)

        stop_event.set()

        for p in processes:
            p.join(timeout=2)
            if p.is_alive():
                p.terminate()
                p.join()

        # Results
        winner = None
        while not result_queue.empty():
            try:
                result = result_queue.get_nowait()
                if result[2] is not None:
                    winner = result
            except Empty:
                break

        elapsed = perf_counter() - start_time

        print("\n" + "=" * 70)
        print("RESULT")
        print("=" * 70)

        if winner:
            w_id, w_attempts, w_match = winner
            print(f"✓ MATCH FOUND!")
            print(f"  Worker #{w_id} found: '{w_match}'")
            print(f"  Time: {elapsed:.2f} seconds")
            print(f"  Total attempts: {progress_counter.value:,}")
            print(f"  Rate: {progress_counter.value / elapsed:,.0f} attempts/second")
            print(f"  Probability: 1 in {search_space:.2e}")
        else:
            print("✗ No match found (interrupted)")
            print(f"  Total attempts: {progress_counter.value:,}")
            print(f"  Time: {elapsed:.2f} seconds")

        print("=" * 70)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted. Stopping workers...")
        stop_event.set()
        for p in processes:
            p.terminate()
            p.join()
        print("✓ Stopped.")


if __name__ == "__main__":
    mp.freeze_support()
    main()