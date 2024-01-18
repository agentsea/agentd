import time
import random
import os
from datetime import datetime
import base64
import uuid

from fastapi import FastAPI, HTTPException
import pyautogui
from mss import mss

from .models import (
    MoveMouseToModel,
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
)
from .chromium import is_chromium_running, is_chromium_window_open
from .recording import RecordingSession, lock, sessions

# from .storage import upload_directory_to_gcs

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Agent in the shell"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/mouse_coordinates")
async def mouse_coordinates() -> CoordinatesModel:
    x, y = pyautogui.position()
    return CoordinatesModel(x=x, y=y)


@app.post("/open_url")
async def open_url(request: OpenURLModel):
    try:
        if is_chromium_running():
            print("Chromium is running. Restarting it...")
            os.system("pkill chrome")
            time.sleep(5)
        else:
            print("Chromium is not running. Starting it...")

        os.system(f'chromium-browser --kiosk --no-first-run "{request.url}" &')

        while not is_chromium_window_open():
            time.sleep(1)
            print("chrome window not open yet...")

        time.sleep(5)
        return {"status": "success"}

    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/move_mouse_to")
async def move_mouse_to(request: MoveMouseToModel):
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
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            return session.as_schema()
    else:
        return RecordingSession.load(session_id).as_schema()


@app.get("/recordings/{session_id}/event/{event_id}", response_model=RecordedEvent)
async def get_event(session_id: str, event_id: str):
    if session_id in sessions:
        with lock:
            session: RecordingSession = sessions.get(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

    else:
        session: RecordingSession = RecordingSession.load(session_id)

    event = session.find_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


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
