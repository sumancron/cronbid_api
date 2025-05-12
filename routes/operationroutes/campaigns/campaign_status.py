import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import APIRouter, HTTPException, Request
import aiomysql
from database import Database

# Constants
APP_NAME = "CRONBID"
SENDER_EMAIL = "admin@cronbid.com"
APP_PASSWORD = "dcfl kybe tokq ydyv"  # Use ENV in production
ADMIN_EMAIL = "admin@cronbid.com"
LOGO_URL = "https://ads.cronbid.com/cronbaylogo.png"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
VALID_API_KEY = "jdfjdhfjdhbfjdhfjhdjjhbdj"

router = APIRouter()


def send_campaign_activation_email(to_email: str, is_active: bool, campaign_name: str):
    """Send activation/deactivation email for a campaign."""
    status_text = "activated ✅" if is_active else "deactivated ❌"
    bg_color = "#d4edda" if is_active else "#f8d7da"
    text_color = "#155724" if is_active else "#721c24"

    subject = f"{APP_NAME} Campaign Has Been {status_text.capitalize()}"

    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; background-color: {bg_color}; color: {text_color};">
            <div style="text-align: center;">
                <img src="{LOGO_URL}" alt="{APP_NAME} Logo" width="150" style="margin-bottom: 20px;">
                <h2>Your Campaign has been {status_text}</h2>
                <p>Dear User,</p>
                <p>Your campaign <strong>{campaign_name}</strong> on <strong>{APP_NAME}</strong> has been <strong>{status_text}</strong>.</p>
                <p>{'You can login now at <a href="https://ads.cronbid.com/">ads.cronbid.com</a>' if is_active else f'Please contact support: <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a>'}</p>
            </div>
        </body>
    </html>
    """

    message = MIMEMultipart()
    message["From"] = SENDER_EMAIL
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(message)
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email to {to_email}: {str(e)}")


@router.post("/campaign_activation/{campaign_id}")
async def activate_campaign(campaign_id: str, request: Request):
    """Activate or deactivate a campaign."""
    x_api_key = request.headers.get("x-api-key")
    if x_api_key != VALID_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    try:
        data = await request.json()
        is_active = data.get("is_active")

        if not isinstance(is_active, bool):
            raise HTTPException(status_code=400, detail="`is_active` must be a boolean.")

        new_status = "active" if is_active else "inactive"

        pool = await Database.connect()

        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # Update campaign status
                await cur.execute("""
                    UPDATE cronbid_campaigns
                    SET status = %s
                    WHERE campaign_id = %s
                """, (new_status, campaign_id))
                await conn.commit()

                # Get user email and campaign title
                await cur.execute("""
                    SELECT u.email, c.campaign_title
                    FROM cronbid_campaigns c
                    JOIN cronbid_users u ON c.created_by = u.user_id
                    WHERE c.campaign_id = %s
                """, (campaign_id,))
                result = await cur.fetchone()

                if result:
                    user_email, campaign_title = result
                    send_campaign_activation_email(
                        to_email=user_email,
                        is_active=is_active,
                        campaign_name=campaign_title or "Unknown"
                    )

        return {
            "status": "success",
            "message": f"Campaign `{campaign_id}` status updated to '{new_status}'."
        }

    except aiomysql.MySQLError as db_err:
        raise HTTPException(status_code=500, detail=f"MySQL error: {str(db_err)}")
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(ex)}")
