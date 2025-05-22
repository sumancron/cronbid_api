from pydantic import BaseModel
from typing import Literal


class AppDetails(BaseModel):
    name: str
    icon: str
    description: str
    developer: str
    store_url: str
    os: Literal["android", "ios"]
    device: Literal["mobile", "tablet", "unknown"] = "mobile"
