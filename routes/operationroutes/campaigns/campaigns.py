from fastapi import APIRouter, Depends, HTTPException, Query
from database import Database
from auth import verify_api_key
import aiomysql
from typing import Optional, List
import json

import os
from dotenv import load_dotenv

# Load environment variables (assuming UPLOADS_DIR might be an environment variable)
load_dotenv()

# Define the base directory for media uploads, similar to add_campaigns.py
# You should ensure this path is correctly configured for file access.
UPLOADS_DIR = os.getenv("UPLOADS_DIR", "uploads/campaignsmedia") # Fallback to a local path

router = APIRouter()

@router.get("/get_campaigns/", dependencies=[Depends(verify_api_key)])
async def get_campaigns(
    campaign_id: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    campaign_title: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    created_by: Optional[str] = Query(None)
):
    try:
        filters = []
        values = []

        if campaign_id:
            filters.append("campaign_id = %s")
            values.append(campaign_id)
        if brand:
            filters.append("brand = %s")
            values.append(brand)
        if campaign_title:
            filters.append("campaign_title = %s")
            values.append(campaign_title)
        if country:
            filters.append("country = %s")
            values.append(country)
        if status:
            filters.append("status = %s")
            values.append(status)
        if created_by:
            filters.append("created_by = %s")
            values.append(created_by)

        query = "SELECT * FROM cronbid_campaigns"
        if filters:
            query += " WHERE " + " AND ".join(filters)

        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, values)
                rows = await cur.fetchall()

        # Define the default simplified structure: [{"country": null, "excludedStates": [], "includedStates": []}]
        DEFAULT_TARGETING = [{"country": None, "excludedStates": [], "includedStates": []}]

        for row in rows:
            # Handle conversion_flow (kept as per original logic)
            if "conversion_flow" in row and row["conversion_flow"]:
                try:
                    cf = json.loads(row["conversion_flow"])
                    if isinstance(cf, dict) and "amount" in cf:
                        cf["payout"] = cf["amount"]
                        row["conversion_flow"] = json.dumps(cf)
                except json.JSONDecodeError:
                    pass

            # --- ROBUST TARGETING LOGIC START ---
            
            source_targeting_str = row.get("targeting")
            original_targeting_data = None
            
            # 1. Try to load the data from the 'targeting' column (which holds the raw DB data)
            if source_targeting_str:
                try:
                    original_targeting_data = json.loads(source_targeting_str)
                except json.JSONDecodeError:
                    original_targeting_data = None # Failed to parse

            # 2. Store the original data in 'advanced_targeting' for completeness
            row["advanced_targeting"] = json.dumps(original_targeting_data if original_targeting_data is not None else {})

            simplified_targeting = []
            
            if original_targeting_data is not None:
                
                # Case 1: Complex structure with 'countrySelections' (from your full data example)
                if isinstance(original_targeting_data, dict) and "countrySelections" in original_targeting_data:
                    country_selections = original_targeting_data.get("countrySelections", [])
                    if isinstance(country_selections, list):
                        for item in country_selections:
                            # Use 'selectedCountry' key if present; this handles the complex structure
                            country_val = item.get("selectedCountry") or item.get("country")
                            
                            simplified_targeting.append({
                                "country": country_val,
                                "excludedStates": item.get("excludedStates", []),
                                "includedStates": item.get("includedStates", [])
                            })

                # Case 2: Simplified List Format (from your direct DB query output)
                elif isinstance(original_targeting_data, list):
                    for item in original_targeting_data:
                        # Use 'country' key if present; this handles the already simplified structure
                        if isinstance(item, dict):
                            simplified_targeting.append({
                                "country": item.get("country"),
                                "excludedStates": item.get("excludedStates", []),
                                "includedStates": item.get("includedStates", [])
                            })
            
            # 3. If no countries were successfully extracted, use the default structure
            if not simplified_targeting:
                simplified_targeting = DEFAULT_TARGETING
                
            # 4. Assign the final simplified structure to the 'targeting' key
            # This ensures the output format is ALWAYS [{"country": "...", "excludedStates": [], "includedStates": []}]
            row["targeting"] = json.dumps(simplified_targeting)
            
            # --- ROBUST TARGETING LOGIC END ---

        return {"campaigns": rows}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"API Error: {str(e)}")
    




