from fastapi import APIRouter, Depends, HTTPException, Query
from database import Database
from auth import verify_api_key
import aiomysql
from typing import Optional

router = APIRouter()

@router.get("/partner-status/", dependencies=[Depends(verify_api_key)])
async def get_partner_status():
    try:
        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                query = "SELECT * FROM partner_status"
                await cur.execute(query)
                rows = await cur.fetchall()
        return {"status": "success", "data": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/partner-status/", dependencies=[Depends(verify_api_key)])
async def create_or_update_partner_status(
    status: str,
    source_id: int,
    campaign_id: int
):
    try:
        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Check if record exists
                check_query = """
                SELECT id FROM partner_status 
                WHERE source_id = %s AND campaign_id = %s
                """
                await cur.execute(check_query, (source_id, campaign_id))
                existing_record = await cur.fetchone()

                if existing_record:
                    # Update existing record
                    update_query = """
                    UPDATE partner_status 
                    SET status = %s 
                    WHERE source_id = %s AND campaign_id = %s
                    """
                    await cur.execute(update_query, (status, source_id, campaign_id))
                    message = "Status updated successfully"
                else:
                    # Insert new record
                    insert_query = """
                    INSERT INTO partner_status (status, source_id, campaign_id) 
                    VALUES (%s, %s, %s)
                    """
                    await cur.execute(insert_query, (status, source_id, campaign_id))
                    message = "Status created successfully"
                
                await conn.commit()
                
        return {"status": "success", "message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))