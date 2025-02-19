from __future__ import annotations

import atexit
import base64
import io
import json
import mimetypes
import os
import queue
import re
import shutil
import signal
import subprocess
import threading
import time
from .util import OrderLock
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
    ActionDetails,
    Recording,
)

import logging
import logging.config
from .logging_config import LOGGING_CONFIG  # or wherever you store the config

logging.config.dictConfig(LOGGING_CONFIG)

recording_logger = logging.getLogger("recording")

DESKTOP_TOOL_REF = V1ToolRef(
    module="agentdesk.device", type="Desktop", package="agentdesk"
)

PYNPUT_TO_PYAUTOGUI: Dict[Key, str] = {
    Key.tab: "tab",
    Key.enter: "enter",
    Key.space: "space",
    Key.backspace: "backspace",
    Key.delete: "delete",
    Key.up: "up",
    Key.down: "down",
    Key.left: "left",
    Key.right: "right",
    Key.home: "home",
    Key.end: "end",
    Key.page_up: "pageup",
    Key.page_down: "pagedown",
    Key.insert: "insert",
    Key.esc: "escape",
    Key.caps_lock: "capslock",
    Key.shift: "shift",
    Key.shift_l: "shiftleft",
    Key.shift_r: "shiftright",
    Key.ctrl: "ctrl",
    Key.ctrl_l: "ctrlleft",
    Key.ctrl_r: "ctrlright",
    Key.alt: "alt",
    Key.alt_l: "altleft",
    Key.alt_r: "altright",
    Key.cmd: "command",
    Key.cmd_l: "winleft",
    Key.cmd_r: "winright",
    Key.menu: "apps",
    Key.num_lock: "numlock",
    Key.scroll_lock: "scrolllock",
    Key.print_screen: "printscreen",
    Key.pause: "pause",
    # Function keys
    Key.f1: "f1",
    Key.f2: "f2",
    Key.f3: "f3",
    Key.f4: "f4",
    Key.f5: "f5",
    Key.f6: "f6",
    Key.f7: "f7",
    Key.f8: "f8",
    Key.f9: "f9",
    Key.f10: "f10",
    Key.f11: "f11",
    Key.f12: "f12",
}

sessions: Dict[str, RecordingSession] = {}
lock = Lock()

