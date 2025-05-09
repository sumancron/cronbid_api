from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from decimal import Decimal, InvalidOperation
from database import Database
from auth import verify_api_key
import datetime
import random
import string
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

router = APIRouter()

# Email credentials and constants
APP_PASSWORD = "dcfl kybe tokq ydyv"
SENDER_EMAIL = "admin@cronbid.com"
ADMIN_EMAIL = "admin@cronbid.com"
APP_NAME = "CRONBID"
LOGO_URL = "https://ads.cronbid.com/cronbaylogo.png"

class FundRequest(BaseModel):
    user_id: str = Field(..., min_length=3)
    user_name: str = Field(..., min_length=1)
    fund: str = Field(..., min_length=1)
    created_by: str = Field(..., min_length=1)
    email: str = Field(..., min_length=5)

def generate_clean_id(prefix: str) -> str:
    timestamp = datetime.datetime.now().strftime("%y%m%d%H%M%S")
    rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{prefix}-{timestamp}{rand_suffix}"

def send_fund_email(to_email: str, user_name: str, amount: str, balance: str, transaction_type: str):
    subject = f"{APP_NAME} | Fund {transaction_type.capitalize()}"

    html_content = f"""
    <html>
    <body style="margin: 0; padding: 0; background: linear-gradient(135deg, rgb(26,38,113), rgb(44,98,174)); font-family: Arial, sans-serif;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="padding: 40px 0;">
            <tr>
                <td align="center">
                    <table border="0" cellpadding="0" cellspacing="0" width="600" style="background: #ffffff; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); overflow: hidden;">
                        <tr>
                            <td align="center" style="padding: 30px 20px 20px;">
                                <img src="{LOGO_URL}" alt="{APP_NAME} Logo" style="max-width: 180px; display: block; margin: 0 auto;" />
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 0 40px 20px; text-align: center;">
                                <h2 style="color: #1a2671;">Hi {user_name},</h2>
                                <p style="font-size: 16px; color: #333333;">
                                    Your account has been <strong style="color: #1a2671;">{transaction_type}ed</strong> with <strong style="color: #1a2671;">INR {amount}</strong>.
                                </p>
                                <p style="font-size: 16px; color: #333333;">
                                    Your updated balance is <strong style="color: #1a2671;">INR {balance}</strong>.
                                </p>
                                <p style="font-size: 15px; color: #777777; margin-top: 30px;">
                                    Thank you for using <strong>{APP_NAME}</strong>.
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 20px; background: #f4f4f4; text-align: center; font-size: 12px; color: #999;">
                                &copy; {datetime.datetime.now().year} {APP_NAME}. All rights reserved.
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Failed to send email: {e}")

@router.post("/post_fund/", dependencies=[Depends(verify_api_key)])
async def post_funds(payload: FundRequest):
    try:
        try:
            fund_amount = Decimal(payload.fund)
            if fund_amount <= 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            raise HTTPException(status_code=400, detail="Invalid fund amount. Must be a positive number.")

        fund_id = generate_clean_id("fund")
        transaction_id = generate_clean_id("txn")
        currency = "INR"
        current_time = datetime.datetime.now()

        pool = await Database.connect()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("START TRANSACTION")

                await cur.execute("""
                    SELECT fund FROM cronbid_user_funds WHERE user_id = %s
                """, (payload.user_id,))
                result = await cur.fetchone()

                if result:
                    current_fund = Decimal(result[0])
                    new_fund = current_fund + fund_amount
                    await cur.execute("""
                        UPDATE cronbid_user_funds
                        SET fund = %s, updated_at = %s
                        WHERE user_id = %s
                    """, (new_fund, current_time, payload.user_id))
                else:
                    new_fund = fund_amount
                    await cur.execute("""
                        INSERT INTO cronbid_user_funds (
                            fund_id, user_id, user_name, fund, currency, created_by
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        fund_id, payload.user_id, payload.user_name,
                        fund_amount, currency, payload.created_by
                    ))

                await cur.execute("""
                    INSERT INTO cronbid_fund_transactions (
                        transaction_id, user_id, user_name, currency,
                        amount, type, description, balance_after_transaction,
                        created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    transaction_id, payload.user_id, payload.user_name,
                    currency, fund_amount, "credit", "Fund added",
                    new_fund, payload.created_by
                ))

                await cur.execute("COMMIT")

        send_fund_email(payload.email, payload.user_name, str(fund_amount), str(new_fund), "credit")

        return {
            "message": "Funds processed successfully.",
            "user_id": payload.user_id,
            "fund_id": fund_id,
            "amount_added": str(fund_amount),
            "new_balance": str(new_fund)
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        async with (await Database.connect()).acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("ROLLBACK")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
