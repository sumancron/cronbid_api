from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime
import uuid
import json
import os
import threading
import requests

# =====================================================
# ROUTER (🔥 THIS FIXES YOUR ERROR)
# =====================================================

router = APIRouter(prefix="/audiences", tags=["Audience Sync Integration"])

# =====================================================
# CONFIG
# =====================================================

PARTNER_API_KEY = "787febebhevdhhvedh787dederrr"

BASE_DIR = "app/data"
SYNC_LOG_DIR = f"{BASE_DIR}/sync_logs"
CSV_DIR = f"{BASE_DIR}/csv_files"
CONTAINERS_FILE = f"{BASE_DIR}/containers.json"

os.makedirs(SYNC_LOG_DIR, exist_ok=True)
os.makedirs(CSV_DIR, exist_ok=True)
os.makedirs(BASE_DIR, exist_ok=True)

if not os.path.exists(CONTAINERS_FILE):
    with open(CONTAINERS_FILE, "w") as f:
        json.dump({}, f)

# =====================================================
# AUTH
# =====================================================

def verify_api_key(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.replace("Bearer ", "")
    if token != PARTNER_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

# =====================================================
# STORAGE HELPERS
# =====================================================

def load_containers() -> Dict[str, Dict]:
    with open(CONTAINERS_FILE, "r") as f:
        return json.load(f)

def save_containers(data: Dict[str, Dict]):
    with open(CONTAINERS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def save_sync_log(container_id: str, log: Dict):
    path = f"{SYNC_LOG_DIR}/{container_id}.json"

    if os.path.exists(path):
        with open(path, "r") as f:
            existing = json.load(f)
    else:
        existing = {"container_id": container_id, "syncs": []}

    existing["syncs"].append(log)

    with open(path, "w") as f:
        json.dump(existing, f, indent=4)

# =====================================================
# BACKGROUND CSV DOWNLOAD
# =====================================================

def download_csv(url: str, filename: str):
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()

        with open(filename, "wb") as f:
            f.write(r.content)

        print(f"[DOWNLOADED] {filename}")
    except Exception as e:
        print(f"[DOWNLOAD FAILED] {url} -> {e}")

def background_download(container_id: str, urls: Dict[str, str]):
    for key, url in urls.items():
        if not url:
            continue

        filename = f"{CSV_DIR}/{container_id}_{key}.csv"
        download_csv(url, filename)

# =====================================================
# MODELS
# =====================================================

class CreateAudienceRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    platform: Optional[str] = None

class CreateAudienceResponse(BaseModel):
    container_id: str

class SyncRequest(BaseModel):
    container_id: str
    url_adid_sha256: Optional[str] = None
    url_email_sha256: Optional[str] = None
    url_phone_sha256: Optional[str] = None

class SyncResponse(BaseModel):
    message: str
    details: str

# =====================================================
# ENDPOINTS
# =====================================================

@router.post("/validate")
async def validate_connection(_: None = Depends(verify_api_key)):
    return {"status": "success"}

@router.post("/create", response_model=CreateAudienceResponse)
async def create_audience(
    data: CreateAudienceRequest,
    _: None = Depends(verify_api_key)
):
    container_id = str(uuid.uuid4())

    containers = load_containers()
    containers[container_id] = {
        "name": data.name,
        "platform": data.platform,
        "created_at": datetime.utcnow().isoformat()
    }

    save_containers(containers)
    return {"container_id": container_id}

@router.post("/sync", response_model=SyncResponse)
async def sync_audience(
    data: SyncRequest,
    _: None = Depends(verify_api_key)
):
    containers = load_containers()

    if data.container_id not in containers:
        return SyncResponse(
            message="Container not found",
            details="Sync ignored"
        )

    urls = {
        "adid": data.url_adid_sha256,
        "email": data.url_email_sha256,
        "phone": data.url_phone_sha256
    }

    save_sync_log(data.container_id, {
        "timestamp": datetime.utcnow().isoformat(),
        "urls_received": urls
    })

    threading.Thread(
        target=background_download,
        args=(data.container_id, urls),
        daemon=True
    ).start()

    return SyncResponse(
        message="Sync received successfully",
        details="Files downloading in background"
    )
