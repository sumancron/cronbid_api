# services/app_details_service.py

import httpx
from fastapi import HTTPException
from google_play_scraper import app as gp_app
from models.app_details_model import AppDetails


async def fetch_app_details(package_id: str) -> AppDetails:
    gplay_data = None
    ios_data = None

    # Attempt to fetch from Google Play (Android)
    try:
        gplay_data = gp_app(package_id, lang='en', country='us')
    except Exception:
        pass  # Continue to fallback

    # Attempt to fetch from Apple App Store (iOS)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://itunes.apple.com/lookup",
                params={"bundleId": package_id}
            )
            results = response.json().get("results", [])
            ios_data = results[0] if results else None
        except Exception:
            pass  # Continue

    # Determine which store provided valid data
    if gplay_data and gplay_data.get("title"):
        return AppDetails(
            name=gplay_data.get("title"),
            icon=gplay_data.get("icon"),
            description=gplay_data.get("description"),
            developer=gplay_data.get("developer"),
            store_url=gplay_data.get("url"),
            os="android",
            device="mobile"  # Default assumption, can improve with more logic
        )

    if ios_data and ios_data.get("trackName"):
        return AppDetails(
            name=ios_data.get("trackName"),
            icon=ios_data.get("artworkUrl100"),
            description=ios_data.get("description"),
            developer=ios_data.get("artistName"),
            store_url=ios_data.get("trackViewUrl"),
            os="ios",
            device="mobile"  # Default assumption, can improve with more logic
        )

    # If neither worked
    raise HTTPException(status_code=404, detail="App data unavailable")
