import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def is_valid_email(email):
    import re
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(email_regex, email) is not None

SMTP_SERVER = "smtp.gmail.com"  # Replace with your SMTP server
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER")  # Set your email in environment variables
SMTP_PASS = os.getenv("SMTP_PASS")  # Set your email password in environment variables

def send_email(to_email, subject, body, bulletin_month):
    try:
        # Append the link and unsubscribe note to the email body
        body += f"""
                <br><br>
                <p>🚀 <a href="https://visa-bulletin-checker.vercel.app/" target="_blank">Visit Visa Bulletin Checker Page</a> ⬅ 🔕 Unsubscribe here</p>
                """

        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print(f"📧 Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")