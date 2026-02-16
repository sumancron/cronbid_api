from fastapi import APIRouter, HTTPException, Body, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import json
import os
import uuid
import aiohttp
import asyncio
import csv
from typing import Optional, Dict, List, Any
from datetime import datetime

router = APIRouter()

# === CONFIGURATION ===
PARTNER_AUDIENCE_API_KEY = "787febebhevdhhvedh787dederrr"
PARTNER_PULL_KEY = "uerm7ilkmjw1ek"

SYNC_DATA_DIR = "sync_data/partner_audiences"
CSV_STORAGE_DIR = "csv_storage"
CONTAINER_STORE_FILE = os.path.join(SYNC_DATA_DIR, "containers.json")
SYNC_HISTORY_FILE = os.path.join(SYNC_DATA_DIR, "sync_history.json")

# === AUTO-CREATE DIRECTORIES ON STARTUP ===
os.makedirs(SYNC_DATA_DIR, exist_ok=True)
os.makedirs(CSV_STORAGE_DIR, exist_ok=True)

if not os.path.exists(CONTAINER_STORE_FILE):
    with open(CONTAINER_STORE_FILE, 'w') as f:
        json.dump({}, f)

if not os.path.exists(SYNC_HISTORY_FILE):
    with open(SYNC_HISTORY_FILE, 'w') as f:
        json.dump([], f)

# === STORAGE UTILITY FUNCTIONS ===

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

