from fastapi import APIRouter, Depends, HTTPException
from database import Database
from auth import verify_api_key
import aiomysql

router = APIRouter()

@router.get("/", dependencies=[Depends(verify_api_key)])
async def get_campaigns():
    try:
        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM cronbid_campaigns")
                rows = await cur.fetchall()
        return {"campaigns": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
