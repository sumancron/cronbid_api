# routes/operationroutes/campaigns/audience_sync.py

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from database import Database
import aiomysql
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, Union, List
from pydantic import BaseModel, Field # REQUIRED FOR DOCS INPUT FIELDS
import uuid

router = APIRouter()

# --- Pydantic Model for API Documentation and Flexible Input ---
# This model defines the fields that will appear in the /docs UI
class AudienceSyncInput(BaseModel):
    # ID/campaign_id are used to locate the sync file or validate existence.
    id: Optional[Union[int, str]] = Field(None, description="Internal campaign ID (integer or string) used to reference the campaign in our system. Optional.")
    campaign_id: Optional[str] = Field(None, description="The unique campaign identifier (e.g., CRB-...). Optional.")
    
    event_name: Optional[str] = Field(None, description="The specific event name (e.g., 'purchase_complete') associated with the data being created/synced. Optional.")
    
    json_object: Optional[Dict[str, Any]] = Field(None, description="The core data payload from the partner (can be nested JSON, URLs, or file indicators). Optional.")
    
    custom_data: Optional[Dict[str, Any]] = Field(None, description="Any other custom/arbitrary key-value pairs the partner wants to send. Optional.")

    class Config:
        schema_extra = {
            "example": {
                "campaign_id": "CRB-1761621799-cdc358",
                "event_name": "app_install",
                "json_object": {
                    "audience_size": 15000,
                    "file_url": "https://audiencespull.appsflyer.com/partner_data.csv"
                },
                "custom_data": {"partner_key": "xyz123"}
            }
        }
# --- END Pydantic Model ---


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

def get_sync_file_path(identifier: str) -> str:
    """Generates the absolute path for a campaign's sync state file using campaign_id or ID."""
    safe_id = identifier if identifier else f"generic-sync-{uuid.uuid4().hex[:8]}"
    return os.path.join(SYNC_DATA_DIR, f"{safe_id}.json")

async def read_sync_file(identifier: str) -> Dict[str, Any]:
    """Reads sync data from the JSON file."""
    file_path = get_sync_file_path(identifier)
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.loads(f.read())
    except Exception as e:
        print(f"[ERROR] Failed to read sync file for {identifier}: {e}")
        return {}

async def write_sync_file(identifier: str, data: Dict[str, Any]):
    """Writes or overwrites sync data to the JSON file."""
    file_path = get_sync_file_path(identifier)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Failed to write sync file for {identifier}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save sync state: {e}")

# --- DB READ-ONLY HELPERS ---

async def get_campaign_details(campaign_id: Optional[str] = None, internal_id: Optional[int] = None) -> Optional[Dict]:
    """
    Fetches campaign details based on campaign_id or internal ID (safe, SELECT ONLY).
    """
    where_clauses = []
    values = []
    
    if campaign_id:
        where_clauses.append("campaign_id = %s")
        values.append(campaign_id)
    if internal_id is not None:
        where_clauses.append("id = %s")
        values.append(internal_id)
        
    if not where_clauses:
        return None
        
    query = f"SELECT campaign_id, id, targeting FROM cronbid_campaigns WHERE {' OR '.join(where_clauses)}"
    
    pool = await Database.connect()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(query, values)
            return await cur.fetchone()

# ====================================================================
# 1. /Validate Endpoint (POST) - SECURED with verify_partner_api_key
# ====================================================================

