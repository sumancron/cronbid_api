from fastapi import Request
from database import Database
import uuid

async def handle_register_user(request: Request):
    data = await request.json()

    # Extracting and normalizing fields
    user_id = str(uuid.uuid4())
    first_name = data.get("firstName")
    last_name = data.get("lastName")
    company_name = data.get("companyName") or None
    tax_id = None if data.get("taxId") == "null" else data.get("taxId")
    email = data.get("email")
    additional_email = data.get("additionalEmail") or None
    address = data.get("address") or None
    country = data.get("country")
    phone = data.get("phone") or None
    skype = data.get("skype") or None
    referrer_email = data.get("referrerEmail") or None
    password = data.get("password")
    is_company = data.get("isCompany", False)
    terms_accepted = data.get("termsAccepted", False)

    query = """
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

    values = (
        user_id, first_name, last_name, company_name, tax_id, email,
        additional_email, address, country, phone, skype, referrer_email,
        password, is_company, terms_accepted
    )

    async with Database.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, values)

    return "User registered successfully"
