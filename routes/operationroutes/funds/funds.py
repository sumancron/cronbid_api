from fastapi import APIRouter, Depends, HTTPException, Query
from database import Database
from auth import verify_api_key
import aiomysql
from typing import Optional

router = APIRouter()

@router.get("/get_user_funds/", dependencies=[Depends(verify_api_key)])
async def get_user_funds(
    user_id: Optional[str] = Query(None),
    user_name: Optional[str] = Query(None),
    fund_id: Optional[str] = Query(None),
    created_by: Optional[str] = Query(None),
):
    try:
        filters = []
        values = []

        if user_id:
            filters.append("user_id = %s")
            values.append(user_id)
        if user_name:
            filters.append("user_name = %s")
            values.append(user_name)
        if fund_id:
            filters.append("fund_id = %s")
            values.append(fund_id)
        if created_by:
            filters.append("created_by = %s")
            values.append(created_by)

        # Base query
        query = "SELECT * FROM cronbid_user_funds"
        if filters:
            query += " WHERE " + " AND ".join(filters)

        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, values)
                rows = await cur.fetchall()

        return {"user_funds": rows}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
@router.get("/get_fund_transactions/", dependencies=[Depends(verify_api_key)])
async def get_fund_transactions(
    transaction_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    user_name: Optional[str] = Query(None),
    fund_id: Optional[str] = Query(None),
    created_by: Optional[str] = Query(None),
):
    try:
        filters = []
        values = []

        if transaction_id:
            filters.append("transaction_id = %s")
            values.append(transaction_id)
        if user_id:
            filters.append("user_id = %s")
            values.append(user_id)
        if user_name:
            filters.append("user_name = %s")
            values.append(user_name)
        if fund_id:
            filters.append("fund_id = %s")
            values.append(fund_id)
        if created_by:
            filters.append("created_by = %s")
            values.append(created_by)

        # Base query
        query = "SELECT * FROM cronbid_fund_transactions"
        if filters:
            query += " WHERE " + " AND ".join(filters)

        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, values)
                rows = await cur.fetchall()

        return {"fund_transactions": rows}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
