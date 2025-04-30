import jwt
from fastapi import Request, HTTPException, status
from database import Database
from utils.security import verify_password
from config import settings

async def handle_login_user(request: Request):
    data = await request.json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required."
        )

    pool = await Database.connect()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT user_id, first_name, last_name, company_name, tax_id, email,
                       additional_email, address, country, phone, skype,
                       referrer_email, is_company, terms_accepted, is_active,
                       created_at, updated_at, password
                FROM cronbid_users
                WHERE email = %s
                """,
                (email,)
            )
            row = await cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    (
        user_id, first_name, last_name, company_name, tax_id, email,
        additional_email, address, country, phone, skype,
        referrer_email, is_company, terms_accepted, is_active,
        created_at, updated_at, hashed_password
    ) = row

    if not verify_password(password, hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    token_payload = {
        "user_id": user_id,
        "email": email
    }
    token = jwt.encode(token_payload, settings.jwt_secret_key, algorithm="HS256")

    return {
        "message": "Login successful",
        "token": token,
        "user": {
            "user_id": user_id,
            "first_name": first_name,
            "last_name": last_name,
            "company_name": company_name,
            "tax_id": tax_id,
            "email": email,
            "additional_email": additional_email,
            "address": address,
            "country": country,
            "phone": phone,
            "skype": skype,
            "referrer_email": referrer_email,
            "is_company": is_company,
            "terms_accepted": terms_accepted,
            "is_active": is_active,
            "created_at": created_at.isoformat(),
            "updated_at": updated_at.isoformat()
        }
    }
