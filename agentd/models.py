from typing import Optional, List

from pydantic import BaseModel


class OpenURLModel(BaseModel):
    url: str


class MoveMouseToModel(BaseModel):
    x: int
    y: int
    duration: float = 1.0
    tween: str = "easeInOutQuad"


class ClickModel(BaseModel):
    button: str = "left"


class TypeTextModel(BaseModel):
    text: str
    min_interval: float = 0.05
    max_interval: float = 0.25


class PressKeyModel(BaseModel):
    key: str


class ScrollModel(BaseModel):
    clicks: int = 3


class DragMouseModel(BaseModel):
    x: int
    y: int


class ScreenshotResponseModel(BaseModel):
    status: str
    image: str
    file_path: str


class CoordinatesModel(BaseModel):
    x: int
    y: int


class RecordRequest(BaseModel):
    description: str


class RecordResponse(BaseModel):
    session_id: str


class ClickData(BaseModel):
    x: int
    y: int
    button: str
    pressed: bool


class KeyData(BaseModel):
    key: str


class ScrollData(BaseModel):
    x: int
    y: int
    dx: int
    dy: int


class RecordedEvent(BaseModel):
    type: str
    timestamp: float
    click_data: Optional[ClickData]
    screenshot_path: str
    key_data: Optional[KeyData]


class Recording(BaseModel):
    id: str
    description: str
    start_time: float
    end_time: float
    events: List[RecordedEvent] = []


class Recordings(BaseModel):
    recordings: List[str]
