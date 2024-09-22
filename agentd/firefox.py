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
        output = subprocess.check_output(
            ["xdotool", "search", "--onlyvisible", "--class", "firefox"]
        )
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
    Maximizes the Firefox window by resizing it to the full screen size.
    """
    try:
        # Get the window ID(s) of the Firefox window(s)
        window_ids_output = subprocess.check_output(
            ["xdotool", "search", "--onlyvisible", "--class", "firefox"]
        )
        window_ids = window_ids_output.decode("utf-8").split()

        # Get the display geometry (screen width and height)
        geometry_output = subprocess.check_output(["xdotool", "getdisplaygeometry"])
        screen_width, screen_height = geometry_output.decode("utf-8").split()

        for window_id in window_ids:
            # Activate the window
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", window_id], check=True
            )

            # Resize the window to match the screen dimensions
            subprocess.run(
                ["xdotool", "windowsize", window_id, screen_width, screen_height],
                check=True,
            )

            # Move the window to the top-left corner
            subprocess.run(["xdotool", "windowmove", window_id, "0", "0"], check=True)

            print(f"Maximized Firefox window with window ID {window_id}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to maximize Firefox window: {e}")


def close_firefox_window():
    """
    Closes the Firefox window gracefully using xdotool's windowclose command.
    """
    try:
        # Get the window ID(s) of the Firefox window(s)
        window_ids_output = subprocess.check_output(
            ["xdotool", "search", "--onlyvisible", "--class", "firefox"]
        )
        window_ids = window_ids_output.decode("utf-8").split()

        for window_id in window_ids:
            # Close the window
            subprocess.run(["xdotool", "windowclose", window_id], check=True)

            print(f"Closed Firefox window with window ID {window_id}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to close Firefox window: {e}")
