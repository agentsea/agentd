import subprocess
import os
import signal


def is_chromium_running() -> list:
    """
    Checks if Chromium is running and returns a list of PIDs.
    """
    try:
        output = subprocess.check_output(["pgrep", "-f", "chromium"])
        return [int(pid) for pid in output.decode().strip().split("\n")]
    except subprocess.CalledProcessError:
        return []


def is_chromium_window_open():
    try:
        output = subprocess.check_output(["wmctrl", "-l"])
        return "Chromium" in output.decode()
    except subprocess.CalledProcessError:
        return False


def gracefully_terminate_chromium(pids: list):
    """
    Attempts to gracefully terminate Chromium processes given their PIDs.
    """
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Sent SIGTERM to Chromium process {pid}.")
        except ProcessLookupError:
            print(f"Chromium process {pid} not found.")
        except Exception as e:
            print(f"Error terminating Chromium process {pid}: {e}")
