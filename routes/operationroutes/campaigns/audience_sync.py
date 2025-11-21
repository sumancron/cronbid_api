from fastapi import APIRouter, HTTPException, Body, Response
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
from fastapi import APIRouter, HTTPException, Body, Request
from pydantic import BaseModel, Field
import json
import os
import uuid
from typing import Optional, Dict, List, Any
from datetime import datetime # datetime is needed for timestamping

router = APIRouter()

# --- PARTNER API KEY CONFIGURATION ---
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
        
def get_sync_data_file_path(container_id: str) -> str:
    """Generates the file path for the container's sync history."""
    return os.path.join(SYNC_DATA_DIR, f"{container_id}_sync_data.json")

def _load_sync_data(container_id: str) -> Dict[str, Any]:
    """Loads a specific container's sync history."""
    file_path = get_sync_data_file_path(container_id)
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Return an empty structure if the file doesn't exist or is corrupt
        return {"container_id": container_id, "sync_history": []}

def _save_sync_data(container_id: str, data: Dict[str, Any]):
    """Saves a specific container's sync history."""
    file_path = get_sync_data_file_path(container_id)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

# --- API KEY VALIDATION LOGIC ---

def validate_api_key(received_key: str):
    """Checks the API key (Keeping it for validate/create but skipping it for sync)."""
    if received_key != PARTNER_AUDIENCE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key for authentication.")
    return True

# --- Pydantic Models (Kept for /validate and /create documentation) ---

class BaseAudienceRequest(BaseModel):
    api_key: str = Field(..., description="The unique API key issued to the advertiser.", example="d41ac239b3b918e28fa0c") 

class AudienceValidateRequest(BaseAudienceRequest):
    pass
    
class AudienceCreateRequest(BaseAudienceRequest):
    name: str = Field(..., description="The unique name of the audience.")
    platform: Optional[str] = Field(None, description="The platform (e.g., 'android', 'ios').")
    
class AudienceCreateResponse(BaseModel):
    container_id: str = Field(..., description="The unique ID created by the Partner (you).")

class AudienceSyncRequest(BaseAudienceRequest):
    container_id: str = Field(..., description="The unique ID of the audience container.")
    url_adid_sha256: Optional[str] = Field(None, description="Pre-signed AWS URL for ADID/IDFA file.")
    url_email_sha256: Optional[str] = Field(None, description="Pre-signed AWS URL for Email file.")
    url_phone_sha256: Optional[str] = Field(None, description="Pre-signed AWS URL for Phone Number file.")

class AudienceSyncResponse(BaseModel):
    message: str = "Sync request successfully received and initiated."
    details: str = "Download process acknowledged. File download must be completed within 2 hours."


# ====================================================================
# 1. /Validate Endpoint (POST) - (Untouched)
# ====================================================================

@router.post(
    "/validate", 
    summary="1. Validate Advertiser API Key (in Body)",
    description="AppsFlyer calls this once to validate the API key supplied in the request body. Returns 401 if invalid.",
    response_model=Dict[str, str],
    status_code=200
)
async def validate_audience_connection(
    request_data: AudienceValidateRequest = Body(
        ...,
        example={"api_key": "d41ac239b3b918e28fa0c"}
    )
):
    validate_api_key(request_data.api_key)
    return {"status": "success", "message": "API Key is valid."}

# ====================================================================
# 2. /Create Endpoint (POST) - (Untouched)
# ====================================================================

@router.post(
    "/create", 
    summary="2. Create Audience Container",
    description="AppsFlyer calls this once per new audience. MUST return a 200 response containing the generated 'container_id'.",
    response_model=AudienceCreateResponse,
    status_code=200
)
async def create_audience_sync(
    request_data: AudienceCreateRequest = Body(
        ..., 
        example={
            "api_key": "d41ac239b3b918e28fa0c",
            "name": "High-Value Users - Android",
            "platform": "android"
        }
    )
):
    validate_api_key(request_data.api_key)
    
    new_container_id = str(uuid.uuid4())
    
    containers = _load_containers()
    containers[new_container_id] = {
        "name": request_data.name,
        "platform": request_data.platform,
        "created_at": str(datetime.now().isoformat()) # Using datetime.now() for consistency
    }
    _save_containers(containers)
    
    # Create the initial sync history file
    _save_sync_data(new_container_id, {"container_id": new_container_id, "sync_history": []})
    
    return {"container_id": new_container_id}

# ====================================================================
# 3. /Sync Endpoint (POST) - (REWRITTEN FOR ROBUSTNESS)
# ====================================================================

