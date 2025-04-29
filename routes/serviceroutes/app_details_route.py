# routes/app_details_route.py
from fastapi import APIRouter, Query
from models.app_details_model import AppDetails
from services.customapis.app_details_services import fetch_app_details

router = APIRouter()

@router.get("", response_model=AppDetails)
async def get_app_details(package_id: str = Query(..., alias="package")):
    return await fetch_app_details(package_id)
