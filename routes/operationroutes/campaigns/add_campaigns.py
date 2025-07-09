# routes/operationroutes/campaigns/add_campaigns.py
import os
import base64
import uuid
import json
import re
import binascii
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from database import Database
from auth import verify_api_key
from utils.logger import generate_log_id, insert_log_entry

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
    """Enhanced input validation to prevent malicious content"""
    regex = re.compile(
        r"(['\";]|--|\b(drop|alter|insert|delete|update|select|union|exec|sleep|waitfor|shutdown)\b)|(<script>)",
        re.IGNORECASE
    )
    return bool(regex.search(value))

def sanitize_input(data: dict):
    """Recursive sanitization check that excludes fileData and description fields"""
    def recursive_check(data_node, path=""):
        if isinstance(data_node, dict):
            for key, value in data_node.items():
                current_path = f"{path}.{key}" if path else key
                if key in {'fileData', 'description'}:  # Skip validation for specific fields
                    continue
                if isinstance(value, str):
                    if is_malicious_input(value):
                        raise HTTPException(status_code=400, detail=f"Invalid input detected in field: {current_path}")
                elif isinstance(value, (dict, list)):
                    recursive_check(value, current_path)
        elif isinstance(data_node, list):
            for idx, item in enumerate(data_node):
                recursive_check(item, f"{path}[{idx}]")
    
    try:
        recursive_check(data)
        return True
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Input validation failed: {str(e)}")

def get_file_extension(mime_type: str) -> str:
    """Get file extension from MIME type with validation"""
    return ALLOWED_MIME_TYPES.get(mime_type.split(';')[0].strip(), None)

async def save_media_files(creatives_data: dict, user_id: str, campaign_id: str) -> dict:
    """Process and save media files to filesystem"""
    if not creatives_data.get("files"):
        return creatives_data

    processed_files = []
    for file in creatives_data["files"]:
        try:
            # Validate file data structure
            if not isinstance(file, dict) or 'fileData' not in file:
                raise ValueError("Invalid file structure")

            file_data = file["fileData"]
            if not file_data.startswith("data:"):
                raise ValueError("Invalid file data format")

            # Split and validate base64 header
            header, _, encoded_data = file_data.partition(",")
            if not header.startswith("data:") or not encoded_data:
                raise ValueError("Malformed data URL")

            # Validate content type and extension
            mime_type = header.split(":")[1].split(";")[0].strip()
            extension = get_file_extension(mime_type)
            if not extension:
                raise ValueError(f"Unsupported file type: {mime_type}")

            # Validate base64 encoding
            try:
                file_bytes = base64.b64decode(encoded_data, validate=True)
            except binascii.Error:
                raise ValueError("Invalid base64 encoding")

            # Create directory structure
            user_dir = os.path.join(UPLOADS_DIR, user_id)
            campaign_dir = os.path.join(user_dir, campaign_id)
            os.makedirs(campaign_dir, exist_ok=True)

            # Generate unique filename
            filename = f"{uuid.uuid4().hex}{extension}"
            file_path = os.path.join(campaign_dir, filename)

            # Save file
            with open(file_path, "wb") as f:
                f.write(file_bytes)

            # Update file entry with relative path
            processed_files.append({
                **file,
                "fileData": f"{user_id}/{campaign_id}/{filename}",
                "filePath": f"/campaignsmedia/{user_id}/{campaign_id}/{filename}"
            })

        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"File processing failed: {str(e)}"
            )

    return {**creatives_data, "files": processed_files}

def process_targeting_data(targeting: dict) -> dict:
    """Process and structure targeting data for insertion"""
    if not targeting:
        return {
            "countrySelections": [],
            "formData": {}
        }
    
    # Extract country selections in the required format
    country_selections = []
    for entry in targeting.get("countrySelections", []):
        country_name = entry.get("selectedCountry", {}).get("country", "")
        if not country_name:
            continue
            
        country_selections.append({
            "country": country_name,
            "includedStates": entry.get("includedStates", []),
            "excludedStates": entry.get("excludedStates", [])
        })
    
    return {
        "countrySelections": country_selections,
        "formData": targeting.get("formData", {})
    }


@router.post("/post_campaign/", dependencies=[Depends(verify_api_key)])
async def post_campaign(request: Request):
    try:
        data = await request.json()
        sanitize_input(data)

        # Extract basic info
        user_id = data.get("user_id", "unknown")
        user_name = data.get("user_name", "Unknown User")
        campaign_id = f"CRB-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:6]}"
        log_id = generate_log_id()

        # Save media files
        creatives = await save_media_files(
            data.get("creatives", {}),
            user_id,
            campaign_id
        )

        # Process targeting data
        targeting_data = process_targeting_data(data.get("targeting", {}))
        targeting_json = json.dumps(targeting_data)

        # Prepare JSON data for new columns
        app_details = json.dumps(data.get("appDetails", {}))
        budget = json.dumps(data.get("budget", {}))
        campaign_details = json.dumps(data.get("campaignDetails", {}))
        conversion_flow = json.dumps(data.get("conversionFlow", {}))
        source_json = json.dumps(data.get("source", {}))
        targeting_json = json.dumps(targeting_data)

        # Prepare DB values
        values = (
            campaign_id,
            data.get("general", {}).get("brandId"),  # brand (brandId)
            data.get("general", {}).get("brandName"),  # brand_name
            app_details,
            campaign_details,
            json.dumps(creatives.get("files", [])),  # creatives remains as-is
            conversion_flow,
            budget,
            targeting_json,
            source_json,
            user_id,
            log_id
        )

        query = """
        INSERT INTO cronbid_campaigns (
            campaign_id, brand, brand_name, app_details, campaign_details,
            creatives, conversion_flow, budget, targeting,
            source, created_by, log_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, values)

                await insert_log_entry(
                    conn=conn,
                    action="create",
                    table_name="cronbid_campaigns",
                    record_id=campaign_id,
                    user_id=user_id,
                    username=user_name,
                    action_description=f"Campaign created with ID {campaign_id}",
                    log_id=log_id
                )

        return {
            "success": True,
            "message": "Campaign created successfully",
            "campaign_id": campaign_id,
            "log_id": log_id
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Campaign creation failed: {str(e)}"
        )