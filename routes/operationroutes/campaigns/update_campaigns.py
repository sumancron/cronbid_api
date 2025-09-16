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
from routes.operationroutes.campaigns.add_campaigns import get_file_extension
from utils.logger import generate_log_id, insert_log_entry
import aiomysql

router = APIRouter()

UPLOADS_DIR = "uploads/campaignsmedia"
ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "text/csv": ".csv"
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

def delete_media_file(file_path: str, user_id: str, campaign_id: str, subdir: str = ""):
    """Delete a media file from the filesystem"""
    try:
        # Extract filename from file path
        base_path = f"/campaignsmedia/{user_id}/{campaign_id}/"
        if subdir:
            base_path += f"{subdir}/"
        
        if file_path.startswith(base_path):
            filename = file_path.split("/")[-1]
            full_path = os.path.join(UPLOADS_DIR, user_id, campaign_id, subdir, filename)
            if os.path.exists(full_path):
                os.remove(full_path)
                print(f"[INFO] Deleted file: {full_path}")
            else:
                print(f"[WARNING] File not found for deletion: {full_path}")
    except Exception as e:
        print(f"[WARNING] Failed to delete file {file_path}: {str(e)}")

async def save_media_files(creatives_data: dict, user_id: str, campaign_id: str, existing_files=None, subdir: str = "") -> dict:
    """Handle media files with support for additions and deletions"""
    if not creatives_data or "files" not in creatives_data:
        # If no creatives data provided, return existing files
        return {"files": existing_files or []}

    existing_files = existing_files or []
    new_files_list = creatives_data["files"]
    
    # Track which existing files are still present
    existing_file_paths = {file.get("filePath") for file in existing_files if file.get("filePath")}
    new_file_paths = {file.get("filePath") for file in new_files_list if file.get("filePath") and not file.get("fileData", "").startswith("data:")}
    
    # Find files to delete (existing files not present in new list)
    files_to_delete = existing_file_paths - new_file_paths
    
    # Delete removed files from filesystem
    for file_path in files_to_delete:
        delete_media_file(file_path, user_id, campaign_id, subdir)
    
    processed_files = []
    
    for file in new_files_list:
        # If file has filePath and no new fileData, it's an existing file to keep
        if "filePath" in file and not file.get("fileData", "").startswith("data:"):
            processed_files.append(file)
            continue

        # Only process files with new base64 data
        if not file.get("fileData", "").startswith("data:"):
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
            if subdir:
                campaign_dir = os.path.join(campaign_dir, subdir)
            os.makedirs(campaign_dir, exist_ok=True)

            filename = f"{uuid.uuid4().hex}{extension}"
            file_path = os.path.join(campaign_dir, filename)

            with open(file_path, "wb") as f:
                f.write(file_bytes)

            processed_file_path = os.path.join(user_id, campaign_id, subdir, filename) if subdir else os.path.join(user_id, campaign_id, filename)
            processed_file = {
                **file,
                "fileData": processed_file_path,
                "filePath": f"/campaignsmedia/{processed_file_path}"
            }
            processed_files.append(processed_file)

        except Exception as e:
            print(f"[ERROR] Media file save failed: {str(e)}")
            traceback.print_exc()
            raise HTTPException(status_code=400, detail=f"Media file save error: {str(e)}")

    return {"files": processed_files}

def process_targeting_data(targeting: dict, existing_targeting=None) -> dict:
    """Process targeting data into the new unified format"""
    if not targeting:
        return existing_targeting or {
            "countrySelections": [],
            "formData": {},
            "audienceTargeting": {},
        }
    
    country_selections = []
    for entry in targeting.get("countrySelections", []):
        country_name = entry.get("selectedCountry", "")
        if not country_name:
            continue
            
        country_selections.append({
            "country": country_name,
            "includedStates": entry.get("includedStates", []),
            "excludedStates": entry.get("excludedStates", [])
        })
    
    form_data = targeting.get("formData", existing_targeting.get("formData", {}) 
                             if existing_targeting else {})
    
    audience_targeting_data = targeting.get("audienceTargeting", existing_targeting.get("audienceTargeting", {}) 
                                           if existing_targeting else {})
    
    processed_countries = []
    
    if isinstance(country_selections, list) and country_selections:
        if all(isinstance(item, dict) and "country" in item for item in country_selections):
            processed_countries = country_selections
    
    elif isinstance(country_selections, dict):
        selected_countries = country_selections.get("selectedCountries", [])
        included_states = country_selections.get("includedStates", [])
        excluded_states = country_selections.get("excludedStates", [])

        if selected_countries:
            country_states = {}
            for country in selected_countries:
                country_states[country] = {
                    "includedStates": [],
                    "excludedStates": []
                }

            for state_info in included_states:
                if isinstance(state_info, dict) and "country" in state_info and "state" in state_info:
                    country = state_info["country"]
                    if country in country_states:
                        country_states[country]["includedStates"].append(state_info["state"])

            for state_info in excluded_states:
                if isinstance(state_info, dict) and "country" in state_info and "state" in state_info:
                    country = state_info["country"]
                    if country in country_states:
                        country_states[country]["excludedStates"].append(state_info["state"])

            for country in selected_countries:
                processed_countries.append({
                    "country": country,
                    "includedStates": country_states[country]["includedStates"],
                    "excludedStates": country_states[country]["excludedStates"]
                })

    if not processed_countries and existing_targeting:
        processed_countries = existing_targeting.get("countrySelections", [])
    
    if existing_targeting and not form_data:
        form_data = existing_targeting.get("formData", {})
    
    return {
        "countrySelections": processed_countries,
        "formData": form_data,
        "audienceTargeting": audience_targeting_data,
    }

