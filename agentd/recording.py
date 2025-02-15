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

import logging
import logging.config
from .logging_config import LOGGING_CONFIG  # or wherever you store the config

logging.config.dictConfig(LOGGING_CONFIG)

recording_logger = logging.getLogger("recording")

DESKTOP_TOOL_REF = V1ToolRef(
    module="agentdesk.device", type="Desktop", package="agentdesk"
)

PYNPUT_TO_PYAUTOGUI: Dict[KeyCode, str] = {
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
SCREENSHOT_INTERVAL = 0.2


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

        self.typing_in_progress = False
        self.text_start_state = None
        self.last_click_time = None
        self.last_click_button = None
        self.scroll_timer = None
        self.scroll_dx = 0
        self.scroll_dy = 0
        self.scroll_start_state = None
        self.actions = []
        self.mouse_moving = False
        self.mouse_move_timer = None
        self.mouse_move_start_pos = None
        self.mouse_move_start_state = None
        self.last_mouse_position = None
        self.movement_buffer = []
        self.MOVEMENT_BUFFER_TIME = 3
        self.last_movement_time = None
        self.MOVEMENT_THRESHOLD = 5
        self.lock = threading.Lock()

    def start(self):
        x, y = pyautogui.position()
        self.last_mouse_position = (x, y)
        self.last_movement_time = time.time()

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
    
    def send_useSecret_action(self, secret_name, field):
        recording_logger.info(f"send use secret action: {secret_name} with field {field} to celery")
        recording_logger.info(
            f"send_useSecret_action waiting lock with name: {secret_name} count of actions {len(self.actions)}")
        with self.lock:
            recording_logger.info(f"send_useSecret_action acquired lock with name: {secret_name} count of actions {len(self.actions)}")

            try:
                if self.typing_in_progress:
                    recording_logger.info("Finalizing text event due to use secret...")
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
                    event_order=len(self.actions),
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
            recording_logger.info(f"send_useSecret_action releasing lock with name: {secret_name} count of actions {len(self.actions)}")

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

    def _record_mouse_move_action(self, x, y, end_screenshot_path=None):
        """Records the mouse movement action."""

        recording_logger.info("_record_mouse_move_action starting")
        if not self.mouse_moving:
            return  # Already recorded or not moving

        if not self.mouse_move_start_pos:
            recording_logger.warning("Warning: No start position for mouse movement")
            return

        self.mouse_moving = False

        # Use the most recent valid coordinates
        final_x, final_y = x, y
        if self.movement_buffer:
            recording_logger.info("_record_mouse_move_action setting movement buffer")
            final_x, final_y, _ = self.movement_buffer[-1]

        # Ensure start state has two images
        recording_logger.info("_record_mouse_move_action checking start state images")
        if self.mouse_move_start_state and len(self.mouse_move_start_state.images) < 2:
            # Get an additional screenshot to have two before images
            recording_logger.info("_record_mouse_move_action getting start state screenshots")
            additional_screenshots = self._get_latest_screenshots(2)
            if additional_screenshots:
                self.mouse_move_start_state.images.insert(
                    0, self.encode_image_to_base64(additional_screenshots[0])
                )
                recording_logger.info("_record_mouse_move_action getting start state screenshots completed")

        # Use the provided end screenshot, or take new ones
        if end_screenshot_path is None:
            recording_logger.info("_record_mouse_move_action taking new end screenshots")
            # Take two screenshots after movement
            end_screenshots = []
            end_screenshots.append(self.take_screenshot("mouse_move_end"))
            time.sleep(0.05)
            end_screenshots.append(self.take_screenshot("mouse_move_end"))
            recording_logger.info("_record_mouse_move_action taking new end screenshots completed")
        else:
            # Ensure we have two end screenshots
            recording_logger.info("_record_mouse_move_action taking additional end screenshot")
            additional_screenshot = self.take_screenshot("mouse_move_end")
            end_screenshots = [end_screenshot_path, additional_screenshot]
            recording_logger.info("_record_mouse_move_action taking additional end screenshot completed")

        # Prepare end state
        recording_logger.info("_record_mouse_move_action setting end state")
        end_state = EnvState(
            images=[
                self.encode_image_to_base64(screenshot)
                for screenshot in end_screenshots
            ],
            coordinates=(int(x), int(y)),
        )

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
        action_event = ActionEvent(
            state=self.mouse_move_start_state,
            action=action,
            tool=DESKTOP_TOOL_REF,
            end_state=end_state,
            event_order=len(self.actions),
        )

        self.actions.append(action_event)

        # Send the action to Celery (or your task queue)
        recording_logger.info("_record_mouse_move_action building action payload")
        action_payload = [
            self._task.id,
            self._task.auth_token,
            self._task.owner_id,
            self._task.to_v1().model_dump(),
            action_event.to_v1().model_dump(),
        ]
        # Use dictionary unpacking to pass arguments
        recording_logger.info("_record_mouse_move_action sending action to celery")
        send_action.delay(*action_payload)

        # Reset movement tracking variables
        recording_logger.info("_record_mouse_move_action Reset movement tracking variables")
        self.mouse_move_start_pos = None
        self.mouse_move_start_state = None
        self.mouse_move_timer = None
        self.last_mouse_position = (x, y)
        recording_logger.info("_record_mouse_move_action completed")

    def on_move(self, x, y):
        """Handles mouse movement events."""
        recording_logger.info(f"Mouse moved to ({x}, {y})")
        with self.lock:
            if self.typing_in_progress:
                recording_logger.info("Finalizing text event due to mouse movement...")
                self.record_text_action()

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
                start_screenshots = self._get_latest_screenshots(2)
                self.mouse_move_start_state = EnvState(
                    images=[
                        self.encode_image_to_base64(screenshot)
                        for screenshot in start_screenshots
                    ],
                    coordinates=tuple(map(int, self.last_mouse_position)),
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

    def on_mouse_stop(self, x, y):
        """Called when the mouse stops moving."""
        recording_logger.info(f"Mouse stopped at ({x}, {y})")
        with self.lock:
            if not self.mouse_moving:
                recording_logger.info("Mouse movement already recorded")
                return
            # Mouse movement has stopped
            self._record_mouse_move_action(x, y)

    def on_press(self, key: Key):
        recording_logger.info(f"on_press waiting for lock with key {key} count of actions {len(self.actions)}")

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
                key_start_screenshots = self._get_latest_screenshots(2)
                recording_logger.info("Recording mouse movement before handling key press")
                mouse_x, mouse_y = pyautogui.position()
                end_screenshot = (
                    key_start_screenshots[-1] if key_start_screenshots else None
                )
                self._record_mouse_move_action(
                    mouse_x, mouse_y, end_screenshot_path=end_screenshot
                )

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
                        recording_logger.info("Finalizing text event due to special key...")
                        self.record_text_action()

                    x, y = pyautogui.position()
                    pyautogui_key = PYNPUT_TO_PYAUTOGUI.get(key, str(key))

                    # This is too slow, we need to duplicate one back
                    start_screenshot_path = self._get_latest_screenshots(1, 1)
                    start_screenshot_path.append(start_screenshot_path[0])
                    recording_logger.info('creating state')
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
                    recording_logger.info('creating end state')
                    end_state = EnvState(
                        images=[
                            self.encode_image_to_base64(screenShot)
                            for screenShot in end_screenshot_path
                        ],
                        coordinates=(int(x), int(y)),
                    )

                    # Record special key event as an action
                    recording_logger.info('creating action')
                    action = V1Action(
                        name="press_key", parameters={"key": pyautogui_key}
                    )
                    recording_logger.info('creating action event')
                    action_event = ActionEvent(
                        state=state,
                        action=action,
                        tool=DESKTOP_TOOL_REF,
                        end_state=end_state,
                        event_order=len(self.actions),
                    )
                    self.actions.append(action_event)
                    # kicking off celery job for sending the action
                    action_payload = [
                        self._task.id,
                        self._task.auth_token,
                        self._task.owner_id,
                        self._task.to_v1().model_dump(),
                        action_event.to_v1().model_dump(),
                    ]
                    # recording_logger.info(f'on_press sending action {action_payload}')
                    send_action.delay(
                        *action_payload
                    )
            recording_logger.info(
                f"on_press releasing lock with key {key} count of actions {len(self.actions)}"
            )

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
            # Cancel any pending mouse movement recording
            if self.mouse_move_timer:
                self.mouse_move_timer.cancel()

            # We replicate the screenshot beforw which mimics more of what the agent will see
            start_screenshot_path = self._get_latest_screenshots(1)
            recording_logger.info(f"got screenshots: {start_screenshot_path}")
            start_screenshot_path.append(start_screenshot_path[0])

            # If there was mouse movement, record it with the current position
            if self.mouse_moving:
                self._record_mouse_move_action(x, y)

            # Clear movement buffer
            self.movement_buffer = []
            self.last_mouse_position = (x, y)

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

            recording_logger.info(f"clicked button: {x}, {y}, {button}, {pressed}", )

            try:
                if self.typing_in_progress:
                    recording_logger.info("Finalizing text event due to click...")
                    self.record_text_action()

                if self.mouse_moving:
                    recording_logger.info("Recording mouse movement before handling click")
                    # Use the last screenshot as the end screenshot for mouse movement
                    end_screenshot = (
                        start_screenshot_path[-1] if start_screenshot_path else None
                    )
                    self._record_mouse_move_action(
                        x, y, end_screenshot_path=end_screenshot
                    )

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

                action_event = ActionEvent(
                    state=state,
                    action=action,
                    tool=DESKTOP_TOOL_REF,
                    end_state=end_state,
                    event_order=len(self.actions),
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

            except Exception as e:
                recording_logger.info(f"Error recording click event: {e}")
            recording_logger.info(
                f"on_click releasing lock with x,y: {x}, {y} count of actions {len(self.actions)}"                
            )

    def on_scroll(self, x, y, dx, dy):
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
                self.record_text_action()

            if self.mouse_move_timer:
                self.mouse_move_timer.cancel()

            # If mouse is moving, record the movement action first
            if self.mouse_moving:
                # Get the latest two screenshots before the key press
                key_start_screenshots = self._get_latest_screenshots(2)
                recording_logger.info("Recording mouse movement before handling key press")
                mouse_x, mouse_y = pyautogui.position()
                end_screenshot = (
                    key_start_screenshots[-1] if key_start_screenshots else None
                )
                self._record_mouse_move_action(
                    mouse_x, mouse_y, end_screenshot_path=end_screenshot
                )

            self.scroll_dx += dx
            self.scroll_dy += dy

            if self.scroll_timer:
                self.scroll_timer.cancel()

            if self.scroll_start_state is None:
                start_screenshot_path = self._get_latest_screenshots(2)
                mouse_x, mouse_y = pyautogui.position()
                self.scroll_start_state = EnvState(
                    images=[
                        self.encode_image_to_base64(screenShot)
                        for screenShot in start_screenshot_path
                    ],
                    coordinates=(int(mouse_x), int(mouse_y)),
                )

            self.scroll_timer = threading.Timer(
                0.25, self._send_scroll_action, args=(x, y, len(self.actions))
            )
            self.scroll_timer.start()
            recording_logger.info(
                f"on_scroll releasing lock with x,y: {x}, {y}; dx, dy: {dx}, {dy} count of actions {len(self.actions)}"                
            )

    def send_final_action(self, result, comment):
        recording_logger.info(
            f"send_final_action waiting lock with result, comment: {result}, {comment} count of actions {len(self.actions)}"            
        )
        with self.lock:
            recording_logger.info(
                f"send_final_action acquired lock with result, comment: {result}, {comment} count of actions {len(self.actions)}"                
            )

            try:
                if self.typing_in_progress:
                    recording_logger.info("Finalizing text event due to end recording...")
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
                    event_order=len(self.actions),
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
                f"send_final_action releasing lock with result, comment: {result}, {comment} count of actions {len(self.actions)}"                
            )

    def _send_scroll_action(self, x, y, action_order):
        recording_logger.info(
            f"_send_scroll_action waiting lock with x,y: {x}, {y}; dx, dy: {self.scroll_dx}, {self.scroll_dy} count of actions {action_order}"            
        )
        with self.lock:
            recording_logger.info(
                f"_send_scroll_action acquired lock with x,y: {x}, {y}; dx, dy: {self.scroll_dx}, {self.scroll_dy} count of actions {action_order}"                
            )

            state = self.scroll_start_state
            if state is None:
                recording_logger.info(
                    "_send_scroll_action: scroll_start_state is None, setting state here."                    
                )
                start_screenshot_path = self._get_latest_screenshots(2)
                mouse_x, mouse_y = pyautogui.position()
                state = EnvState(
                    images=[
                        self.encode_image_to_base64(screenShot)
                        for screenShot in start_screenshot_path
                    ],
                    coordinates=(int(mouse_x), int(mouse_y)),
                )

            # Get the end screenshots
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

            clicks = -int(self.scroll_dy)

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

            # Reset scroll deltas
            self.scroll_dx = 0
            self.scroll_dy = 0
            self.scroll_start_state = None
            self.scroll_timer = None
            recording_logger.info(
                f"_send_scroll_action releasing lock with x,y: {x}, {y}; dx, dy: {self.scroll_dx}, {self.scroll_dy} count of actions {action_order}"                
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
        recording_logger.info("recording text action")
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
            recording_logger.info('record_text_action sending action')
            send_action.delay(
                self._task.id,
                self._task.auth_token,
                self._task.owner_id,
                self._task.to_v1().model_dump(),
                action_event.to_v1().model_dump(),
            )
            recording_logger.info(f"Recorded text action: {self.text_buffer}")

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
                    recording_logger.info(
                        f"Verification failed for {temp_file_path}, "
                        f"attempt {attempt_num + 1}, retry {retry_num + 1}: {e}"                        
                    )
                    time.sleep(delay)  # Small delay before retrying verification

            # If verification failed after retries, remove the temp file and try again
            recording_logger.info(
                f"Verification failed after {max_retries_per_attempt} retries for "
                f"screenshot {temp_file_path}, taking a new screenshot..."                
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
                recording_logger.info(
                    f"Error encoding image {image_path} on attempt {attempt + 1}: {e}"                    
                )
                time.sleep(delay)

        recording_logger.info(
            f"Failed to encode image {image_path} after {max_retries} attempts"            
        )
        return None
