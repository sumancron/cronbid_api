from fastapi import APIRouter, HTTPException, Request
from services.authapis.register_service import handle_register_user
from services.authapis.login_service import handle_login_user
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from database import Database
from utils import security

router = APIRouter()

APP_PASSWORD = "dcfl kybe tokq ydyv"
SENDER_EMAIL = "admin@cronbid.com"
APP_NAME = "CRONBID"
LOGO_URL = "https://ads.cronbid.com/cronbaylogo.png"

@router.post("/register")
async def register_user(request: Request):
    try:
        result = await handle_register_user(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
async def login_user(request: Request):
    try:
        result = await handle_login_user(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# checking if email is already registered in cronbid_users table
@router.post("/check_email")
async def check_email(request: Request):
    try:
        data = await request.json()
        email = data.get("email")

        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        pool = await Database.connect()  # ✅ Await the coroutine
        async with pool.acquire() as conn:  # ✅ Acquire a connection from the pool
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) FROM cronbid_users WHERE email = %s", (email,))
                count = await cur.fetchone()

        return {"status": "success", "exists": count[0] > 0}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error checking email: {str(e)}")



@router.post("/send_otp")
async def send_otp(request: Request):
    try:
        data = await request.json()
        email = data.get("email")
        otp = data.get("otp")

        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        if not otp:
            raise HTTPException(status_code=400, detail="OTP is required")

        # Build HTML email content
        subject = f"{APP_NAME} - Your OTP Code"
        html_content = f"""
        <html>
        <body style="background: linear-gradient(to bottom, #142c54, #1d179b); color: white; font-family: Arial, sans-serif; padding: 40px;">
            <div style="max-width: 600px; margin: auto; text-align: center;">
                <img src="{LOGO_URL}" alt="{APP_NAME} Logo" style="width: 150px; margin-bottom: 30px;" />
                <h2>Your One-Time Password (OTP)</h2>
                <p>Use the following OTP to complete your verification process:</p>
                <div style="font-size: 28px; font-weight: bold; background-color: white; color: #1d179b; padding: 15px 25px; border-radius: 8px; display: inline-block; margin: 20px 0;">
                    {otp}
                </div>
                <p>This OTP is valid for a limited time and should not be shared with anyone.</p>
                <br />
                <p>Regards,<br /><strong>{APP_NAME} Team</strong></p>
            </div>
        </body>
        </html>
        """

        # Send email using SMTP
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)

        return {"status": "success", "message": "OTP sent successfully"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to send OTP: {str(e)}")
    
@router.post("/reset_password")
async def reset_password(request: Request):
    try:
        data = await request.json()
        email = data.get("email")
        new_password = data.get("new_password")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        if not new_password:
            raise HTTPException(status_code=400, detail="New password is required")

        new_password = security.hash_password(new_password)

        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE cronbid_users SET password = %s WHERE email = %s",
                    (new_password, email)
                )
                # No need for `conn.commit()` if autocommit=True (which it is in your config)

        return {"status": "success", "message": "Password reset successfully"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to reset password: {str(e)}")
