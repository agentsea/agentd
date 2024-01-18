from __future__ import annotations
from typing import List, Optional
from threading import Lock
import time
import json
import os
import uuid
import base64
from datetime import datetime

from pynput import keyboard, mouse
from mss import mss
import pyautogui

from .models import (
    Recording,
    RecordedEvent,
    KeyData,
    ClickData,
    ScrollData,
    CoordinatesModel,
)

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
        x, y = pyautogui.position()
        initial_event = RecordedEvent(
            id=str(uuid.uuid4()),
            type="init",
            timestamp=time.time(),
            screenshot_path=self.take_screenshot(),
            coordinates=CoordinatesModel(x=x, y=y),
        )
        self._data: List[RecordedEvent] = [initial_event]
        self._end_time = 0

    def start(self):
        self.keyboard_listener.start()
        self.mouse_listener.start()

    def stop(self):
        self.keyboard_listener.stop()
        self.mouse_listener.stop()
        self._end_time = time.time()

    def on_press(self, key: str):
        print("pressed key: ", key)
        print("type key: ", type(key))
        x, y = pyautogui.position()
        event = RecordedEvent(
            id=str(uuid.uuid4()),
            type="key",
            timestamp=time.time(),
            screenshot_path=self.take_screenshot(),
            coordinates=CoordinatesModel(x=x, y=y),
            key_data=KeyData(key=key),
        )
        self._data.append(event)

    def on_click(self, x, y, button, pressed):
        print("clicked button: ", x, y, button, pressed)
        event = RecordedEvent(
            id=str(uuid.uuid4()),
            type="mouse",
            timestamp=time.time(),
            screenshot_path=self.take_screenshot(),
            coordinates=CoordinatesModel(x=x, y=y),
            key_data=ClickData(button=button, pressed=pressed),
        )
        self._data.append(event)

    def on_scroll(self, x, y, dx, dy):
        print("scrolled: ", x, y, dx, dy)
        event = RecordedEvent(
            id=str(uuid.uuid4()),
            type="scroll",
            timestamp=time.time(),
            screenshot_path=self.take_screenshot(),
            coordinates=CoordinatesModel(x=x, y=y),
            key_data=ScrollData(dx=dx, dy=dy),
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
                with open(event.screenshot_path, "rb") as image_file:
                    encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
                    event.screenshot_b64 = encoded_image
                return event
        return None

    def save_to_file(self) -> str:
        session_dir = self._dir()
        os.makedirs(session_dir, exist_ok=True)

        filepath = os.path.join(session_dir, f"session.json")
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
        session = cls.__new__(RecordingSession)
        session._start_time = data.start_time
        session._id = data.id
        session._description = data.description
        session.keyboard_listener = keyboard.Listener(on_press=session.on_press)
        session.mouse_listener = mouse.Listener(
            on_click=session.on_click, on_scroll=session.on_scroll
        )
        session._data: List[RecordedEvent] = data.events
        session._end_time = data.end_time
        return session

    @classmethod
    def load(cls, session_id: str) -> RecordingSession:
        """Loads a recording session from a file given the session ID."""

        file_path = os.path.join(RECORDINGS_DIR, session_id, f"session.json")
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

    def encode_image_to_base64(image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
        return encoded_image

    def as_actions(self) -> List[dict]:
        actions = []
        text_buffer = ""
        last_event_type = None
        previous_screenshot_encoded = None
        previous_coordinates = None

        for event in self._data:
            if event.type == "init":
                # Skip the first event and encode its screenshot
                previous_screenshot_encoded = self.encode_image_to_base64(
                    event.screenshot_path
                )
                previous_coordinates = {
                    "x": event.coordinates.x,
                    "y": event.coordinates.y,
                }
                continue

            if event.type == "key" and last_event_type == "key":
                text_buffer += event.key_data.key
            else:
                if text_buffer:
                    actions.append(
                        {
                            "action": {
                                "name": "type_text",
                                "parameters": {
                                    "text": text_buffer,
                                },
                            },
                            "screenshot": previous_screenshot_encoded,
                            "previous_coordinates": previous_coordinates,
                        }
                    )
                    text_buffer = ""

                if event.type == "mouse":
                    if event.click_data.pressed:
                        actions.append(
                            {
                                "action": {
                                    "name": "click_coords",
                                    "parameters": {
                                        "x": event.coordinates.x,
                                        "y": event.coordinates.y,
                                        "button": event.click_data.button,
                                    },
                                },
                                "screenshot": previous_screenshot_encoded,
                                "previous_coordinates": previous_coordinates,
                            }
                        )
                elif event.type == "scroll":
                    actions.append(
                        {
                            "action": {
                                "name": "scroll",
                                "parameters": {"clicks": event.scroll_data.dy},
                            },
                            "screenshot": previous_screenshot_encoded,
                            "previous_coordinates": previous_coordinates,
                        }
                    )

            last_event_type = event.type
            previous_screenshot_encoded = self.encode_image_to_base64(
                event.screenshot_path
            )
            previous_coordinates = {
                "x": event.coordinates.x,
                "y": event.coordinates.y,
            }

        if text_buffer:
            actions.append(
                {
                    "action": {
                        "name": "type_text",
                        "parameters": {
                            "text": text_buffer,
                        },
                    },
                    "screenshot": previous_screenshot_encoded,
                    "previous_coordinates": previous_coordinates,
                }
            )

        return actions
