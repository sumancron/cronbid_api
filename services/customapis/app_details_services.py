# services/app_details_service.py

import httpx
from fastapi import HTTPException
from google_play_scraper import app as gp_app
from models.app_details_model import AppDetails


async def fetch_app_details(package_id: str) -> AppDetails:
    gplay_data = None
    ios_data = None
    app_store_id = None

    # Check if it's an App Store ID like 'id123456789'
    if package_id.startswith("id") and package_id[2:].isdigit():
        app_store_id = package_id[2:]

    # Try fetching from Google Play Store (Android)
    if not app_store_id:
        try:
            gplay_data = gp_app(package_id, lang='en', country='us')
        except Exception as e:
            print(f"[Google Play] Error fetching data for {package_id}: {e}")

    # Try fetching from Apple App Store (iOS)
    async with httpx.AsyncClient() as client:
        try:
            params = {"id": app_store_id} if app_store_id else {"bundleId": package_id}
            response = await client.get("https://itunes.apple.com/lookup", params=params)
            response.raise_for_status()
            json_data = response.json()
            results = json_data.get("results", [])
            if not results:
                print(f"[App Store] Empty results for package_id: {package_id}")
                print(f"[App Store] Full response: {json_data}")
            ios_data = results[0] if results else None
        except Exception as e:
            print(f"[App Store] Error fetching data for {package_id}: {e}")

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

    # Neither store returned data
    raise HTTPException(status_code=404, detail="App data unavailable. It may not exist or is restricted for your IP.")
