"""
emailer.py — send email via Gmail SMTP
======================================
Uses Python's built-in smtplib (no extra library). Reads credentials from
environment variables so secrets never live in the code:

    GMAIL_ADDRESS   your full gmail address, e.g. you@gmail.com
    GMAIL_APP_PW    the 16-char app password (spaces removed)

If those aren't set, send_email() does nothing and returns False, so the app
still works without email configured (e.g. during local testing).
"""
import os
import smtplib
import ssl
from email.message import EmailMessage

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _credentials():
    addr = os.environ.get("GMAIL_ADDRESS")
    pw = os.environ.get("GMAIL_APP_PW")
    if pw:
        pw = pw.replace(" ", "")   # allow pasting the spaced form
    return addr, pw


def email_configured() -> bool:
    addr, pw = _credentials()
    return bool(addr and pw)


def send_email(to_address: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True on success, False if not configured
    or on failure (failure is logged, never crashes the app)."""
    addr, pw = _credentials()
    if not (addr and pw):
        print("[emailer] GMAIL_ADDRESS / GMAIL_APP_PW not set — skipping email.")
        return False
    if not to_address:
        print("[emailer] no recipient address — skipping email.")
        return False

    msg = EmailMessage()
    msg["From"] = addr
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls(context=context)   # upgrade to encrypted TLS
            server.login(addr, pw)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[emailer] failed to send to {to_address}: {e}")
        return False


# ---------- ready-made messages for our two moments ----------
def send_welcome(to_address: str, name: str) -> bool:
    return send_email(
        to_address,
        "Welcome to Marginalia",
        f"Hi {name},\n\n"
        "Your Marginalia account is ready. Upload research papers and ask "
        "questions, get plain-language explanations, or quiz yourself — every "
        "answer is grounded in your own papers.\n\n"
        "Happy studying.\n— Marginalia",
    )


def send_new_password(to_address: str, name: str, new_password: str) -> bool:
    return send_email(
        to_address,
        "Your Marginalia password was reset",
        f"Hi {name},\n\n"
        "You requested a password reset. Your new temporary password is:\n\n"
        f"    {new_password}\n\n"
        "Log in with it, then change it from your account. If you didn't request "
        "this, contact the site owner.\n\n— Marginalia",
    )
