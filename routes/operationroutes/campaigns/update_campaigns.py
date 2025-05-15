import os
import base64
import uuid
import json
import re
import traceback
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from database import Database
from auth import verify_api_key
from utils.logger import generate_log_id, insert_log_entry
import aiomysql

router = APIRouter()

UPLOADS_DIR = "uploads/campaignsmedia"
ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov"
}

def is_malicious_input(value: str) -> bool:
    regex = re.compile(
        r"(['\";]|--|\b(drop|alter|insert|delete|update|select|union|exec|sleep|waitfor|shutdown)\b)|(<script>)",
        re.IGNORECASE
    )
    return bool(regex.search(value))

def sanitize_input(data: dict):
    def recursive_check(data_node, path=""):
        if isinstance(data_node, dict):
            for key, value in data_node.items():
                current_path = f"{path}.{key}" if path else key
                if key in {'fileData', 'description'}:
                    continue
                if isinstance(value, str) and is_malicious_input(value):
                    raise HTTPException(status_code=400, detail=f"Invalid input in: {current_path}")
                elif isinstance(value, (dict, list)):
                    recursive_check(value, current_path)
        elif isinstance(data_node, list):
            for idx, item in enumerate(data_node):
                recursive_check(item, f"{path}[{idx}]")
    recursive_check(data)
    return True

def get_file_extension(mime_type: str) -> str:
    return ALLOWED_MIME_TYPES.get(mime_type.split(';')[0].strip())

async def get_existing_campaign(campaign_id: str, conn):
    try:
        query = "SELECT * FROM cronbid_campaigns WHERE campaign_id = %s"
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(query, (campaign_id,))
            result = await cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")
            return result
    except Exception as e:
        print(f"[ERROR] Fetching campaign failed: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error fetching campaign")

async def save_media_files(creatives_data: dict, user_id: str, campaign_id: str, existing_files=None) -> dict:
    if not creatives_data.get("files"):
        return creatives_data

    processed_files = existing_files or []
    new_files = []

    for file in creatives_data["files"]:
        if "filePath" in file and not file.get("fileData", "").startswith("data:"):
            processed_files.append(file)
            continue

        try:
            if not isinstance(file, dict) or 'fileData' not in file:
                raise ValueError("Invalid file structure")

            file_data = file["fileData"]
            header, _, encoded_data = file_data.partition(",")
            mime_type = header.split(":")[1].split(";")[0].strip()
            extension = get_file_extension(mime_type)
            if not extension:
                raise ValueError(f"Unsupported file type: {mime_type}")

            file_bytes = base64.b64decode(encoded_data, validate=True)

            campaign_dir = os.path.join(UPLOADS_DIR, user_id, campaign_id)
            os.makedirs(campaign_dir, exist_ok=True)

            filename = f"{uuid.uuid4().hex}{extension}"
            file_path = os.path.join(campaign_dir, filename)

            with open(file_path, "wb") as f:
                f.write(file_bytes)

            processed_file = {
                **file,
                "fileData": f"{user_id}/{campaign_id}/{filename}",
                "filePath": f"/campaignsmedia/{user_id}/{campaign_id}/{filename}"
            }
            new_files.append(processed_file)

        except Exception as e:
            print(f"[ERROR] Media file save failed: {str(e)}")
            traceback.print_exc()
            raise HTTPException(status_code=400, detail=f"Media file save error: {str(e)}")

    return {**creatives_data, "files": processed_files + new_files}

def process_targeting_data(targeting: dict) -> list:
    processed = []
    if isinstance(targeting, list):
        return targeting

    if not targeting or not isinstance(targeting, dict):
        return processed

    country_selections = targeting
    if not isinstance(country_selections, list):
        return processed

    for entry in country_selections:
        if not isinstance(entry, dict):
            continue
        country_data = {
            "country": entry.get("selectedCountry", {}).get("country", ""),
            "includedStates": [s for s in entry.get("includedStates", []) if isinstance(s, str)],
            "excludedStates": [s for s in entry.get("excludedStates", []) if isinstance(s, str)]
        }
        if country_data["country"]:
            processed.append(country_data)

    return processed

@router.put("/update_campaign/{campaign_id}", dependencies=[Depends(verify_api_key)])
async def update_campaign(campaign_id: str, request: Request):
    try:
        # 1) Read & sanitize
        data = await request.json()
        sanitize_input(data)

        # 2) Identify user & log
        user_id   = data.get("user_id", "unknown")
        user_name = data.get("user_name", "Unknown User")
        log_id    = generate_log_id()

        # 3) Connect & fetch existing
        pool = await Database.connect()
        async with pool.acquire() as conn:
            existing = await get_existing_campaign(campaign_id, conn)
            old_creatives = json.loads(existing.get("creatives", "[]"))

            # 4) Save any new media
            creatives = await save_media_files(
                data.get("creatives", {}),
                user_id,
                campaign_id,
                old_creatives
            )

            # 5) Re‑process targeting
            targeting_data = process_targeting_data(data.get("targeting", {}))

            # 6) Build the full `source` JSON
            source_json = json.dumps(data.get("source", {}))

            # 7) Prepare all fields to update
            to_update = {
                "brand":           data["general"].get("brandId"),
                "app_package_id":  data["appDetails"].get("packageId"),
                "app_name":        data["appDetails"].get("appName"),
                "preview_url":     data["appDetails"].get("previewUrl"),
                "description":     data["appDetails"].get("description"),
                "category":        data["campaignDetails"].get("category"),
                "campaign_title":  data["campaignDetails"].get("campaignTitle"),
                "kpis":            data["campaignDetails"].get("kpis"),
                "mmp":             data["campaignDetails"].get("mmp"),
                "click_url":       data["campaignDetails"].get("clickUrl"),
                "impression_url":  data["campaignDetails"].get("impressionUrl"),
                "deeplink":        data["campaignDetails"].get("deeplink"),
                "creatives":       json.dumps(creatives.get("files", [])),
                "events":          json.dumps(data["conversionFlow"].get("events", [])),
                "payable":         int(bool(data["conversionFlow"].get("selectedPayable"))),
                "event_amount":    data["conversionFlow"].get("amount", 0),
                "campaign_budget": data["budget"].get("campaignBudget", 0),
                "daily_budget":    data["budget"].get("dailyBudget", 0),
                "monthly_budget":  data["budget"].get("monthlyBudget", 0),
                "targeting":       json.dumps(targeting_data),
                "source":          source_json,
                "created_by":      user_id,
                "updated_at":      datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "log_id":          log_id
            }

            # 8) Build & execute the UPDATE
            cols = ", ".join(f"{col} = %s" for col in to_update)
            sql  = f"UPDATE cronbid_campaigns SET {cols} WHERE campaign_id = %s"
            params = list(to_update.values()) + [campaign_id]

            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                await insert_log_entry(
                    conn,
                    action="update",
                    table_name="cronbid_campaigns",
                    record_id=campaign_id,
                    user_id=user_id,
                    username=user_name,
                    action_description=f"Updated campaign {campaign_id}",
                    log_id=log_id
                )

        return {
            "success":     True,
            "message":     "Campaign updated successfully",
            "campaign_id": campaign_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error during campaign update: {e}"
        )