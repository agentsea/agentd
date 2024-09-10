from __future__ import annotations

import base64
import json
import os
import time
import uuid
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional, Set
import subprocess
import signal
import atexit

import pyautogui
from mss import mss
from pynput import keyboard, mouse
from pynput.keyboard import Key, KeyCode

from .models import (
    ClickData,
    CoordinatesModel,
    KeyData,
    RecordedEvent,
    Recording,
    ScrollData,
    TextData,
)

sessions: Dict[str, RecordingSession] = {}
lock = Lock()

RECORDINGS_DIR = os.getenv("RECORDINGS_DIR", ".recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)
SCREENSHOT_INTERVAL = 0.5


class RecordingSession:
    """A recording session"""

    def __init__(self, id: str, description: str) -> None:
        self._start_time = time.time()
        self._id = id
        self._description = description
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release
        )
        self.mouse_listener = mouse.Listener(
            on_click=self.on_click, on_scroll=self.on_scroll
        )
        x, y = pyautogui.position()
        initial_event = RecordedEvent(
            id=str(uuid.uuid4()),
            type="init",
            timestamp=time.time(),
            after_screenshot_path=self.take_screenshot(),
            coordinates=CoordinatesModel(x=x, y=y),
        )
        self._data: List[RecordedEvent] = [initial_event]
        self._status = "initialized"
        self._end_time = 0
        self.text_buffer = ""
        self.shift_pressed = False
        self.caps_lock_on = False
        self.screenshot_process = None
        self.used_screenshots: Set[str] = set()

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
            self._cleanup_unused_screenshots()
            self._status = "stopped"
            atexit.unregister(self.stop)

    def _start_screenshot_subprocess(self):
        screenshot_script = f"""
import time
import os
from mss import mss

SCREENSHOT_INTERVAL = {SCREENSHOT_INTERVAL}
SESSION_DIR = "{self._dir()}"

def take_screenshots():
    with mss() as sct:
        while True:
            timestamp = time.time()
            filename = f"screenshot_{{timestamp}}.png"
            file_path = os.path.join(SESSION_DIR, filename)
            sct.shot(output=file_path)
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
        for filename in os.listdir(session_dir):
            if filename.startswith("screenshot_") and filename.endswith(".png"):
                file_path = os.path.join(session_dir, filename)
                if file_path not in self.used_screenshots:
                    try:
                        os.remove(file_path)
                        print(f"Deleted unused screenshot: {file_path}")
                    except OSError as e:
                        print(f"Error deleting unused screenshot {file_path}: {e}")

    def on_press(self, key: Key):
        print("\npressed key: ", key)
        before_screenshot = self._get_latest_screenshot()
        # Handle shift and caps lock keys
        if key in [Key.shift, Key.shift_r, Key.shift_l]:
            self.shift_pressed = True
            return

        if key == Key.caps_lock:
            self.caps_lock_on = not self.caps_lock_on
            return

        if key == Key.space:
            self.text_buffer += " "
            self.update_last_text_event()
            return

        # Handle backspace
        if key == Key.backspace:
            if self.text_buffer:
                self.text_buffer = self.text_buffer[:-1]
                self.update_last_text_event()
            return

        # Handle regular character keys
        if isinstance(key, KeyCode):
            char = key.char
            if char:
                # Apply shift modification for the next character
                if self.shift_pressed and char.isalpha():
                    char = char.upper()
                    self.shift_pressed = False  # Reset shift state after applying
                elif self.caps_lock_on and char.isalpha():
                    char = char.upper() if char.islower() else char.lower()

                self.text_buffer += char
                self.update_last_text_event()

        # Handle Enter key to finalize text event
        elif key == Key.enter:
            self.text_buffer = ""

        # Handle special keys
        else:
            if key not in [
                Key.shift,
                Key.shift_r,
                Key.shift_l,
                Key.caps_lock,
                Key.backspace,
            ]:
                x, y = pyautogui.position()
                # Create a special key event
                special_key_event = RecordedEvent(
                    id=str(uuid.uuid4()),
                    type="key",
                    timestamp=time.time(),
                    after_screenshot_path=self.take_screenshot(),
                    before_screenshot_path=before_screenshot,
                    coordinates=CoordinatesModel(x=x, y=y),
                    key_data=KeyData(key=str(key)),
                )
                self._data.append(special_key_event)

    def update_last_text_event(self):
        x, y = pyautogui.position()
        if self._data and self._data[-1].type == "text":
            # Update the last text event if it's not empty
            if self.text_buffer.strip():
                self._data[-1].text_data.text = self.text_buffer
        elif self.text_buffer.strip():
            # Add a new text event if the text buffer is not just whitespace
            event = RecordedEvent(
                id=str(uuid.uuid4()),
                type="text",
                timestamp=time.time(),
                after_screenshot_path=self.take_screenshot(),
                coordinates=CoordinatesModel(x=x, y=y),
                text_data=TextData(text=self.text_buffer),
            )
            self._data.append(event)

    def on_release(self, key):
        if key in [Key.shift, Key.shift_r, Key.shift_l]:
            self.shift_pressed = False

    def on_click(self, x, y, button, pressed):
        print("clicked button: ", x, y, button, pressed)
        try:
            screenshot_path = self._get_latest_screenshot()
            event = RecordedEvent(
                id=str(uuid.uuid4()),
                type="click",
                timestamp=time.time(),
                before_screenshot_path=screenshot_path,
                after_screenshot_path=self.take_screenshot(),
                coordinates=CoordinatesModel(x=int(x), y=int(y)),
                click_data=ClickData(button=button._name_, pressed=pressed),
            )
            self._data.append(event)
        except Exception as e:
            print(f"Error recording click event: {e}")
        print("recorded event: ", event)

    def on_scroll(self, x, y, dx, dy):
        print("scolled: ", x, y, dx, dy)
        screenshot_path = self._get_latest_screenshot()
        if self._data and self._data[-1].type == "scroll":
            # Update the last scroll event
            self._data[-1].scroll_data.dx += dx
            self._data[-1].scroll_data.dy += dy
        else:
            # Add a new scroll event
            event = RecordedEvent(
                id=str(uuid.uuid4()),
                type="scroll",
                timestamp=time.time(),
                before_screenshot_path=screenshot_path,
                after_screenshot_path=self.take_screenshot(),
                coordinates=CoordinatesModel(x=x, y=y),
                scroll_data=ScrollData(dx=dx, dy=dy),
            )
            self._data.append(event)

    def as_schema(self) -> Recording:
        return Recording(
            id=self._id,
            description=self._description,
            start_time=self._start_time,
            end_time=self._end_time,
            events=self._data,
        )

    def get_event(self, event_id: str) -> Optional[RecordedEvent]:
        for event in self._data:
            if event.id == event_id:
                if not event.before_screenshot_path:
                    raise ValueError("Event has no screenshot")
                with open(event.before_screenshot_path, "rb") as image_file:
                    encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
                    event.before_screenshot_b64 = encoded_image
                if not event.after_screenshot_path:
                    raise ValueError("Event has no screenshot")
                with open(event.after_screenshot_path, "rb") as image_file:
                    encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
                    event.after_screenshot_b64 = encoded_image
                return event
        return None

    def delete_event(self, event_id: str) -> None:
        out = []
        for event in self._data:
            if event.id != event_id:
                out.append(event)
        self._data = out
        return None

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
    async def list_recordings(cls) -> List[str]:
        directory_names = [
            name
            for name in os.listdir(RECORDINGS_DIR)
            if os.path.isdir(os.path.join(RECORDINGS_DIR, name))
        ]
        return directory_names

    @classmethod
    def from_schema(cls, data: Recording) -> RecordingSession:
        session = cls.__new__(cls)
        session._start_time = data.start_time
        session._id = data.id
        session._description = data.description
        session.keyboard_listener = keyboard.Listener(on_press=session.on_press)  # type: ignore
        session.mouse_listener = mouse.Listener(
            on_click=session.on_click, on_scroll=session.on_scroll
        )
        session._data: List[RecordedEvent] = data.events  # type: ignore
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
        session_dir = self._dir()
        os.makedirs(session_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(session_dir, f"screenshot_{timestamp}.png")

        with mss(with_cursor=True) as sct:
            sct.shot(output=file_path)

        return file_path

    def find_event(self, id: str) -> Optional[RecordedEvent]:
        for event in self._data:
            if event.id == id:
                return event
        return None

    def encode_image_to_base64(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
        return encoded_image

    def as_actions(self) -> List[dict]:
        """Convert to tool schema actions that can be used with Agent Desk

        Returns:
            List[dict]: A list of action schemas
        """
        actions = []
        before_screenshot_encoded = None
        after_screenshot_encoded = None
        previous_coordinates = None

        for event in self._data:
            if event.type == "init":
                # Skip the first event and encode its screenshot
                if not event.before_screenshot_path:
                    raise ValueError("Event has no screenshot")
                before_screenshot_encoded = self.encode_image_to_base64(
                    event.before_screenshot_path
                )
                if not event.after_screenshot_path:
                    raise ValueError("Event has no screenshot")
                after_screenshot_encoded = self.encode_image_to_base64(
                    event.after_screenshot_path
                )
                previous_coordinates = {
                    "x": event.coordinates.x,
                    "y": event.coordinates.y,
                }
                continue

            if event.type == "text":
                # Handle text events
                actions.append(
                    {
                        "action": {
                            "name": "type_text",
                            "parameters": {
                                "text": event.text_data.text,
                            },
                        },
                        "before_screenshot": before_screenshot_encoded,
                        "after_screenshot": after_screenshot_encoded,
                        "previous_coordinates": previous_coordinates,
                    }
                )
            elif event.type == "click":
                # Handle click events
                if event.click_data.pressed:
                    actions.append(
                        {
                            "action": {
                                "name": "click",
                                "parameters": {
                                    "x": event.coordinates.x,
                                    "y": event.coordinates.y,
                                    "button": event.click_data.button,
                                },
                            },
                            "before_screenshot": before_screenshot_encoded,
                            "after_screenshot": after_screenshot_encoded,
                            "previous_coordinates": previous_coordinates,
                        }
                    )
            elif event.type == "scroll":
                # Handle scroll events
                actions.append(
                    {
                        "action": {
                            "name": "scroll",
                            "parameters": {"clicks": event.scroll_data.dy},
                        },
                        "before_screenshot": before_screenshot_encoded,
                        "after_screenshot": after_screenshot_encoded,
                        "previous_coordinates": previous_coordinates,
                    }
                )
            elif event.type == "key":
                # Handle special key events

                actions.append(
                    {
                        "action": {
                            "name": "press_key",
                            "parameters": {"key": event.key_data.key},
                        },
                        "before_screenshot": before_screenshot_encoded,
                        "after_screenshot": after_screenshot_encoded,
                        "previous_coordinates": previous_coordinates,
                    }
                )
            else:
                raise ValueError(f"Unknown event type '{event.type}'")

            # Update the previous screenshot and coordinates for the next event
            before_screenshot_encoded = self.encode_image_to_base64(
                event.before_screenshot_path
            )
            previous_coordinates = {"x": event.coordinates.x, "y": event.coordinates.y}

        return actions
