from typing import List
from threading import Lock
import time
import json
import os
from datetime import datetime

from pynput import keyboard, mouse
from mss import mss

from .models import Recording, RecordedEvent, KeyData, ClickData, ScrollData

sessions = {}
lock = Lock()

RECORDINGS_DIR = os.getenv("RECORDINGS_DIR", ".recordings")


class RecordingSession:
    """A recording session"""

    def __init__(self, id: str, description: str) -> None:
        self._start_time = time.time()
        self._id = id
        self._description = description
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press)
        self.mouse_listener = mouse.Listener(
            on_click=self.on_click, on_scroll=self.on_scroll
        )
        self._data: List[RecordedEvent] = []
        self._end_time = 0

    def start(self):
        self.keyboard_listener.start()
        self.mouse_listener.start()

    def stop(self):
        self.keyboard_listener.stop()
        self.mouse_listener.stop()
        self._end_time = time.time()

    def on_press(self, key: str):
        event = RecordedEvent(
            type="key",
            timestamp=time.time(),
            screenshot_path=self.take_screenshot(),
            key_data=KeyData(key=key),
        )
        self._data.append(event)

    def on_click(self, x, y, button, pressed):
        event = RecordedEvent(
            type="mouse",
            timestamp=time.time(),
            screenshot_path=self.take_screenshot(),
            key_data=ClickData(key=button, pressed=pressed, x=x, y=y),
        )
        self._data.append(event)

    def on_scroll(self, x, y, dx, dy):
        event = RecordedEvent(
            type="scroll",
            timestamp=time.time(),
            screenshot_path=self.take_screenshot(),
            key_data=ScrollData(x=x, y=y, dx=dx, dy=dy),
        )
        self._data.append(event)

    def get_record(self) -> Recording:
        return Recording(
            id=self._id,
            description=self._description,
            start_time=self._start_time,
            end_time=self._end_time,
            events=self._data,
        )

    def save_to_file(self) -> str:
        session_dir = os.path.join(RECORDINGS_DIR, self._id)
        os.makedirs(session_dir, exist_ok=True)
        filepath = os.path.join(session_dir, f"session.json")
        with open(filepath, "w") as file:
            record = self.get_record()
            json.dump(record.model_dump(), file, indent=4)

        return filepath

    @classmethod
    async def list_recordings(cls) -> List[str]:
        directory_names = [
            name
            for name in os.listdir(RECORDINGS_DIR)
            if os.path.isdir(os.path.join(RECORDINGS_DIR, name))
        ]
        return directory_names

    @classmethod
    def load_from_file(cls, session_id: str) -> Recording:
        """Loads a recording session from a file given the session ID."""

        file_path = os.path.join(RECORDINGS_DIR, session_id, f"session.json")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No recording found for session ID {session_id}")

        with open(file_path, "r") as file:
            data = json.load(file)
            Recording.model_validate(data)
            recording = Recording(**data)
            return recording

    async def take_screenshot(self) -> str:
        session_dir = os.path.join(RECORDINGS_DIR, self._id)
        os.makedirs(session_dir, exist_ok=True)

        # Generate a unique file name based on the current timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(session_dir, f"screenshot_{timestamp}.png")

        with mss(with_cursor=True) as sct:
            # Save to the picture file
            sct.shot(output=file_path)

        return file_path
