from fastapi import APIRouter, HTTPException, Body, Request, BackgroundTasks, Cookie
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from pydantic import BaseModel, Field
import json
import os
import uuid
import aiohttp
import asyncio
import csv
from typing import Optional, Dict, List, Any
from datetime import datetime
import hashlib

router = APIRouter()

# === CONFIGURATION ===
PARTNER_AUDIENCE_API_KEY = "787febebhevdhhvedh787dederrr"
PARTNER_PULL_KEY = "uerm7ilkmjw1ek"

# === LOGIN CREDENTIALS ===
DASHBOARD_USERNAME = "filtercoffe"
DASHBOARD_PASSWORD = "d0wn10ad9"

# === ABSOLUTE PATHS (Works in both localhost and production) ===
# Get the directory where this file is located, then navigate to project root
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SYNC_DATA_DIR = os.path.join(SCRIPT_DIR, "sync_data", "partner_audiences")
CSV_STORAGE_DIR = os.path.join(SCRIPT_DIR, "csv_storage")
CONTAINER_STORE_FILE = os.path.join(SYNC_DATA_DIR, "containers.json")
SYNC_HISTORY_FILE = os.path.join(SYNC_DATA_DIR, "sync_history.json")

# === AUTO-CREATE DIRECTORIES ON STARTUP ===
os.makedirs(SYNC_DATA_DIR, exist_ok=True)
os.makedirs(CSV_STORAGE_DIR, exist_ok=True)

if not os.path.exists(CONTAINER_STORE_FILE):
    with open(CONTAINER_STORE_FILE, "w") as f:
        json.dump({}, f)

if not os.path.exists(SYNC_HISTORY_FILE):
    with open(SYNC_HISTORY_FILE, "w") as f:
        json.dump([], f)

# === STORAGE UTILITY FUNCTIONS ===


