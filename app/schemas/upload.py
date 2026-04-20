from pydantic import BaseModel, ConfigDict


class UploadResponse(BaseModel):
    accepted: int
    job_ids: list[str]

    model_config = ConfigDict(from_attributes=True)
