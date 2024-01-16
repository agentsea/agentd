from typing import List
from threading import Lock
import time
import json
import os
import glob

from pynput import keyboard, mouse

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
            key_data=KeyData(key=key),
        )
        self._data.append(event)

    def on_click(self, x, y, button, pressed):
        event = RecordedEvent(
            type="mouse",
            timestamp=time.time(),
            key_data=ClickData(key=button, pressed=pressed, x=x, y=y),
        )
        self._data.append(event)

    def on_scroll(self, x, y, dx, dy):
        event = RecordedEvent(
            type="scroll",
            timestamp=time.time(),
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
        filepath = os.path.join(RECORDINGS_DIR, f"{self._id}.json")
        with open(filepath, "w") as file:
            record = self.get_record()
            json.dump(record.model_dump(), file, indent=4)

        return filepath

    @classmethod
    async def list_recordings(cls) -> List[str]:
        pattern = os.path.join(RECORDINGS_DIR, "*.json")
        files = glob.glob(pattern)
        sessions = [os.path.basename(f).replace(".json", "") for f in files]
        return sessions

    @classmethod
    def load_from_file(cls, session_id: str) -> Recording:
        """Loads a recording session from a file given the session ID."""

        file_path = os.path.join(RECORDINGS_DIR, f"{session_id}.json")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No recording found for session ID {session_id}")

        with open(file_path, "r") as file:
            data = json.load(file)
            Recording.model_validate(data)
            recording = Recording(**data)
            return recording