RECORDINGS_DIR = os.getenv("RECORDINGS_DIR", ".recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)
SCREENSHOT_INTERVAL = 0.15
action_delay = .4
before_screenshot_offset = .03 # offset from the event_time to make sure we can get a true before screenshot


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
        recording_logger.info(
            f"waiting for celery worker to finish tasks... reserved_tasks: {len(reserved_tasks) if reserved_tasks else 0} active_tasks: {len(active_tasks) if active_tasks else 0}"
        )
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

    recording_logger.info("celery worker completed all tasks")
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
            on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll
        )
        self.text_buffer = ""
        self.shift_pressed = False
        self.caps_lock_on = False
        self.screenshot_process = None
        self.used_screenshots: Set[str] = set()
        self.test_start_time = None
        self.typing_in_progress = False
        self.text_start_state = None
        self.last_click_time = None
        self.last_click_button = None
        self.scroll_timer = None
        self.scroll_dx = 0
        self.scroll_dy = 0
        self.scroll_start_state = None
        self.actions = []
        self.event_order = 0
        self.send_action_queue = queue.Queue()
        self.mouse_moving = False
        self.mouse_move_timer = None
        self.mouse_move_start_pos = None
        self.mouse_move_start_state = None
        self.last_mouse_position = None
        self.movement_buffer = []
        self.MOVEMENT_BUFFER_TIME = 3
        self.last_movement_time = None
        self.MOVEMENT_THRESHOLD = 5
        # Replace the standard lock with a FairLock
        self.lock = OrderLock()

    def start(self):
        x, y = pyautogui.position()
        self.last_mouse_position = (x, y)
        # self.last_movement_time = time.time() I am not sure why we are doing this

        self.keyboard_listener.start()
        time.sleep(1)
        self.mouse_listener.start()

        self._status = "running"
        self.action_count = 0
        self._start_screenshot_subprocess()
        update_task.delay(
            self._task.id,
            self._task.remote,
            self._task.auth_token,
            V1TaskUpdate(status=TaskStatus.IN_PROGRESS.value).model_dump(),
        )
        atexit.register(self.stop)
    
    def record_useSecret_action(self, secret_name, field):
        event_time = time.time()

        # These are so I can get the details I need from self while locked and then send the action outside of the lock
        text_action_details = None
        # TODO Add mouse move recorder

        recording_logger.info(f"{secret_name} used with field {field} to celery")
        recording_logger.info(
            f"waiting lock with name: {secret_name}")
        try:
            with self.lock:
                recording_logger.info(f"acquired lock with name: {secret_name}")

                if self.typing_in_progress:
                    recording_logger.info("Finalizing text event due to use secret...")
                    text_action_details = self.record_text_action_details()
                
                # need to set event order to get action place in order.
                event_order = self.event_order
                self.event_order += 1
                x, y = pyautogui.position()
                recording_logger.info(f"releasing lock with name: {secret_name} count of actions {event_order}")

            # moving most logic outside lock to avoid locking too long
            # waiting for screenshots to finish writing
            time.sleep(action_delay)

            if text_action_details:
                self.send_text_action(text_action_details)

            before_time = event_time - before_screenshot_offset  # 30ms earlier to make sure we get true before screenshots
            start_screenshot_path = self._get_screenshots_by_time(2, before_time, "before")
            recording_logger.info(f"task: {self._task.id} event_order: {event_order} start_screenshot_path: {start_screenshot_path}")
            state = EnvState(
                images=[
                    self.encode_image_to_base64(screenShot)
                    for screenShot in start_screenshot_path
                ],
                coordinates=(int(x), int(y)),
                timestamp=event_time
            )

            end_screenshot_path = []
            end_screenshot_path = self._get_screenshots_by_time(2, event_time, "after")
            recording_logger.info(f"task: {self._task.id} event_order: {event_order} end_screenshot_path: {end_screenshot_path}")
            end_state = EnvState(
                images=[
                    self.encode_image_to_base64(screenShot)
                    for screenShot in end_screenshot_path
                ],
                coordinates=(int(x), int(y)),
                timestamp=event_time
            )

            # Record final end event as an action
            action = V1Action(
                name="use_secret",
                parameters={
                    "name": secret_name,
                    "field": field
                },
            )

            action_event = ActionEvent(
                state=state,
                action=action,
                tool=DESKTOP_TOOL_REF,
                end_state=end_state,
                event_order=event_order,
            )
            self.actions.append(action_event)
            # kicking off celery job
            send_action.delay(
                self._task.id,
                self._task.auth_token,
                self._task.owner_id,
                self._task.to_v1().model_dump(),
                action_event.to_v1().model_dump(),
            )

        except Exception as e:
            recording_logger.info(f"Error recording send_useSecret_action event: {e}")   

    def stop(self, result, comment):
        recording_logger.info("send update_task to celery for finished")
        self.send_final_action(result, comment)
        update_task.delay(
            self._task.id,
            self._task.remote,
            self._task.auth_token,
            V1TaskUpdate(status=TaskStatus.REVIEW.value).model_dump(),
        )
        wait_for_celery_tasks()
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
        subprocess.Popen(["scrot", "-z", "-p", file_path])
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

    def _get_screenshots_by_time(self, n: int, target_timestamp: float, mode: str = "closest") -> list[str]:
        """
        Return the file paths for the n screenshots based on the given mode relative to the target timestamp.

        Modes:
          - "closest": Returns the n screenshots whose filename-embedded timestamps are closest to target_timestamp.
          - "before":  Returns the n screenshots taken before target_timestamp.
          - "after":   Returns the n screenshots taken after target_timestamp.

        Screenshots must be named in the format "screenshot_{timestamp}.png" where {timestamp} is a float.
        The returned list is always sorted in chronological order (oldest to newest).
        """
        session_dir = self._dir()
        screenshot_files = [
            f for f in os.listdir(session_dir)
            if f.startswith("screenshot_") and f.endswith(".png")
        ]
        if not screenshot_files:
            return []

        # Use a regex to extract the timestamp from the filename.
        timestamp_pattern = re.compile(r"screenshot_(\d+\.\d+)\.png")
        screenshots = []
        for filename in screenshot_files:
            match = timestamp_pattern.match(filename)
            if not match:
                continue
            try:
                file_timestamp = float(match.group(1))
            except ValueError:
                continue
            screenshots.append((filename, file_timestamp))

        selected_paths: list[str] = []

        if mode == "closest":
            # Compute the absolute difference from target_timestamp.
            screenshots_with_diff = [
                (abs(file_timestamp - target_timestamp), filename, file_timestamp)
                for filename, file_timestamp in screenshots
            ]
            screenshots_with_diff.sort(key=lambda x: x[0])
            selected = screenshots_with_diff[:n]
            # Sort selected screenshots in chronological order.
            selected.sort(key=lambda x: x[2])
            selected_paths = [os.path.join(session_dir, filename) for _, filename, _ in selected]
        elif mode == "before":
            # Filter for screenshots taken before target_timestamp.
            filtered = [
                (filename, file_timestamp)
                for filename, file_timestamp in screenshots
                if file_timestamp < target_timestamp
            ]
            if not filtered:
                selected_paths = []
            else:
                # Sort descending so that the screenshot immediately before target time is first.
                filtered.sort(key=lambda x: x[1], reverse=True)
                selected = filtered[:n]
                # Finally, sort the selected ones in chronological (ascending) order.
                selected.sort(key=lambda x: x[1])
                selected_paths = [os.path.join(session_dir, filename) for filename, _ in selected]
        elif mode == "after":
            # Filter for screenshots taken after target_timestamp.
            filtered = [
                (filename, file_timestamp)
                for filename, file_timestamp in screenshots
                if file_timestamp > target_timestamp
            ]
            if not filtered:
                selected_paths = []
            else:
                # Sort ascending so that the one immediately after target time is first.
                filtered.sort(key=lambda x: x[1])
                selected = filtered[:n]
                selected_paths = [os.path.join(session_dir, filename) for filename, _ in selected]
        else:
            raise ValueError("Invalid mode: must be 'closest', 'before', or 'after'")

        self.used_screenshots.update(selected_paths)
        return selected_paths

    def _get_latest_screenshots(self, n: int, start_index: int = 0) -> List[str]:
        session_dir = self._dir()
        screenshot_files = [
            f
            for f in os.listdir(session_dir)
            if f.startswith("screenshot_") and f.endswith(".png")
        ]

        if not screenshot_files:
            return []

        # Step 1: Sort from newest to oldest
        sorted_screenshots = sorted(
            screenshot_files,
            key=lambda f: os.path.getmtime(os.path.join(session_dir, f)),
            reverse=True,
        )

        # Step 2: Select the n latest screenshots starting from start_index
        selected_screenshots = sorted_screenshots[start_index : start_index + n]

        # Step 3: Reverse to have them in ascending order (oldest to newest)
        selected_screenshots = selected_screenshots[::-1]

        # Get the full paths of the screenshots
        selected_paths = [
            os.path.join(session_dir, screenshot) for screenshot in selected_screenshots
        ]

        # Add the screenshots to the used_screenshots set
        self.used_screenshots.update(selected_paths)

        return selected_paths

    def _cleanup_unused_screenshots(self):
        session_dir = self._dir()
        shutil.rmtree(session_dir)

    def _record_mouse_move_action_details(self, x, y, event_time: float | None = None):
        """Records the mouse movement action."""
        recording_logger.info("_record_mouse_move_action starting")
        event_time = time.time() if not event_time else event_time
        if not self.mouse_moving or not self.mouse_move_start_state:
            return  # Already recorded or not moving

        if not self.mouse_move_start_pos:
            recording_logger.warning("Warning: No start position for mouse movement")
            return
        
        start_state = self.mouse_move_start_state
        event_order = self.event_order
        self.event_order += 1

        # Reset movement tracking variables
        self.mouse_moving = False
        recording_logger.info("_record_mouse_move_action Reset movement tracking variables")
        self.mouse_move_start_pos = None
        self.mouse_move_start_state = None
        self.mouse_move_timer = None
        self.last_mouse_position = (x, y)

        # Use the most recent valid coordinates
        final_x, final_y = x, y
        if self.movement_buffer:
            recording_logger.info("_record_mouse_move_action setting movement buffer")
            final_x, final_y, _ = self.movement_buffer[-1]

        recording_logger.info("_record_mouse_move_action setting action")
        # Create and record the action event
        action = V1Action(
            name="move_mouse",
            parameters={
                "x": int(final_x),
                "y": int(final_y),
            },
        )
        recording_logger.info("_record_mouse_move_action setting action event")

        return ActionDetails(
                    x=x,
                    y=y,
                    action=action,
                    start_state=start_state.to_v1(),
                    end_stamp=event_time,
                    event_order=event_order
                )
    
    def _send_mouse_move_action(
        self, 
        mouse_move_details: ActionDetails, 
        end_screenshot_path: list[str] | None = None
    ):
        """Records the mouse movement action."""
        recording_logger.info("_send_mouse_move_action starting")
        if not mouse_move_details.start_state:
            raise ValueError(f"_send_mouse_move_action failure mouse_move_details.start_state not set {mouse_move_details.model_dump_json()}")
        # Use the most recent valid coordinates
        final_x, final_y = mouse_move_details.x, mouse_move_details.y

        # Ensure start state has two images
        recording_logger.info("_send_mouse_move_action checking start state images")
        if mouse_move_details.start_state.images is None or len(mouse_move_details.start_state.images) < 2:
            # Get an additional screenshot to have two before images
            recording_logger.info("_send_mouse_move_action getting start state screenshots")
            if mouse_move_details.start_state.timestamp:
                before_time = mouse_move_details.start_state.timestamp - before_screenshot_offset  # 30ms earlier to make sure we get true before screenshots
                additional_screenshots = self._get_screenshots_by_time(2, before_time, "before")
                mouse_move_details.start_state.images = list(filter(None, (self.encode_image_to_base64(screenShot) for screenShot in additional_screenshots)))
                recording_logger.info("_send_mouse_move_action getting start state screenshots completed")

        # Use the provided end screenshot, or take new ones
        if end_screenshot_path is None:
            recording_logger.info("_send_mouse_move_action taking new end screenshots")
            # Take two screenshots after movement
            end_screenshots = []
            if mouse_move_details.end_stamp:
                end_screenshots = self._get_screenshots_by_time(2, mouse_move_details.end_stamp, "after")
            else:
                raise ValueError("End_stamp required for _send_mouse_move_action")
            recording_logger.info(f"_send_mouse_move_action taking new end screenshots completed {end_screenshot_path}")
        else:
            # shouldn't run
            # Ensure we have two end screenshots
            end_screenshots = []
            if mouse_move_details.end_stamp:
                recording_logger.info("_send_mouse_move_action adding additional end screenshot")
                additional_screenshot = self._get_screenshots_by_time(1, mouse_move_details.end_stamp, "after")
                end_screenshots = end_screenshot_path + additional_screenshot
            recording_logger.info("_send_mouse_move_action taking additional end screenshot completed")

        # Prepare end state
        recording_logger.info("_send_mouse_move_action setting end state")
        end_state = EnvState(
            images=[
                self.encode_image_to_base64(screenshot)
                for screenshot in end_screenshots
            ],
            coordinates=(int(final_x), int(final_y)),
            timestamp=mouse_move_details.end_stamp
        )

        recording_logger.info("_send_mouse_move_action setting action")
        # Create and record the action event
        action = mouse_move_details.action
        recording_logger.info("_send_mouse_move_action setting action event")
        action_event = ActionEvent(
            state=EnvState.from_v1(mouse_move_details.start_state),
            action=action,
            tool=DESKTOP_TOOL_REF,
            end_state=end_state,
            event_order=mouse_move_details.event_order,
        )
        self.actions.append(action_event)

        # Send the action to Celery
        recording_logger.info("_send_mouse_move_action building action payload")
        action_payload = [
            self._task.id,
            self._task.auth_token,
            self._task.owner_id,
            self._task.to_v1().model_dump(),
            action_event.to_v1().model_dump(),
        ]

        recording_logger.info("_send_mouse_move_action sending action to celery")
        send_action.delay(*action_payload)

        recording_logger.info("_send_mouse_move_action completed")

    def on_move(self, x, y):
        """Handles mouse movement events."""
        event_time = time.time()
        text_action_details = None
        recording_logger.info(f"Mouse moved to ({x}, {y})")

        with self.lock:
            if self.typing_in_progress:
                recording_logger.info("Finalizing text event due to mouse movement...")
                text_action_details = self.record_text_action_details()
            
            current_time = time.time()

            # Initialize last position if needed
            if self.last_mouse_position is None:
                self.last_mouse_position = (x, y)
                self.last_movement_time = current_time
                # Do not return here; proceed to process the movement

            # Calculate distance moved
            dx = x - self.last_mouse_position[0]
            dy = y - self.last_mouse_position[1]
            distance_moved = (dx**2 + dy**2) ** 0.5

            # If movement is below threshold, ignore the event
            if distance_moved < self.MOVEMENT_THRESHOLD:
                return

            # Start a new movement sequence if not already moving
            if not self.mouse_moving:
                self.mouse_moving = True
                self.mouse_move_start_pos = self.last_mouse_position
                # Not including any images so we can move the encoding outside the lock. 
                # Look at the _send_mouse_move_action to see how the images are added based on timestamp
                self.mouse_move_start_state = EnvState(
                    images=[],
                    coordinates=tuple(map(int, self.last_mouse_position)),
                    timestamp=event_time
                )
                self.movement_buffer = [(x, y, current_time)]
            else:
                # Continue existing movement sequence
                self.movement_buffer.append((x, y, current_time))

            self.last_mouse_position = (x, y)
            self.last_movement_time = current_time

            # Reset the timer
            if self.mouse_move_timer:
                self.mouse_move_timer.cancel()

            self.mouse_move_timer = threading.Timer(4, self.on_mouse_stop, args=(x, y))
            self.mouse_move_timer.start()
        
        # if there is a text action due to mouse movement go ahead and send it outside lock
        if text_action_details:
            # waiting for screenshots to finish writing
            time.sleep(action_delay)
            self.send_text_action(text_action_details)

    def on_mouse_stop(self, x, y):
        """Called when the mouse stops moving."""
        mouse_move_details = None
        event_time= time.time()
        recording_logger.info(f"Mouse stopped at ({x}, {y})")
        with self.lock:
            if not self.mouse_moving:
                recording_logger.info("Mouse movement already recorded")
                return
            # Mouse movement has stopped
            mouse_move_details = self._record_mouse_move_action_details(x, y, event_time)

        if mouse_move_details:
            # waiting for screenshots to finish writing
            time.sleep(action_delay)
            self._send_mouse_move_action(mouse_move_details)

    def on_press(self, key: Key):
        recording_logger.info(f"on_press waiting for lock with key {key} count of actions {len(self.actions)}")
        event_time = time.time()
        before_time = event_time - before_screenshot_offset  # 30ms earlier to make sure we get screenshots before the keypress
        mouse_move_details = None
        special_key_details = None
        text_action_details = None
        with self.lock:
            recording_logger.info(
                f"on_press acquired lock with key {key} count of actions {len(self.actions)}"
            )
            recording_logger.info(f"\npressed key: {key}")

            if self.mouse_move_timer:
                self.mouse_move_timer.cancel()

            # If mouse is moving, record the movement action first
            if self.mouse_moving:
                # Get the latest two screenshots before the key press
                recording_logger.info("Recording mouse movement before handling key press")
                mouse_x, mouse_y = pyautogui.position()
                # end_screenshot = (
                #     key_start_screenshots[-1] if key_start_screenshots else None
                # )
                mouse_move_details = self._record_mouse_move_action_details(mouse_x, mouse_y, event_time)
            
            event_order = self.event_order
            self.event_order += 1

            # Handle shift and caps lock keys
            if key in [Key.shift, Key.shift_r, Key.shift_l]:
                self.shift_pressed = True
            elif key == Key.caps_lock:
                self.caps_lock_on = not self.caps_lock_on
            elif key == Key.space:
                # Start typing if not already in progress
                if not self.typing_in_progress:
                    self.start_typing_sequence(event_time)
                self.text_buffer += " "
            # Handle backspace
            elif key == Key.backspace:
                if self.text_buffer:
                    self.text_buffer = self.text_buffer[:-1]
            # Handle regular character keys
            elif isinstance(key, KeyCode):
                char = key.char
                if char:
                    # Start typing if not already in progress
                    if not self.typing_in_progress:
                        self.start_typing_sequence(event_time)

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
                        recording_logger.info("Finalizing text event due to special key...")
                        text_action_details = self.record_text_action_details()
                        # self.record_text_action()

                    x, y = pyautogui.position()
                    pyautogui_key = PYNPUT_TO_PYAUTOGUI.get(key, str(key))
                    action = V1Action(
                        name="press_key", parameters={"key": pyautogui_key}
                    )
                    special_key_details = ActionDetails(
                        x=x,
                        y=y,
                        action=action,
                        start_state=None,
                        end_stamp=event_time,
                        event_order=event_order
                    )

            recording_logger.info(
                f"on_press releasing lock with key {key} event_order: {event_order}"
            )

        if mouse_move_details or special_key_details or text_action_details:
            time.sleep(action_delay)
            if mouse_move_details:
                # waiting for screenshots to finish writing
                mouse_move_end_screenshots = self._get_screenshots_by_time(2, before_time, "before")
                self._send_mouse_move_action(mouse_move_details, mouse_move_end_screenshots)
            if text_action_details:
                self.send_text_action(text_action_details)
            if special_key_details:
                # This is too slow, we need to duplicate one back
                # start_screenshot_path = self._get_latest_screenshots(1, 1)
                # start_screenshot_path.append(start_screenshot_path[0])
                start_screenshot_path = self._get_screenshots_by_time(2, before_time, "before")
                recording_logger.info('creating state')
                start_state = EnvState(
                    images=[
                        self.encode_image_to_base64(screenShot)
                        for screenShot in start_screenshot_path
                    ],
                    coordinates=(int(special_key_details.x), int(special_key_details.y)),
                    timestamp=event_time
                )
                special_key_details.start_state = start_state
                self.send_text_action(special_key_details)

    def on_release(self, key):
        recording_logger.info(
            f"on_release waiting lock with key {key} count of actions {len(self.actions)}"            
        )
        with self.lock:
            recording_logger.info(
                f"on_release acquired lock with key {key} count of actions {len(self.actions)}"                
            )
            if key in [Key.shift, Key.shift_r, Key.shift_l]:
                self.shift_pressed = False
            recording_logger.info(
                f"on_release releasing lock with key {key} count of actions {len(self.actions)}"                
            )

    def on_click(self, x, y, button, pressed):
        event_time = time.time()
        before_time = event_time - before_screenshot_offset  # 30ms earlier to make sure we get screenshots before the click
        mouse_move_details = None
        text_action_details = None
        action = None
        event_order = None
        if not pressed:
            recording_logger.info("skipping button up event")
            return
        recording_logger.info(
            f"on_click waiting lock with x,y: {x}, {y} count of actions {len(self.actions)}"            
        )
        with self.lock:
            recording_logger.info(
                f"on_click acquired lock with x,y: {x}, {y} count of actions {len(self.actions)}"                
            )
            try:
                # Cancel any pending mouse movement recording
                if self.mouse_move_timer:
                    self.mouse_move_timer.cancel()

                # If there was mouse movement, record it with the current position
                if self.mouse_moving:
                    recording_logger.info("Recording mouse movement before handling click")
                    # mouse_move_end_screenshots = self._get_screenshots_by_time(2, before_time, "before")
                    mouse_move_details = self._record_mouse_move_action_details(x, y, event_time)
                
                if self.typing_in_progress:
                    recording_logger.info("Finalizing text event due to click...")
                    text_action_details = self.record_text_action_details()

                # Clear movement buffer
                self.movement_buffer = []
                self.last_mouse_position = (x, y)

                is_double_click = False
                DOUBLE_CLICK_THRESHOLD = (
                    0.3  # Time threshold for double-click detection (in seconds)
                )

                if self.last_click_time and self.last_click_button == button:
                    time_since_last_click = event_time - self.last_click_time
                    if time_since_last_click <= DOUBLE_CLICK_THRESHOLD:
                        is_double_click = True

                self.last_click_time = event_time
                self.last_click_button = button
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
                    recording_logger.info("Double-click detected")
                else:
                    # Record regular click event as an action
                    action = V1Action(
                        name="click",
                        parameters={
                            "x": int(x),
                            "y": int(y),
                            "button": button._name_,
                        },
                    )
                event_order = self.event_order
                self.event_order += 1
                recording_logger.info(f"clicked button: {x}, {y}, {button}, {pressed}", )
                
            except Exception as e:
                recording_logger.info(f"Error recording click event in lock: {e}")
            recording_logger.info(
                f"on_click releasing lock with x,y: {x}, {y} count of actions {len(self.actions)}"                
            )
        try:
            time.sleep(action_delay)
            if mouse_move_details:
                mouse_move_end_screenshots = self._get_screenshots_by_time(2, before_time, "before")
                self._send_mouse_move_action(mouse_move_details, mouse_move_end_screenshots)
            if text_action_details:
                self.send_text_action(text_action_details)
            if action:
                # We replicate the screenshot beforw which mimics more of what the agent will see
                # start_screenshot_path = self._get_latest_screenshots(1)
                start_screenshot_path = self._get_screenshots_by_time(2, before_time, "before")
                recording_logger.info(f"got screenshots: {start_screenshot_path}")
                # start_screenshot_path.append(start_screenshot_path[0])

                start_state = EnvState(
                        images=[
                            self.encode_image_to_base64(screenShot)
                            for screenShot in start_screenshot_path
                        ],
                        coordinates=(int(x), int(y)),
                        timestamp=before_time
                    )

                end_screenshot_path = self._get_screenshots_by_time(2, event_time, "after")
                end_state = EnvState(
                    images=[
                        self.encode_image_to_base64(screenShot)
                        for screenShot in end_screenshot_path
                    ],
                    coordinates=(int(x), int(y)),
                    timestamp=event_time
                )

                action_event = ActionEvent(
                    state=start_state,
                    action=action,
                    tool=DESKTOP_TOOL_REF,
                    end_state=end_state,
                    event_order=event_order,
                )
                self.actions.append(action_event)
                # kicking off celery job
                recording_logger.info('on_click sending action')
                send_action.delay(
                    self._task.id,
                    self._task.auth_token,
                    self._task.owner_id,
                    self._task.to_v1().model_dump(),
                    action_event.to_v1().model_dump(),
                )
            else:
                raise ValueError(f"No action defined due to previous errors, could not record click event")

        except Exception as e:
            recording_logger.info(f"Error recording click event: {e}")        

    def on_scroll(self, x, y, dx, dy):
        event_time = time.time()
        before_time = event_time - before_screenshot_offset  # 30ms earlier to make sure we get screenshots before the click
        mouse_move_details = None
        text_action_details = None
        recording_logger.info(
            f"on_scroll waiting lock with x,y: {x}, {y}; dx, dy: {dx} count of actions {len(self.actions)}"            
        )
        with self.lock:
            recording_logger.info(
                f"on_scroll acquired lock with x,y: {x}, {y}; dx, dy: {dx}, {dy} count of actions {len(self.actions)}"                
            )

            # Before recording the scroll, check if there is pending text
            if self.typing_in_progress:
                recording_logger.info("Finalizing text event due to scroll...")
                text_action_details = self.record_text_action_details()

            if self.mouse_move_timer:
                self.mouse_move_timer.cancel()

            # If mouse is moving, record the movement action first
            if self.mouse_moving:
                # key_start_screenshots = self._get_latest_screenshots(2)
                recording_logger.info("Recording mouse movement before handling scroll")
                # mouse_move_end_screenshots = self._get_screenshots_by_time(2, before_time, "before")
                mouse_x, mouse_y = pyautogui.position()
                mouse_move_details = self._record_mouse_move_action_details(mouse_x, mouse_y, event_time)
                # end_screenshot = (
                #     key_start_screenshots[-1] if key_start_screenshots else None
                # )
                # self._record_mouse_move_action(
                #     mouse_x, mouse_y, end_screenshot_path=end_screenshot
                # )

            self.scroll_dx += dx
            self.scroll_dy += dy

            if self.scroll_timer:
                self.scroll_timer.cancel()

            if self.scroll_start_state is None:
                # start_screenshot_path = self._get_latest_screenshots(2)
                mouse_x, mouse_y = pyautogui.position()
                self.scroll_start_state = EnvState(
                    images=None,
                    coordinates=(int(mouse_x), int(mouse_y)),
                    timestamp=event_time
                )
            event_order = self.event_order
            self.event_order += 1
            self.scroll_timer = threading.Timer(
                0.25, self._send_scroll_action, args=(x, y, event_order)
            )
            self.scroll_timer.start()
            recording_logger.info(
                f"on_scroll releasing lock with x,y: {x}, {y}; dx, dy: {dx}, {dy} count of actions {event_order}"                
            )
        if mouse_move_details or text_action_details:
            time.sleep(action_delay)
            if mouse_move_details:
                # waiting for screenshots to finish writing
                mouse_move_end_screenshots = self._get_screenshots_by_time(2, before_time, "before")
                self._send_mouse_move_action(mouse_move_details, mouse_move_end_screenshots)
            if text_action_details:
                self.send_text_action(text_action_details)

    def send_final_action(self, result, comment):
        recording_logger.info(
            f"send_final_action waiting lock with result, comment: {result}, {comment} count of actions {len(self.actions)}"            
        )
        event_time = time.time()
        before_time = event_time - before_screenshot_offset  # 30ms earlier to make sure we get screenshots before the click

        with self.lock:
            recording_logger.info(
                f"send_final_action acquired lock with result, comment: {result}, {comment} count of actions {len(self.actions)}"                
            )
            event_order = self.event_order
            self.event_order += 1
            try:
                if self.typing_in_progress:
                    recording_logger.info("Finalizing text event due to end recording...")
                    text_action_details = self.record_text_action_details()
                    # not worried about lock since this is the final action
                    self.send_text_action(text_action_details)

                x, y = pyautogui.position()
                start_screenshot_path = self._get_screenshots_by_time(2, before_time, "before")

                state = EnvState(
                    images=[
                        self.encode_image_to_base64(screenShot)
                        for screenShot in start_screenshot_path
                    ],
                    coordinates=(int(x), int(y)),
                    timestamp=event_time
                )

                end_screenshot_path = self._get_screenshots_by_time(2, event_time, "after")

                end_state = EnvState(
                    images=[
                        self.encode_image_to_base64(screenShot)
                        for screenShot in end_screenshot_path
                    ],
                    coordinates=(int(x), int(y)),
                    timestamp=event_time
                )

                # Record final end event as an action
                action = V1Action(
                    name="end",
                    parameters={
                        "result": result,
                        "comment": comment
                    },
                )
                
                action_event = ActionEvent(
                    state=state,
                    action=action,
                    tool=DESKTOP_TOOL_REF,
                    end_state=end_state,
                    event_order=event_order,
                )
                self.actions.append(action_event)
                # kicking off celery job
                recording_logger.info('send_final_action sending action')
                send_action.delay(
                    self._task.id,
                    self._task.auth_token,
                    self._task.owner_id,
                    self._task.to_v1().model_dump(),
                    action_event.to_v1().model_dump(),
                )

            except Exception as e:
                recording_logger.info(f"Error recording final end event: {e}")
            recording_logger.info(
                f"send_final_action releasing lock with result, comment: {result}, {comment} count of actions {event_order}"                
            )

    def _send_scroll_action(self, x, y, action_order):
        recording_logger.info(
            f"_send_scroll_action waiting lock with x,y: {x}, {y}; dx, dy: {self.scroll_dx}, {self.scroll_dy} count of actions {action_order}"            
        )

        event_time = time.time()
        with self.lock:
            recording_logger.info(
                f"_send_scroll_action acquired lock with x,y: {x}, {y}; dx, dy: {self.scroll_dx}, {self.scroll_dy} count of actions {action_order}"                
            )

            state = self.scroll_start_state
            if state is None:
                recording_logger.info(
                    "_send_scroll_action: scroll_start_state is None, setting state here."                    
                )
                # start_screenshot_path = self._get_latest_screenshots(2)
                mouse_x, mouse_y = pyautogui.position()
                state = EnvState(
                    images=None,
                    coordinates=(int(mouse_x), int(mouse_y)),
                    timestamp=event_time
                )
            scroll_dx = self.scroll_dx
            scroll_dy = self.scroll_dy
            # Reset scroll deltas
            self.scroll_dx = 0
            self.scroll_dy = 0
            self.scroll_start_state = None
            self.scroll_timer = None
            recording_logger.info(
                f"_send_scroll_action releasing lock with x,y: {x}, {y}; dx, dy: {scroll_dx}, {scroll_dy} count of actions {action_order}"                
            )
        time.sleep(action_delay)
        if (state.images is None or len(state.images) < 2) and state.timestamp:
            before_time = state.timestamp - before_screenshot_offset  # 30ms earlier to make sure we get screenshots before the click
            start_screenshot_path = self._get_screenshots_by_time(2, before_time, "before")
            state.images = list(filter(None, (self.encode_image_to_base64(screenShot) for screenShot in start_screenshot_path)))

        # Get the end screenshots
        end_screenshot_path = []
        end_stamp = state.timestamp if state.timestamp else event_time
        end_screenshot_path = self._get_screenshots_by_time(2, end_stamp, "after")

        end_state = EnvState(
            images=[
                self.encode_image_to_base64(screenShot)
                for screenShot in end_screenshot_path
            ],
            coordinates=(int(x), int(y)),
            timestamp=end_stamp
        )

        clicks = -int(scroll_dy)

        action = V1Action(name="scroll", parameters={"clicks": clicks})
        action_event = ActionEvent(
            state=state,
            action=action,
            end_state=end_state,
            tool=DESKTOP_TOOL_REF,
            event_order=action_order,
        )

        self.actions.append(action_event)
        recording_logger.info('_send_scroll_action sending action')
        # Send the action to Celery
        send_action.delay(
            self._task.id,
            self._task.auth_token,
            self._task.owner_id,
            self._task.to_v1().model_dump(),
            action_event.to_v1().model_dump(),
        )

    def start_typing_sequence(self, event_time):
        x, y = pyautogui.position()
        # start_screenshot_path = self._get_latest_screenshots(2)
        # Not including any images so we can move the encoding outside the lock. 
        # Look at the send_text_action to see how the images are added based on timestamp
        self.text_start_state = EnvState(
            images=None,
            coordinates=(int(x), int(y)),
            timestamp=event_time
        )
        self.typing_in_progress = True

    def record_text_action_details(self):
        end_stamp = time.time()
        recording_logger.info("recording text action details")
        if self.text_buffer.strip():
            x, y = pyautogui.position()

            action = V1Action(name="type_text", parameters={"text": self.text_buffer})

            if not self.text_start_state:
                raise ValueError("No text start state available")
            
            text_start_state = self.text_start_state
            event_order = self.event_order
            self.event_order += 1

            # Reset the typing state
            self.text_buffer = ""
            self.typing_in_progress = False
            self.text_start_state = None

            return ActionDetails(
                    x=x,
                    y=y,
                    action=action,
                    start_state=text_start_state.to_v1(),
                    end_stamp=end_stamp,
                    event_order=event_order
                )
        else:
            # Reset the typing state
            text_buffer_error = self.text_buffer
            self.text_buffer = ""
            self.typing_in_progress = False
            self.text_start_state = None
            raise ValueError(f"text_buffer_error cannot strip text_buffer: {text_buffer_error}")

    def send_text_action(self, text_action_details: ActionDetails):
        if not text_action_details.start_state or not text_action_details.end_stamp:
            raise ValueError(f"start_state or end_stamp in text_action_details is None! text_action_details: {text_action_details.model_dump_json()}")
        

        end_screenshot_path = []
        end_screenshot_path = self._get_screenshots_by_time(2, text_action_details.end_stamp, "after")
        
        recording_logger.info(f'end_screenshot_path: {end_screenshot_path}')

        end_state = EnvState(
            images=[
                self.encode_image_to_base64(screenShot)
                for screenShot in end_screenshot_path
            ],
            coordinates=(int(text_action_details.x), int(text_action_details.y)),
            timestamp=text_action_details.end_stamp
        )

        if text_action_details.start_state.images is None or len(text_action_details.start_state.images) < 2:
            # Get an additional screenshot to have two before images
            recording_logger.info("send_text_action getting start state screenshots")
            if text_action_details.start_state.timestamp:
                before_time = text_action_details.start_state.timestamp - before_screenshot_offset  # 30ms earlier to make sure we get true before screenshots
                additional_screenshots = self._get_screenshots_by_time(2, before_time, "before")
                text_action_details.start_state.images = list(filter(None, (self.encode_image_to_base64(screenShot) for screenShot in additional_screenshots)))
                recording_logger.info("send_text_action getting start state screenshots completed")                    

        action_event = ActionEvent(
            state=EnvState.from_v1(text_action_details.start_state),
            action=text_action_details.action,
            tool=DESKTOP_TOOL_REF,
            end_state=end_state,
            event_order=text_action_details.event_order,
        )
        self.actions.append(action_event)
        # kicking off celery job
        recording_logger.info('record_text_action sending action')
        send_action.delay(
            self._task.id,
            self._task.auth_token,
            self._task.owner_id,
            self._task.to_v1().model_dump(),
            action_event.to_v1().model_dump(),
        )
        recording_logger.info(f"sent text action: {text_action_details.action.model_dump_json()}")


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
                recording_logger.info(
                    f"Error encoding image {image_path} on attempt {attempt + 1}: {e}"                    
                )
                time.sleep(delay)

        recording_logger.info(
            f"Failed to encode image {image_path} after {max_retries} attempts"            
        )
        return None
