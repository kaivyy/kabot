"""Quarantined PIDLock multiprocessing stress test.

Reason: Windows sandbox/permission constraints can block named pipe creation.
"""

import multiprocessing
from pathlib import Path

from kabot.utils.pid_lock import PIDLock


def _concurrent_worker(lock_path, results_queue, worker_id):
    try:
        import time

        lock = PIDLock(Path(lock_path), timeout=2)
        lock.acquire()

        test_file = Path(lock_path).parent / "shared_counter.txt"
        if test_file.exists():
            with open(test_file) as f:
                count = int(f.read().strip())
        else:
            count = 0

        time.sleep(0.1)
        with open(test_file, "w") as f:
            f.write(str(count + 1))

        lock.release()
        results_queue.put(("success", worker_id))
    except Exception as e:
        results_queue.put(("error", str(e)))


def test_concurrent_process_safety(tmp_path):
    """Test that only one process can hold lock at a time."""
    temp_lock_path = tmp_path / "test_resource.json"
    num_workers = 5
    results_queue = multiprocessing.Queue()
    processes = []

    for i in range(num_workers):
        p = multiprocessing.Process(
            target=_concurrent_worker,
            args=(str(temp_lock_path), results_queue, i),
        )
        p.start()
        processes.append(p)

    for p in processes:
        p.join(timeout=10)

    results = []
    while not results_queue.empty():
        results.append(results_queue.get())

    assert len(results) == num_workers
    assert all(status == "success" for status, _ in results)

    counter_file = temp_lock_path.parent / "shared_counter.txt"
    with open(counter_file) as f:
        final_count = int(f.read().strip())
    assert final_count == num_workers
