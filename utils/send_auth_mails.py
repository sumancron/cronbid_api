import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

APP_PASSWORD = "dcfl kybe tokq ydyv"
SENDER_EMAIL = "admin@cronbid.com"
ADMIN_EMAIL = "admin@cronbid.com"
APP_NAME = "CRONBID"
LOGO_URL = "https://ads.cronbid.com/cronbaylogo.png"

def send_user_confirmation_email(to_email: str, first_name: str):
    subject = f"Welcome to {APP_NAME} - Registration Successful"
    html_content = f"""
    <html>
    <body style="background: linear-gradient(to bottom, #142c54, #1d179b); color: white; font-family: Arial, sans-serif; padding: 40px;">
        <div style="max-width: 600px; margin: auto; text-align: center;">
            <img src="{LOGO_URL}" alt="CRONBID Logo" style="width: 150px; margin-bottom: 30px;" />
            <h2>Hi {first_name},</h2>
            <p>Thank you for registering at <strong>{APP_NAME}</strong>.</p>
            <p>Your account has been successfully created. Once your account is activated, you will be able to log in and start using all features.</p>
            <p>We'll notify you once it's activated.</p>
            <br />
            <p>Regards,<br /><strong>{APP_NAME} Team</strong></p>
        </div>
    </body>
    </html>
    """
    send_email(to_email, subject, html_content)


def send_admin_user_alert(user_data: dict):
    subject = f"New User Registered on {APP_NAME}"
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2>New User Registration Alert</h2>
        <p>A new user has registered on {APP_NAME}. Please review and activate or reject the account.</p>
        <ul>
            {''.join(f"<li><strong>{key.replace('_', ' ').capitalize()}</strong>: {value}</li>" for key, value in user_data.items())}
        </ul>
        <p><strong>Action Needed:</strong> Review and activate or reject this user in the admin panel. <a href="https://ads.cronbid.com/dashboard/users">USERS MANAGEMENT SECTION</a> </p>
    </body>
    </html>
    """
    send_email(ADMIN_EMAIL, subject, html_content)


def send_email(to_email: str, subject: str, html_content: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)

    except Exception as e:
        print(f"Email sending failed: {e}")

def send_partner_status_notification(status: str, source_id: int, campaign_id: int, source_name:str, campaign_name:str):
    subject = f"{APP_NAME} - Partner Status Update"
    html_content = f"""
    <html>
    <body style="background: linear-gradient(to bottom, #142c54, #1d179b); color: white; font-family: Arial, sans-serif; padding: 40px;">
        <div style="max-width: 600px; margin: auto; text-align: center;">
            <img src="{LOGO_URL}" alt="CRONBID Logo" style="width: 150px; margin-bottom: 30px;" />
            <h2>Partner Status Update</h2>
            <p>A partner status has been {'updated' if status else 'created'}.</p>
            <ul style="list-style: none; padding: 0;">
                <li><strong>Status:</strong> {status}</li>
                <li><strong>Source ID:</strong> {source_id} {source_name}</li>
                <li><strong>Campaign ID:</strong> {campaign_id} {campaign_name}</li>
            </ul>
            <br />
            <p>Regards,<br /><strong>{APP_NAME} Team</strong></p>
        </div>
    </body>
    </html>
    """
    send_email(ADMIN_EMAIL, subject, html_content)

def send_sub2_status_notification(status: str, campaign_id: int, source_id: int, sub2: str,source_name:str,campaign_name:str):
    subject = f"{APP_NAME} - Sub2 Status Update"
    html_content = f"""
    <html>
    <body style="background: linear-gradient(to bottom, #142c54, #1d179b); color: white; font-family: Arial, sans-serif; padding: 40px;">
        <div style="max-width: 600px; margin: auto; text-align: center;">
            <img src="{LOGO_URL}" alt="CRONBID Logo" style="width: 150px; margin-bottom: 30px;" />
            <h2>Sub2 Status Update</h2>
            <p>A sub2 status has been {'updated' if status else 'created'}.</p>
            <ul style="list-style: none; padding: 0;">
                <li><strong>Status:</strong> {status}</li>
                <li><strong>Campaign ID:</strong> {campaign_id} {campaign_name}</li>
                <li><strong>Source ID:</strong> {source_id} {source_name}</li>
                <li><strong>Sub2:</strong> {sub2}</li>
            </ul>
            <br />
            <p>Regards,<br /><strong>{APP_NAME} Team</strong></p>
        </div>
    </body>
    </html>
    """
    send_email(ADMIN_EMAIL, subject, html_content)
