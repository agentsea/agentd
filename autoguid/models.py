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
