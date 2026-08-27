#!/usr/bin/env python3
"""Kontrola nových objednávek na objednavky.cun.cz.

Přihlásí se, přečte počet objednávek z textu "Všechny (N)"
a při zvýšení pošle e-mail. Stav (poslední známý počet) se
ukládá do seen_count.json a commituje zpět přes GitHub Actions.
"""

import json
import os
import re
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

import requests

BASE = "https://objednavky.cun.cz"
LIST_URL = f"{BASE}/objednavky"
LOGIN_URL = f"{BASE}/login"
STATE_FILE = Path(__file__).parent / "seen_count.json"


def env(name: str, required: bool = True, default: str = "") -> str:
    val = os.environ.get(name, default)
    if required and not val:
        sys.exit(f"CHYBA: chybí proměnná prostředí {name}")
    return val


def get_csrf(html: str) -> str:
    m = re.search(r'name="_token"\s+value="([^"]+)"', html)
    if not m:
        m = re.search(r'content="([^"]+)"\s+name="csrf-token"', html)
    if not m:
        sys.exit("CHYBA: nepodařilo se najít CSRF token")
    return m.group(1)


def login(session: requests.Session, email: str, password: str) -> str:
    r = session.get(LIST_URL, timeout=30)
    r.raise_for_status()
    token = get_csrf(r.text)

    session.post(
        LOGIN_URL,
        data={"_token": token, "email": email, "password": password, "remember": "1"},
        timeout=30,
        allow_redirects=True,
    ).raise_for_status()

    r = session.get(LIST_URL, timeout=30)
    r.raise_for_status()

    if 'name="password"' in r.text:
        sys.exit("CHYBA: přihlášení selhalo — zkontroluj CUN_EMAIL a CUN_PASSWORD")
    return r.text


def extract_count(html: str) -> int:
    m = re.search(r"Všechny\s*\((\d+)\)", html)
    if not m:
        sys.exit("CHYBA: nepodařilo se najít text 'Všechny (N)' na stránce — možná se změnila struktura")
    return int(m.group(1))


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"count": None}


def save_state(count: int) -> None:
    STATE_FILE.write_text(
        json.dumps({"count": count}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def send_email(new_count: int, old_count: int) -> None:
    smtp_host = env("SMTP_HOST", required=False, default="smtp.gmail.com")
    smtp_port = int(env("SMTP_PORT", required=False, default="587"))
    smtp_user = env("SMTP_USER")
    smtp_pass = env("SMTP_PASS")
    mail_to = env("MAIL_TO")
    mail_from = env("MAIL_FROM", required=False, default=smtp_user)

    diff = new_count - old_count
    subject = f"Nová objednávka přepisu (+{diff})"
    body = (
        f"Na {LIST_URL} přibyly nové objednávky.\n\n"
        f"Dříve: {old_count}\n"
        f"Nyní:  {new_count} (+{diff})\n\n"
        f"Otevřít: {LIST_URL}\n"
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as s:
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.send_message(msg)
    print(f"E-mail odeslán na {mail_to}")


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (order-notifier)"})

    html = login(session, env("CUN_EMAIL"), env("CUN_PASSWORD"))
    count = extract_count(html)
    print(f"Počet objednávek: {count}")

    state = load_state()
    last = state.get("count")

    if last is None:
        print("První běh — ukládám aktuální počet bez notifikace.")
        save_state(count)
        return

    if count > last:
        print(f"NOVÉ objednávky: {last} → {count}")
        send_email(count, last)
        save_state(count)
    elif count < last:
        print(f"Počet klesl ({last} → {count}), aktualizuji stav.")
        save_state(count)
    else:
        print("Beze změny.")


if __name__ == "__main__":
    main()
