from fastapi import APIRouter, Depends, HTTPException, Query
from database import Database
from auth import verify_api_key
import aiomysql
from typing import Optional
import json

router = APIRouter()

@router.get("/get_campaigns/", dependencies=[Depends(verify_api_key)])
async def get_campaigns(
    campaign_id: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    campaign_title: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    created_by: Optional[str] = Query(None)
):
    try:
        filters = []
        values = []

        if campaign_id:
            filters.append("campaign_id = %s")
            values.append(campaign_id)
        if brand:
            filters.append("brand = %s")
            values.append(brand)
        if campaign_title:
            filters.append("campaign_title = %s")
            values.append(campaign_title)
        if country:
            filters.append("country = %s")
            values.append(country)
        if status:
            filters.append("status = %s")
            values.append(status)
        if created_by:
            filters.append("created_by = %s")
            values.append(created_by)

        query = "SELECT * FROM cronbid_campaigns"
        if filters:
            query += " WHERE " + " AND ".join(filters)

        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, values)
                rows = await cur.fetchall()

        # Define the default simplified structure: [{"country": null, "excludedStates": [], "includedStates": []}]
        DEFAULT_TARGETING = [{"country": None, "excludedStates": [], "includedStates": []}]

        for row in rows:
            # Handle conversion_flow (kept as per original logic)
            if "conversion_flow" in row and row["conversion_flow"]:
                try:
                    cf = json.loads(row["conversion_flow"])
                    if isinstance(cf, dict) and "amount" in cf:
                        cf["payout"] = cf["amount"]
                        row["conversion_flow"] = json.dumps(cf)
                except json.JSONDecodeError:
                    pass

            # --- ROBUST TARGETING LOGIC START ---
            
            source_targeting_str = row.get("targeting")
            original_targeting_data = None
            
            # 1. Try to load the data from the 'targeting' column (which holds the raw DB data)
            if source_targeting_str:
                try:
                    original_targeting_data = json.loads(source_targeting_str)
                except json.JSONDecodeError:
                    original_targeting_data = None # Failed to parse

            # 2. Store the original data in 'advanced_targeting' for completeness
            row["advanced_targeting"] = json.dumps(original_targeting_data if original_targeting_data is not None else {})

            simplified_targeting = []
            
            if original_targeting_data is not None:
                
                # Case 1: Complex structure with 'countrySelections' (from your full data example)
                if isinstance(original_targeting_data, dict) and "countrySelections" in original_targeting_data:
                    country_selections = original_targeting_data.get("countrySelections", [])
                    if isinstance(country_selections, list):
                        for item in country_selections:
                            # Use 'selectedCountry' key if present; this handles the complex structure
                            country_val = item.get("selectedCountry") or item.get("country")
                            
                            simplified_targeting.append({
                                "country": country_val,
                                "excludedStates": item.get("excludedStates", []),
                                "includedStates": item.get("includedStates", [])
                            })

                # Case 2: Simplified List Format (from your direct DB query output)
                elif isinstance(original_targeting_data, list):
                    for item in original_targeting_data:
                        # Use 'country' key if present; this handles the already simplified structure
                        if isinstance(item, dict):
                            simplified_targeting.append({
                                "country": item.get("country"),
                                "excludedStates": item.get("excludedStates", []),
                                "includedStates": item.get("includedStates", [])
                            })
            
            # 3. If no countries were successfully extracted, use the default structure
            if not simplified_targeting:
                simplified_targeting = DEFAULT_TARGETING
                
            # 4. Assign the final simplified structure to the 'targeting' key
            # This ensures the output format is ALWAYS [{"country": "...", "excludedStates": [], "includedStates": []}]
            row["targeting"] = json.dumps(simplified_targeting)
            
            # --- ROBUST TARGETING LOGIC END ---

        return {"campaigns": rows}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"API Error: {str(e)}")