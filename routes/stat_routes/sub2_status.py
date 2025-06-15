from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from database import Database
from auth import verify_api_key
import aiomysql
from typing import Optional
from utils.send_auth_mails import send_sub2_status_notification

router = APIRouter()

# Add Pydantic model for request body
class Sub2StatusRequest(BaseModel):
    status: str
    campaign_id: int
    source_id: int
    sub2: str
    source_name: str
    campaign_name: str

@router.get("/sub2-status/", dependencies=[Depends(verify_api_key)])
async def get_sub2_status():
    try:
        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                query = "SELECT * FROM sub2_status"
                await cur.execute(query)
                rows = await cur.fetchall()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sub2-status/", dependencies=[Depends(verify_api_key)])
async def create_or_update_sub2_status(request: Sub2StatusRequest):
    try:
        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Check if record exists
                check_query = """
                    SELECT id FROM sub2_status 
                    WHERE campaign_id = %s AND source_id = %s AND sub2 = %s
                """
                await cur.execute(check_query, (request.campaign_id, request.source_id, request.sub2))
                existing_record = await cur.fetchone()

                if existing_record:
                    # Update existing record
                    update_query = """
                        UPDATE sub2_status 
                        SET status = %s 
                        WHERE campaign_id = %s AND source_id = %s AND sub2 = %s
                    """
                    await cur.execute(update_query, (request.status, request.campaign_id, request.source_id, request.sub2))
                    message = "Status updated successfully"
                else:
                    # Insert new record
                    insert_query = """
                        INSERT INTO sub2_status (status, campaign_id, source_id, sub2, source_name, campaign_name) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    await cur.execute(insert_query, (request.status, request.campaign_id, request.source_id, request.sub2, request.source_name, request.campaign_name))
                    message = "Status created successfully"

                await conn.commit()

                # Send email notification
                send_sub2_status_notification(request.status, request.campaign_id, request.source_id, request.sub2, request.source_name, request.campaign_name)

        return {"status": "success", "message": message}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))