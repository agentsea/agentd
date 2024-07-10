import os
import signal
import subprocess

def is_firefox_running() -> list:
    """
    Checks if Firefox is running and returns a list of PIDs.
    """
    try:
        output = subprocess.check_output(["pgrep", "-f", "firefox"])
        return [int(pid) for pid in output.decode().strip().split("\n")]
    except subprocess.CalledProcessError:
        return []

def is_firefox_window_open():
    try:
        output = subprocess.check_output(["wmctrl", "-l", "-x"])
        return "Navigator.Firefox" in output.decode()
    except subprocess.CalledProcessError:
        return False

def gracefully_terminate_firefox(pids: list):
    """
    Attempts to gracefully terminate Firefox processes given their PIDs.
    """
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Sent SIGTERM to Firefox process {pid}.")
        except ProcessLookupError:
            print(f"Firefox process {pid} not found.")
        except Exception as e:
            print(f"Error terminating Firefox process {pid}: {e}")
