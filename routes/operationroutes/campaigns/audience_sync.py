from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
import json
import os
import uuid
from typing import Optional, Dict, List

router = APIRouter()

# --- PARTNER API KEY CONFIGURATION ---
# This key is used internally for validation
PARTNER_AUDIENCE_API_KEY = "787febebhevdhhvedh787dederrr" 

# --- FILE-BASED STORAGE CONFIGURATION ---
SYNC_DATA_DIR = "sync_data/partner_audiences"
CONTAINER_STORE_FILE = os.path.join(SYNC_DATA_DIR, "containers.json")
os.makedirs(SYNC_DATA_DIR, exist_ok=True)

if not os.path.exists(CONTAINER_STORE_FILE):
    with open(CONTAINER_STORE_FILE, 'w') as f:
        json.dump({}, f)

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

# --- API KEY VALIDATION LOGIC (Used internally by each endpoint) ---

def validate_api_key(received_key: str):
    """Checks the API key from the request body against the internal key."""
    if received_key != PARTNER_AUDIENCE_API_KEY:
        # AppsFlyer FAQ requires 401 for invalid authentication
        raise HTTPException(status_code=401, detail="Invalid API key for authentication.")
    return True

# --- Pydantic Models for Schema/Docs (Now includes api_key in Body) ---

# Base Model for all requests that require API Key validation in the body
class BaseAudienceRequest(BaseModel):
    # Added api_key here. Hiding the actual key in the example.
    api_key: str = Field(..., description="The unique API key issued to the advertiser, sent in the request body for authentication.", example="d41ac239b3b918e28fa0c") 

# 1. /Validate Models
class AudienceValidateRequest(BaseAudienceRequest):
    # api_key is inherited
    pass
    
# 2. /Create Models
class AudienceCreateRequest(BaseAudienceRequest):
    name: str = Field(..., description="The unique name of the audience, as it appears in the AppsFlyer UI.")
    platform: Optional[str] = Field(None, description="The platform associated with the audience (e.g., 'android', 'ios').")
    
class AudienceCreateResponse(BaseModel):
    container_id: str = Field(..., description="The unique ID created by the Partner (you) to reference this specific audience container.")

# 3. /Sync Models
class AudienceSyncRequest(BaseAudienceRequest):
    container_id: str = Field(..., description="The unique ID of the audience container created during the /create call.")
    url_adid_sha256: Optional[str] = Field(None, description="Pre-signed AWS URL to download the SHA256 hashed ADID/IDFA file.")
    url_email_sha256: Optional[str] = Field(None, description="Pre-signed AWS URL to download the SHA256 hashed Email file.")
    url_phone_sha256: Optional[str] = Field(None, description="Pre-signed AWS URL to download the SHA256 hashed Phone Number file.")
    # Add other potential URL identifiers as needed

class AudienceSyncResponse(BaseModel):
    message: str = "Sync request successfully received and initiated."
    details: str = "Download process acknowledged. File download must be completed within 2 hours."

# ====================================================================
# 1. /Validate Endpoint (POST)
# ====================================================================

@router.post(
    "/validate", 
    # REMOVED: dependencies=[Depends(verify_partner_api_key)]
    summary="1. Validate Advertiser API Key (in Body)",
    description="AppsFlyer calls this once to validate the API key supplied in the request body. Returns 401 if invalid.",
    response_model=Dict[str, str],
    status_code=200
)
async def validate_audience_connection(
    request_data: AudienceValidateRequest = Body(
        ...,
        example={"api_key": "d41ac239b3b918e28fa0c"} # Example does not reveal your actual key
    )
):
    # API Key validation now happens inside the function, checking the body field
    validate_api_key(request_data.api_key)
    
    return {"status": "success", "message": "API Key is valid."}

# ====================================================================
# 2. /Create Endpoint (POST)
# ====================================================================

@router.post(
    "/create", 
    # REMOVED: dependencies=[Depends(verify_partner_api_key)]
    summary="2. Create Audience Container",
    description="AppsFlyer calls this once per new audience. MUST return a 200 response containing the generated 'container_id'.",
    response_model=AudienceCreateResponse,
    status_code=200
)
async def create_audience_sync(
    request_data: AudienceCreateRequest = Body(
        ..., 
        example={
            "api_key": "d41ac239b3b918e28fa0c", # Example does not reveal your actual key
            "name": "High-Value Users - Android",
            "platform": "android"
        }
    )
):
    # API Key validation now happens inside the function
    validate_api_key(request_data.api_key)
    
    # 1. Generate a unique ID for the container
    new_container_id = str(uuid.uuid4())
    
    # 2. Store the container mapping (simulating DB insertion)
    containers = _load_containers()
    containers[new_container_id] = {
        "name": request_data.name,
        "platform": request_data.platform,
        "created_at": str(os.path.getmtime(CONTAINER_STORE_FILE)) 
    }
    _save_containers(containers)
    
    # 3. Return the generated container ID 
    return {"container_id": new_container_id}

# ====================================================================
# 3. /Sync Endpoint (POST)
# ====================================================================

@router.post(
    "/sync", 
    # REMOVED: dependencies=[Depends(verify_partner_api_key)]
    summary="3. Initiate Audience Data Sync",
    description="AppsFlyer calls this for daily/manual uploads. The body contains the container_id and pre-signed AWS URLs.",
    response_model=AudienceSyncResponse,
    status_code=200
)
async def sync_audience_data(
    request_data: AudienceSyncRequest = Body(
        ...,
        example={
            "api_key": "d41ac239b3b918e28fa0c", # Example does not reveal your actual key
            "container_id": "a1b2c3d4-e5f6-7890-abcd-ef0123456789",
            "url_adid_sha256": "https://audiencespull.appsflyer.com/{{PARTNER_PULL_KEY}}/file_1.csv?X-Amz...",
        }
    )
):
    # API Key validation now happens inside the function
    validate_api_key(request_data.api_key)

    # 1. Check if the container ID exists
    containers = _load_containers()
    if request_data.container_id not in containers:
        raise HTTPException(status_code=404, detail=f"Container ID '{request_data.container_id}' not found.")

    # 2. Log or initiate the file download process
    urls_received = {k: v for k, v in request_data.model_dump().items() if k.startswith('url_') and v is not None}
    
    print(f"--- SYNC INITIATED for Container: {request_data.container_id} ---")
    print(f"URLs to download: {json.dumps(urls_received, indent=2)}")

    # 3. Return 200 OK immediately
    return AudienceSyncResponse()