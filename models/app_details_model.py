# models/app_details_model.py
from pydantic import BaseModel

class AppDetails(BaseModel):
    name: str
    icon: str
    description: str
    developer: str
    store_url: str
