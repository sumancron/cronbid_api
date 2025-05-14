from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from database import Database
from auth import verify_api_key
from utils.logger import insert_log_entry, generate_log_id
import logging

router = APIRouter()

# Create a logger instance
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class UpdateBrandModel(BaseModel):
    brand_id: str
    company_name: Optional[str] = None
    brand_logo: Optional[str] = None
    country: Optional[str] = None
    state_region: Optional[str] = None
    city: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    zip_postal_code: Optional[str] = None
    currency: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    contact: Optional[str] = None
    mobile: Optional[str] = None
    status: Optional[str] = None
    updated_by: Optional[str] = None
    user_id: str  # For logging only
    user_name: str  # For logging only

@router.put("/update_brand/", dependencies=[Depends(verify_api_key)])
async def update_brand(brand_data: UpdateBrandModel, request: Request):
    log_id = generate_log_id()
    logger.info(f"[{log_id}] Request received to update brand with brand_id: {brand_data.brand_id}")

    pool = await Database.connect()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # Check if brand exists
            logger.info(f"[{log_id}] Checking if brand exists with brand_id: {brand_data.brand_id}")
            await cur.execute("SELECT 1 FROM cronbid_brands WHERE brand_id = %s", (brand_data.brand_id,))
            brand_exists = await cur.fetchone()
            if not brand_exists:
                logger.error(f"[{log_id}] Brand with brand_id {brand_data.brand_id} not found")
                raise HTTPException(status_code=404, detail="Brand not found")

            # Exclude non-database fields
            exclude_fields = {"brand_id", "user_id", "user_name"}
            fields_to_update = []
            values = []

            for field, value in brand_data.dict(exclude_unset=True).items():
                if field in exclude_fields:
                    continue
                fields_to_update.append(f"{field} = %s")
                values.append(value)

            if not fields_to_update:
                logger.warning(f"[{log_id}] No valid fields to update for brand_id: {brand_data.brand_id}")
                raise HTTPException(status_code=400, detail="No valid fields to update.")

            # Add system-generated metadata fields
            fields_to_update.extend([
                "updated_at = %s",
                "log_id = %s",
                "created_by = %s"
            ])
            values.extend([
                datetime.utcnow(),
                log_id,
                brand_data.updated_by or "system"
            ])

            # Add brand_id at the end for WHERE clause
            values.append(brand_data.brand_id)

            update_query = f"""
                UPDATE cronbid_brands
                SET {', '.join(fields_to_update)}
                WHERE brand_id = %s
            """

            try:
                logger.info(f"[{log_id}] Executing update query for brand_id: {brand_data.brand_id}")
                await cur.execute(update_query, values)
                await conn.commit()
                logger.info(f"[{log_id}] Brand updated successfully with brand_id: {brand_data.brand_id}")
            except Exception as e:
                logger.error(f"[{log_id}] Failed to update brand with brand_id {brand_data.brand_id}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to update brand: {str(e)}")

            # Insert log entry
            try:
                log_entry_id = await insert_log_entry(
                    conn=conn,
                    action="update",
                    table_name="cronbid_brands",
                    record_id=brand_data.brand_id,
                    user_id=brand_data.user_id,
                    username=brand_data.user_name,
                    action_description="Brand details updated",
                    log_id=log_id
                )
                logger.info(f"[{log_id}] Log entry inserted with log_id: {log_entry_id}")
            except Exception as e:
                logger.error(f"[{log_id}] Failed to insert log entry: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to insert log entry")

            return JSONResponse(status_code=200, content={
                "message": "Brand updated successfully",
                "log_id": log_entry_id
            })
