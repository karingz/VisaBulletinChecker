import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def is_valid_email(email):
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(email_regex, email) is not None

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

def _wrap_email_html(body, bulletin_month, unsubscribe_url):
    """Wrap bulletin content in a polished email template."""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background:#f1f5f9; font-family:Arial, Helvetica, sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9; padding:24px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px; width:100%; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.08);">

  <!-- Header bar -->
  <tr><td style="background:linear-gradient(135deg,#1e293b,#0f172a); padding:24px 32px;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="font-size:18px; font-weight:700; color:#f1f5f9; letter-spacing:-0.02em;">
        Visa Bulletin Checker
      </td>
      <td align="right" style="font-size:12px; color:#94a3b8;">
        {bulletin_month}
      </td>
    </tr></table>
  </td></tr>

  <!-- Content -->
  <tr><td style="padding:28px 32px;">
    {body}
  </td></tr>

  <!-- Footer -->
  <tr><td style="padding:20px 32px 28px; border-top:1px solid #e2e8f0;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="font-size:13px; color:#64748b;">
        <a href="https://visa-bulletin-checker.vercel.app/" target="_blank" style="color:#2563eb; text-decoration:none; font-weight:500;">Visit Website</a>
        &nbsp;&nbsp;&middot;&nbsp;&nbsp;
        <a href="https://visa-bulletin-checker.vercel.app/history" target="_blank" style="color:#2563eb; text-decoration:none; font-weight:500;">View History</a>
        &nbsp;&nbsp;&middot;&nbsp;&nbsp;
        <a href="{unsubscribe_url}" target="_blank" style="color:#94a3b8; text-decoration:none;">Unsubscribe</a>
      </td>
    </tr></table>
  </td></tr>

</table>
<p style="text-align:center; font-size:11px; color:#94a3b8; margin:16px 0 0;">
  Visa Bulletin Checker &mdash; automated updates from the U.S. Department of State
</p>
</td></tr>
</table>
</body>
</html>"""

def send_email(to_email, subject, body, bulletin_month):
    try:
        from urllib.parse import quote
        unsubscribe_url = f"https://visa-bulletin-checker.vercel.app/unsubscribe?email={quote(to_email)}"

        # Strip the clock/updated section from body
        body = re.split(r'<div id="last-updated-wrap"', body)[0]
        # Also handle legacy format
        body = body.split("⌛ Last updated time:")[0]

        html = _wrap_email_html(body, bulletin_month, unsubscribe_url)

        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print(f"Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
