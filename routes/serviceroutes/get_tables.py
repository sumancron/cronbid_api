# app/routes/database_routes.py
from fastapi import APIRouter, Request, Header, HTTPException
from database import Database
# from config import settings
import aiomysql

router = APIRouter()

@router.get("/fetch/{table_name}")
async def fetch_table_data(
    table_name: str,
    x_api_key: str = Header(None)
):
    if x_api_key != "jdfjdhfjdhbfjdhfjhdjjhbdj":
        raise HTTPException(status_code=403, detail="Invalid or missing API key")

    pool = await Database.connect()
    
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            try:
                await cur.execute(f"SELECT * FROM `{table_name}`")
                rows = await cur.fetchall()
                return {"status": "success", "data": rows}
            except aiomysql.MySQLError as e:
                raise HTTPException(status_code=500, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error fetching data from table `{table_name}`: {str(e)}")
