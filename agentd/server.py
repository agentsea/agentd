import time
import random
import os
from datetime import datetime
import base64
import uuid
import logging
import subprocess
import sys
import tempfile
import platform

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

import pyautogui
from mss import mss
import psutil

from .models import (
    MoveMouseModel,
    ClickModel,
    TypeTextModel,
    PressKeyModel,
    ScrollModel,
    DragMouseModel,
    ScreenshotResponseModel,
    OpenURLModel,
    CoordinatesModel,
    Recording,
    RecordResponse,
    Recordings,
    RecordRequest,
    RecordedEvent,
    Actions,
    SystemUsageModel,
    SystemInfoModel,
    ScreenSizeModel,
)
from .chromium import (
    is_chromium_running,
    is_chromium_window_open,
    gracefully_terminate_chromium,
)
from .recording import RecordingSession, lock, sessions

app = FastAPI()

logging.basicConfig(
    filename="audit.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log the request details
    logging.info(f"Method: {request.method} Path: {request.url.path}")
    response = await call_next(request)
    return response


@app.get("/")
async def root():
    return {"message": "Agent in the shell"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/info", response_model=SystemInfoModel)
async def get_info():
    # Screen size
    width, height = pyautogui.size()
    screen_size = ScreenSizeModel(x=width, y=height)

    # OS Info
    os_info = f"{platform.system()} {platform.release()}"

    # Code Version (Git)
    try:
        code_version = (
            subprocess.check_output(["git", "rev-parse", "HEAD"])
            .decode("utf-8")
            .strip()
        )
    except Exception as e:
        code_version = None

    # Last Activity from log
    try:
        with open("audit.log", "r") as f:
            lines = f.readlines()
            last_activity_unix = None
            if lines:
                last_line = lines[-1]
                last_activity_str = last_line.split(" - ")[0]
                last_activity_datetime = datetime.strptime(
                    last_activity_str, "%Y-%m-%d %H:%M:%S"
                )
                last_activity_unix = int(
                    time.mktime(last_activity_datetime.timetuple())
                )
    except Exception as e:
        last_activity_unix = None

    return SystemInfoModel(
        last_activity_ts=last_activity_unix,
        screen_size=screen_size,
        os_info=os_info,
        code_version=code_version,
    )


@app.get("/screen_size")
def get_screen_size() -> ScreenSizeModel:
    width, height = pyautogui.size()
    return ScreenSizeModel(x=width, y=height)


@app.get("/mouse_coordinates")
async def mouse_coordinates() -> CoordinatesModel:
    x, y = pyautogui.position()
    return CoordinatesModel(x=x, y=y)


@app.post("/open_url")
async def open_url(request: OpenURLModel):
    try:
        chromium_pids = is_chromium_running()
        if chromium_pids:
            print("Chromium is running. Restarting it...")
            gracefully_terminate_chromium(chromium_pids)
            time.sleep(5)

        user_data_dir = tempfile.mkdtemp()  # TODO: this is a hack to prevent corruption

        print("Starting Chromium...")
        subprocess.Popen(
            [
                "chromium",
                "--no-first-run",
                "--start-fullscreen",
                "--user-data-dir=" + user_data_dir,
                request.url,
            ],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        while not is_chromium_window_open():
            time.sleep(1)
            print("Waiting for the Chromium window to open...")

        time.sleep(5)
        return {"status": "success"}

    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/move_mouse")
async def move_mouse_to(request: MoveMouseModel):
    try:
        tween_func = getattr(pyautogui, request.tween, pyautogui.linear)
        pyautogui.moveTo(
            request.x, request.y, duration=request.duration, tween=tween_func
        )
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/click")
async def click(request: ClickModel):
    if request.location:
        tween_func = getattr(pyautogui, request.location.tween, pyautogui.linear)
        pyautogui.moveTo(
            request.location.x,
            request.location.y,
            duration=request.location.duration,
            tween=tween_func,
        )
    try:
        pyautogui.click(button=request.button)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/double_click")
async def double_click():
    try:
        pyautogui.doubleClick()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/type_text")
async def type_text(request: TypeTextModel):
    try:
        for char in request.text:
            pyautogui.write(
                char,
                interval=random.uniform(request.min_interval, request.max_interval),
            )
            time.sleep(random.uniform(request.min_interval, request.max_interval))
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/press_key")
async def press_key(request: PressKeyModel):
    try:
        pyautogui.press(request.key)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scroll")
async def scroll(request: ScrollModel):
    try:
        pyautogui.scroll(request.clicks)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/drag_mouse")
async def drag_mouse(request: DragMouseModel):
    try:
        pyautogui.dragTo(request.x, request.y)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/screenshot", response_model=ScreenshotResponseModel)
async def take_screenshot() -> ScreenshotResponseModel:
    try:
        # Create a directory for screenshots if it doesn't exist
        screenshots_dir = "screenshots"
        os.makedirs(screenshots_dir, exist_ok=True)

        # Generate a unique file name based on the current timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(screenshots_dir, f"screenshot_{timestamp}.png")

        with mss(with_cursor=True) as sct:
            # Save to the picture file
            sct.shot(output=file_path)

        # Read and encode the image
        with open(file_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

        # Return the encoded image and the file path
        response = ScreenshotResponseModel(
            status="success", image=encoded_image, file_path=file_path
        )

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recordings", response_model=RecordResponse)
async def start_recording(request: RecordRequest):
    session_id = str(uuid.uuid4())
    with lock:
        session = RecordingSession(session_id, request.description)
        sessions[session_id] = session
        session.start()
    return RecordResponse(session_id=session_id)


@app.get("/recordings", response_model=Recordings)
async def list_recordings():
    out = await RecordingSession.list_recordings()
    return Recordings(recordings=out)


@app.post("/recordings/{session_id}/stop")
async def stop_recording(session_id: str):
    with lock:
        session: RecordingSession = sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session.stop()
        path = session.save_to_file()
        print("Saved recording to file:", path)

        # print("uploading to gcs")
        # bucket_name = "agentdesk-temp"
        # destination_blob_prefix = f"recordings/{session_id}"
        # upload_directory_to_gcs(bucket_name, session._dir(), destination_blob_prefix)

        del sessions[session_id]
    return


@app.get("/recordings/{session_id}", response_model=Recording)
async def get_recording(session_id: str):
    if session_id in sessions:
        with lock:
            session: RecordingSession = sessions.get(session_id)
            print("got in-mem session: ", session)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            return session.as_schema()
    else:
        session = RecordingSession.load(session_id).as_schema()
        print("got disk session: ", session)
        return session


@app.get("/recordings/{session_id}/event/{event_id}", response_model=RecordedEvent)
async def get_event(session_id: str, event_id: str):
    if session_id in sessions:
        with lock:
            session: RecordingSession = sessions.get(session_id)
            print("got in-mem session: ", session)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

    else:
        session: RecordingSession = RecordingSession.load(session_id)
        print("got disk session: ", session)

    event = session.find_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.delete("/recordings/{session_id}/event/{event_id}", response_model=Recording)
async def delete_event(session_id: str, event_id: str):
    if session_id in sessions:
        with lock:
            # Retrieve the session
            session: RecordingSession = sessions.get(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            # Delete the event from the session
            session.delete_event(event_id)

            return session.as_schema()

    else:
        session = RecordingSession.load(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Delete the event from the session
        session.delete_event(event_id)
        session.save_to_file()

        return session.as_schema()


@app.get("/active_sessions", response_model=Recordings)
async def list_sessions():
    out = []
    for id, _ in sessions.items():
        out.append(id)

    return Recordings(recordings=out)


@app.get("/recordings/{session_id}/actions", response_model=Actions)
async def get_actions(session_id: str):
    if session_id in sessions:
        with lock:
            session: RecordingSession = sessions.get(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

    else:
        session = RecordingSession.load(session_id)

    return Actions(actions=session.as_actions())


@app.get("/system_usage", response_model=SystemUsageModel)
async def system_usage():
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return SystemUsageModel(
        cpu_percent=cpu_percent,
        memory_percent=memory.percent,
        disk_percent=disk.percent,
    )