def _load_containers() -> Dict[str, Dict]:
    """Loads all container mappings from the local JSON file."""
    try:
        with open(CONTAINER_STORE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_containers(data: Dict[str, Dict]):
    """Saves the container mappings to the local JSON file."""
    with open(CONTAINER_STORE_FILE, "w") as f:
        json.dump(data, f, indent=4)


def _load_sync_history() -> List[Dict[str, Any]]:
    """Loads the global sync history."""
    try:
        with open(SYNC_HISTORY_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_sync_history(data: List[Dict[str, Any]]):
    """Saves the global sync history."""
    with open(SYNC_HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)


# === API KEY VALIDATION ===


def validate_api_key(received_key: str):
    """Validates the API key (correct implementation - do not modify)."""
    if received_key != PARTNER_AUDIENCE_API_KEY:
        raise HTTPException(
            status_code=401, detail="Invalid API key for authentication."
        )
    return True


def verify_dashboard_login(auth_token: Optional[str] = Cookie(None)):
    """Verifies if user has valid dashboard authentication token."""
    if not auth_token or auth_token != "authenticated":
        return False
    return True


# === PYDANTIC MODELS ===


class BaseAudienceRequest(BaseModel):
    api_key: str = Field(
        ...,
        description="The unique API key issued to the advertiser.",
        example="d41ac239b3b918e28fa0c",
    )


class AudienceValidateRequest(BaseAudienceRequest):
    pass


class AudienceCreateRequest(BaseAudienceRequest):
    name: str = Field(..., description="The unique name of the audience.")
    platform: Optional[str] = Field(
        None, description="The platform (e.g., 'android', 'ios')."
    )


class AudienceCreateResponse(BaseModel):
    container_id: str = Field(..., description="The unique ID created by the Partner.")


class AudienceSyncRequest(BaseAudienceRequest):
    container_id: str = Field(
        ..., description="The unique ID of the audience container."
    )
    url_adid_sha256: Optional[str] = Field(
        None, description="Pre-signed AWS URL for ADID/IDFA file."
    )
    url_email_sha256: Optional[str] = Field(
        None, description="Pre-signed AWS URL for Email file."
    )
    url_phone_sha256: Optional[str] = Field(
        None, description="Pre-signed AWS URL for Phone Number file."
    )


class AudienceSyncResponse(BaseModel):
    message: str = "Sync request successfully received and initiated."
    details: str = (
        "Download process acknowledged. File download must be completed within 2 hours."
    )


# === BACKGROUND TASK FOR DOWNLOADING CSV ===


async def process_sync_download(container_id: str, urls: Dict[str, str], sync_id: str):
    """
    Background task to download CSV files asynchronously.
    Replaces {{PARTNER_PULL_KEY}} in URLs and saves files to csv_storage/.
    """
    sync_history = _load_sync_history()
    sync_entry = None

    for entry in sync_history:
        if entry["sync_id"] == sync_id:
            sync_entry = entry
            break

    if not sync_entry:
        return

    total_rows_downloaded = 0

    try:
        async with aiohttp.ClientSession() as session:
            for url_type, url in urls.items():
                if not url:
                    continue

                # Replace placeholder with actual PARTNER_PULL_KEY
                actual_url = url.replace("{{PARTNER_PULL_KEY}}", PARTNER_PULL_KEY)

                try:
                    async with session.get(
                        actual_url, timeout=aiohttp.ClientTimeout(total=7200)
                    ) as response:
                        if response.status == 200:
                            content = await response.text()

                            # Count rows (excluding header)
                            lines = content.strip().split("\n")
                            row_count = len(lines) - 1 if len(lines) > 0 else 0
                            total_rows_downloaded += row_count

                            # Save CSV to storage
                            filename = f"{container_id}_{url_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                            filepath = os.path.join(CSV_STORAGE_DIR, filename)

                            with open(filepath, "w", encoding="utf-8") as f:
                                f.write(content)

                            sync_entry["downloaded_files"].append(
                                {
                                    "type": url_type,
                                    "filename": filename,
                                    "rows": row_count,
                                }
                            )
                        else:
                            sync_entry["errors"].append(
                                f"{url_type}: HTTP {response.status}"
                            )

                except asyncio.TimeoutError:
                    sync_entry["errors"].append(
                        f"{url_type}: Download timeout (exceeded 2 hours)"
                    )
                except Exception as e:
                    sync_entry["errors"].append(f"{url_type}: {str(e)}")

        sync_entry["status"] = (
            "Success" if len(sync_entry["errors"]) == 0 else "Partial"
        )
        sync_entry["total_rows_downloaded"] = total_rows_downloaded

    except Exception as e:
        sync_entry["status"] = "Failed"
        sync_entry["errors"].append(f"Background process error: {str(e)}")

    sync_entry["completed_at"] = datetime.now().isoformat()
    _save_sync_history(sync_history)


# === ENDPOINTS ===


@router.post(
    "/validate",
    summary="1. Validate Advertiser API Key (in Body)",
    description="AppsFlyer calls this once to validate the API key.",
    response_model=Dict[str, str],
    status_code=200,
)
async def validate_audience_connection(
    request_data: AudienceValidateRequest = Body(
        ..., example={"api_key": "d41ac239b3b918e28fa0c"}
    )
):
    """Validates the advertiser API key."""
    validate_api_key(request_data.api_key)
    return {"status": "success", "message": "API Key is valid."}


@router.post(
    "/create",
    summary="2. Create Audience Container",
    description="AppsFlyer calls this once per new audience. Returns a container_id.",
    response_model=AudienceCreateResponse,
    status_code=200,
)
async def create_audience_sync(
    request_data: AudienceCreateRequest = Body(
        ...,
        example={
            "api_key": "d41ac239b3b918e28fa0c",
            "name": "High-Value Users - Android",
            "platform": "android",
        },
    )
):
    """Creates a new audience container."""
    validate_api_key(request_data.api_key)

    new_container_id = str(uuid.uuid4())

    containers = _load_containers()
    containers[new_container_id] = {
        "name": request_data.name,
        "platform": request_data.platform,
        "created_at": datetime.now().isoformat(),
    }
    _save_containers(containers)

    return {"container_id": new_container_id}


@router.post(
    "/sync",
    summary="3. Initiate Audience Data Sync (With Background Processing)",
    description="Returns 200 OK immediately. Downloads files asynchronously in background.",
    response_model=AudienceSyncResponse,
    status_code=200,
)
async def sync_audience_data(request: Request, background_tasks: BackgroundTasks):
    """
    Receives sync signal, returns 200 OK immediately.
    Queues background task to download and process CSV files.
    """
    current_time = datetime.now().isoformat()
    container_id = None
    payload = None
    sync_id = str(uuid.uuid4())

    # Parse the JSON request body
    try:
        raw_body = await request.body()
        payload = json.loads(raw_body.decode("utf-8"))
        container_id = payload.get("container_id")
    except Exception as e:
        payload = {"error": f"Failed to parse request: {str(e)}"}

    # Create sync history entry
    containers = _load_containers()
    container_exists = container_id in containers if container_id else False

    sync_entry = {
        "sync_id": sync_id,
        "timestamp": current_time,
        "container_id": container_id,
        "container_exists": container_exists,
        "status": "Pending",
        "downloaded_files": [],
        "errors": [],
        "total_rows_downloaded": 0,
        "completed_at": None,
    }

    sync_history = _load_sync_history()
    sync_history.append(sync_entry)
    _save_sync_history(sync_history)

    # Queue background task if container is valid
    if container_exists and payload:
        urls_to_download = {
            "adid": payload.get("url_adid_sha256"),
            "email": payload.get("url_email_sha256"),
            "phone": payload.get("url_phone_sha256"),
        }
        urls_to_download = {k: v for k, v in urls_to_download.items() if v}

        background_tasks.add_task(
            process_sync_download, container_id, urls_to_download, sync_id
        )

    return AudienceSyncResponse(
        message="Sync request successfully received and initiated.",
        details="Download process acknowledged. File download must be completed within 2 hours.",
    )


@router.post("/login")
async def login(request: Request):
    """Handles dashboard login."""
    try:
        body = await request.json()
        username = body.get("username", "")
        password = body.get("password", "")

        if username == DASHBOARD_USERNAME and password == DASHBOARD_PASSWORD:
            return {"success": True, "message": "Login successful"}
        else:
            return {"success": False, "message": "Invalid credentials"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/logout")
async def logout():
    """Logs out user by clearing session cookie."""
    response = RedirectResponse(url="/audience-sync/dashboard-login")
    response.delete_cookie("auth_token")
    return response


@router.get("/dashboard-login")
async def dashboard_login_page(auth_token: Optional[str] = Cookie(None)):
    """Shows login page if not authenticated."""
    if auth_token == "authenticated":
        return RedirectResponse(url="/audience-sync/dashboard")

    return HTMLResponse(content=_get_login_page())


@router.get(
    "/dashboard",
    summary="Dashboard - Sync History & Data Viewer",
    description="Displays sync history and allows viewing downloaded CSV data.",
    responses={200: {"content": {"text/html": {}}}},
)
async def dashboard(auth_token: Optional[str] = Cookie(None)):
    """Renders the dashboard HTML with sync history and data viewer."""
    # Check authentication
    if auth_token != "authenticated":
        return RedirectResponse(url="/audience-sync/dashboard-login")

    sync_history = _load_sync_history()
    containers = _load_containers()

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cronbid - Audience Sync Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f8fafb;
            min-height: 100vh;
            padding: 0;
        }}
        
        .header {{
            background: white;
            border-bottom: 1px solid #e5e7eb;
            padding: 16px 0;
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        
        .header-content {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 64px;
        }}
        
        .logo-section {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .logo {{
            height: 36px;
            width: auto;
            background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
            padding: 4px 8px;
            border-radius: 6px;
            filter: brightness(0) invert(1);
        }}
        
        .header-title {{
            font-size: 16px;
            font-weight: 600;
            color: #1f2937;
            letter-spacing: -0.5px;
        }}
        
        .logout-btn {{
            padding: 8px 16px;
            background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
            box-shadow: 0 2px 6px rgba(6, 182, 212, 0.2);
        }}
        
        .logout-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(6, 182, 212, 0.3);
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 32px 24px;
        }}
        
        .page-header {{
            margin-bottom: 32px;
        }}
        
        .page-title {{
            font-size: 24px;
            font-weight: 700;
            color: #111827;
            margin-bottom: 8px;
            letter-spacing: -0.6px;
        }}
        
        .page-subtitle {{
            font-size: 14px;
            color: #6b7280;
            font-weight: 400;
        }}
        
        .dashboard-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 24px;
        }}
        
        .card {{
            background: white;
            border-radius: 12px;
            border: 1px solid #e5e7eb;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
            transition: box-shadow 0.2s ease;
        }}
        
        .card:hover {{
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }}
        
        .card-title {{
            font-size: 16px;
            font-weight: 600;
            color: #111827;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 2px solid #f3f4f6;
            letter-spacing: -0.3px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 0;
        }}
        
        .stat-box {{
            background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 12px rgba(6, 182, 212, 0.2);
            transition: transform 0.2s ease;
        }}
        
        .stat-box:hover {{
            transform: translateY(-4px);
        }}
        
        .stat-value {{
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 6px;
            letter-spacing: -0.5px;
        }}
        
        .stat-label {{
            font-size: 12px;
            opacity: 0.9;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .table-wrapper {{
            overflow-x: auto;
        }}
        
        .sync-history-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        
        .sync-history-table thead {{
            background: #f9fafb;
            border-bottom: 2px solid #e5e7eb;
        }}
        
        .sync-history-table th {{
            padding: 14px 16px;
            text-align: left;
            font-weight: 600;
            color: #374151;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }}
        
        .sync-history-table td {{
            padding: 14px 16px;
            border-bottom: 1px solid #f3f4f6;
            color: #4b5563;
            font-weight: 400;
        }}
        
        .sync-history-table tbody tr {{
            transition: background-color 0.15s ease;
        }}
        
        .sync-history-table tbody tr:hover {{
            background: #f9fafb;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 6px;
            font-weight: 500;
            font-size: 11px;
            text-transform: capitalize;
            letter-spacing: 0.3px;
        }}
        
        .status-success {{
            background: #d1fae5;
            color: #065f46;
        }}
        
        .status-pending {{
            background: #fed7aa;
            color: #92400e;
        }}
        
        .status-failed {{
            background: #fee2e2;
            color: #991b1b;
        }}
        
        .status-partial {{
            background: #dbeafe;
            color: #1e40af;
        }}
        
        .action-btn {{
            padding: 8px 14px;
            font-size: 12px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
            color: white;
            font-weight: 500;
            transition: all 0.2s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 2px 6px rgba(6, 182, 212, 0.2);
        }}
        
        .action-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(6, 182, 212, 0.3);
        }}
        
        .action-btn:active {{
            transform: translateY(0);
        }}
        
        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: #9ca3af;
        }}
        
        .empty-state-text {{
            font-size: 14px;
            color: #6b7280;
        }}
        
        .modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        
        .modal.active {{
            display: flex;
        }}
        
        .modal-content {{
            background: white;
            border-radius: 12px;
            max-width: 1000px;
            max-height: 85vh;
            overflow-y: auto;
            padding: 32px;
            position: relative;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
        }}
        
        .modal-close {{
            position: absolute;
            top: 16px;
            right: 16px;
            background: none;
            border: none;
            font-size: 28px;
            cursor: pointer;
            color: #d1d5db;
            width: 36px;
            height: 36px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 6px;
            transition: all 0.2s ease;
        }}
        
        .modal-close:hover {{
            background: #f3f4f6;
            color: #6b7280;
        }}
        
        .modal-title {{
            font-size: 18px;
            font-weight: 700;
            color: #111827;
            margin-bottom: 16px;
            letter-spacing: -0.3px;
        }}
        
        .modal-info {{
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f7ff 100%);
            padding: 14px 16px;
            border-radius: 8px;
            margin-bottom: 16px;
            font-size: 12px;
            color: #0369a1;
            border: 1px solid #cffafe;
        }}
        
        .download-btn {{
            display: inline-block;
            padding: 10px 20px;
            background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 13px;
            margin-bottom: 16px;
            transition: all 0.2s ease;
            box-shadow: 0 4px 12px rgba(6, 182, 212, 0.25);
            cursor: pointer;
            border: none;
        }}
        
        .download-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(6, 182, 212, 0.4);
        }}
        
        .csv-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            margin-top: 12px;
        }}
        
        .csv-table thead {{
            background: #f9fafb;
            border-bottom: 2px solid #e5e7eb;
        }}
        
        .csv-table th {{
            padding: 12px 14px;
            text-align: left;
            font-weight: 600;
            color: #374151;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }}
        
        .csv-table td {{
            padding: 10px 14px;
            border-bottom: 1px solid #f3f4f6;
            color: #4b5563;
            word-break: break-word;
        }}
        
        .csv-table tbody tr:hover {{
            background: #f9fafb;
        }}
        
        @media (max-width: 768px) {{
            .header-content {{
                padding: 0 16px;
            }}
            
            .container {{
                padding: 16px;
            }}
            
            .page-title {{
                font-size: 20px;
            }}
            
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            
            .modal-content {{
                padding: 20px;
            }}
            
            .sync-history-table {{
                font-size: 11px;
            }}
            
            .sync-history-table th,
            .sync-history-table td {{
                padding: 8px 10px;
            }}
        }}
    </style>
</head>
<body>
<header style="
    background: #0f172a; 
    color: white; 
    padding: 0.75rem 2rem; 
    display: flex; 
    align-items: center; 
    justify-content: center; 
    border-bottom: 1px solid rgba(255,255,255,0.1);
    font-family: 'Inter', sans-serif;
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
">
    <div style="
        width: 100%; 
        max-width: 1200px; 
        display: flex; 
        justify-content: space-between; 
        align-items: center;
    ">
        <div style="display: flex; align-items: center; gap: 15px;">
            <img src="https://ads.cronbid.com/cronbaylogo.png" 
                 alt="Cronbid" 
                 style="height: 35px; width: auto; filter: drop-shadow(0 0 4px rgba(255,255,255,0.2));">
            
            <div style="
                width: 1px; 
                height: 24px; 
                background: rgba(255,255,255,0.2);
            "></div>

            <div style="
                font-size: 1.2rem; 
                font-weight: 600; 
                letter-spacing: -0.02em;
                background: linear-gradient(to right, #fff, #94a3b8);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            ">Audience Sync</div>
        </div>

        <a href="/audience-sync/logout" style="
            text-decoration: none;
            color: #f1f5f9;
            font-size: 0.875rem;
            font-weight: 500;
            padding: 8px 16px;
            border-radius: 6px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            transition: all 0.2s ease;
        " onmouseover="this.style.background='rgba(255,255,255,0.1)'; this.style.borderColor='rgba(255,255,255,0.2)';" 
           onmouseout="this.style.background='rgba(255,255,255,0.05)'; this.style.borderColor='rgba(255,255,255,0.1)';">
           Sign Out
        </a>
    </div>
</header>
    
    <div class="container">
        <div class="page-header">
            <h1 class="page-title">Sync Dashboard</h1>
            <p class="page-subtitle">AppsFlyer Audience Integration - Real-time Sync History & Preview</p>
        </div>
        
        <div class="dashboard-grid">
            <!-- Stats Section -->
            <div class="card">
                <div class="card-title">Overview Statistics</div>
                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="stat-value">{len(sync_history)}</div>
                        <div class="stat-label">Total Syncs</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">{len([s for s in sync_history if s['status'] == 'Success'])}</div>
                        <div class="stat-label">Successful</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">{sum(s.get('total_rows_downloaded', 0) for s in sync_history):,}</div>
                        <div class="stat-label">Total Rows</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">{len(containers)}</div>
                        <div class="stat-label">Containers</div>
                    </div>
                </div>
            </div>
            
            <!-- Sync History Section -->
            <div class="card">
                <div class="card-title">Sync History</div>
                {_render_sync_history_table(sync_history) if sync_history else '<div class="empty-state"><p class="empty-state-text">No sync records available yet. Syncs will appear here when files are downloaded.</p></div>'}
            </div>
        </div>
    </div>
    
    <!-- Data Viewer Modal -->
    <div id="dataModal" class="modal">
        <div class="modal-content">
            <button class="modal-close" onclick="closeModal()">×</button>
            <h2 class="modal-title" id="modalTitle"></h2>
            <div id="modalInfo" class="modal-info"></div>
            <a id="downloadLink" href="#" class="download-btn" style="display: none;">Download Full File</a>
            <div id="modalBody"></div>
        </div>
    </div>
    
    <script>
        function viewData(filename) {{
            document.getElementById('dataModal').classList.add('active');
            document.getElementById('modalTitle').textContent = filename;
            document.getElementById('modalInfo').innerHTML = '<strong>Loading preview...</strong>';
            document.getElementById('modalBody').innerHTML = '';
            document.getElementById('downloadLink').style.display = 'none';
            
            fetch('/audience-sync/get-csv/' + filename)
                .then(response => response.json())
                .then(data => {{
                    if (data.error) {{
                        document.getElementById('modalBody').innerHTML = '<p style="color: #dc2626; font-weight: 500;">Error loading data: ' + data.error + '</p>';
                        document.getElementById('modalInfo').innerHTML = '';
                    }} else {{
                        const fileSize = data.file_size_mb || 0;
                        const previewCount = data.preview_count || 0;
                        const totalRows = previewCount === 1000 ? 'More than 1,000+' : previewCount;
                        
                        const infoHtml = `<strong>File Size:</strong> ${{fileSize}} MB &nbsp;&nbsp;|&nbsp;&nbsp; <strong>Preview:</strong> First 1,000 rows`;
                        document.getElementById('modalInfo').innerHTML = infoHtml;
                        
                        const downloadLink = document.getElementById('downloadLink');
                        downloadLink.href = '/audience-sync/download-csv/' + filename;
                        downloadLink.download = filename;
                        downloadLink.style.display = 'inline-block';
                        
                        const html = renderCsvTable(data.rows);
                        document.getElementById('modalBody').innerHTML = html;
                    }}
                }})
                .catch(error => {{
                    document.getElementById('modalBody').innerHTML = '<p style="color: #dc2626; font-weight: 500;">Failed to load preview data</p>';
                    document.getElementById('modalInfo').innerHTML = '';
                    document.getElementById('downloadLink').style.display = 'none';
                }});
        }}
        
        function closeModal() {{
            document.getElementById('dataModal').classList.remove('active');
        }}
        
        function renderCsvTable(rows) {{
            if (!rows || rows.length === 0) {{
                return '<p>No data available.</p>';
            }}
            
            let html = '<table class="csv-table"><thead><tr>';
            const headers = Object.keys(rows[0]);
            headers.forEach(header => {{
                html += '<th>' + escapeHtml(header) + '</th>';
            }});
            
            html += '</tr></thead><tbody>';
            rows.slice(0, 1000).forEach(row => {{
                html += '<tr>';
                headers.forEach(header => {{
                    html += '<td>' + escapeHtml(String(row[header] || '')) + '</td>';
                }});
                html += '</tr>';
            }});
            
            html += '</tbody></table>';
            
            if (rows.length > 1000) {{
                html += '<p style="color: #999; margin-top: 10px;">Showing 1000 of ' + rows.length + ' rows</p>';
            }}
            
            return html;
        }}
        
        function escapeHtml(text) {{
            const map = {{
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            }};
            return text.replace(/[&<>"']/g, m => map[m]);
        }}
        
        document.getElementById('dataModal').addEventListener('click', function(event) {{
            if (event.target === this) {{
                closeModal();
            }}
        }});
    </script>
</body>
</html>"""

    return HTMLResponse(content=html_content)


def _render_sync_history_table(sync_history: List[Dict]) -> str:
    """Renders the sync history table HTML with professional design."""
    html = '<div class="table-wrapper"><table class="sync-history-table"><thead><tr>'
    html += "<th>Time</th>"
    html += "<th>Container</th>"
    html += "<th>Status</th>"
    html += "<th>Rows</th>"
    html += "<th>Files</th>"
    html += "<th>Actions</th>"
    html += "</tr></thead><tbody>"

    for entry in reversed(sync_history):
        status = entry.get("status", "Unknown")
        status_class = f"status-{status.lower()}"

        timestamp = entry.get("timestamp", "N/A")
        if "T" in str(timestamp):
            timestamp = timestamp.split("T")[1][:5]  # HH:MM format

        container_id = entry.get("container_id", "N/A")
        if container_id != "N/A":
            container_id = container_id[:8] + "..."

        rows = entry.get("total_rows_downloaded", 0)
        files = entry.get("downloaded_files", [])

        files_html = ""
        action_html = ""
        if files:
            for f in files:
                files_html += f'<span style="display: inline-block; background: #f3f4f6; padding: 4px 8px; border-radius: 4px; margin-right: 6px; font-size: 11px;">{f["type"]}</span>'
                action_html += f'<a class="action-btn" onclick="viewData(\'{f["filename"]}\')">Preview</a>'
                action_html += f'<a class="action-btn" href="/audience-sync/download-csv/{f["filename"]}" download="{f["filename"]}">Download</a>'
        else:
            files_html = (
                '<span style="color: #9ca3af; font-size: 12px;">No files</span>'
            )
            action_html = '<span style="color: #9ca3af; font-size: 12px;">N/A</span>'

        html += f"<tr>"
        html += f"<td>{timestamp}</td>"
        html += f'<td><code style="background: #f3f4f6; padding: 4px 6px; border-radius: 3px; font-size: 11px;">{container_id}</code></td>'
        html += f'<td><span class="status-badge {status_class}">{status}</span></td>'
        html += f'<td style="font-weight: 500;">{rows:,}</td>'
        html += f"<td>{files_html}</td>"
        html += f"<td>{action_html}</td>"
        html += f"</tr>"

    html += "</tbody></table></div>"
    return html


def _get_login_page() -> str:
    """Returns the login page HTML."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cronbid - Audience Sync Login</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #f8fafb 0%, #e8f4f8 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .login-container {
            width: 100%;
            max-width: 380px;
        }
        
        .login-card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            padding: 40px;
        }
        
        .logo-section {
            text-align: center;
            margin-bottom: 32px;
        }
        
        .logo {
            height: 48px;
            width: auto;
            margin-bottom: 16px;
            filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
        }
        
        .title {
            font-size: 20px;
            font-weight: 700;
            color: #111827;
            margin-bottom: 8px;
            letter-spacing: -0.4px;
        }
        
        .subtitle {
            font-size: 13px;
            color: #6b7280;
            font-weight: 400;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            font-size: 12px;
            font-weight: 600;
            color: #374151;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.4px;
        }
        
        .form-group input {
            width: 100%;
            padding: 11px 14px;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            font-family: 'Inter', sans-serif;
            font-size: 14px;
            color: #111827;
            transition: all 0.2s ease;
        }
        
        .form-group input:focus {
            outline: none;
            border-color: #06b6d4;
            box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.1);
        }
        
        .login-btn {
            width: 100%;
            padding: 12px 16px;
            background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 4px 12px rgba(6, 182, 212, 0.25);
            font-family: 'Inter', sans-serif;
            margin-top: 8px;
        }
        
        .login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(6, 182, 212, 0.4);
        }
        
        .login-btn:active {
            transform: translateY(0);
        }
        
        .error-message {
            color: #dc2626;
            font-size: 12px;
            margin-top: 8px;
            display: none;
            font-weight: 500;
        }
        
        .loading {
            display: none;
        }
        
        .spinner {
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top: 2px solid white;
            border-radius: 50%;
            width: 16px;
            height: 16px;
            animation: spin 0.8s linear infinite;
            display: inline-block;
            margin-right: 8px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-card">
            <div class="logo-section">
                <img src="https://ads.cronbid.com/cronbaylogo.png" 
     alt="Cronbid" 
     style="background-color: #1a1a1a; padding: 10px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 200px;">
                <h1 class="title">Dashboard Access</h1>
                <p class="subtitle">Audience Sync Management</p>
            </div>
            
            <form id="loginForm" onsubmit="handleLogin(event)">
                <div class="form-group">
                    <label for="username">Username</label>
                    <input type="text" id="username" name="username" required autocomplete="username">
                </div>
                
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" id="password" name="password" required autocomplete="current-password">
                </div>
                
                <button type="submit" class="login-btn" id="loginBtn">Sign In</button>
                
                <div class="error-message" id="errorMsg"></div>
            </form>
        </div>
    </div>
    
    <script>
        async function handleLogin(event) {
            event.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const loginBtn = document.getElementById('loginBtn');
            const errorMsg = document.getElementById('errorMsg');
            
            loginBtn.disabled = true;
            loginBtn.innerHTML = '<span class="spinner"></span>Signing in...';
            errorMsg.style.display = 'none';
            
            try {
                const response = await fetch('/audience-sync/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ username, password })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Set cookie and redirect
                    document.cookie = "auth_token=authenticated; path=/; max-age=86400";
                    window.location.href = '/audience-sync/dashboard';
                } else {
                    errorMsg.textContent = data.message || 'Invalid username or password';
                    errorMsg.style.display = 'block';
                    loginBtn.disabled = false;
                    loginBtn.innerHTML = 'Sign In';
                }
            } catch (error) {
                errorMsg.textContent = 'An error occurred. Please try again.';
                errorMsg.style.display = 'block';
                loginBtn.disabled = false;
                loginBtn.innerHTML = 'Sign In';
            }
        }
        
        // Focus username field on load
        document.getElementById('username').focus();
    </script>
</body>
</html>"""


@router.get("/get-csv/{filename}")
async def get_csv_data(filename: str):
    """Returns first 1,000 rows of CSV as JSON preview (memory-efficient)."""
    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        return {"error": "Invalid filename"}

    # Construct full file path with absolute normalization
    filepath = os.path.abspath(os.path.join(CSV_STORAGE_DIR, filename))
    csv_storage_abs = os.path.abspath(CSV_STORAGE_DIR)
    
    # Ensure file path stays within csv_storage directory
    if not filepath.startswith(csv_storage_abs):
        return {"error": "Invalid file path"}

    if not os.path.isfile(filepath):
        return {"error": "File not found"}

    try:
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        rows = []
        row_count = 0

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row_count >= 1000:  # Limit to 1,000 rows for preview
                    break
                rows.append(row)
                row_count += 1

        return {
            "rows": rows,
            "preview_count": len(rows),
            "file_size_mb": round(file_size_mb, 2),
            "filename": filename,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/download-csv/{filename}")
async def download_csv_file(filename: str):
    """Streams full CSV file to user's computer (handles large files)."""
    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Construct full file path
    filepath = os.path.abspath(os.path.join(CSV_STORAGE_DIR, filename))
    csv_storage_abs = os.path.abspath(CSV_STORAGE_DIR)
    
    # Ensure the file path is within csv_storage directory
    if not filepath.startswith(csv_storage_abs):
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    # Check if file exists
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    
    try:
        # Return file with proper headers for download
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")
