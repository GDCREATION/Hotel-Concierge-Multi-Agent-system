from pydantic import BaseModel, ConfigDict


class GuestContext(BaseModel):
    """Identity supplied by the app. The model is not allowed to fill these fields."""

    model_config = ConfigDict(extra="forbid")

    guest_id: str
    room: str
