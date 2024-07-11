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
        output = subprocess.check_output(["xdotool", "search", "--onlyvisible", "--class", "firefox"])
        return bool(output.strip())
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

def maximize_firefox_window():
    """
    Maximizes the Firefox window.
    """
    try:
        window_id = subprocess.check_output(["xdotool", "search", "--onlyvisible", "--class", "firefox"]).strip().decode('utf-8')
        subprocess.run(["wmctrl", "-i", "-r", window_id, "-b", "add,maximized_vert,maximized_horz"], check=True)
        print(f"Maximized Firefox window with window ID {window_id}")
    except subprocess.CalledProcessError:
        print("Failed to maximize Firefox window.")