def _load_sync_history() -> List[Dict[str, Any]]:
    """Loads the global sync history."""
    try:
        with open(SYNC_HISTORY_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def _save_sync_history(data: List[Dict[str, Any]]):
    """Saves the global sync history."""
    with open(SYNC_HISTORY_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# === API KEY VALIDATION ===

def validate_api_key(received_key: str):
    """Validates the API key (correct implementation - do not modify)."""
    if received_key != PARTNER_AUDIENCE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key for authentication.")
    return True

# === PYDANTIC MODELS ===

class BaseAudienceRequest(BaseModel):
    api_key: str = Field(..., description="The unique API key issued to the advertiser.", example="d41ac239b3b918e28fa0c")

class AudienceValidateRequest(BaseAudienceRequest):
    pass

class AudienceCreateRequest(BaseAudienceRequest):
    name: str = Field(..., description="The unique name of the audience.")
    platform: Optional[str] = Field(None, description="The platform (e.g., 'android', 'ios').")

class AudienceCreateResponse(BaseModel):
    container_id: str = Field(..., description="The unique ID created by the Partner.")

class AudienceSyncRequest(BaseAudienceRequest):
    container_id: str = Field(..., description="The unique ID of the audience container.")
    url_adid_sha256: Optional[str] = Field(None, description="Pre-signed AWS URL for ADID/IDFA file.")
    url_email_sha256: Optional[str] = Field(None, description="Pre-signed AWS URL for Email file.")
    url_phone_sha256: Optional[str] = Field(None, description="Pre-signed AWS URL for Phone Number file.")

class AudienceSyncResponse(BaseModel):
    message: str = "Sync request successfully received and initiated."
    details: str = "Download process acknowledged. File download must be completed within 2 hours."

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
                    async with session.get(actual_url, timeout=aiohttp.ClientTimeout(total=7200)) as response:
                        if response.status == 200:
                            content = await response.text()
                            
                            # Count rows (excluding header)
                            lines = content.strip().split('\n')
                            row_count = len(lines) - 1 if len(lines) > 0 else 0
                            total_rows_downloaded += row_count
                            
                            # Save CSV to storage
                            filename = f"{container_id}_{url_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                            filepath = os.path.join(CSV_STORAGE_DIR, filename)
                            
                            with open(filepath, 'w', encoding='utf-8') as f:
                                f.write(content)
                            
                            sync_entry["downloaded_files"].append({
                                "type": url_type,
                                "filename": filename,
                                "rows": row_count
                            })
                        else:
                            sync_entry["errors"].append(f"{url_type}: HTTP {response.status}")
                
                except asyncio.TimeoutError:
                    sync_entry["errors"].append(f"{url_type}: Download timeout (exceeded 2 hours)")
                except Exception as e:
                    sync_entry["errors"].append(f"{url_type}: {str(e)}")
        
        sync_entry["status"] = "Success" if len(sync_entry["errors"]) == 0 else "Partial"
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
    status_code=200
)
async def validate_audience_connection(
    request_data: AudienceValidateRequest = Body(
        ...,
        example={"api_key": "d41ac239b3b918e28fa0c"}
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
    """Creates a new audience container."""
    validate_api_key(request_data.api_key)
    
    new_container_id = str(uuid.uuid4())
    
    containers = _load_containers()
    containers[new_container_id] = {
        "name": request_data.name,
        "platform": request_data.platform,
        "created_at": datetime.now().isoformat()
    }
    _save_containers(containers)
    
    return {"container_id": new_container_id}

@router.post(
    "/sync",
    summary="3. Initiate Audience Data Sync (With Background Processing)",
    description="Returns 200 OK immediately. Downloads files asynchronously in background.",
    response_model=AudienceSyncResponse,
    status_code=200
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
        payload = json.loads(raw_body.decode('utf-8'))
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
        "completed_at": None
    }
    
    sync_history = _load_sync_history()
    sync_history.append(sync_entry)
    _save_sync_history(sync_history)
    
    # Queue background task if container is valid
    if container_exists and payload:
        urls_to_download = {
            'adid': payload.get('url_adid_sha256'),
            'email': payload.get('url_email_sha256'),
            'phone': payload.get('url_phone_sha256')
        }
        urls_to_download = {k: v for k, v in urls_to_download.items() if v}
        
        background_tasks.add_task(process_sync_download, container_id, urls_to_download, sync_id)
    
    return AudienceSyncResponse(
        message="Sync request successfully received and initiated.",
        details="Download process acknowledged. File download must be completed within 2 hours."
    )

@router.get(
    "/dashboard",
    summary="Dashboard - Sync History & Data Viewer",
    description="Displays sync history and allows viewing downloaded CSV data.",
    responses={200: {"content": {"text/html": {}}}}
)
async def dashboard():
    """Renders the dashboard HTML with sync history and data viewer."""
    sync_history = _load_sync_history()
    containers = _load_containers()
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audience Sync Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .header h1 {{
            color: #333;
            font-size: 28px;
            margin-bottom: 10px;
        }}
        
        .header p {{
            color: #666;
            font-size: 14px;
        }}
        
        .dashboard-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 20px;
        }}
        
        .card {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            padding: 20px;
        }}
        
        .card h2 {{
            color: #333;
            font-size: 18px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        
        .stat-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        
        .stat-box .value {{
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .stat-box .label {{
            font-size: 12px;
            opacity: 0.9;
        }}
        
        .sync-history-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        .sync-history-table thead {{
            background: #f7f7f7;
        }}
        
        .sync-history-table th {{
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #333;
            font-size: 13px;
            border-bottom: 2px solid #ddd;
        }}
        
        .sync-history-table td {{
            padding: 12px;
            border-bottom: 1px solid #eee;
            color: #666;
            font-size: 13px;
        }}
        
        .sync-history-table tr:hover {{
            background: #f9f9f9;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 12px;
        }}
        
        .status-success {{
            background: #d4edda;
            color: #155724;
        }}
        
        .status-pending {{
            background: #fff3cd;
            color: #856404;
        }}
        
        .status-failed {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        .status-partial {{
            background: #cfe2ff;
            color: #084298;
        }}
        
        .action-btn {{
            padding: 6px 12px;
            font-size: 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            background: #667eea;
            color: white;
            transition: background 0.2s;
            margin-right: 5px;
        }}
        
        .action-btn:hover {{
            background: #5568d3;
        }}
        
        .action-btn:disabled {{
            background: #ccc;
            cursor: not-allowed;
        }}
        
        .empty-state {{
            text-align: center;
            padding: 40px 20px;
            color: #999;
        }}
        
        .modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }}
        
        .modal.active {{
            display: flex;
        }}
        
        .modal-content {{
            background: white;
            border-radius: 8px;
            max-width: 900px;
            max-height: 80vh;
            overflow-y: auto;
            padding: 20px;
            position: relative;
        }}
        
        .modal-close {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: #999;
        }}
        
        .modal-close:hover {{
            color: #333;
        }}
        
        .csv-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}
        
        .csv-table thead {{
            background: #f7f7f7;
            position: sticky;
            top: 0;
        }}
        
        .csv-table th {{
            padding: 10px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #ddd;
        }}
        
        .csv-table td {{
            padding: 8px 10px;
            border-bottom: 1px solid #eee;
            word-break: break-all;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Audience Sync Dashboard</h1>
            <p>AppsFlyer Audience Integration - Sync History & Data Viewer</p>
        </div>
        
        <div class="dashboard-grid">
            <!-- Stats Section -->
            <div class="card">
                <h2>Overview Statistics</h2>
                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="value">{len(sync_history)}</div>
                        <div class="label">Total Syncs</div>
                    </div>
                    <div class="stat-box">
                        <div class="value">{len([s for s in sync_history if s['status'] == 'Success'])}</div>
                        <div class="label">Successful</div>
                    </div>
                    <div class="stat-box">
                        <div class="value">{sum(s.get('total_rows_downloaded', 0) for s in sync_history)}</div>
                        <div class="label">Total Rows</div>
                    </div>
                    <div class="stat-box">
                        <div class="value">{len(containers)}</div>
                        <div class="label">Containers</div>
                    </div>
                </div>
            </div>
            
            <!-- Sync History Section -->
            <div class="card">
                <h2>Sync History</h2>
                {_render_sync_history_table(sync_history) if sync_history else '<div class="empty-state">No sync records yet.</div>'}
            </div>
        </div>
    </div>
    
    <!-- Data Viewer Modal -->
    <div id="dataModal" class="modal">
        <div class="modal-content">
            <button class="modal-close" onclick="closeModal()">×</button>
            <h2 id="modalTitle" style="margin-bottom: 15px;"></h2>
            <div id="modalBody"></div>
        </div>
    </div>
    
    <script>
        function viewData(filename) {{
            document.getElementById('dataModal').classList.add('active');
            document.getElementById('modalTitle').textContent = 'CSV Data: ' + filename;
            
            fetch('/audience-sync/get-csv/' + filename)
                .then(response => response.json())
                .then(data => {{
                    if (data.error) {{
                        document.getElementById('modalBody').innerHTML = '<p style="color: red;">Error: ' + data.error + '</p>';
                    }} else {{
                        const html = renderCsvTable(data.rows);
                        document.getElementById('modalBody').innerHTML = html;
                    }}
                }})
                .catch(error => {{
                    document.getElementById('modalBody').innerHTML = '<p style="color: red;">Failed to load data: ' + error + '</p>';
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
    """Renders the sync history table HTML."""
    html = '<table class="sync-history-table"><thead><tr>'
    html += '<th>Timestamp</th>'
    html += '<th>Container ID</th>'
    html += '<th>Status</th>'
    html += '<th>Rows Downloaded</th>'
    html += '<th>Files</th>'
    html += '<th>Actions</th>'
    html += '</tr></thead><tbody>'
    
    for entry in reversed(sync_history):
        status = entry.get('status', 'Unknown')
        status_class = f'status-{status.lower()}'
        
        timestamp = entry.get('timestamp', 'N/A')
        if 'T' in str(timestamp):
            timestamp = timestamp.split('T')[1][:8]
        
        container_id = entry.get('container_id', 'N/A')
        if container_id != 'N/A':
            container_id = container_id[:8] + '...'
        
        rows = entry.get('total_rows_downloaded', 0)
        files = entry.get('downloaded_files', [])
        
        files_html = ''
        if files:
            for f in files:
                files_html += f'<button class="action-btn" onclick="viewData(\'{f["filename"]}\')">View {f["type"]}</button> '
        else:
            files_html = '<span style="color: #999;">No files</span>'
        
        html += f'<tr>'
        html += f'<td>{timestamp}</td>'
        html += f'<td>{container_id}</td>'
        html += f'<td><span class="status-badge {status_class}">{status}</span></td>'
        html += f'<td>{rows}</td>'
        html += f'<td>{files_html}</td>'
        html += f'<td></td>'
        html += f'</tr>'
    
    html += '</tbody></table>'
    return html

@router.get("/get-csv/{filename}")
async def get_csv_data(filename: str):
    """Returns CSV data as JSON for the modal viewer."""
    if ".." in filename or "/" in filename or "\\" in filename:
        return {"error": "Invalid filename"}
    
    filepath = os.path.join(CSV_STORAGE_DIR, filename)
    
    if not os.path.isfile(filepath):
        return {"error": "File not found"}
    
    try:
        rows = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        
        return {"rows": rows}
    except Exception as e:
        return {"error": str(e)}