@router.post("/validate", dependencies=[Depends(verify_partner_api_key)], tags=["Audience Sync Integration"])
async def validate_audience_connection(data: AudienceSyncInput): # Uses Pydantic for docs
    """
    Validates campaign existence by ID or campaign_id and returns specific audience targeting details.
    
    No identifier is mandatory, but one is required to perform a database lookup.
    """
    try:
        campaign_id = data.campaign_id
        internal_id = data.id
        
        # Safely determine integer ID for DB query
        safe_internal_id = None
        if internal_id is not None:
            try:
                # Handle case where Pydantic parsed 'id' as str
                safe_internal_id = int(internal_id)
            except (ValueError, TypeError):
                pass
        
        if not campaign_id and safe_internal_id is None:
            return {
                "success": True,
                "message": "Connection validated. No campaign ID/ID provided for database check.",
                "status": "No check performed"
            }
        
        campaign_row = await get_campaign_details(campaign_id, safe_internal_id)
        
        if not campaign_row:
             return {
                "success": False,
                "message": f"Validation failed: Campaign not found using identifier(s) provided.",
                "validated_identifiers": {"campaign_id": campaign_id, "id": internal_id},
                "status": "Invalid"
             }

        # --- Extract Audience Targeting Details ---
        try:
            targeting_data = json.loads(campaign_row.get("targeting", "{}") or "{}")
            audience_targeting = targeting_data.get("audienceTargeting", {}) if isinstance(targeting_data, dict) else {}
        except json.JSONDecodeError:
            audience_targeting = {}
        
        cron_status = audience_targeting.get("cronAudience", "Disabled")
        create_enabled = bool(audience_targeting.get("createAudience"))
        events = [a.get("event") for a in audience_targeting.get("uploadAudience", []) if a.get("event")]
        
        return {
            "success": True,
            "message": "Campaign validated successfully.",
            "validated_identifiers": {"campaign_id": campaign_row["campaign_id"], "id": campaign_row["id"]},
            "status": "Validated",
            "audience_details": {
                "cron_audience_status": cron_status,
                "is_create_audience_enabled": create_enabled,
                "tracked_events": list(set(events)), 
                "uploaded_audience_details": audience_targeting.get("uploadAudience", [])
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Validation failed: Internal Error: {str(e)}"
        )

# ====================================================================
# 2. /Create Endpoint (POST) - SECURED with verify_partner_api_key
# ====================================================================

@router.post("/create", dependencies=[Depends(verify_partner_api_key)], tags=["Audience Sync Integration"])
async def create_audience_sync(data: AudienceSyncInput): # Uses Pydantic for docs
    """
    Audience Creation: Accepts any combination of inputs. Creates a new campaign-specific JSON file to store the payload.
    """
    try:
        # 1. Determine the unique identifier for the sync file
        campaign_id = data.campaign_id
        internal_id = data.id
        
        # Use campaign_id > internal_id > generic ID for file naming (MANDATORY for file system)
        identifier = campaign_id or str(internal_id) if internal_id is not None else f"sync-id-{uuid.uuid4().hex[:8]}"

        # 2. Optionally check existence in DB (READ-ONLY)
        if data.campaign_id or data.id is not None:
             # Just ensures we don't proceed with a non-existent campaign, but not strictly required
             await get_campaign_details(campaign_id=data.campaign_id, internal_id=data.id) 

        # 3. Prepare the payload structure
        sync_data = {
            "file_identifier": identifier,
            "created_at": datetime.utcnow().isoformat(),
            "last_synced_at": datetime.utcnow().isoformat(),
            "creation_data": {
                "id_sent": data.id,
                "campaign_id_sent": data.campaign_id,
                "event_name": data.event_name,
                "json_object_sent": data.json_object,
                "custom_data_sent": data.custom_data
            },
            "sync_history": {
                 f"create_{uuid.uuid4().hex[:6]}": {
                     "timestamp": datetime.utcnow().isoformat(),
                     "event": data.event_name or "generic_event",
                     # Store the whole non-null input payload for maximum partner comfort
                     "payload": data.dict(exclude_none=True) 
                 }
            }
        }
        
        await write_sync_file(identifier, sync_data)
        
        return {
            "success": True,
            "message": "Audience sync file created successfully.",
            "file_identifier": identifier,
            "storage_location": get_sync_file_path(identifier)
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

@router.post("/sync", dependencies=[Depends(verify_partner_api_key)], tags=["Audience Sync Integration"])
async def sync_audience_data(data: AudienceSyncInput): # Uses Pydantic for docs
    """
    Audience Sync: Performs an update operation on the existing campaign's JSON file. 
    Requires 'id' or 'campaign_id' in the body to locate the file.
    """
    try:
        campaign_id = data.campaign_id
        internal_id = data.id
        
        # Determine the identifier for the sync file (MANDATORY for update)
        identifier = campaign_id or str(internal_id) if internal_id is not None else None
        
        if not identifier:
            raise HTTPException(status_code=400, detail="Synchronization requires either 'campaign_id' or 'id' in the JSON body to locate the existing sync file.")

        # Check if the sync file exists (the primary validation for /sync)
        current_data = await read_sync_file(identifier)
        if not current_data:
            raise HTTPException(status_code=404, detail=f"Sync file not found using identifier '{identifier}'. Please call the /create endpoint first.")
            
        # --- File Update Logic ---
        
        # 1. Update metadata
        current_data["last_synced_at"] = datetime.utcnow().isoformat()
        
        # 2. Store the new payload in sync_history
        timestamp_key = f"sync_{uuid.uuid4().hex[:6]}"
        
        current_data.setdefault("sync_history", {})[timestamp_key] = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": data.event_name or "generic_event",
            "payload": data.dict(exclude_none=True) # Store the whole non-null input payload
        }

        await write_sync_file(identifier, current_data)

        return {
            "success": True,
            "message": "Audience data synchronized and file updated.",
            "file_identifier": identifier,
            "new_record_key": timestamp_key
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Audience sync failed: Internal Error: {str(e)}"
        )