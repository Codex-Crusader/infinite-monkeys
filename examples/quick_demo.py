#!/usr/bin/env python3
"""
Quick Demo - Infinite Monkey Theorem

This will find "Hi!" in seconds (not hours!)
Search space: 94^3 = 830,584 possibilities

Perfect for testing that everything works.
"""

import multiprocessing as mp
from random import randrange
from time import perf_counter
from queue import Empty

# Simple configuration - finds match in seconds!
TARGET = "Hi!"
CHARSET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
MONKEY_COUNT = 8  # Lower count for quick demo
EVENT_CHECK_INTERVAL = 5000


def worker(worker_id, target, charset, stop_event, progress_counter):
    """Generate random strings until we match the target."""
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
    """Wrapper to handle results."""
    try:
        result = worker(worker_id, target, charset, stop_event, progress_counter)
        result_queue.put(result)
    except (KeyboardInterrupt, SystemExit):
        result_queue.put((worker_id, 0, None))
        raise
    except (ValueError, TypeError, RuntimeError):
        result_queue.put((worker_id, 0, None))


def main():
    print("=" * 60)
    print("QUICK DEMO - Infinite Monkey Theorem")
    print("=" * 60)
    print(f"Target: '{TARGET}' (only {len(TARGET)} characters!)")
    print(f"Search space: {len(CHARSET)}^{len(TARGET)} = {len(CHARSET)**len(TARGET):,} possibilities")
    print(f"Workers: {MONKEY_COUNT}")
    print(f"\nThis should complete in SECONDS, not hours! 🚀\n")

    ctx = mp.get_context('spawn')
    stop_event = ctx.Event()
    progress_counter = ctx.Value('L', 0)
    result_queue = ctx.Queue()

    start_time = perf_counter()
    processes = []

    try:
        for i in range(MONKEY_COUNT):
            p = ctx.Process(target=worker_wrapper,
                          args=(i, TARGET, CHARSET, stop_event, progress_counter, result_queue))
            p.start()
            processes.append(p)

        # Wait for completion
        while not stop_event.is_set():
            while not result_queue.empty():
                result = result_queue.get()
                if result[2] is not None:
                    stop_event.set()
                    break

            if not stop_event.is_set():
                import time
                time.sleep(0.05)

        stop_event.set()

        for p in processes:
            p.join(timeout=1)
            if p.is_alive():
                p.terminate()
                p.join()

        # Collect results
        winner = None
        while not result_queue.empty():
            try:
                result = result_queue.get_nowait()
                if result[2] is not None:
                    winner = result
            except Empty:
                break

        elapsed = perf_counter() - start_time

        print("\n" + "=" * 60)
        if winner:
            w_id, w_attempts, w_match = winner
            print(f"✓ SUCCESS! Worker #{w_id} found: '{w_match}'")
            print(f"  Time: {elapsed:.2f} seconds")
            print(f"  Total attempts: {progress_counter.value:,}")
            print(f"  Rate: {progress_counter.value/elapsed:,.0f} attempts/sec")
        else:
            print("✗ No match (interrupted)")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Stopping...")
        stop_event.set()
        for p in processes:
            p.terminate()
            p.join()


if __name__ == "__main__":
    mp.freeze_support()
    main()