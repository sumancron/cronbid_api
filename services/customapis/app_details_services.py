# services/app_details_service.py

import re
import httpx
from fastapi import HTTPException
from google_play_scraper import app as gp_app
from models.app_details_model import AppDetails


async def fetch_app_details(package_id: str) -> AppDetails:
    gplay_data = None
    ios_data = None

    app_store_id = None

    # Case 1: Input is in the form 'id123456789'
    if package_id.startswith("id") and package_id[2:].isdigit():
        app_store_id = package_id[2:]

    # Attempt to fetch from Google Play (Android) if it's not an App Store ID
    if not app_store_id:
        try:
            gplay_data = gp_app(package_id, lang='en', country='us')
        except Exception:
            pass  # Continue to fallback

    # Attempt to fetch from Apple App Store (iOS)
    async with httpx.AsyncClient() as client:
        try:
            if app_store_id:
                response = await client.get(
                    "https://itunes.apple.com/lookup",
                    params={"id": app_store_id}
                )
            else:
                response = await client.get(
                    "https://itunes.apple.com/lookup",
                    params={"bundleId": package_id}
                )
            results = response.json().get("results", [])
            ios_data = results[0] if results else None
        except Exception:
            pass  # Continue

    # Return Android app if found
    if gplay_data and gplay_data.get("title"):
        return AppDetails(
            name=gplay_data.get("title"),
            icon=gplay_data.get("icon"),
            description=gplay_data.get("description"),
            developer=gplay_data.get("developer"),
            store_url=gplay_data.get("url"),
            os="android",
            device="mobile"
        )

    # Return iOS app if found
    if ios_data and ios_data.get("trackName"):
        return AppDetails(
            name=ios_data.get("trackName"),
            icon=ios_data.get("artworkUrl100"),
            description=ios_data.get("description"),
            developer=ios_data.get("artistName"),
            store_url=ios_data.get("trackViewUrl"),
            os="ios",
            device="mobile"
        )

    # If neither worked
    raise HTTPException(status_code=404, detail="App data unavailable")
