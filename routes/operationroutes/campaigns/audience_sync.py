# routes/operationroutes/campaigns/audience_sync.py

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from database import Database
import aiomysql
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import uuid # Added uuid for generic IDs

router = APIRouter()

# --- PARTNER API KEY CONFIGURATION ---
PARTNER_AUDIENCE_API_KEY = "787febebhevdhhvedh787dederrr"

async def verify_partner_api_key(x_api_key: Optional[str] = Header(None)):
    """
    Dependency to verify the partner's unique API key. 
    (Test API-Key: 787febebhevdhhvedh787dederrr)
    """
    if x_api_key != PARTNER_AUDIENCE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key for Audience Sync Partner.")
    return True

# --- FILE-BASED STORAGE CONFIGURATION ---
SYNC_DATA_DIR = "sync_data/partner_audiences"
os.makedirs(SYNC_DATA_DIR, exist_ok=True)

def get_sync_file_path(campaign_id: str) -> str:
    """Generates the absolute path for a campaign's sync state file."""
    # Note: Using a default ID if campaign_id is not provided/valid
    safe_id = campaign_id if campaign_id else "generic-partner-sync"
    return os.path.join(SYNC_DATA_DIR, f"{safe_id}.json")

async def read_sync_file(campaign_id: str) -> Dict[str, Any]:
    """Reads sync data from the JSON file."""
    file_path = get_sync_file_path(campaign_id)
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.loads(f.read())
    except Exception as e:
        print(f"[ERROR] Failed to read sync file for {campaign_id}: {e}")
        return {}

