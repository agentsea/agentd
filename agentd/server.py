import base64
import logging
import os
import platform
import random
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from typing import Optional
import threading

import psutil
import pyautogui
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from mss import mss
from pydantic import BaseModel
from fastapi.responses import FileResponse


from .firefox import (
    gracefully_terminate_firefox,
    is_firefox_running,
    is_firefox_window_open,
    maximize_firefox_window
)
from .models import (
    Actions,
    ClickModel,
    CoordinatesModel,
    DragMouseModel,
    MoveMouseModel,
    OpenURLModel,
    PressKeyModel,
    PressKeysModel,
    RecordedEvent,
    Recording,
    Recordings,
    RecordRequest,
    RecordResponse,
    ScreenshotResponseModel,
    ScreenSizeModel,
    ScrollModel,
    SystemInfoModel,
    SystemUsageModel,
    TypeTextModel,
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
    except Exception:
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
    except Exception:
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
    return CoordinatesModel(x=x, y=y)  # type: ignore


@app.post("/open_url")
async def open_url(request: OpenURLModel):
    try:
        firefox_pids = is_firefox_running()
        if firefox_pids:
            print("Firefox is running. Restarting it...")
            gracefully_terminate_firefox(firefox_pids)
            time.sleep(5)

        print("Starting Firefox...")
        subprocess.Popen(
            [
                "firefox",
                request.url,
            ],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        while not is_firefox_window_open():
            time.sleep(1)
            print("Waiting for the Firefox window to open...")

        maximize_firefox_window()

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


@app.post("/hot_key")
async def hot_key(request: PressKeysModel):
    try:
        pyautogui.hotkey(*request.keys)
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
        session: Optional[RecordingSession] = sessions.get(session_id)
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
            session: Optional[RecordingSession] = sessions.get(session_id)
            print("got in-mem session: ", session)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            return session.as_schema()
    else:
        rec_session = RecordingSession.load(session_id).as_schema()
        print("got disk session: ", rec_session)
        return rec_session


@app.get("/recordings/{session_id}/event/{event_id}", response_model=RecordedEvent)
async def get_event(session_id: str, event_id: str):
    if session_id in sessions:
        with lock:
            rec_session: Optional[RecordingSession] = sessions.get(session_id)  # type: ignore
            print("got in-mem session: ", rec_session)
            if not rec_session:
                raise HTTPException(status_code=404, detail="Session not found")

    else:
        rec_session: RecordingSession = RecordingSession.load(session_id)
        print("got disk session: ", rec_session)

    event = rec_session.find_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.delete("/recordings/{session_id}/event/{event_id}", response_model=Recording)
async def delete_event(session_id: str, event_id: str):
    if session_id in sessions:
        with lock:
            # Retrieve the session
            session: Optional[RecordingSession] = sessions.get(session_id)
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
            session: Optional[RecordingSession] = sessions.get(session_id)
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

##
### Recording
##

video_recording_process = None
video_recording_lock = threading.Lock()
video_recordings_dir = "video_recordings"
os.makedirs(video_recordings_dir, exist_ok=True)


class VideoRecordRequest(BaseModel):
    framerate: int

class VideoRecordResponse(BaseModel):
    session_id: str

class VideoRecordings(BaseModel):
    recordings: list[str]

class VideoRecordModel(BaseModel):
    status: str
    file_path: str


@app.post("/start_video_recording", response_model=VideoRecordResponse)
async def start_video_recording(request: VideoRecordRequest):
    global video_recording_process
    with video_recording_lock:
        if video_recording_process is not None:
            raise HTTPException(status_code=400, detail="Video recording is already in progress.")
        
        session_id = str(uuid.uuid4())
        file_path = os.path.join(video_recordings_dir, f"{session_id}.mp4")

        video_recording_process = subprocess.Popen([
            "ffmpeg", "-video_size", "1920x1080", "-framerate", f"{request.framerate}", "-f", "x11grab",
            "-i", ":0.0", file_path
        ])

    return VideoRecordResponse(session_id=session_id)


@app.post("/stop_video_recording", response_model=VideoRecordModel)
async def stop_video_recording():
    global video_recording_process
    with video_recording_lock:
        if video_recording_process is None:
            raise HTTPException(status_code=400, detail="No video recording in progress.")
        
        video_recording_process.terminate()
        video_recording_process = None

        session_id = str(uuid.uuid4())
        file_path = os.path.join(video_recordings_dir, f"{session_id}.mp4")

    return VideoRecordModel(status="success", file_path=file_path)


@app.get("/video_recordings", response_model=VideoRecordings)
async def list_video_recordings():
    recordings = os.listdir(video_recordings_dir)
    return VideoRecordings(recordings=recordings)


@app.get("/video_recordings/{session_id}", response_class=FileResponse)
async def get_video_recording(session_id: str):
    file_path = os.path.join(video_recordings_dir, f"{session_id}.mp4")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Recording not found.")
    
    return FileResponse(file_path, media_type="video/mp4", filename=f"{session_id}.mp4")


@app.delete("/video_recordings/{session_id}", response_model=VideoRecordModel)
async def delete_video_recording(session_id: str):
    file_path = os.path.join(video_recordings_dir, f"{session_id}.mp4")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Recording not found.")
    
    os.remove(file_path)
    return VideoRecordModel(status="success", file_path=file_path)