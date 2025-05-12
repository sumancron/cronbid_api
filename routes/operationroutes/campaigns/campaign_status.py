import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import APIRouter, HTTPException, Request
import aiomysql
from database import Database  # adjust if your Database import is different

APP_PASSWORD = "dcfl kybe tokq ydyv"
SENDER_EMAIL = "admin@cronbid.com"
APP_NAME = "CRONBID"
LOGO_URL = "https://ads.cronbid.com/cronbaylogo.png"
ADMIN_EMAIL = "admin@cronbid.com"

router = APIRouter()

def send_campaign_activation_email(to_email: str, is_active: bool, context: str = "account", campaign_name: str = ""):
    subject_context = f"{APP_NAME} {context.capitalize()}"
    subject = f"Your {subject_context} Has Been {'Activated' if is_active else 'Deactivated'}"

    bg_color = "#d4edda" if is_active else "#f8d7da"
    text_color = "#155724" if is_active else "#721c24"
    status_text = "activated ✅" if is_active else "deactivated ❌"
    support_text = (
        "You can login now. <a href='https://ads.cronbid.com/'>ads.cronbid.com</a>"
        if is_active else
        f"Please contact support. <a href='mailto:{ADMIN_EMAIL}'>{ADMIN_EMAIL}</a>"
    )

    extra_info = f"<p><strong>Campaign:</strong> {campaign_name}</p>" if context == "campaign" else ""

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; background-color: {bg_color}; color: {text_color};">
        <div style="text-align: center;">
            <img src="{LOGO_URL}" alt="{APP_NAME} Logo" width="150" style="margin-bottom: 20px;">
            <h2>Your {context} has been {status_text}</h2>
            <p>Dear User,</p>
            <p>Your {context} on <strong>{APP_NAME}</strong> has been <strong>{status_text}</strong>.</p>
            {extra_info}
            <p>{support_text}</p>
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
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(message)
    except Exception as e:
        print(f"Failed to send email: {e}")


@router.post("/campaign_activation/{campaign_id}")
async def activate_campaign(campaign_id: str, request: Request):
    x_api_key = request.headers.get("x-api-key")
    if x_api_key != "jdfjdhfjdhbfjdhfjhdjjhbdj":
        raise HTTPException(status_code=403, detail="Invalid API key")

    data = await request.json()
    is_active = data.get("is_active", False)

    if not isinstance(is_active, bool):
        raise HTTPException(status_code=400, detail="Invalid value for is_active. Must be a boolean.")

    new_status = "active" if is_active else "inactive"

    pool = await Database.connect()

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            try:
                # Update the campaign status
                await cur.execute(
                    "UPDATE cronbid_campaigns SET status = %s WHERE campaign_id = %s",
                    (new_status, campaign_id)
                )
                await conn.commit()

                # Fetch campaign owner's email and campaign name
                await cur.execute("""
                    SELECT u.email, c.campaign_name
                    FROM cronbid_campaigns c
                    JOIN cronbid_users u ON c.user_id = u.user_id
                    WHERE c.campaign_id = %s
                """, (campaign_id,))
                result = await cur.fetchone()
                if result and result[0]:
                    user_email = result[0]
                    campaign_name = result[1] if result[1] else ""
                    send_campaign_activation_email(
                        to_email=user_email,
                        is_active=is_active,
                        context="campaign",
                        campaign_name=campaign_name
                    )

                return {
                    "status": "success",
                    "message": f"Campaign {campaign_id} status updated to '{new_status}'."
                }
            except aiomysql.MySQLError as e:
                raise HTTPException(status_code=500, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error updating campaign status: {str(e)}")

