import os
import pwd
import subprocess
import threading
import queue


def run_as_user(command, username):
    # Get the user's UID and GID
    pw_record = pwd.getpwnam(username)
    user_uid = pw_record.pw_uid
    user_gid = pw_record.pw_gid

    def preexec_fn():
        os.setgid(user_gid)
        os.setuid(user_uid)

    return subprocess.Popen(command, preexec_fn=preexec_fn)

def log_subprocess_output(pipe, sub_process):
    for line in iter(pipe.readline, b''): # b'\n'-separated lines
        if line:  # Check if the line is not empty
            print(f'from subprocess: {sub_process} got line: {line.strip()}', flush=True)

class OrderLock:
    """
    A lock that ensures threads acquire the lock in FIFO (first-in, first-out) order
    using queue.Queue(). Each thread places an Event in the queue and waits for
    its Event to be set before proceeding to acquire the internal lock.

    This approach automates queue management, removing the need for manual
    Condition objects and notify/wait calls.

    Usage:
        order_lock = OrderLock()

        def worker(i):
            print(f"Worker {i} waiting for lock")
            with order_lock:
                print(f"Worker {i} acquired lock")
                time.sleep(1)
            print(f"Worker {i} released lock")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    Behavior:
        1. Thread enqueues a threading.Event (thread’s place in line).
        2. If it’s the only event in the queue, it is immediately set.
        3. The thread waits on the Event until it is set, then acquires the lock.
        4. On release, the thread dequeues its own Event and sets the next Event
           in the queue (if any), transferring ownership of the lock to that thread.

    Note:
        - This enforces strict FIFO ordering.
        - If you don’t need ordering, a regular threading.Lock is simpler/faster.
        - If you need complex ordering (e.g., priority), you’ll need a more advanced approach.
    """

    def __init__(self):
        # Lock for the shared resource
        self._resource_lock = threading.Lock()
        # A queue of Event objects, one per waiting thread
        self._queue = queue.Queue()
        # Internal lock to ensure enqueue/dequeue operations are atomic
        self._queue_lock = threading.Lock()

    def acquire(self):
        """Acquire the lock in FIFO order."""
        my_event = threading.Event()

        with self._queue_lock:
            self._queue.put(my_event)
            # If this is the only event in the queue, allow the thread to proceed
            if self._queue.qsize() == 1:
                my_event.set()

        # Block until my_event is set, meaning it's this thread's turn
        my_event.wait()
        self._resource_lock.acquire()

    def release(self):
        """Release the lock, notify the next waiting thread (if any)."""
        self._resource_lock.release()

        with self._queue_lock:
            # Remove this thread’s event from the queue
            finished_event = self._queue.get()
            # Optional: sanity check
            # assert finished_event.is_set()

            # If there is another thread waiting, set its event
            if not self._queue.empty():
                next_event = self._queue.queue[0]  # Peek at the next event
                next_event.set()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
