from typing import Any, Dict, List, Optional

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
    images: List[str]


class CoordinatesModel(BaseModel):
    x: int
    y: int


class RecordRequest(BaseModel):
    description: Optional[str] = None
    task_id: Optional[str] = None
    token: str
    server_address: str
    owner_id: str

class StopRequest(BaseModel):
    result: Optional[str] = None
    comment: Optional[str] = None


class RecordResponse(BaseModel):
    task_id: str


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
    before_screenshot_path: Optional[str] = None
    after_screenshot_path: Optional[str] = None
    before_screenshot_b64: Optional[str] = None
    after_screenshot_b64: Optional[str] = None
    click_data: Optional[ClickData] = None
    key_data: Optional[KeyData] = None
    scroll_data: Optional[ScrollData] = None
    text_data: Optional[TextData] = None


class Recording(BaseModel):
    id: str
    description: Optional[str] = None
    start_time: float
    end_time: float
    events: List[RecordedEvent] = []
    task_id: str


class Recordings(BaseModel):
    recordings: List[str]


class Actions(BaseModel):
    actions: List[Dict[str, Any]]


class SystemUsageModel(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
