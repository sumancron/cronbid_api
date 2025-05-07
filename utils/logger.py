# app/utils/logger.py

import uuid
from fastapi import HTTPException
from database import Database
from datetime import datetime

def generate_log_id():
    return f"LOG-{uuid.uuid4().hex[:10]}"

async def insert_log_entry(
    conn,
    action: str,
    table_name: str,
    record_id: str,
    user_id: str,
    username: str = None,
    action_description: str = None,
    log_id: str = None
) -> str:
    if not log_id:
        log_id = generate_log_id()

    try:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO cronbid_logs (
                    log_id, action, table_name, record_id,
                    user_id, username, action_description
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
            """, (
                log_id,
                action,
                table_name,
                record_id,
                user_id,
                username,
                action_description
            ))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Log insertion failed: {e}")

    return log_id