async def write_sync_file(campaign_id: str, data: Dict[str, Any]):
    """Writes or overwrites sync data to the JSON file."""
    file_path = get_sync_file_path(campaign_id)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Failed to write sync file for {campaign_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save sync state: {e}")

# --- DB READ-ONLY HELPERS ---

async def check_campaign_exists(campaign_id: str) -> bool:
    """Checks campaign existence via DB read (safe, SELECT ONLY)."""
    pool = await Database.connect()
    async with pool.acquire() as conn:
        query = "SELECT campaign_id FROM cronbid_campaigns WHERE campaign_id = %s"
        async with conn.cursor() as cur:
            await cur.execute(query, (campaign_id,))
            return bool(await cur.fetchone())

# ====================================================================
# 1. /Validate Endpoint (POST) - SECURED with verify_partner_api_key
# ====================================================================

@router.post("/validate", dependencies=[Depends(verify_partner_api_key)])
async def validate_audience_connection(request: Request):
    """
    Partnership Validation: Checks connection and optionally validates a campaign_id 
    against the read-only database. Returns success for connection if API key is valid.
    """
    try:
        # We wrap this in a try/except to handle non-JSON or empty bodies gracefully
        try:
            data = await request.json()
        except json.JSONDecodeError:
            data = {"message": "Empty or non-JSON body received, API key verified."}
            
        campaign_id = data.get("campaign_id")
        
        # If campaign_id is provided, check existence (READ-ONLY DB access)
        if campaign_id and not await check_campaign_exists(campaign_id):
             return {
                "success": False, 
                "message": f"Validation Error: Campaign ID '{campaign_id}' not found in database.",
                "data_received": data
             }
        
        return {
            "success": True,
            "message": "Connection validated successfully.",
            "data_received": data,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Validation failed: Internal Error: {str(e)}"
        )

# ====================================================================
# 2. /Create Endpoint (POST) - FULL FLEXIBILITY, FILE-BASED WRITE
# ====================================================================

@router.post("/create", dependencies=[Depends(verify_partner_api_key)])
async def create_audience_sync(request: Request):
    """
    Audience Creation: Accepts ANY data, stores it in a campaign-specific JSON file. 
    No constraints. The database is NOT modified.
    """
    try:
        # Read the body, gracefully handling non-JSON or empty bodies
        try:
            data = await request.json()
        except json.JSONDecodeError:
            data = {"error": "Invalid JSON or empty body received for creation."}
            
        # Determine the campaign_id to use for the file name. 
        # If not provided, use a generic ID.
        campaign_id = data.get("campaign_id", f"sync-id-{uuid.uuid4().hex[:8]}")
        
        # If a campaign_id exists, validate it (READ-ONLY)
        if data.get("campaign_id") and not await check_campaign_exists(data["campaign_id"]):
             print(f"[WARNING] Campaign ID {data['campaign_id']} not found in DB, using for sync file creation.")

        # --- File Write Logic ---
        sync_data = {
            "created_at": datetime.utcnow().isoformat(),
            "last_synced_at": datetime.utcnow().isoformat(),
            "partner_payload_creation": data
        }
        
        # NOTE on File/Excel Handling: 
        # The partner can send a URL or path to their file (CSV/Excel) within the JSON payload.
        # Example keys to look for: "file_url", "aws_s3_path", "urls" (as per AppsFlyer FAQ).
        # Your background service would read the path from the JSON file and download the data later.

        await write_sync_file(campaign_id, sync_data)
        
        return {
            "success": True,
            "message": "Audience sync state created successfully (DB write skipped).",
            "campaign_id_used": campaign_id,
            "storage_location": get_sync_file_path(campaign_id),
            "next_step": "Use the 'campaign_id_used' in the /sync endpoint to update data."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Audience creation failed: Internal Error: {str(e)}"
        )


# ====================================================================
# 3. /Sync Endpoint (POST) - FULL FLEXIBILITY, FILE-BASED WRITE
# ====================================================================

@router.post("/sync", dependencies=[Depends(verify_partner_api_key)])
async def sync_audience_data(request: Request):
    """
    Audience Sync: Accepts ANY data and updates the existing campaign's JSON file. 
    Requires a 'campaign_id' to locate the file. The database is NOT modified.
    """
    try:
        # Read the body, gracefully handling non-JSON or empty bodies
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Synchronization requires a valid JSON body.")
            
        campaign_id = data.get("campaign_id") 
        
        if not campaign_id:
            raise HTTPException(status_code=400, detail="Synchronization requires a 'campaign_id' in the JSON body to identify the sync file.")

        # Check if the sync file exists 
        current_data = await read_sync_file(campaign_id)
        if not current_data:
            raise HTTPException(status_code=404, detail=f"Sync state not found for campaign {campaign_id}. Please call /create first.")
            
        # --- File Update Logic ---
        
        # 1. Update metadata
        current_data["last_synced_at"] = datetime.utcnow().isoformat()
        
        # 2. Store the new payload under a timestamped key for history/flexibility
        timestamp_key = f"sync_payload_{uuid.uuid4().hex[:6]}"
        if "sync_history" not in current_data:
            current_data["sync_history"] = {}
        
        current_data["sync_history"][timestamp_key] = {
            "timestamp": datetime.utcnow().isoformat(),
            "payload": data
        }

        await write_sync_file(campaign_id, current_data)

        return {
            "success": True,
            "message": "Audience data synchronized and file updated.",
            "campaign_id_used": campaign_id,
            "new_record_key": timestamp_key
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Audience sync failed: Internal Error: {str(e)}"
        )
        
# ====================================================================
# 4. /get_sync_data Endpoint (GET) - FOR INTERNAL VIEWING/DEBUGGING
# ====================================================================

@router.get("/get_sync_data/{campaign_id}", dependencies=[Depends(verify_partner_api_key)])
async def get_sync_data(campaign_id: str):
    """
    Allows viewing the stored JSON sync file for a specific campaign ID. 
    """
    try:
        data = await read_sync_file(campaign_id)
        if not data:
            raise HTTPException(status_code=404, detail=f"No sync data found for campaign ID '{campaign_id}'.")
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "sync_data": data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve sync data: {str(e)}"
        )