import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

APP_PASSWORD = "vlmx lbff rsvo llvr"
SENDER_EMAIL = "suman@cronbaytechnologies.com"
ADMIN_EMAIL = "suman@cronbaytechnologies.com"
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
        <p><strong>Action Needed:</strong> Review and activate or reject this user in the admin panel.</p>
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
