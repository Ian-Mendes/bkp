import os, smtplib
from email.message import EmailMessage

def _cfg():
    return {
        "host": os.getenv("SMTP_HOST", "mailpit"),
        "port": int(os.getenv("SMTP_PORT", "1025")),
        "user": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "starttls": os.getenv("SMTP_STARTTLS", "0") == "1",
        "sender": os.getenv("MAIL_FROM", "BKP <no-reply@bkp.local>"),
    }

def frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")

def send_smtp(to: str, subject: str, text: str) -> None:
    c = _cfg()
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = c["sender"], to, subject
    msg.set_content(text)
    with smtplib.SMTP(c["host"], c["port"], timeout=15) as s:
        if c["starttls"]:
            s.starttls()
        if c["user"]:
            s.login(c["user"], c["password"])
        s.send_message(msg)
