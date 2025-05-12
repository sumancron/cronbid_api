from fastapi import APIRouter, Depends, HTTPException, Query
from database import Database
from auth import verify_api_key
import aiomysql
from typing import Optional

router = APIRouter()

@router.get("/get_campaigns/", dependencies=[Depends(verify_api_key)])
async def get_campaigns(
    id: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    campaign_title: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    created_by: Optional[str] = Query(None)
):
    try:
        filters = []
        values = []

        if id:
            filters.append("id = %s")
            values.append(id)
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

        return {"campaigns": rows}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
