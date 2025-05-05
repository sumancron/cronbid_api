from fastapi import Request, HTTPException
from database import Database
from utils.id_generator import generate_custom_id
from utils.security import hash_password
from utils.send_auth_mails import send_user_confirmation_email, send_admin_user_alert

async def handle_register_user(request: Request):
    data = await request.json()

    user_id = generate_custom_id("USER")
    first_name = (data.get("firstName") or "").strip()
    last_name = (data.get("lastName") or "").strip()
    company_name = data.get("companyName") or None
    if company_name:
        company_name = company_name.strip()

    tax_id = None if data.get("taxId") == "null" else data.get("taxId")
    email = (data.get("email") or "").strip().lower()
    additional_email = data.get("additionalEmail") or None
    address = data.get("address") or None
    country = (data.get("country") or "").strip()
    phone = data.get("phone") or None
    skype = data.get("skype") or None
    referrer_email = data.get("referrerEmail") or None
    password = data.get("password") or ""
    is_company = bool(data.get("isCompany", False))
    terms_accepted = bool(data.get("termsAccepted", False))

    required_fields = [first_name, email, password, country]
    if not all(required_fields):
        raise HTTPException(status_code=400, detail="Missing required fields.")

    async with Database.pool.acquire() as conn:
        async with conn.cursor() as cur:
            # Check email uniqueness
            await cur.execute("SELECT COUNT(*) FROM cronbid_users WHERE email = %s", (email,))
            if (await cur.fetchone())[0] > 0:
                raise HTTPException(status_code=400, detail="This email is already registered.")

            # Check company uniqueness (if provided)
            if company_name:
                await cur.execute("SELECT COUNT(*) FROM cronbid_users WHERE company_name = %s", (company_name,))
                if (await cur.fetchone())[0] > 0:
                    raise HTTPException(status_code=400, detail="This company name is already registered.")

            hashed_password = hash_password(password)

            insert_query = """
                INSERT INTO cronbid_users (
                    user_id, first_name, last_name, company_name, tax_id, email,
                    additional_email, address, country, phone, skype, referrer_email,
                    password, is_company, terms_accepted
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
            """
            await cur.execute(insert_query, (
                user_id, first_name, last_name, company_name, tax_id, email,
                additional_email, address, country, phone, skype, referrer_email,
                hashed_password, is_company, terms_accepted
            ))

    # Send confirmation email to user
    try:
        send_user_confirmation_email(email, first_name)
    except Exception as e:
        print(f"[Email Error] Failed to send confirmation email to user: {e}")

    # Send alert email to admin
    try:
        user_info = {
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
            "terms_accepted": terms_accepted
        }
        send_admin_user_alert(user_info)
    except Exception as e:
        print(f"[Email Error] Failed to send admin alert email: {e}")

    return {"message": "User registered successfully", "user_id": user_id}