# Placeholder for CSV reading. YOU MUST IMPLEMENT THIS on your server.
def read_csv_file_content_as_json(file_path: str) -> List[dict]:
    """
    Simulates reading a CSV file and converting its content to a list of dicts (JSON array).
    
    NOTE: This function requires access to the filesystem on your server.
    The UPLOADS_DIR must be correctly configured to resolve paths like:
    uploads/campaignsmedia/admin-001/CRB-1761621799-cdc358/audiences/84a0ab571ee240c790cea1dfc9443fe6.csv
    
    Example implementation:
    full_path = os.path.join(UPLOADS_DIR, *file_path.lstrip('/').split('/')[1:])
    try:
        if not os.path.exists(full_path):
            print(f"File not found: {full_path}")
            return [{"error": "File not found"}]
            
        with open(full_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
            
    except Exception as e:
        print(f"Error reading CSV {full_path}: {str(e)}")
        return [{"error": f"Failed to read file: {str(e)}"}]
    """
    # Placeholder implementation:
    print(f"Attempting to read file at path: {file_path}")
    
    # Example logic to resolve the path structure:
    # file_path is like '/campaignsmedia/user_id/campaign_id/audiences/file.csv'
    # We strip '/campaignsmedia/' and join with UPLOADS_DIR
    relative_path_parts = file_path.lstrip('/').split('/')
    if len(relative_path_parts) > 1 and relative_path_parts[0] == 'campaignsmedia':
        # Remove 'campaignsmedia' from the start
        relative_path_to_file = relative_path_parts[1:]
        # Join with the configured UPLOADS_DIR
        full_path = os.path.join(UPLOADS_DIR, *relative_path_to_file)
        
        # Correct path for Windows/Linux based on your example:
        # C:\Users\suman\OneDrive\Desktop\dashboard\cronbid_api\uploads\campaignsmedia\admin-001\CRB-1761621799-cdc358\audiences\84a0ab571ee240c790cea1dfc9443fe6.csv
        # The file_path in DB is 'admin-001\\\\CRB-1761621799-cdc358\\\\audiences\\\\84a0ab571ee240c790cea1dfc9443fe6.csv' when you extract it
        # Let's adjust for the stored path format: '/campaignsmedia/admin-001\\CRB-1761621799-cdc358\\audiences\\file.csv'
        # The stored path might use backslashes on Windows, which need to be replaced for os.path.join on some systems
        path_to_use = file_path.replace('/campaignsmedia/', '').replace('\\', os.path.sep)
        full_path_corrected = os.path.join(UPLOADS_DIR, path_to_use)
        
        try:
            # Simplified mock reading for demonstration purposes without real file access
            if "84a0ab571ee240c790cea1dfc9443fe6.csv" in file_path:
                print(f"[MOCK] Reading CSV file content from {full_path_corrected}")
                return [
                    {"email": "user1@example.com", "id": "1001"},
                    {"email": "user2@example.com", "id": "1002"}
                ]
            else:
                 return [{"error": "Mock file not found or path not matched"}]
            
        except Exception as e:
            return [{"error": f"Mock failed: {str(e)}"}]
    
    return [{"error": "Invalid file path format"}]

# ----------------------------------------------------------------------
# NEW API ENDPOINT: /get_audience_data/
# ----------------------------------------------------------------------

