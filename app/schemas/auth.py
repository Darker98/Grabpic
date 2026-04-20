from pydantic import BaseModel, ConfigDict


class SelfieResponse(BaseModel):
    token: str
    expires_in: int
    match_confidence: float

    model_config = ConfigDict(from_attributes=True)
