import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import APIRouter, HTTPException, Request
import aiomysql
from database import Database
import logging
from typing import Optional

# Constants
APP_NAME = "CRONBID"
SENDER_EMAIL = "admin@cronbid.com"
APP_PASSWORD = "dcfl kybe tokq ydyv"  # Use ENV in production
ADMIN_EMAIL = "admin@cronbid.com"
LOGO_URL = "https://ads.cronbid.com/cronbaylogo.png"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
VALID_API_KEY = "jdfjdhfjdhbfjdhfjhdjjhbdj"

# Add logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    try:
        # Validate API key
        x_api_key = request.headers.get("x-api-key")
        if x_api_key != VALID_API_KEY:
            raise HTTPException(status_code=403, detail="Invalid API key")

        # Get and validate request body
        try:
            data = await request.json()
            is_active = data.get("is_active")
            if is_active is None:
                raise HTTPException(status_code=400, detail="is_active field is required")
            if not isinstance(is_active, bool):
                raise HTTPException(status_code=400, detail="is_active must be a boolean")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid request body: {str(e)}")

        new_status = "active" if is_active else "inactive"
        
        # Get database connection
        pool = await Database.connect()
        if not pool:
            logger.error("Failed to establish database connection")
            raise HTTPException(status_code=500, detail="Database connection failed")

        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:  # Use DictCursor for named columns
                # Check campaign existence
                await cur.execute(
                    "SELECT created_by FROM cronbid_campaigns WHERE campaign_id = %s",
                    (campaign_id,)
                )
                campaign = await cur.fetchone()
                if not campaign:
                    raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

                try:
                    # Update campaign status
                    await cur.execute(
                        "UPDATE cronbid_campaigns SET status = %s WHERE campaign_id = %s",
                        (new_status, campaign_id)
                    )
                    await conn.commit()
                except Exception as e:
                    logger.error(f"Database update error: {str(e)}")
                    await conn.rollback()
                    raise HTTPException(status_code=500, detail="Failed to update campaign status")

                # Get user email and campaign details
                try:
                    await cur.execute("""
                        SELECT u.email, 
                               JSON_UNQUOTE(JSON_EXTRACT(c.campaign_details, '$.campaign_title')) as campaign_title
                        FROM cronbid_campaigns c
                        JOIN cronbid_users u ON c.created_by = u.user_id
                        WHERE c.campaign_id = %s
                    """, (campaign_id,))
                    result = await cur.fetchone()
                except Exception as e:
                    logger.error(f"Error fetching campaign details: {str(e)}")
                    raise HTTPException(status_code=500, detail="Failed to fetch campaign details")

                if result and result.get('email'):
                    try:
                        send_campaign_activation_email(
                            to_email=result['email'],
                            is_active=is_active,
                            campaign_name=result.get('campaign_title') or 'Untitled Campaign'
                        )
                    except Exception as e:
                        logger.error(f"Email sending failed: {str(e)}")
                        # Don't fail the request if email fails

        return {
            "status": "success",
            "message": f"Campaign {campaign_id} status updated to '{new_status}'",
            "campaign_id": campaign_id,
            "new_status": new_status
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

