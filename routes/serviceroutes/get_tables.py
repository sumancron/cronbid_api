# app/routes/database_routes.py
from fastapi import APIRouter, Request, Header, HTTPException
from database import Database
# from config import settings
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import aiomysql

router = APIRouter()

@router.get("/fetch/{table_name}")
async def fetch_table_data(
    table_name: str,
    x_api_key: str = Header(None)
):
    if x_api_key != "jdfjdhfjdhbfjdhfjhdjjhbdj":
        raise HTTPException(status_code=403, detail="Invalid or missing API key")

    pool = await Database.connect()
    
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            try:
                await cur.execute(f"SELECT * FROM `{table_name}`")
                rows = await cur.fetchall()
                return {"status": "success", "data": rows}
            except aiomysql.MySQLError as e:
                raise HTTPException(status_code=500, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error fetching data from table `{table_name}`: {str(e)}")



APP_PASSWORD = "vlmx lbff rsvo llvr"
SENDER_EMAIL = "suman@cronbaytechnologies.com"
ADMIN_EMAIL = "suman@cronbaytechnologies.com"
APP_NAME = "CRONBID"
LOGO_URL = "https://ads.cronbid.com/cronbaylogo.png"

def send_activation_email(to_email: str, is_active: bool):
    subject = f"Your {APP_NAME} Account Has Been {'Activated' if is_active else 'Deactivated'}"
    bg_color = "#d4edda" if is_active else "#f8d7da"
    text_color = "#155724" if is_active else "#721c24"
    status_text = "activated ✅" if is_active else "deactivated ❌"

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; background-color: {bg_color}; color: {text_color};">
        <div style="text-align: center;">
            <img src="{LOGO_URL}" alt="{APP_NAME} Logo" width="150" style="margin-bottom: 20px;">
            <h2>Your account has been {status_text}</h2>
            <p>Dear User,</p>
            <p>Your account on <strong>{APP_NAME}</strong> has been <strong>{status_text}</strong>.</p>
            <p>If you have any questions, please contact support.</p>
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


@router.post("/user_activation/{user_id}")
async def activate_user(user_id: str, request: Request):
    x_api_key = request.headers.get("x-api-key")
    if x_api_key != "jdfjdhfjdhbfjdhfjhdjjhbdj":
        raise HTTPException(status_code=403, detail="Invalid API key")

    data = await request.json()
    is_active = data.get("is_active", False)

    if not isinstance(is_active, bool):
        raise HTTPException(status_code=400, detail="Invalid value for is_active. Must be a boolean.")

    pool = await Database.connect()

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    "UPDATE cronbid_users SET is_active = %s WHERE user_id = %s",
                    (is_active, user_id)
                )
                await conn.commit()

                # fetch email to send notification
                await cur.execute("SELECT email FROM cronbid_users WHERE user_id = %s", (user_id,))
                result = await cur.fetchone()
                if result and result[0]:
                    send_activation_email(result[0], is_active)

                return {"status": "success", "message": f"User {user_id} activation status updated."}
            except aiomysql.MySQLError as e:
                raise HTTPException(status_code=500, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error updating user activation status: {str(e)}")