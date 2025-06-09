import re
from fastapi import APIRouter, HTTPException, Header, status
from database import Database
from typing import Dict, List
import os
from dotenv import load_dotenv
import aiomysql

load_dotenv()

router = APIRouter()

def is_malicious_input(value: str) -> bool:
    """Enhanced check to detect SQL/malicious input."""
    # More comprehensive regex pattern
    regex = re.compile(
        r"['\";]|--|#|/\*|\*/|"  # SQL comment markers and string terminators
        r"\b(drop|alter|insert|delete|update|select|union|create|"  # SQL commands
        r"exec|execute|declare|set|waitfor|cast|convert)\b|"  # More SQL keywords
        r"xp_|sp_|syscolumns|syslogins|sysusers|sysobjects",  # SQL stored procedures and system tables
        re.IGNORECASE
    )
    return bool(regex.search(str(value)))

def validate_email(email: str) -> bool:
    """Validate email format."""
    email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    return bool(email_regex.match(email))

def sanitize_input(data: dict):
    """Enhanced input sanitization and validation."""
    # Validate email formats if provided
    if "email" in data and data["email"]:
        if not validate_email(data["email"]):
            raise HTTPException(
                status_code=400,
                detail="Invalid email format"
            )
    
    if "additional_email" in data and data["additional_email"]:
        if not validate_email(data["additional_email"]):
            raise HTTPException(
                status_code=400,
                detail="Invalid additional email format"
            )
    
    if "referrer_email" in data and data["referrer_email"]:
        if not validate_email(data["referrer_email"]):
            raise HTTPException(
                status_code=400,
                detail="Invalid referrer email format"
            )

    # Validate phone number format
    if "phone" in data and data["phone"]:
        if len(data["phone"]) > 20:
            raise HTTPException(
                status_code=400,
                detail="Phone number too long (max 20 characters)"
            )
    
    # Check for malicious input in all string fields
    for key, value in data.items():
        if isinstance(value, str) and is_malicious_input(value):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid or dangerous input in field: {key}"
            )
    
    # Clean string inputs
    string_fields = [
        "first_name", "last_name", "company_name", "tax_id", 
        "email", "additional_email", "country", "phone", 
        "skype", "referrer_email"
    ]
    
    for field in string_fields:
        if field in data and isinstance(data[field], str):
            data[field] = data[field].strip()
            if field in ["email", "additional_email", "referrer_email"]:
                data[field] = data[field].lower()
    
    return data

@router.get("/get_user")
async def get_users(skip: int = 0, limit: int = 10, x_api_key: str = Header(None)):
    if x_api_key != "jdfjdhfjdhbfjdhfjhdjjhbdj":
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
        
    pool = await Database.connect()
    if pool is None:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    conn = await pool.acquire()
    try:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SELECT * FROM cronbid_users LIMIT %s OFFSET %s", (limit, skip))
            users = await cursor.fetchall()
            return users
    finally:
        pool.release(conn)

@router.get("/get_user/{user_id}")
async def get_user(user_id: int, x_api_key: str = Header(None)):
    if x_api_key != "jdfjdhfjdhbfjdhfjhdjjhbdj":
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
        
    pool = await Database.connect()
    if pool is None:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    conn = await pool.acquire()
    try:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SELECT * FROM cronbid_users WHERE id = %s", (user_id,))
            user_data = await cursor.fetchone()
            
            if not user_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            return user_data
    finally:
        pool.release(conn)

@router.put("/put_user/{user_id}")
async def update_user(user_id: int, user: Dict, x_api_key: str = Header(None)):
    # Sanitize and validate input
    user = sanitize_input(user)
   
    if x_api_key != "jdfjdhfjdhbfjdhfjhdjjhbdj":
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
        
    pool = await Database.connect()
    if pool is None:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    conn = await pool.acquire()
    try:
        async with conn.cursor() as cursor:
            # Check if user exists
            await cursor.execute("SELECT * FROM cronbid_users WHERE id = %s", (user_id,))
            if not await cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Update user
            query = """
            UPDATE cronbid_users 
            SET first_name = %s,
                last_name = %s,
                company_name = %s,
                tax_id = %s,
                email = %s,
                additional_email = %s,
                address = %s,
                country = %s,
                phone = %s,
                skype = %s,
                referrer_email = %s,
                is_company = %s,
                updated_at = NOW()
            WHERE id = %s
            """
            await cursor.execute(query, (
                user.get("first_name"),
                user.get("last_name"),
                user.get("company_name"),
                user.get("tax_id"),
                user.get("email"),
                user.get("additional_email"),
                user.get("address"),
                user.get("country"),
                user.get("phone"),
                user.get("skype"),
                user.get("referrer_email"),
                user.get("is_company"),
                user_id
            ))
            
            # # Get updated user
            # await cursor.execute("SELECT * FROM cronbid_users WHERE id = %s", (user_id,))
            # updated_user = await cursor.fetchone()
            
            await conn.commit()
            return {"res":"User Updated ✅"}
            
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        pool.release(conn)

@router.delete("/del_user/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, x_api_key: str = Header(None)):
        
    if x_api_key != "jdfjdhfjdhbfjdhfjhdjjhbdj":
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
        
    pool = await Database.connect()
    if pool is None:
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    conn = await pool.acquire()
    try:
        async with conn.cursor() as cursor:
            # Check if user exists
            await cursor.execute("SELECT * FROM cronbid_users WHERE id = %s", (user_id,))
            if not await cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Delete user
            await cursor.execute("DELETE FROM cronbid_users WHERE id = %s", (user_id,))
            await conn.commit()
            
            return None
            
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        pool.release(conn)