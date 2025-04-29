# services/app_details_service.py
import httpx
from fastapi import HTTPException
from google_play_scraper import app as gp_app
from models.app_details_model import AppDetails

async def fetch_app_details(package_id: str) -> AppDetails:
    # Android (Play Store)
    try:
        gplay = gp_app(package_id, lang='en', country='us')
    except Exception:
        gplay = None  # fallback to iOS

    # iOS (App Store)
    itunes_data = []
    async with httpx.AsyncClient() as client:
        try:
            itunes_resp = await client.get(
                "https://itunes.apple.com/lookup",
                params={"bundleId": package_id}
            )
            itunes_data = itunes_resp.json().get("results", [])
        except Exception:
            itunes_data = []

    # Choose source (Android preferred, fallback iOS)
    source = gplay if gplay and gplay.get("title") else (itunes_data[0] if itunes_data else None)
    if not source:
        raise HTTPException(status_code=404, detail="App data unavailable")

    return AppDetails(
        name=source.get("title") or source.get("trackName"),
        icon=source.get("icon") or source.get("artworkUrl100"),
        description=source.get("description"),
        developer=source.get("developer") or source.get("artistName"),
        store_url=source.get("url") or source.get("trackViewUrl")
    )
