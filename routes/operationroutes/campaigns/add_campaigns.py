# app/routes/campaigns.py

from fastapi import APIRouter, Depends, HTTPException, Request
from database import Database
from auth import verify_api_key
import uuid
import json
from datetime import datetime

router = APIRouter()

@router.post("/post_campaign/", dependencies=[Depends(verify_api_key)])
async def post_campaign(request: Request):
    data = await request.json()
    try:
        # Extract all relevant data from the nested payload
        general = data.get("general", {})
        app = data.get("appDetails", {})
        campaign = data.get("campaignDetails", {})
        creatives = data.get("creatives", {})
        flow = data.get("conversionFlow", {})
        budget = data.get("budget", {})
        targeting = data.get("targeting", {})
        source = data.get("source", {})

        # Build insert values safely
        campaign_id = f"CRB-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:6]}"
        values = (
            campaign_id,
            general.get("brandName"),
            app.get("packageId"),
            app.get("appName"),
            app.get("previewUrl"),
            app.get("description"),
            campaign.get("category"),
            campaign.get("campaignTitle"),
            campaign.get("kpis"),
            campaign.get("mmp"),
            campaign.get("clickUrl"),
            campaign.get("impressionUrl"),
            campaign.get("deeplink"),
            json.dumps(creatives.get("files", [])),  # Store as JSON
            json.dumps(flow.get("events", [])),      # Store as JSON
            1 if flow.get("selectedPayable") else 0,
            flow.get("amount"),
            budget.get("campaignBudget"),
            budget.get("dailyBudget"),
            budget.get("monthlyBudget"),
            targeting.get("selectedCountry", {}).get("country"),
            json.dumps(targeting.get("includedStates", [])),
            json.dumps(targeting.get("selectedCountry", {}).get("states", [])),
            1 if source.get("programmaticEnabled") else 0,
            json.dumps(source.get("selectedApps", {})),
            1 if source.get("expandedCategories", {}).get("directApps") else 0,
            1 if source.get("expandedCategories", {}).get("oem") else 0,
            "admin@example.com",  # Replace with real user if available
            str(uuid.uuid4()),    # log_id
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

        return {"success": True, "message": "Campaign inserted", "campaign_id": campaign_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insertion failed: {str(e)}")
