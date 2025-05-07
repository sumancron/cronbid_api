from fastapi import APIRouter, Depends, HTTPException, Request
from database import Database
from auth import verify_api_key
import uuid
import json
from datetime import datetime
import re
from utils.logger import generate_log_id, insert_log_entry

router = APIRouter()

def is_malicious_input(value: str) -> bool:
    """Basic check to detect SQL/malicious input."""
    regex = re.compile(r"['\";]|--|\b(drop|alter|insert|delete|update|select)\b", re.IGNORECASE)
    return bool(regex.search(value))

def sanitize_input(data: dict):
    """Raise an error if any string field is malicious."""
    for key, value in data.items():
        if isinstance(value, str) and is_malicious_input(value):
            raise HTTPException(status_code=400, detail=f"Invalid or dangerous input in field: {key}")
    return True

@router.post("/post_campaign/", dependencies=[Depends(verify_api_key)])
async def post_campaign(request: Request):
    data = await request.json()

    # Extract user info
    user_id = data.get("user_id", "null")  # fallback
    user_name = data.get("user_name", "Unknown User")   # fallback

    # Sanitize only top-level primitive fields
    sanitize_input({k: v for k, v in data.items() if isinstance(v, str)})

    try:
        general = data.get("general", {})
        app = data.get("appDetails", {})
        campaign = data.get("campaignDetails", {})
        creatives = data.get("creatives", {})
        flow = data.get("conversionFlow", {})
        budget = data.get("budget", {})
        targeting = data.get("targeting", {})
        source = data.get("source", {})

        campaign_id = f"CRB-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:6]}"
        log_id = generate_log_id()

        values = (
            campaign_id,
            general.get("brandName", ""),
            app.get("packageId", ""),
            app.get("appName", ""),
            app.get("previewUrl", ""),
            app.get("description", ""),
            campaign.get("category", ""),
            campaign.get("campaignTitle", ""),
            campaign.get("kpis", ""),
            campaign.get("mmp", ""),
            campaign.get("clickUrl", ""),
            campaign.get("impressionUrl", ""),
            campaign.get("deeplink", ""),
            json.dumps(creatives.get("files", [])),
            json.dumps(flow.get("events", [])),
            1 if flow.get("selectedPayable") else 0,
            flow.get("amount", 0),
            budget.get("campaignBudget", 0),
            budget.get("dailyBudget", 0),
            budget.get("monthlyBudget", 0),
            targeting.get("selectedCountry", {}).get("country", ""),
            json.dumps(targeting.get("includedStates", [])),
            json.dumps(targeting.get("selectedCountry", {}).get("states", [])),
            1 if source.get("programmaticEnabled") else 0,
            json.dumps(source.get("selectedApps", {})),
            1 if source.get("expandedCategories", {}).get("directApps") else 0,
            1 if source.get("expandedCategories", {}).get("oem") else 0,
            user_id,
            log_id,
        )

        query = """
        INSERT INTO cronbid_campaigns (
            campaign_id, brand, app_package_id, app_name, preview_url, description,
            category, campaign_title, kpis, mmp, click_url, impression_url, deeplink,
            creatives, events, payable, event_amount,
            campaign_budget, daily_budget, monthly_budget,
            country, included_states, excluded_states,
            programmatic, core_partners, direct_apps, oems,
            created_by, log_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s,
                  %s, %s, %s,
                  %s, %s, %s,
                  %s, %s, %s, %s,
                  %s, %s)
        """

        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, values)

                await insert_log_entry(
                    conn=conn,
                    action="create",
                    table_name="cronbid_campaigns",
                    record_id=campaign_id,
                    user_id=user_id,
                    username=user_name,
                    action_description=f"Campaign created with ID {campaign_id}",
                    log_id=log_id
                )

        return {"success": True, "message": "Campaign inserted", "campaign_id": campaign_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insertion failed: {str(e)}")
