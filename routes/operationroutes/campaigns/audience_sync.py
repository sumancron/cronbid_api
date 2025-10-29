# routes/operationroutes/campaigns/audience_sync.py

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from database import Database
# NOTE: We keep verify_api_key import but don't use it directly on the router posts
import aiomysql
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

router = APIRouter()

# --- PARTNER API KEY CONFIGURATION ---
PARTNER_AUDIENCE_API_KEY = "787febebhevdhhvedh787dederrr"

async def verify_partner_api_key(x_api_key: Optional[str] = Header(None)):
    """Dependency to verify the partner's unique API key."""
    if x_api_key != PARTNER_AUDIENCE_API_KEY:
        # Deny access if the key is missing or incorrect
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key for Audience Sync Partner.")
    return True

# --- FILE-BASED STORAGE CONFIGURATION ---
# Store the sync state in a dedicated local directory to avoid touching the DB.
# Make sure this directory exists and is writable by your FastAPI server.
SYNC_DATA_DIR = "sync_data/partner_audiences"
os.makedirs(SYNC_DATA_DIR, exist_ok=True)

def get_sync_file_path(campaign_id: str) -> str:
    """Generates the absolute path for a campaign's sync state file."""
    return os.path.join(SYNC_DATA_DIR, f"{campaign_id}.json")

async def read_sync_file(campaign_id: str) -> Dict[str, Any]:
    """Reads sync data from the JSON file."""
    file_path = get_sync_file_path(campaign_id)
    if not os.path.exists(file_path):
        return {}
    try:
        # Use standard open/read as this is outside of the DB pool
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
    """Checks campaign existence via DB read (safe)."""
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
    Validates connection and the existence of the campaign_id in the database.
    """
    try:
        data = await request.json()
        campaign_id = data.get("campaign_id")
        
        if not campaign_id:
            raise HTTPException(status_code=400, detail="Missing required field: campaign_id")

        if not await check_campaign_exists(campaign_id):
             raise HTTPException(status_code=404, detail=f"Campaign ID '{campaign_id}' not found.")
        
        return {
            "success": True,
            "message": "Connection and campaign ID validated successfully.",
            "validated_campaign_id": campaign_id,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Validation failed: Internal Error: {str(e)}"
        )

# ====================================================================
# 2. /Create Endpoint (POST) - SECURED with verify_partner_api_key
# ====================================================================

@router.post("/create", dependencies=[Depends(verify_partner_api_key)])
async def create_audience_sync(request: Request):
    """
    Initializes audience sync. Registers the partner's audience ID and creates 
    the campaign's dedicated JSON file for sync state management.
    """
    try:
        data = await request.json()
        campaign_id = data.get("campaign_id")
        partner_audience_id = data.get("partner_audience_id") 
        
        if not campaign_id or not partner_audience_id:
            raise HTTPException(status_code=400, detail="Missing required fields: campaign_id and partner_audience_id")

        if not await check_campaign_exists(campaign_id):
            raise HTTPException(status_code=404, detail=f"Cannot create sync state, Campaign ID '{campaign_id}' not found.")

        # --- File Write Logic (Replaces DB Write) ---
        initial_sync_data = {
            "campaign_id": campaign_id,
            "partner_audience_id": partner_audience_id,
            "sync_status": "PENDING_CREATE",
            "initial_creation_data": data, # Store partner's full creation payload
            "last_sync_time": datetime.utcnow().isoformat(),
            "synced_audience_data": [] # Array to hold data from /sync endpoint
        }
        
        await write_sync_file(campaign_id, initial_sync_data)
        
        return {
            "success": True,
            "message": "Audience sync state created in local file.",
            "campaign_id": campaign_id,
            "partner_audience_id": partner_audience_id,
            "storage_location": get_sync_file_path(campaign_id) 
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Audience creation failed: Internal Error: {str(e)}"
        )


# ====================================================================
# 3. /Sync Endpoint (POST) - SECURED with verify_partner_api_key
# ====================================================================

@router.post("/sync", dependencies=[Depends(verify_partner_api_key)])
async def sync_audience_data(request: Request):
    """
    Receives synchronized audience data and updates the local JSON file.
    """
    try:
        data = await request.json()
        campaign_id = data.get("campaign_id")
        sync_payload = data.get("sync_payload", {}) 
        
        if not campaign_id or not sync_payload:
            raise HTTPException(status_code=400, detail="Missing required fields: campaign_id and sync_payload")

        # Check if the sync file exists (implies it was created via /create)
        current_data = await read_sync_file(campaign_id)
        if not current_data:
            raise HTTPException(status_code=404, detail=f"Sync state not initialized for campaign {campaign_id}. Please call /create first.")
            
        # --- File Update Logic (Replaces DB Update) ---
        
        # 1. Update status and metadata
        current_data["sync_status"] = sync_payload.get("status", "SYNCED")
        current_data["audience_size"] = sync_payload.get("audience_size", 0)
        current_data["last_sync_time"] = datetime.utcnow().isoformat()
        current_data["last_sync_payload"] = sync_payload # Store the latest raw payload
        
        # 2. Store the actual audience data in the 'synced_audience_data' field
        if "audience_data" in sync_payload:
            current_data["synced_audience_data"] = sync_payload["audience_data"] 

        await write_sync_file(campaign_id, current_data)

        return {
            "success": True,
            "message": "Audience data synchronized and file updated.",
            "campaign_id": campaign_id,
            "new_sync_status": current_data["sync_status"],
            "audience_size": current_data.get("audience_size")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Audience sync failed: Internal Error: {str(e)}"
        )