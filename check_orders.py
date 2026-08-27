#!/usr/bin/env python3
"""Kontrola nových objednávek na objednavky.cun.cz.

Přihlásí se, načte seznam objednávek, porovná s uloženým stavem
(seen_ids.json) a při nové objednávce pošle e-mail. Stav se ukládá
zpět do repozitáře přes GitHub Actions.
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
STATE_FILE = Path(__file__).parent / "seen_ids.json"

# URL formát: https://objednavky.cun.cz/13443-nazev-objednavky
ID_PATTERNS = [
    re.compile(r'href="(?:https://objednavky\.cun\.cz)?/(\d+)-'),
]


def env(name: str, required: bool = True, default: str = "") -> str:
    val = os.environ.get(name, default)
    if required and not val:
        sys.exit(f"CHYBA: chybí proměnná prostředí {name}")
    return val


def get_csrf(html: str) -> str:
    m = re.search(r'name="_token"\s+value="([^"]+)"', html)
    if not m:
        m = re.search(r'name="csrf-token"\s+content="([^"]+)"', html)
    if not m:
        sys.exit("CHYBA: nepodařilo se najít CSRF token na přihlašovací stránce")
    return m.group(1)


def login(session: requests.Session, email: str, password: str) -> str:
    r = session.get(LIST_URL, timeout=30)
    r.raise_for_status()
    token = get_csrf(r.text)

    r = session.post(
        LOGIN_URL,
        data={"_token": token, "email": email, "password": password, "remember": "1"},
        timeout=30,
        allow_redirects=True,
    )
    r.raise_for_status()

    # Po přihlášení načteme seznam objednávek
    r = session.get(LIST_URL, timeout=30)
    r.raise_for_status()

    if 'name="password"' in r.text and 'name="email"' in r.text:
        sys.exit("CHYBA: přihlášení selhalo (vrácena přihlašovací stránka) — zkontroluj e-mail/heslo")
    return r.text


def extract_ids(html: str) -> set[str]:
    ids: set[str] = set()
    for pat in ID_PATTERNS:
        ids.update(pat.findall(html))
    return ids


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"seen": [], "seeded": False}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def send_email(new_ids: list[str]) -> None:
    smtp_host = env("SMTP_HOST", required=False, default="smtp.gmail.com")
    smtp_port = int(env("SMTP_PORT", required=False, default="587"))
    smtp_user = env("SMTP_USER")
    smtp_pass = env("SMTP_PASS")
    mail_to = env("MAIL_TO")
    mail_from = env("MAIL_FROM", required=False, default=smtp_user)

    count = len(new_ids)
    subject = f"Nová objednávka přepisu ({count})" if count > 1 else "Nová objednávka přepisu"
    body = (
        f"Na {LIST_URL} se objevila nová objednávka.\n\n"
        f"Počet nových: {count}\n"
        f"ID: {', '.join(new_ids)}\n\n"
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
    print(f"E-mail odeslán na {mail_to} (nových: {count})")


def main() -> None:
    email = env("CUN_EMAIL")
    password = env("CUN_PASSWORD")

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (order-notifier)"})

    html = login(session, email, password)
    current_ids = extract_ids(html)
    print(f"Nalezeno objednávek: {len(current_ids)}")

    if not current_ids:
        # Ochrana: pokud parser nic nenašel, nechceme smazat stav ani
        # falešně tvrdit, že objednávky zmizely. Skončíme bez změny.
        print("VAROVÁNÍ: nenalezeny žádné ID objednávek — možná se změnila struktura stránky. Stav neměním.")
        sys.exit(0)

    state = load_state()
    seen = set(state.get("seen", []))

    new_ids = sorted(current_ids - seen, key=lambda x: int(x))

    if not state.get("seeded"):
        # První běh: uložíme aktuální stav bez notifikace
        print("První běh — ukládám aktuální stav bez notifikace.")
        save_state({"seen": sorted(current_ids, key=lambda x: int(x)), "seeded": True})
        return

    if new_ids:
        print(f"NOVÉ objednávky: {new_ids}")
        send_email(new_ids)
    else:
        print("Žádné nové objednávky.")

    # Uložíme aktuální stav (sjednocení, aby nezmizely dřívější)
    save_state(
        {"seen": sorted(seen | current_ids, key=lambda x: int(x)), "seeded": True}
    )


if __name__ == "__main__":
    main()