async def process_audience_targeting_data(audience_targeting: dict, user_id: str, campaign_id: str, existing_audience=None) -> dict:
    """Process and save audience targeting data with updates"""
    existing_audience = existing_audience or {
        "uploadAudience": [],
        "createAudience": [],
        "cronAudience": "Disabled"
    }

    if not audience_targeting:
        # If the incoming data is empty, but there's existing data, we should keep it.
        # This is because the form fields are optional.
        return existing_audience
    
    # Handle uploaded files
    new_uploaded_audiences = []
    for audience in audience_targeting.get("uploadAudience", []):
        # Existing file, keep it as is
        if "filePath" in audience and not audience.get("fileData", "").startswith("data:"):
            new_uploaded_audiences.append(audience)
        # New file, save it
        elif "fileData" in audience and audience["fileData"].startswith("data:"):
            processed_file = await save_media_files(
                {"files": [audience]},
                user_id,
                campaign_id,
                existing_files=[],
                subdir="audiences"
            )
            new_uploaded_audiences.append({
                "filePath": processed_file["files"][0]["filePath"],
                "event": audience.get("event"),
                "isEncrypted": audience.get("isEncrypted", False),
                "encryptionKey": audience.get("encryptionKey")
            })
        
    # Find files to delete that were in the old list but not the new list
    existing_file_paths = {f["filePath"] for f in existing_audience.get("uploadAudience", []) if f.get("filePath")}
    new_file_paths = {f["filePath"] for f in new_uploaded_audiences if f.get("filePath")}
    files_to_delete = existing_file_paths - new_file_paths
    for file_path in files_to_delete:
        delete_media_file(file_path, user_id, campaign_id, "audiences")

    return {
        "uploadAudience": new_uploaded_audiences,
        "createAudience": audience_targeting.get("createAudience", existing_audience["createAudience"]),
        "cronAudience": audience_targeting.get("cronAudience", existing_audience["cronAudience"])
    }

def compare_json_fields(new_data, old_data):
    """Compare JSON fields and return True if different"""
    if new_data is None and old_data is None:
        return False
    if new_data is None or old_data is None:
        return True
        
    try:
        if isinstance(old_data, str):
            old_json = old_data
        else:
            old_json = json.dumps(old_data, sort_keys=True)
        
        if isinstance(new_data, str):
            new_json = new_data
        else:
            new_json = json.dumps(new_data, sort_keys=True)
        
        return new_json != old_json
    except Exception as e:
        print(f"[WARNING] JSON comparison failed: {e}")
        return True

def safe_get_nested_value(data: dict, key: str, default=None):
    """Safely get nested dictionary values"""
    try:
        return data.get(key, default) if data else default
    except (AttributeError, TypeError):
        return default

def has_valid_targeting_data(targeting_data):
    """Check if targeting data is valid and should be processed"""
    if not targeting_data or not isinstance(targeting_data, dict):
        print("[DEBUG] Invalid: No targeting data or not a dict")
        return False
    
    if targeting_data.get("isValid") is not True:
        print("[DEBUG] Invalid: isValid is not True")
        return False
    
    country_selections = targeting_data.get("countrySelections")
    if not country_selections:
        print("[DEBUG] Invalid: No countrySelections found")
        return False
    
    if isinstance(country_selections, dict):
        selected_countries = country_selections.get("selectedCountries", [])
        if not selected_countries:
            print("[DEBUG] Invalid: No countries selected in dict format")
        return bool(selected_countries)
    
    if isinstance(country_selections, list):
        if len(country_selections) == 0:
            print("[DEBUG] Invalid: Empty country selections list")
            return False
        
        valid_items = []
        for item in country_selections:
            if isinstance(item, dict):
                if "selectedCountry" in item or "country" in item:
                    valid_items.append(item)
        
        if not valid_items:
            print("[DEBUG] Invalid: No valid country selections found in list")
            return False
        
        print(f"[DEBUG] Valid: Found {len(valid_items)} valid country selections")
        return True
    
    print("[DEBUG] Invalid: Unrecognized countrySelections format")
    return False

