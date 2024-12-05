from __future__ import annotations

import atexit
import base64
import io
import json
import mimetypes
import os
import shutil
import signal
import subprocess
import threading
import time
from datetime import datetime
from itertools import chain
from threading import Lock
from typing import Dict, List, Optional, Set

import pyautogui
from PIL import Image
from pynput import keyboard, mouse
from pynput.keyboard import Key, KeyCode
from skillpacks import ActionEvent, EnvState, V1Action, V1ToolRef
from taskara import Task
from taskara.task import TaskStatus, V1TaskUpdate

from .celery_worker import celery_app, send_action, update_task
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


def wait_for_celery_tasks():
    inspect = celery_app.control.inspect()
    reserved_tasks = inspect.reserved()  # these are pending tasks enqueued
    reserved_tasks = (
        list(chain(*reserved_tasks.values())) if reserved_tasks else None
    )  # merge all the arrays
    active_tasks = inspect.active()
    active_tasks = (
        list(chain(*active_tasks.values())) if active_tasks else None
    )  # merge all the arrays
    while active_tasks or reserved_tasks:
        print("waiting for celery worker to finish tasks...", flush=True)
        time.sleep(1)
        # no need for a sleep function as the inspect functions do take time
        reserved_tasks = inspect.reserved()  # reassign to retest
        reserved_tasks = (
            list(chain(*reserved_tasks.values())) if reserved_tasks else None
        )  # merge all the arrays
        active_tasks = inspect.active()  # reassign to retest
        active_tasks = (
            list(chain(*active_tasks.values())) if active_tasks else None
        )  # merge all the arrays

    print("celery worker completed all tasks", flush=True)
    return {"active_tasks": active_tasks, "reserved_tasks": reserved_tasks}


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
        update_task.delay(
            self._task.id,
            self._task.remote,
            self._task.auth_token,
            V1TaskUpdate(status=TaskStatus.IN_PROGRESS.value).model_dump(),
        )
        atexit.register(self.stop)

    def stop(self):

        wait_for_celery_tasks()
        print("send update_task to celery for finished", flush=True)
        update_task.delay(
            self._task.id,
            self._task.remote,
            self._task.auth_token,
            V1TaskUpdate(status=TaskStatus.FINISHED.value).model_dump(),
        )
        if self._status != "stopped":
            self._status = "stopping"
            self.keyboard_listener.stop()
            self.mouse_listener.stop()
            self._stop_screenshot_subprocess()
            self._end_time = time.time()
            # for action in self.actions:
            #     self._task.record_action_event(action)
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

    def _get_latest_screenshots(self, n: int) -> List[str]:
        session_dir = self._dir()
        screenshot_files = [
            f
            for f in os.listdir(session_dir)
            if f.startswith("screenshot_") and f.endswith(".png")
        ]

        if not screenshot_files:
            return []

        # Sort the files by modification time in descending order
        sorted_screenshots = sorted(
            screenshot_files,
            key=lambda f: os.path.getmtime(os.path.join(session_dir, f)),
            reverse=True,
        )

        # Select the top n screenshots (or fewer if there are not enough files)
        latest_screenshots = sorted_screenshots[:n]

        # Get the full paths of the screenshots
        latest_paths = [
            os.path.join(session_dir, screenshot) for screenshot in latest_screenshots
        ]

        # Add the screenshots to the used_screenshots set
        self.used_screenshots.update(latest_paths)

        return latest_paths

    def _cleanup_unused_screenshots(self):
        session_dir = self._dir()
        shutil.rmtree(session_dir)

    def on_press(self, key: Key):
        print(
            f"on_press waiting for lock with key {key} count of actions {len(self.actions)}",
            flush=True,
        )
        with self.lock:
            print(
                f"on_press acquired lock with key {key} count of actions {len(self.actions)}",
                flush=True,
            )
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

                    start_screenshot_path = self._get_latest_screenshots(2)
                    state = EnvState(
                        images=[
                            self.encode_image_to_base64(screenShot)
                            for screenShot in start_screenshot_path
                        ],
                        coordinates=(int(x), int(y)),
                    )
                    end_screenshot_path = []
                    end_screenshot_path.append(self.take_screenshot())
                    end_screenshot_path.append(self.take_screenshot("delayed_end_shot"))
                    end_state = EnvState(
                        images=[
                            self.encode_image_to_base64(screenShot)
                            for screenShot in end_screenshot_path
                        ],
                        coordinates=(int(x), int(y)),
                    )

                    # Record special key event as an action
                    action = V1Action(name="press_key", parameters={"key": str(key)})
                    action_event = ActionEvent(
                        state=state,
                        action=action,
                        tool=DESKTOP_TOOL_REF,
                        end_state=end_state,
                        event_order=len(self.actions),
                    )
                    self.actions.append(action_event)
                    # kicking off celery job for sending the action
                    send_action.delay(
                        self._task.id,
                        self._task.to_v1().model_dump(),
                        action_event.to_v1().model_dump(),
                    )
            print(
                f"on_press releasing lock with key {key} count of actions {len(self.actions)}",
                flush=True,
            )

    def on_release(self, key):
        print(
            f"on_release waiting lock with key {key} count of actions {len(self.actions)}",
            flush=True,
        )
        with self.lock:
            print(
                f"on_release acquired lock with key {key} count of actions {len(self.actions)}",
                flush=True,
            )
            if key in [Key.shift, Key.shift_r, Key.shift_l]:
                self.shift_pressed = False
            print(
                f"on_release releasing lock with key {key} count of actions {len(self.actions)}",
                flush=True,
            )

    def on_click(self, x, y, button, pressed):
        if not pressed:
            print("skipping button up event", flush=True)
            return
        print(
            f"on_click waiting lock with x,y: {x}, {y} count of actions {len(self.actions)}",
            flush=True,
        )
        with self.lock:
            print(
                f"on_click acquired lock with x,y: {x}, {y} count of actions {len(self.actions)}",
                flush=True,
            )
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

                start_screenshot_path = self._get_latest_screenshots(2)

                state = EnvState(
                    images=[
                        self.encode_image_to_base64(screenShot)
                        for screenShot in start_screenshot_path
                    ],
                    coordinates=(int(x), int(y)),
                )

                end_screenshot_path = []
                end_screenshot_path.append(self.take_screenshot())
                end_screenshot_path.append(self.take_screenshot("delayed_end_shot"))

                end_state = EnvState(
                    images=[
                        self.encode_image_to_base64(screenShot)
                        for screenShot in end_screenshot_path
                    ],
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
                    event_order=len(self.actions),
                )
                self.actions.append(action_event)
                # kicking off celery job
                send_action.delay(
                    self._task.id,
                    self._task.remote,
                    self._task.auth_token,
                    self._task.owner_id,
                    action_event.to_v1().model_dump(),
                )

            except Exception as e:
                print(f"Error recording click event: {e}", flush=True)
            print(
                f"on_click releasing lock with x,y: {x}, {y} count of actions {len(self.actions)}",
                flush=True,
            )

    def on_scroll(self, x, y, dx, dy):
        print(
            f"on_scroll waiting lock with x,y: {x}, {y}; dx, dy: {dx} count of actions {len(self.actions)}",
            flush=True,
        )
        with self.lock:
            print(
                f"on_scroll acquired lock with x,y: {x}, {y}; dx, dy: {dx}, {dy} count of actions {len(self.actions)}",
                flush=True,
            )
            mouse_x, mouse_y = pyautogui.position()
            print("scrolled: ", x, y, dx, dy, flush=True)

            # Before recording the scroll, check if there is pending text
            if self.typing_in_progress:
                print("Finalizing text event due to scroll...", flush=True)
                self.record_text_action()

            start_screenshot_path = self._get_latest_screenshots(2)

            state = EnvState(
                images=[
                    self.encode_image_to_base64(screenShot)
                    for screenShot in start_screenshot_path
                ],
                coordinates=(int(mouse_x), int(mouse_y)),
            )

            end_screenshot_path = []
            end_screenshot_path.append(self.take_screenshot())
            end_screenshot_path.append(self.take_screenshot("delayed_end_shot"))

            end_state = EnvState(
                images=[
                    self.encode_image_to_base64(screenShot)
                    for screenShot in end_screenshot_path
                ],
                coordinates=(int(mouse_x), int(mouse_y)),
            )

            action = V1Action(name="scroll", parameters={"dx": dx, "dy": dy})
            action_event = ActionEvent(
                state=state,
                action=action,
                end_state=end_state,
                tool=DESKTOP_TOOL_REF,
                event_order=len(self.actions),
            )
            self.actions.append(action_event)
            # kicking off celery job
            send_action.delay(
                self._task.id,
                self._task.remote,
                self._task.auth_token,
                self._task.owner_id,
                action_event.to_v1().model_dump(),
            )
            print(
                f"on_scroll releasing lock with x,y: {x}, {y}; dx, dy: {dx}, {dy} count of actions {len(self.actions)}",
                flush=True,
            )

    def start_typing_sequence(self):
        x, y = pyautogui.position()
        start_screenshot_path = self._get_latest_screenshots(2)
        self.text_start_state = EnvState(
            images=[
                self.encode_image_to_base64(screenShot)
                for screenShot in start_screenshot_path
            ],
            coordinates=(int(x), int(y)),
        )
        self.typing_in_progress = True

    def record_text_action(self):
        print("recording text action", flush=True)
        if self.text_buffer.strip():
            x, y = pyautogui.position()

            end_screenshot_path = []
            end_screenshot_path.append(self.take_screenshot())
            end_screenshot_path.append(self.take_screenshot("delayed_end_shot"))

            end_state = EnvState(
                images=[
                    self.encode_image_to_base64(screenShot)
                    for screenShot in end_screenshot_path
                ],
                coordinates=(int(x), int(y)),
            )

            action = V1Action(name="type_text", parameters={"text": self.text_buffer})

            if not self.text_start_state:
                raise ValueError("No text start state available")
            action_event = ActionEvent(
                state=self.text_start_state,
                action=action,
                tool=DESKTOP_TOOL_REF,
                end_state=end_state,
                event_order=len(self.actions),
            )
            self.actions.append(action_event)
            # kicking off celery job
            send_action.delay(
                self._task.id,
                self._task.remote,
                self._task.auth_token,
                self._task.owner_id,
                action_event.to_v1().model_dump(),
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

    def _temp_dir(self) -> str:
        return os.path.join(RECORDINGS_DIR, f"{self._id}_temp")

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

    def take_screenshot(
        self,
        name: Optional[str] = None,
        max_attempts: int = 3,
        max_retries_per_attempt: int = 3,
        delay: float = 0.05,
    ) -> str:
        # Get the temp and session directories and create them if they don't exist
        temp_dir = self._temp_dir()
        os.makedirs(temp_dir, exist_ok=True)
        session_dir = self._dir()
        os.makedirs(session_dir, exist_ok=True)

        for attempt_num in range(max_attempts):
            # Generate a unique temporary file name to avoid overwriting
            temp_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            temp_filename = (
                f"{name}_screenshot_{temp_timestamp}_attempt{attempt_num}.png"
                if name
                else f"screenshot_{temp_timestamp}_attempt{attempt_num}.png"
            )
            temp_file_path = os.path.join(temp_dir, temp_filename)

            # Take a screenshot and write it to the temp directory
            subprocess.run(["scrot", "-z", "-p", temp_file_path], check=True)

            # Try to verify the image up to max_retries_per_attempt times
            for retry_num in range(max_retries_per_attempt):
                try:
                    with open(temp_file_path, "rb") as image_file:
                        image_data = image_file.read()
                        # Validate image using PIL
                        image = Image.open(io.BytesIO(image_data))
                        image.verify()  # Raises an exception if the image is invalid

                    # After successful verification, generate the final filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = (
                        f"{name}_screenshot_{timestamp}.png"
                        if name
                        else f"screenshot_{timestamp}.png"
                    )
                    file_path = os.path.join(session_dir, filename)

                    # Move the file to the session directory with the final filename
                    os.rename(temp_file_path, file_path)
                    return file_path
                except Exception as e:
                    print(
                        f"Verification failed for {temp_file_path}, "
                        f"attempt {attempt_num + 1}, retry {retry_num + 1}: {e}",
                        flush=True,
                    )
                    time.sleep(delay)  # Small delay before retrying verification

            # If verification failed after retries, remove the temp file and try again
            print(
                f"Verification failed after {max_retries_per_attempt} retries for "
                f"screenshot {temp_file_path}, taking a new screenshot...",
                flush=True,
            )
            # Remove the invalid temp file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

        # If all attempts fail, raise an exception or handle the failure accordingly
        raise Exception(
            f"Failed to take a valid screenshot after {max_attempts} attempts"
        )

    def encode_image_to_base64(
        self, image_path: str, max_retries: int = 3, delay: float = 0.1
    ) -> Optional[str]:
        for attempt in range(max_retries):
            try:
                with open(image_path, "rb") as image_file:
                    image_data = image_file.read()
                    # Validate image
                    image = Image.open(io.BytesIO(image_data))
                    image.verify()  # Raises an exception if image is invalid

                encoded_image = base64.b64encode(image_data).decode("utf-8")
                mime_type, _ = mimetypes.guess_type(image_path)
                if not mime_type:
                    mime_type = "application/octet-stream"  # Default if MIME type can't be determined
                return f"data:{mime_type};base64,{encoded_image}"

            except Exception as e:
                print(
                    f"Error encoding image {image_path} on attempt {attempt + 1}: {e}",
                    flush=True,
                )
                time.sleep(delay)

        print(
            f"Failed to encode image {image_path} after {max_retries} attempts",
            flush=True,
        )
        return None