@router.get("/get_audience_data/", dependencies=[Depends(verify_api_key)])
async def get_audience_data(
    cron_audience_status: Optional[str] = Query(None, description="Filter by cronAudience status (e.g., 'Enabled', 'Disabled', 'Processing')"),
    has_create_audience: Optional[bool] = Query(None, description="Filter by presence of data in createAudience array"),
    has_upload_audience: Optional[bool] = Query(None, description="Filter by presence of files in uploadAudience array"),
    upload_event: Optional[str] = Query(None, description="Filter uploaded audiences by event name")
):
    try:
        # 1. Fetch data from the database
        query = "SELECT campaign_id, brand_name, campaign_details, targeting FROM cronbid_campaigns"
        
        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query)
                rows = await cur.fetchall()

        results = []

        # 2. Process and filter the data
        for row in rows:
            campaign_id = row["campaign_id"]
            brand_name = row["brand_name"]
            
            # Safely parse campaign_details
            campaign_details = {}
            if row["campaign_details"]:
                try:
                    campaign_details = json.loads(row["campaign_details"])
                except json.JSONDecodeError:
                    pass
            
            # Safely parse targeting data
# Safely parse targeting data
            targeting_data = {}
            audience_targeting = {}
            if row["targeting"]:
                try:
                    parsed_targeting = json.loads(row["targeting"])
                    
                    # FIX: Check if the parsed data is a dictionary (the expected full format)
                    if isinstance(parsed_targeting, dict):
                        targeting_data = parsed_targeting
                        audience_targeting = targeting_data.get("audienceTargeting", {})
                    # If it's a list, it's likely an old or simplified format without audienceTargeting
                    elif isinstance(parsed_targeting, list):
                        # Treat it as data without audience targeting for this API's purpose
                        # If you later discover audience data is nested, you'd update this logic
                        pass 
                        
                except json.JSONDecodeError:
                    pass
            
            # audience_targeting = targeting_data.get("audienceTargeting", {})
            
            cron_status = audience_targeting.get("cronAudience", "Disabled")
            create_audience = audience_targeting.get("createAudience", [])
            upload_audience = audience_targeting.get("uploadAudience", [])

            # Apply filters
            
            # Filter 1: cron_audience_status
            if cron_audience_status and cron_status.lower() != cron_audience_status.lower():
                continue

            # Filter 2: has_create_audience
            if has_create_audience is not None:
                if has_create_audience and not create_audience:
                    continue
                if not has_create_audience and create_audience:
                    continue

            # Filter 3: has_upload_audience
            if has_upload_audience is not None:
                if has_upload_audience and not upload_audience:
                    continue
                if not has_upload_audience and upload_audience:
                    continue
            
            # If no upload audience, we can skip further processing for this part
            if not upload_audience:
                # Append a base record for campaigns that meet the other criteria but have no uploads
                results.append({
                    "campaign_id": campaign_id,
                    "brand_name": brand_name,
                    "campaign_title": campaign_details.get("campaignTitle", "N/A"),
                    "cronAudience_status": cron_status,
                    "createAudience": create_audience,
                    "uploadAudience_files": [],
                    "uploaded_file_content": [], # Empty if no files
                })
                continue

            # Process upload audience (Filter 4: upload_event & CSV reading)
            processed_uploads = []
            
            for upload in upload_audience:
                file_path = upload.get("filePath")
                event = upload.get("event", "")
                
                # Filter 4: upload_event
                if upload_event and event.lower() != upload_event.lower():
                    continue
                
                # Process the file content (CSV to JSON)
                uploaded_content = []
                if file_path and file_path.lower().endswith('.csv'):
                    # IMPORTANT: This calls the placeholder function, which must be implemented
                    uploaded_content = read_csv_file_content_as_json(file_path)
                
                # Append the flattened record for this specific upload file
                results.append({
                    "campaign_id": campaign_id,
                    "brand_name": brand_name,
                    "campaign_title": campaign_details.get("campaignTitle", "N/A"),
                    "cronAudience_status": cron_status,
                    "createAudience": create_audience, # Includes all campaigns that passed filters
                    "upload_event": event,
                    "upload_file_metadata": {
                        "filePath": file_path,
                        "isEncrypted": upload.get("isEncrypted", False),
                        "encryptionKey": upload.get("encryptionKey")
                    },
                    "uploaded_file_content": uploaded_content, # CSV content as JSON
                })

        # 3. Return the results
        return {"audience_data": results}

    except Exception as e:
        print(f"Error in get_audience_data: {e}")
        raise HTTPException(status_code=500, detail=f"API Error fetching audience data: {str(e)}")