from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, Form
from fastapi.responses import JSONResponse
from database import Database
from auth import verify_api_key
import aiomysql
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
    try:
        logo_path = None

        # ✅ Save logo if provided
        if logo:
            upload_dir = "uploads/sourcesmedia"
            os.makedirs(upload_dir, exist_ok=True)

            file_extension = os.path.splitext(logo.filename)[1]
            logo_filename = f"{name}_{source_id}{file_extension}"
            logo_path = f"/uploads/sourcesmedia/{logo_filename}"

            file_location = os.path.join(upload_dir, logo_filename)
            with open(file_location, "wb+") as f:
                content = await logo.read()
                f.write(content)

        # ✅ Insert into DB
        query = """
            INSERT INTO cronbid_sources (source_id, name, category, type, logo)
            VALUES (%s, %s, %s, %s, %s)
        """
        values = (source_id, name, category, type, logo_path)

        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, values)
                await conn.commit()

        return {
            "status": "success",
            "message": "Source added successfully",
            "source": {
                "source_id": source_id,
                "name": name,
                "category": category,
                "type": type,
                "logo": logo_path
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ✅ FIX: Add a fallback GET to avoid 405 when someone visits this route via browser
@router.get("/add_sources/", include_in_schema=False)
async def prevent_get_on_add_sources():
    return JSONResponse(
        status_code=405,
        content={"detail": "Method Not Allowed. Use POST instead."}
    )