@router.put("/update_campaign/{campaign_id}", dependencies=[Depends(verify_api_key)])
async def update_campaign(campaign_id: str, request: Request):
    try:
        data = await request.json()
        sanitize_input(data)

        user_id = data.get("user_id", "unknown")
        user_name = data.get("user_name", "Unknown User")
        log_id = generate_log_id()

        print(f"[INFO] Updating campaign {campaign_id} with data: {list(data.keys())}")

        pool = await Database.connect()
        async with pool.acquire() as conn:
            existing = await get_existing_campaign(campaign_id, conn)
            
            existing_app_details = json.loads(existing.get("app_details", "{}"))
            existing_campaign_details = json.loads(existing.get("campaign_details", "{}"))
            existing_creatives = json.loads(existing.get("creatives", "[]"))
            existing_conversion_flow = json.loads(existing.get("conversion_flow", "{}"))
            existing_budget = json.loads(existing.get("budget", "{}"))
            
            existing_targeting_raw = existing.get("targeting", "{}")
            try:
                existing_targeting = json.loads(existing_targeting_raw)
            except:
                existing_targeting = {
                    "countrySelections": [],
                    "formData": {},
                    "audienceTargeting": {},
                }
            
            existing_source = json.loads(existing.get("source", "{}"))

            updates_to_apply = {}
            
            if "general" in data and data["general"]:
                general_data = data.get("general", {})
                brand_id = safe_get_nested_value(general_data, "brandId")
                brand_name = safe_get_nested_value(general_data, "brandName")
                
                if brand_id and str(brand_id) != str(existing.get("brand", "")):
                    updates_to_apply["brand"] = brand_id
                if brand_name and str(brand_name) != str(existing.get("brand_name", "")):
                    updates_to_apply["brand_name"] = brand_name

            if "appDetails" in data and data["appDetails"]:
                app_details_data = data["appDetails"]
                if compare_json_fields(app_details_data, existing_app_details):
                    merged_app_details = {**existing_app_details, **app_details_data}
                    updates_to_apply["app_details"] = json.dumps(merged_app_details)

            if "campaignDetails" in data and data["campaignDetails"]:
                campaign_details_data = data["campaignDetails"]
                if compare_json_fields(campaign_details_data, existing_campaign_details):
                    merged_campaign_details = {**existing_campaign_details, **campaign_details_data}
                    updates_to_apply["campaign_details"] = json.dumps(merged_campaign_details)

            if "creatives" in data:
                creatives_data = data["creatives"]
                processed_creatives = await save_media_files(
                    creatives_data,
                    user_id,
                    campaign_id,
                    existing_creatives
                )
                updates_to_apply["creatives"] = json.dumps(processed_creatives.get("files", []))

            if "conversionFlow" in data and data["conversionFlow"]:
                conversion_flow_data = data["conversionFlow"]
                if compare_json_fields(conversion_flow_data, existing_conversion_flow):
                    merged_conversion_flow = {**existing_conversion_flow, **conversion_flow_data}
                    updates_to_apply["conversion_flow"] = json.dumps(merged_conversion_flow)

            if "budget" in data and data["budget"]:
                budget_data = data["budget"]
                if compare_json_fields(budget_data, existing_budget):
                    merged_budget = {**existing_budget, **budget_data}
                    updates_to_apply["budget"] = json.dumps(merged_budget)

            if "targeting" in data:
                targeting_data = data["targeting"]
                
                # Fetch existing audience data to handle file deletion
                existing_audience_data = existing_targeting.get("audienceTargeting", {})
                
                # Process the new audience data to handle file uploads/deletions
                processed_audience_targeting = await process_audience_targeting_data(
                    targeting_data.get("audienceTargeting", {}),
                    user_id,
                    campaign_id,
                    existing_audience_data
                )
                
                # Create the combined targeting object for comparison and saving
                new_full_targeting = {
                    "countrySelections": targeting_data.get("countrySelections", []),
                    "formData": targeting_data.get("formData", {}),
                    "audienceTargeting": processed_audience_targeting,
                }
                
                if compare_json_fields(new_full_targeting, existing_targeting):
                    updates_to_apply["targeting"] = json.dumps(new_full_targeting)
                else:
                    print(f"[INFO] No meaningful targeting changes detected, preserving existing.")

            if "source" in data and data["source"]:
                source_data = data["source"]
                if compare_json_fields(source_data, existing_source):
                    merged_source = {**existing_source, **source_data}
                    updates_to_apply["source"] = json.dumps(merged_source)

            updates_to_apply["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            updates_to_apply["log_id"] = log_id

            print(f"[INFO] Fields to update: {list(updates_to_apply.keys())}")

            if len(updates_to_apply) > 2:
                cols = ", ".join(f"{col} = %s" for col in updates_to_apply)
                sql = f"UPDATE cronbid_campaigns SET {cols} WHERE campaign_id = %s"
                params = list(updates_to_apply.values()) + [campaign_id]

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

                updated_fields = [field for field in updates_to_apply.keys() if field not in ["updated_at", "log_id"]]
                print(f"[SUCCESS] Campaign {campaign_id} updated. Fields: {updated_fields}")

                return {
                    "success": True,
                    "message": "Campaign updated successfully",
                    "campaign_id": campaign_id,
                    "changes_made": len(updated_fields),
                    "updated_fields": updated_fields
                }
            else:
                print(f"[INFO] No changes detected for campaign {campaign_id}")
                return {
                    "success": True,
                    "message": "No changes detected - campaign not updated",
                    "campaign_id": campaign_id,
                    "changes_made": 0
                }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Campaign update failed: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error during campaign update: {e}"
        )