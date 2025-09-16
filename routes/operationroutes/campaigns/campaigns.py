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

        for row in rows:
            if "conversion_flow" in row and row["conversion_flow"]:
                try:
                    cf = json.loads(row["conversion_flow"])
                    if isinstance(cf, dict) and "amount" in cf:
                        cf["payout"] = cf["amount"]
                        row["conversion_flow"] = json.dumps(cf)
                except json.JSONDecodeError:
                    pass

            # Handling the main targeting column
            if "targeting" in row and row["targeting"]:
                try:
                    targeting_data = json.loads(row["targeting"])
                    # Use the entire JSON object for `advanced_targeting`
                    row["advanced_targeting"] = json.dumps(targeting_data)
                    # For backward compatibility, `targeting` stores only the country selections
                    if isinstance(targeting_data, dict) and "countrySelections" in targeting_data:
                        simplified = targeting_data["countrySelections"]
                        row["targeting"] = json.dumps(simplified)
                except json.JSONDecodeError:
                    # If the JSON is invalid, provide empty defaults
                    row["advanced_targeting"] = "{}"
                    row["targeting"] = "[]"
            else:
                # If the targeting column is empty or null, provide empty defaults
                row["advanced_targeting"] = "{}"
                row["targeting"] = "[]"

        return {"campaigns": rows}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"API Error: {str(e)}")
    
# from fastapi import APIRouter, Depends, HTTPException, Query
# from database import Database
# from auth import verify_api_key
# import aiomysql
# from typing import Optional
# import json

# router = APIRouter()

# @router.get("/get_campaigns/", dependencies=[Depends(verify_api_key)])
# async def get_campaigns(
#     campaign_id: Optional[str] = Query(None),
#     brand: Optional[str] = Query(None),
#     campaign_title: Optional[str] = Query(None),
#     country: Optional[str] = Query(None),
#     status: Optional[str] = Query(None),
#     created_by: Optional[str] = Query(None)
# ):
#     try:
#         filters = []
#         values = []

#         if campaign_id:
#             filters.append("campaign_id = %s")
#             values.append(campaign_id)
#         if brand:
#             filters.append("brand = %s")
#             values.append(brand)
#         if campaign_title:
#             filters.append("campaign_title = %s")
#             values.append(campaign_title)
#         if country:
#             filters.append("country = %s")
#             values.append(country)
#         if status:
#             filters.append("status = %s")
#             values.append(status)
#         if created_by:
#             filters.append("created_by = %s")
#             values.append(created_by)

#         query = "SELECT * FROM cronbid_campaigns"
#         if filters:
#             query += " WHERE " + " AND ".join(filters)

#         pool = await Database.connect()
#         async with pool.acquire() as conn:
#             async with conn.cursor(aiomysql.DictCursor) as cur:
#                 await cur.execute(query, values)
#                 rows = await cur.fetchall()

#         # Modify conversion_flow by adding 'payout' = 'amount'
#         for row in rows:
#             if "conversion_flow" in row and row["conversion_flow"]:
#                 try:
#                     cf = json.loads(row["conversion_flow"])
#                     if isinstance(cf, dict) and "amount" in cf:
#                         cf["payout"] = cf["amount"]
#                         row["conversion_flow"] = json.dumps(cf)
#                 except json.JSONDecodeError:
#                     pass  # Skip if conversion_flow is not valid JSON

#         return {"campaigns": rows}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

