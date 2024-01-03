import time
import random
import os
from datetime import datetime
import base64

from fastapi import FastAPI, HTTPException
import pyautogui

from .models import (
    MoveMouseToModel,
    ClickModel,
    TypeTextModel,
    PressKeyModel,
    ScrollModel,
    DragMouseModel,
    ScreenshotResponseModel,
    OpenURLModel,
)
from .chromium import is_chromium_running, is_chromium_window_open

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Welcome to autoguid!"}


@app.get("/health")
async def health():
    return {"status": "ok"}


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

        # Take the screenshot and save it
        pyautogui.screenshot(file_path)

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
