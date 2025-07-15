import httpx
from fastapi import HTTPException
from google_play_scraper import app as gp_app
from models.app_details_model import AppDetails


async def fetch_app_details(package_id: str, country: str = "us", lang: str = "en") -> AppDetails:
    gplay_data = None
    ios_data = None
    app_store_id = None
    fallback_countries = [country.lower(), "us", "in", "gb"]

    # Check if it's an App Store ID like 'id123456789'
    if package_id.startswith("id") and package_id[2:].isdigit():
        app_store_id = package_id[2:]

    # Try Google Play Store (Android) — fallback through country list
    if not app_store_id:
        for c in fallback_countries:
            try:
                gplay_data = gp_app(package_id, lang=lang, country=c)
                if gplay_data.get("title"):
                    break  # Found valid data
            except Exception as e:
                print(f"[Google Play] Error fetching for {package_id} in country={c}: {e}")

    # Try Apple App Store (iOS) — fallback through country list
    async with httpx.AsyncClient() as client:
        for c in fallback_countries:
            try:
                params = {"id": app_store_id, "country": c} if app_store_id else {"bundleId": package_id, "country": c}
                response = await client.get("https://itunes.apple.com/lookup", params=params)
                response.raise_for_status()
                json_data = response.json()
                results = json_data.get("results", [])
                if results:
                    ios_data = results[0]
                    break
                else:
                    print(f"[App Store] Empty results for {package_id} in country={c}")
            except Exception as e:
                print(f"[App Store] Error fetching for {package_id} in country={c}: {e}")

    # Return Android app if found
    if gplay_data and gplay_data.get("title"):
        return AppDetails(
            name=str(gplay_data.get("title")),
            icon=str(gplay_data.get("icon")),
            description=str(gplay_data.get("description")),
            developer=str(gplay_data.get("developer")),
            store_url=str(gplay_data.get("url")),
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

    # If neither source returned valid data
    raise HTTPException(
        status_code=404,
        detail="App data unavailable. The app may not exist, be restricted in your region, or blocked due to IP limits."
    )