@router.post(
    "/sync", 
    summary="3. Initiate Audience Data Sync (Fault-Tolerant)",
    description="Accepts ANY payload. Ignores authentication errors and aims for 200 OK. Attempts to save payload to container file or a generic log file.",
    response_model=AudienceSyncResponse,
    status_code=200
)
async def sync_audience_data(request: Request):
    
    current_time = datetime.now().isoformat()
    container_id = None
    payload = None
    
    # 1. Attempt to read JSON body and extract identifier
    try:
        # Read the body fully
        raw_body = await request.body()
        
        # Try to decode the JSON
        payload = json.loads(raw_body.decode('utf-8'))
        
        # If successful, try to find the container_id (the key to file saving)
        container_id = payload.get("container_id")
        
    except json.JSONDecodeError:
        # If JSON decoding fails (e.g., non-JSON data, corrupted payload)
        payload = {"error": "JSON_DECODE_FAILED", "raw_bytes_size": len(raw_body)}
    except Exception as e:
        # Catch any other reading errors
        payload = {"error": f"REQUEST_READ_FAILED: {str(e)}"}

    # --- File/Data Saving Logic ---
    
    containers = _load_containers()
    
    if container_id in containers:
        # Case A: Container is valid. Save payload to its dedicated history file.
        
        sync_data = _load_sync_data(container_id)
        
        # Determine the URLs received (safe check)
        urls_received = {}
        if payload and isinstance(payload, dict):
            urls_received = {k: v for k, v in payload.items() if k.startswith('url_') and v is not None}
            
        sync_data["sync_history"].append({
            "timestamp": current_time,
            "status": "Updated",
            "payload_type": "Recognized Container",
            "urls_received": urls_received,
            "full_payload": payload
        })
        
        try:
            _save_sync_data(container_id, sync_data)
            message = f"Sync successful. Container ID '{container_id}' file updated."
        except Exception as e:
            message = f"Sync received. File update failed for ID '{container_id}'. Error: {str(e)}"
    
    else:
        # Case B: Container ID is missing or unrecognized. Save data to a generic log file.
        
        # Use a unique identifier for the log file
        log_identifier = f"unrecognized_sync_{uuid.uuid4().hex}"
        log_file_path = os.path.join(SYNC_DATA_DIR, f"{log_identifier}.json")
        
        log_data = {
            "timestamp": current_time,
            "received_container_id": container_id,
            "status": "Unrecognized/Missing ID",
            "full_payload": payload
        }
        
        try:
            with open(log_file_path, 'w') as f:
                json.dump(log_data, f, indent=4)
            message = f"Sync received. ID unrecognized/missing. Data logged to file: {log_identifier}.json"
        except Exception as e:
            message = f"Sync received. Failed to log data to disk. Error: {str(e)}"

    print(f"[{current_time}] SYNC OPERATION COMPLETED. Result: {message}")
    
    # 3. Always return 200 OK and AudienceSyncResponse
    return AudienceSyncResponse(message=message)

# NOTE: The dependency on validate_api_key has been removed from the function signature
# and is not called inside the sync_audience_data body, fulfilling the requirement 
# to bypass the 401 Unauthorized error completely.


# Global constants needed by the function
SYNC_DATA_DIR = "sync_data/partner_audiences"

# --- Function to read the content of any JSON file ---
def _read_file_content(file_path: str) -> Any:
    """Safely reads JSON content or returns raw text."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        try:
            # Try to parse as JSON first
            return json.loads(content)
        except json.JSONDecodeError:
            # If not JSON, return as plain text
            return content
    except Exception as e:
        return {"error": f"Failed to read file: {str(e)}"}

# --- THE UNSECURED INTERNAL API ENDPOINT ---

@router.get(
    "/internal/data-viewer/{filename:path}",
    summary="Unsecured File & Directory Viewer (DANGEROUS: Internal Use ONLY)",
    description="Lists all files in the sync directory. If a filename is specified, returns its content. NO AUTHENTICATION REQUIRED.",
    response_class=Response # Allow flexible response type (HTML or JSON)
)
async def unsecured_sync_data_viewer(filename: Optional[str] = None):
    
    # Base directory must be relative to the running script
    if not os.path.exists(SYNC_DATA_DIR):
        raise HTTPException(status_code=404, detail="Sync data directory not found.")

    # --- Case 2: View specific file content ---
    if filename:
        # Sanitize path to prevent directory traversal attacks (though the whole API is unsecured)
        # We ensure the file is strictly inside SYNC_DATA_DIR
        file_path = os.path.normpath(os.path.join(SYNC_DATA_DIR, filename))
        
        # Check if the file path tries to escape the base directory
        if not file_path.startswith(os.path.normpath(SYNC_DATA_DIR)):
            raise HTTPException(status_code=400, detail="Invalid path access attempt.")
        
        if not os.path.isfile(file_path):
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")
        
        content = _read_file_content(file_path)

        # Return JSON if content is parsed as JSON, otherwise return plain text
        if isinstance(content, dict) or isinstance(content, list):
            return Response(content=json.dumps(content, indent=4), media_type="application/json")
        else:
            return Response(content=str(content), media_type="text/plain")
            
    # --- Case 1: List all files in the directory (Default view) ---
    else:
        try:
            files = os.listdir(SYNC_DATA_DIR)
            
            # Create a simple HTML list view for browser compatibility
            html_content = f"<html><head><title>Internal Sync Data Viewer</title></head><body>"
            html_content += f"<h1>Contents of {SYNC_DATA_DIR}</h1><ul>"
            
            for file in sorted(files):
                if os.path.isfile(os.path.join(SYNC_DATA_DIR, file)):
                    # Link points back to this same API endpoint with the filename appended
                    html_content += f'<li><a href="/internal/data-viewer/{file}">{file}</a></li>'
            
            html_content += "</ul></body></html>"
            
            return Response(content=html_content, media_type="text/html")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list directory contents: {str(e)}")