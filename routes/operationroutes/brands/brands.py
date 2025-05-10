from fastapi import APIRouter, Depends, HTTPException, Query
from database import Database
from auth import verify_api_key
import aiomysql
import time
from typing import Optional

router = APIRouter()

@router.get("/get_brands/", dependencies=[Depends(verify_api_key)])
async def get_brands(
    country: Optional[str] = Query(None),
    state_region: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    created_by: Optional[str] = Query(None),
):
    try:
        filters = []
        values = []

        if country:
            filters.append("country = %s")
            values.append(country)
        if state_region:
            filters.append("state_region = %s")
            values.append(state_region)
        if city:
            filters.append("city = %s")
            values.append(city)
        if status:
            filters.append("status = %s")
            values.append(status)
        if created_by:
            filters.append("created_by = %s")
            values.append(created_by)

        query = "SELECT * FROM cronbid_brands"
        if filters:
            query += " WHERE " + " AND ".join(filters)

        # Debug: print the query and values
        print("\n[DEBUG] Executing Query:", query)
        print("[DEBUG] With Values:", values)

        start_time = time.time()

        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, values)
                rows = await cur.fetchall()

        end_time = time.time()
        print(f"[DEBUG] Query Execution Time: {round((end_time - start_time)*1000, 2)} ms")

        return {"brands": rows}

    except Exception as e:
        print("[ERROR] Exception occurred while fetching brands:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
