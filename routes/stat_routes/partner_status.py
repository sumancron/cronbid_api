from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from database import Database
from auth import verify_api_key
import aiomysql
from typing import Optional
from utils.send_auth_mails import send_partner_status_notification

router = APIRouter()

# Add Pydantic model for request body
class PartnerStatusRequest(BaseModel):
    status: str
    source_id: int
    campaign_id: int
    source_name: str
    campaign_name: str

@router.get("/partner-status/", dependencies=[Depends(verify_api_key)])
async def get_partner_status():
    try:
        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                query = "SELECT * FROM partner_status"
                await cur.execute(query)
                rows = await cur.fetchall()
        return  rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/partner-status/", dependencies=[Depends(verify_api_key)])
async def create_or_update_partner_status(request: PartnerStatusRequest):
    try:
        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Check if record exists
                check_query = """
                    SELECT id FROM partner_status 
                    WHERE source_id = %s AND campaign_id = %s
                """
                await cur.execute(check_query, (request.source_id, request.campaign_id))
                existing_record = await cur.fetchone()

                if existing_record:
                    # Update existing record
                    update_query = """
                        UPDATE partner_status 
                        SET status = %s 
                        WHERE source_id = %s AND campaign_id = %s
                    """
                    await cur.execute(update_query, (request.status, request.source_id, request.campaign_id))
                    message = "Status updated successfully"
                else:
                    # Insert new record
                    insert_query = """
                        INSERT INTO partner_status (status, source_id, campaign_id, source_name, campaign_name) 
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    await cur.execute(insert_query, (request.status, request.source_id, request.campaign_id, request.source_name, request.campaign_name))
                    message = "Status created successfully"

                await conn.commit()

                # Send email notification
                send_partner_status_notification(request.status, request.source_id, request.campaign_id, request.source_name, request.campaign_name)

        return {"status": "success", "message": message}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))