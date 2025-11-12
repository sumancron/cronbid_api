from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, Form
from fastapi.responses import JSONResponse
from database import Database
from auth import verify_api_key
import aiomysql
import aiofiles
import os
from typing import Optional

router = APIRouter()


# ✅ GET sources with optional filters
@router.get("/get_sources/", dependencies=[Depends(verify_api_key)])
async def get_sources(
    source_id: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    type: Optional[str] = Query(None)
):
    try:
        filters = []
        values = []

        if source_id:
            filters.append("source_id = %s")
            values.append(source_id)
        if name:
            filters.append("name = %s")
            values.append(name)
        if category:
            filters.append("category = %s")
            values.append(category)
        if type:
            filters.append("type = %s")
            values.append(type)

        query = "SELECT * FROM cronbid_sources"
        if filters:
            query += " WHERE " + " AND ".join(filters)

        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, values)
                rows = await cur.fetchall()

        return {"status": "success", "sources": rows}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ POST: Add a new source

@router.post("/add_sources/", dependencies=[Depends(verify_api_key)])
async def add_sources(
    source_id: str = Form(...),
    name: str = Form(...),
    category: str = Form(...),
    type: str = Form(...),
    logo: Optional[UploadFile] = None
):
    """
    Add a new source record to cronbid_sources.
    Saves logo asynchronously if provided and inserts the record into MySQL.
    """

    try:
        # --- ✅ Prepare upload directory safely ---
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        upload_dir = os.path.join(BASE_DIR, "uploads", "sourcesmedia")
        os.makedirs(upload_dir, exist_ok=True)

        logo_path = None

        # --- ✅ Handle logo upload asynchronously ---
        if logo:
            file_ext = os.path.splitext(logo.filename)[1]
            safe_name = name.replace(" ", "_").replace("/", "_")
            logo_filename = f"{safe_name}_{source_id}{file_ext}"
            file_location = os.path.join(upload_dir, logo_filename)

            # Async file write (non-blocking)
            async with aiofiles.open(file_location, "wb") as f:
                content = await logo.read()
                await f.write(content)

            # Relative path for response and DB
            logo_path = f"/uploads/sourcesmedia/{logo_filename}"

        # --- ✅ Insert record into DB ---
        query = """
            INSERT INTO cronbid_sources (source_id, name, category, type, logo)
            VALUES (%s, %s, %s, %s, %s)
        """
        values = (source_id, name, category, type, logo_path)

        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, values)
                await conn.commit()

        # --- ✅ Response ---
        return {
            "status": "success",
            "message": "Source added successfully",
            "source": {
                "source_id": source_id,
                "name": name,
                "category": category,
                "type": type,
                "logo": logo_path,
            },
        }

    except aiomysql.Error as db_err:
        raise HTTPException(status_code=500, detail=f"Database error: {str(db_err)}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")