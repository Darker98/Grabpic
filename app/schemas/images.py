from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ImageItem(BaseModel):
    image_id: str
    url: str
    expires_at: datetime
    taken_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ImageListResponse(BaseModel):
    grab_id: str
    total: int
    page: int
    images: list[ImageItem]

    model_config = ConfigDict(from_attributes=True)
