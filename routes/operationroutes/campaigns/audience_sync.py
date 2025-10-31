from fastapi import APIRouter, Depends, HTTPException, Header, Body
from pydantic import BaseModel, Field
import json
import os
import uuid
from typing import Optional, Dict, List

router = APIRouter()

# --- PARTNER API KEY CONFIGURATION ---
# This key must match the Test API-Key you send to AppsFlyer
PARTNER_AUDIENCE_API_KEY = "787febebhevdhhvedh787dederrr" 

# --- FILE-BASED STORAGE CONFIGURATION ---
SYNC_DATA_DIR = "sync_data/partner_audiences"
CONTAINER_STORE_FILE = os.path.join(SYNC_DATA_DIR, "containers.json")
os.makedirs(SYNC_DATA_DIR, exist_ok=True)

# Initialize container store file if it doesn't exist
if not os.path.exists(CONTAINER_STORE_FILE):
    with open(CONTAINER_STORE_FILE, 'w') as f:
        json.dump({}, f)

# --- DEPENDENCIES ---

async def verify_partner_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key", description="The Partner's unique API Key.")):
    """
    Dependency to verify the partner's unique API key.
    Returns 401 if invalid, or proceeds if valid (HTTP 200 expectation).
    """
    if x_api_key != PARTNER_AUDIENCE_API_KEY:
        # AppsFlyer FAQ requires 401 for invalid authentication
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key for Audience Sync Partner.")
    return True

# --- Pydantic Models for Schema/Docs ---

# 1. /Create Models
class AudienceCreateRequest(BaseModel):
    name: str = Field(..., description="The unique name of the audience, as it appears in the AppsFlyer UI (2-100 characters, supports all languages/symbols).")
    platform: Optional[str] = Field(None, description="The platform associated with the audience (e.g., 'android', 'ios').")
    
class AudienceCreateResponse(BaseModel):
    container_id: str = Field(..., description="The unique ID created by the Partner (you) to reference this specific audience container.")

# 2. /Sync Models
class AudienceSyncRequest(BaseModel):
    container_id: str = Field(..., description="The unique ID of the audience container created during the /create call.")
    url_adid_sha256: Optional[str] = Field(None, description="Pre-signed AWS URL to download the SHA256 hashed Android/iOS (ADID/IDFA) file.")
    url_email_sha256: Optional[str] = Field(None, description="Pre-signed AWS URL to download the SHA256 hashed Email file.")
    url_phone_sha256: Optional[str] = Field(None, description="Pre-signed AWS URL to download the SHA256 hashed Phone Number file.")
    # Add other potential URL identifiers as needed

class AudienceSyncResponse(BaseModel):
    message: str = "Sync request successfully received and initiated."
    details: str = "Download process acknowledged. File download must be completed within 2 hours."

# --- STORAGE UTILITY FUNCTIONS ---

def _load_containers() -> Dict[str, Dict]:
    """Loads all container mappings from the local JSON file."""
    try:
        with open(CONTAINER_STORE_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_containers(data: Dict[str, Dict]):
    """Saves the container mappings to the local JSON file."""
    with open(CONTAINER_STORE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# ====================================================================
# 1. /Validate Endpoint (POST)
# ====================================================================

@router.post(
    "/validate", 
    dependencies=[Depends(verify_partner_api_key)],
    summary="1. Validate Partner API Key",
    description="AppsFlyer calls this once when an advertiser creates a new connection. It validates the X-API-Key in the header.",
    response_model=Dict[str, str],
    status_code=200
)
async def validate_audience_connection():
    """
    If the verify_partner_api_key dependency succeeds (returns 200), validation is complete.
    """
    return {"status": "success", "message": "API Key is valid."}

# ====================================================================
# 2. /Create Endpoint (POST)
# ====================================================================

@router.post(
    "/create", 
    dependencies=[Depends(verify_partner_api_key)],
    summary="2. Create Audience Container",
    description="AppsFlyer calls this once per new audience to create a unique container ID on the Partner side. The Partner MUST return a 200 response containing the generated 'container_id'.",
    response_model=AudienceCreateResponse,
    status_code=200
)
async def create_audience_sync(
    request_data: AudienceCreateRequest = Body(
        ..., 
        example={"name": "High-Value Users - Android"}
    )
):
    # 1. Generate a unique ID for the container
    new_container_id = str(uuid.uuid4())
    
    # 2. Store the container mapping (simulating DB insertion)
    containers = _load_containers()
    containers[new_container_id] = {
        "name": request_data.name,
        "platform": request_data.platform,
        "created_at": str(os.path.getmtime(CONTAINER_STORE_FILE)) # Simple timestamp placeholder
    }
    _save_containers(containers)
    
    # 3. Return the generated container ID (REQUIRED by AppsFlyer FAQ)
    return {"container_id": new_container_id}

# ====================================================================
# 3. /Sync Endpoint (POST)
# ====================================================================

@router.post(
    "/sync", 
    dependencies=[Depends(verify_partner_api_key)],
    summary="3. Initiate Audience Data Sync",
    description="AppsFlyer calls this whenever an upload is initiated (daily or manual). The body contains the container_id and pre-signed AWS URLs for file download.",
    response_model=AudienceSyncResponse,
    status_code=200
)
async def sync_audience_data(
    request_data: AudienceSyncRequest = Body(
        ...,
        example={
            "container_id": "a1b2c3d4-e5f6-7890-abcd-ef0123456789",
            "url_adid_sha256": "https://audiencespull.appsflyer.com/{{PARTNER_PULL_KEY}}/file_1.csv?X-Amz...",
            "url_email_sha256": "https://audiencespull.appsflyer.com/{{PARTNER_PULL_KEY}}/file_2.csv?X-Amz..."
        }
    )
):
    # 1. Check if the container ID exists (simple validation)
    containers = _load_containers()
    if request_data.container_id not in containers:
        # NOTE: AppsFlyer FAQ doesn't specify an error code for bad container, 
        # but 404 is appropriate for a resource not found.
        raise HTTPException(status_code=404, detail=f"Container ID '{request_data.container_id}' not found.")

    # 2. Log or initiate the file download process (cannot actually download files here)
    urls_received = {k: v for k, v in request_data.model_dump().items() if k.startswith('url_') and v is not None}
    
    print(f"--- SYNC INITIATED for Container: {request_data.container_id} ---")
    print(f"Audience Name: {containers.get(request_data.container_id, {}).get('name', 'N/A')}")
    print(f"URLs to download: {json.dumps(urls_received, indent=2)}")
    print("--- Download logic must be asynchronous and complete within 2 hours. ---")

    # 3. Return 200 OK immediately (REQUIRED by AppsFlyer FAQ)
    return AudienceSyncResponse()
