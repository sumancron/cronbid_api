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
        print(f"[DEBUG] Updating campaign: {campaign_id}")
        data = await request.json()
        print(f"[DEBUG] Payload received: {json.dumps(data, indent=2)}")

        sanitize_input(data)
        user_id = data.get("user_id", "unknown")
        user_name = data.get("user_name", "Unknown User")
        log_id = generate_log_id()

        pool = await Database.connect()
        async with pool.acquire() as conn:
            existing_campaign = await get_existing_campaign(campaign_id, conn)
            existing_creatives = json.loads(existing_campaign.get("creatives", "[]"))

            creatives = await save_media_files(
                data.get("creatives", {}),
                user_id,
                campaign_id,
                existing_creatives
            )

            targeting_data = process_targeting_data(data.get("targeting", []))

            values = {
                "brand": data.get("general", {}).get("brandId"),
                "app_package_id": data.get("appDetails", {}).get("packageId"),
                "app_name": data.get("appDetails", {}).get("appName"),
                "preview_url": data.get("appDetails", {}).get("previewUrl"),
                "description": data.get("appDetails", {}).get("description"),
                "category": data.get("campaignDetails", {}).get("category"),
                "campaign_title": data.get("campaignDetails", {}).get("campaignTitle"),
                "kpis": data.get("campaignDetails", {}).get("kpis"),
                "mmp": data.get("campaignDetails", {}).get("mmp"),
                "click_url": data.get("campaignDetails", {}).get("clickUrl"),
                "impression_url": data.get("campaignDetails", {}).get("impressionUrl"),
                "deeplink": data.get("campaignDetails", {}).get("deeplink"),
                "creatives": json.dumps(creatives.get("files", [])),
                "events": json.dumps(data.get("conversionFlow", {}).get("events", [])),
                "payable": 1 if data.get("conversionFlow", {}).get("selectedPayable") else 0,
                "event_amount": data.get("conversionFlow", {}).get("amount", 0),
                "campaign_budget": data.get("budget", {}).get("campaignBudget", 0),
                "daily_budget": data.get("budget", {}).get("dailyBudget", 0),
                "monthly_budget": data.get("budget", {}).get("monthlyBudget", 0),
                "targeting": json.dumps(targeting_data),
                "programmatic": 1 if data.get("source", {}).get("programmaticEnabled") else 0,
                "core_partners": json.dumps(data.get("source", {}).get("selectedApps", {})),
                "direct_apps": 1 if data.get("source", {}).get("expandedCategories", {}).get("directApps") else 0,
                "oems": 1 if data.get("source", {}).get("expandedCategories", {}).get("oem") else 0,
                "created_by": user_id,
                "created_at": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                "log_id": log_id
            }

            set_clause = ", ".join([f"{k} = %s" for k in values])
            query = f"UPDATE cronbid_campaigns SET {set_clause} WHERE campaign_id = %s"

            print(f"[DEBUG] SQL Query: {query}")
            print(f"[DEBUG] SQL Params: {list(values.values()) + [campaign_id]}")

            async with conn.cursor() as cur:
                await cur.execute(query, list(values.values()) + [campaign_id])
                await insert_log_entry(
                    conn=conn,
                    action="update",
                    table_name="cronbid_campaigns",
                    record_id=campaign_id,
                    user_id=user_id,
                    username=user_name,
                    action_description=f"Updated campaign {campaign_id}",
                    log_id=log_id
                )

        return {
            "success": True,
            "message": "Campaign updated successfully",
            "campaign_id": campaign_id
        }

    except HTTPException as he:
        print(f"[HTTP ERROR] {he.detail}")
        raise he
    except Exception as e:
        print(f"[UNEXPECTED ERROR] {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error during campaign update")
