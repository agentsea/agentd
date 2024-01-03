import subprocess


def is_chromium_running():
    try:
        proc = subprocess.Popen(["pgrep", "chrome"], stdout=subprocess.PIPE)
        output, _ = proc.communicate()
        return output != b""
    except subprocess.CalledProcessError:
        return False


def is_chromium_window_open():
    try:
        output = subprocess.check_output(["wmctrl", "-l"])
        return "Chromium" in output.decode()
    except subprocess.CalledProcessError:
        return False
