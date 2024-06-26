from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel


class OpenURLModel(BaseModel):
    url: str


class ScreenSizeModel(BaseModel):
    x: int
    y: int


class SystemInfoModel(BaseModel):
    last_activity_ts: int | None
    screen_size: ScreenSizeModel
    os_info: str
    code_version: str | None


class MoveMouseModel(BaseModel):
    x: int
    y: int
    duration: float = 1.0
    tween: str = "easeInOutQuad"


class ClickModel(BaseModel):
    button: str = "left"
    location: Optional[MoveMouseModel] = None


class TypeTextModel(BaseModel):
    text: str
    min_interval: float = 0.05
    max_interval: float = 0.25


class PressKeyModel(BaseModel):
    key: str


class PressKeysModel(BaseModel):
    keys: List[str]


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
    button: str
    pressed: bool


class KeyData(BaseModel):
    key: str


class TextData(BaseModel):
    text: str


class ScrollData(BaseModel):
    dx: int
    dy: int


class RecordedEvent(BaseModel):
    id: str
    type: str
    timestamp: float
    coordinates: CoordinatesModel
    screenshot_path: Optional[str] = None
    screenshot_b64: Optional[str] = None
    click_data: Optional[ClickData] = None
    key_data: Optional[KeyData] = None
    scroll_data: Optional[ScrollData] = None
    text_data: Optional[TextData] = None


class Recording(BaseModel):
    id: str
    description: str
    start_time: float
    end_time: float
    events: List[RecordedEvent] = []


class Recordings(BaseModel):
    recordings: List[str]


class Actions(BaseModel):
    actions: List[Dict[str, Any]]


class SystemUsageModel(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
