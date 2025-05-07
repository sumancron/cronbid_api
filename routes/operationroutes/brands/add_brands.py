from fastapi import APIRouter, Depends, HTTPException, Request
from database import Database
from auth import verify_api_key
import uuid
import re
import base64

from utils.logger import generate_log_id, insert_log_entry

router = APIRouter()

def generate_brand_id():
    return f"BRD-{uuid.uuid4().hex[:8]}"


def is_malicious_input(value: str) -> bool:
    """Basic check to detect SQL/malicious input."""
    regex = re.compile(r"['\";]|--|\b(drop|alter|insert|delete|update|select)\b", re.IGNORECASE)
    return bool(regex.search(value))

def sanitize_input(data: dict):
    """Raise an error if any value is malicious."""
    for key, value in data.items():
        # Skip sanitization for brand_logo as it will contain base64 data
        if key != "brand_logo" and isinstance(value, str) and is_malicious_input(value):
            raise HTTPException(status_code=400, detail=f"Invalid or dangerous input in field: {key}")
    return True


@router.post("/post_brand/", dependencies=[Depends(verify_api_key)])
async def post_brand(request: Request):
    data = await request.json()

    user_id = data.get("created_by")
    user_name = data.get("user_name")  # optional
    if not user_id:
        raise HTTPException(status_code=400, detail="created_by is required.")

    # Validate input
    sanitize_input({k: v for k, v in data.items() if v is not None})

    brand_id = generate_brand_id()
    log_id = generate_log_id()

    # Ensure that the brand_logo is base64 encoded and properly formatted
    brand_logo = data.get("brand_logo")
    if brand_logo:
        # Check if it's a valid base64 string (basic check, you may want to improve this)
        if not brand_logo.startswith("data:image"):
            raise HTTPException(status_code=400, detail="Invalid base64 image data for brand_logo.")
        try:
            # Decode base64 to ensure it's valid (if needed for future use)
            decoded_logo = base64.b64decode(brand_logo.split(",")[1])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 encoding for brand_logo.")

    pool = await Database.connect()
    if pool is None:
        raise HTTPException(status_code=500, detail="Database connection failed.")

    conn = await pool.acquire()
    try:
        async with conn.cursor() as cursor:
            # Insert into brands table
            await cursor.execute("""
                INSERT INTO cronbid_brands (
                    brand_id, company_name, brand_logo, country, state_region, city,
                    address_line_1, address_line_2, zip_postal_code, currency,
                    first_name, last_name, contact, mobile,
                    created_by, log_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s
                )
            """, (
                brand_id,
                data.get("company_name"),
                brand_logo,  # Store the base64 string
                data.get("country"),
                data.get("state_region"),
                data.get("city"),
                data.get("address_line_1"),
                data.get("address_line_2"),
                data.get("zip_postal_code"),
                data.get("currency"),
                data.get("first_name"),
                data.get("last_name"),
                data.get("contact"),
                data.get("mobile"),
                user_id,
                log_id
            ))

            # Insert into logs table using reusable helper
            await insert_log_entry(
                conn=conn,
                action="create",
                table_name="cronbid_brands",
                record_id=brand_id,
                user_id=user_id,
                username=user_name,
                action_description=f"Brand created with ID {brand_id}",
                log_id=log_id
            )

            await conn.commit()

    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        pool.release(conn)

    return {
        "message": "Brand successfully added",
        "brand_id": brand_id,
        "log_id": log_id
    }
