#!/usr/bin/env python3
"""Odeslání e-mailu přes SMTP (jen standardní knihovna, bez pip install).

Použití z workflow:  python3 notify.py "Předmět" "Text e-mailu"
Používá ho i check_orders.py (import send_email).
"""

import os
import smtplib
import sys
from email.message import EmailMessage


def _env(name: str, default: str = "") -> str:
    val = os.environ.get(name, "").strip() or default
    if not val:
        sys.exit(f"CHYBA: chybí proměnná prostředí {name}")
    return val


def send_email(subject: str, body: str) -> None:
    smtp_host = _env("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(_env("SMTP_PORT", "587"))
    smtp_user = _env("SMTP_USER")
    smtp_pass = _env("SMTP_PASS")
    mail_to = _env("MAIL_TO")
    mail_from = _env("MAIL_FROM", smtp_user)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as s:
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.send_message(msg)
    print(f"E-mail odeslán: {subject}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Použití: notify.py PŘEDMĚT TEXT")
    send_email(sys.argv[1], sys.argv[2])
