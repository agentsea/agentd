from __future__ import annotations

import base64
import json
import os
import time
from threading import Lock
from typing import Dict, Set
import subprocess
import signal
import atexit
from datetime import datetime
import threading
import mimetypes
import shutil

import pyautogui
from pynput import keyboard, mouse
from pynput.keyboard import Key, KeyCode
from taskara import Task
from skillpacks import V1Action, V1ToolRef, ActionEvent, EnvState

from .models import (
    Recording,
)

DESKTOP_TOOL_REF = V1ToolRef(
    module="agentdesk.device", type="Desktop", package="agentdesk"
)

sessions: Dict[str, RecordingSession] = {}
lock = Lock()

RECORDINGS_DIR = os.getenv("RECORDINGS_DIR", ".recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)
SCREENSHOT_INTERVAL = 0.5


class RecordingSession:
    """A recording session"""

    def __init__(self, id: str, task: Task) -> None:
        self._start_time = time.time()
        self._id = id
        self._task = task  # Store the task object to record actions
        os.makedirs(self._dir(), exist_ok=True)

        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_press,  # type: ignore
            on_release=self.on_release,
        )
        self.mouse_listener = mouse.Listener(
            on_click=self.on_click, on_scroll=self.on_scroll
        )
        self.text_buffer = ""
        self.shift_pressed = False
        self.caps_lock_on = False
        self.screenshot_process = None
        self.used_screenshots: Set[str] = set()

        self.typing_in_progress = False
        self.text_start_state = None
        self.last_click_time = None
        self.last_click_button = None
        self.actions = []
        self.lock = threading.Lock()

    def start(self):
        self.keyboard_listener.start()
        time.sleep(1)
        self.mouse_listener.start()

        self._status = "running"
        self._start_screenshot_subprocess()
        atexit.register(self.stop)

    def stop(self):
        if self._status != "stopped":
            self._status = "stopping"
            self.keyboard_listener.stop()
            self.mouse_listener.stop()
            self._stop_screenshot_subprocess()
            self._end_time = time.time()
            for action in self.actions:
                self._task.record_action_event(action)

            self._cleanup_unused_screenshots()
            self._status = "stopped"
            atexit.unregister(self.stop)

    def _start_screenshot_subprocess(self):
        screenshot_script = f"""
import time
import os
import subprocess

SCREENSHOT_INTERVAL = {SCREENSHOT_INTERVAL}
SESSION_DIR = "{self._dir()}"

def take_screenshots():
    while True:
        timestamp = time.time()
        filename = f"screenshot_{{timestamp}}.png"
        file_path = os.path.join(SESSION_DIR, filename)
        # Use scrot to take a screenshot with the cursor (-p flag)
        subprocess.run(["scrot", "-z", "-p", file_path], check=True)
        time.sleep(SCREENSHOT_INTERVAL)

if __name__ == "__main__":
    os.makedirs(SESSION_DIR, exist_ok=True)
    take_screenshots()
    """
        screenshot_script_path = os.path.join(self._dir(), "screenshot_script.py")
        with open(screenshot_script_path, "w") as f:
            f.write(screenshot_script)

        self.screenshot_process = subprocess.Popen(
            ["python", screenshot_script_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _stop_screenshot_subprocess(self):
        if self.screenshot_process:
            os.kill(self.screenshot_process.pid, signal.SIGTERM)
            self.screenshot_process.wait()

    def _get_latest_screenshot(self) -> str:
        session_dir = self._dir()
        screenshot_files = [
            f
            for f in os.listdir(session_dir)
            if f.startswith("screenshot_") and f.endswith(".png")
        ]
        if not screenshot_files:
            return ""
        latest_screenshot = max(
            screenshot_files,
            key=lambda f: os.path.getmtime(os.path.join(session_dir, f)),
        )
        latest_path = os.path.join(session_dir, latest_screenshot)
        self.used_screenshots.add(latest_path)
        return latest_path

    def _cleanup_unused_screenshots(self):
        session_dir = self._dir()
        shutil.rmtree(session_dir)

    def on_press(self, key: Key):
        with self.lock:
            print("\npressed key: ", key, flush=True)

            # Handle shift and caps lock keys
            if key in [Key.shift, Key.shift_r, Key.shift_l]:
                self.shift_pressed = True
                return

            if key == Key.caps_lock:
                self.caps_lock_on = not self.caps_lock_on
                return

            if key == Key.space:
                # Start typing if not already in progress
                if not self.typing_in_progress:
                    self.start_typing_sequence()
                self.text_buffer += " "
                return

            # Handle backspace
            if key == Key.backspace:
                if self.text_buffer:
                    self.text_buffer = self.text_buffer[:-1]
                return

            # Handle regular character keys
            if isinstance(key, KeyCode):
                char = key.char
                if char:
                    # Start typing if not already in progress
                    if not self.typing_in_progress:
                        self.start_typing_sequence()

                    # Apply shift modification for the next character
                    if self.shift_pressed and char.isalpha():
                        char = char.upper()
                        self.shift_pressed = False  # Reset shift state after applying
                    elif self.caps_lock_on and char.isalpha():
                        char = char.upper() if char.islower() else char.lower()

                    self.text_buffer += char

            # Handle special keys (function keys, etc.)
            else:
                if key not in [
                    Key.shift,
                    Key.shift_r,
                    Key.shift_l,
                    Key.caps_lock,
                    Key.backspace,
                ]:
                    # If typing is in progress, record the text action first
                    if self.typing_in_progress:
                        print("Finalizing text event due to special key...", flush=True)
                        self.record_text_action()

                    x, y = pyautogui.position()

                    start_screenshot_path = self._get_latest_screenshot()
                    state = EnvState(
                        images=[self.encode_image_to_base64(start_screenshot_path)],
                        coordinates=(int(x), int(y)),
                    )

                    end_screenshot_path = self.take_screenshot()
                    end_state = EnvState(
                        images=[self.encode_image_to_base64(end_screenshot_path)],
                        coordinates=(int(x), int(y)),
                    )

                    # Record special key event as an action
                    action = V1Action(name="press_key", parameters={"key": str(key)})

                    self.actions.append(
                        ActionEvent(
                            state=state,
                            action=action,
                            tool=DESKTOP_TOOL_REF,
                            end_state=end_state,
                        )
                    )

    def on_release(self, key):
        with self.lock:
            if key in [Key.shift, Key.shift_r, Key.shift_l]:
                self.shift_pressed = False

    def on_click(self, x, y, button, pressed):
        if not pressed:
            print("skipping button up event", flush=True)
            return
        with self.lock:
            current_time = time.time()
            is_double_click = False
            DOUBLE_CLICK_THRESHOLD = (
                0.3  # Time threshold for double-click detection (in seconds)
            )

            if self.last_click_time and self.last_click_button == button:
                time_since_last_click = current_time - self.last_click_time
                if time_since_last_click <= DOUBLE_CLICK_THRESHOLD:
                    is_double_click = True

            self.last_click_time = current_time
            self.last_click_button = button

            print("clicked button: ", x, y, button, pressed, flush=True)

            try:
                if self.typing_in_progress:
                    print("Finalizing text event due to click...", flush=True)
                    self.record_text_action()

                start_screenshot_path = self._get_latest_screenshot()
                encoded = self.encode_image_to_base64(start_screenshot_path)

                state = EnvState(
                    images=[encoded],
                    coordinates=(int(x), int(y)),
                )

                end_screenshot_path = self.take_screenshot()
                encoded = self.encode_image_to_base64(end_screenshot_path)

                end_state = EnvState(
                    images=[encoded],
                    coordinates=(int(x), int(y)),
                )

                # Record double-click event as an action if detected
                if is_double_click:
                    action = V1Action(
                        name="double_click",
                        parameters={
                            "x": int(x),
                            "y": int(y),
                            "button": button._name_,
                        },
                    )
                    print("Double-click detected", flush=True)
                else:
                    # Record regular click event as an action
                    action = V1Action(
                        name="click",
                        parameters={
                            "x": int(x),
                            "y": int(y),
                            "button": button._name_,
                            "pressed": pressed,
                        },
                    )

                action_event = ActionEvent(
                    state=state,
                    action=action,
                    tool=DESKTOP_TOOL_REF,
                    end_state=end_state,
                )
                self.actions.append(action_event)

            except Exception as e:
                print(f"Error recording click event: {e}", flush=True)

    def on_scroll(self, x, y, dx, dy):
        with self.lock:
            mouse_x, mouse_y = pyautogui.position()
            print("scrolled: ", x, y, dx, dy, flush=True)

            # Before recording the scroll, check if there is pending text
            if self.typing_in_progress:
                print("Finalizing text event due to scroll...", flush=True)
                self.record_text_action()

            start_screenshot_path = self._get_latest_screenshot()
            encoded = self.encode_image_to_base64(start_screenshot_path)

            state = EnvState(
                images=[encoded],
                coordinates=(int(mouse_x), int(mouse_y)),
            )

            end_screenshot_path = self.take_screenshot()
            encoded = self.encode_image_to_base64(end_screenshot_path)

            end_state = EnvState(
                images=[encoded],
                coordinates=(int(mouse_x), int(mouse_y)),
            )

            action = V1Action(name="scroll", parameters={"dx": dx, "dy": dy})

            self.actions.append(
                ActionEvent(
                    state=state,
                    action=action,
                    end_state=end_state,
                    tool=DESKTOP_TOOL_REF,
                )
            )

    def start_typing_sequence(self):
        x, y = pyautogui.position()
        start_screenshot_path = self._get_latest_screenshot()
        self.text_start_state = EnvState(
            images=[self.encode_image_to_base64(start_screenshot_path)],
            coordinates=(int(x), int(y)),
        )
        self.typing_in_progress = True

    def record_text_action(self):
        print("recording text action", flush=True)
        if self.text_buffer.strip():
            x, y = pyautogui.position()

            end_screenshot_path = self.take_screenshot()
            end_state = EnvState(
                images=[self.encode_image_to_base64(end_screenshot_path)],
                coordinates=(int(x), int(y)),
            )

            action = V1Action(name="type_text", parameters={"text": self.text_buffer})

            if not self.text_start_state:
                raise ValueError("No text start state available")

            self.actions.append(
                ActionEvent(
                    state=self.text_start_state,
                    action=action,
                    tool=DESKTOP_TOOL_REF,
                    end_state=end_state,
                )
            )
            print(f"Recorded text action: {self.text_buffer}", flush=True)

            # Reset the typing state
            self.text_buffer = ""
            self.typing_in_progress = False
            self.text_start_state = None

    def as_schema(self) -> Recording:
        return Recording(
            id=self._id,
            start_time=self._start_time,
            end_time=self._end_time,
            task_id=self._task.id,
        )

    def save_to_file(self) -> str:
        session_dir = self._dir()
        os.makedirs(session_dir, exist_ok=True)

        filepath = os.path.join(session_dir, "session.json")
        with open(filepath, "w") as file:
            record = self.as_schema()
            json.dump(record.model_dump(), file, indent=4)

        return filepath

    def _dir(self) -> str:
        return os.path.join(RECORDINGS_DIR, self._id)

    @classmethod
    def from_schema(cls, data: Recording) -> RecordingSession:
        session = cls.__new__(cls)
        session._start_time = data.start_time
        session._id = data.id
        session.keyboard_listener = keyboard.Listener(on_press=session.on_press)  # type: ignore
        session.mouse_listener = mouse.Listener(
            on_click=session.on_click, on_scroll=session.on_scroll
        )
        session._end_time = data.end_time
        return session

    @classmethod
    def load(cls, session_id: str) -> RecordingSession:
        """Loads a recording session from a file given the session ID."""

        file_path = os.path.join(RECORDINGS_DIR, session_id, "session.json")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No recording found for session ID {session_id}")

        with open(file_path, "r") as file:
            data = json.load(file)
            Recording.model_validate(data)
            recording = Recording(**data)
            return cls.from_schema(recording)

    def take_screenshot(self) -> str:
        # Get the session directory and create it if it doesn't exist
        session_dir = self._dir()
        os.makedirs(session_dir, exist_ok=True)

        # Generate a unique file name based on the current timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(session_dir, f"screenshot_{timestamp}.png")

        # Use scrot to take a screenshot with the cursor (-p flag)
        subprocess.run(["scrot", "-z", "-p", file_path], check=True)

        # Return the file path of the screenshot
        return file_path

    def encode_image_to_base64(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = (
                "application/octet-stream"  # default if cannot determine mime type
            )
        return f"data:{mime_type};base64,{encoded_image}"
