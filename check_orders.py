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
    val = os.environ.get(name, "").strip()
    if not val:
        val = default
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


def extract_counts(html: str) -> tuple[int, int]:
    """Vrátí (vsechny, doporucene). Confirmed = vsechny - doporucene."""
    m_all = re.search(r"Všechny\s*\((\d+)\)", html)
    m_rec = re.search(r"Doporučené\s*\((\d+)\)", html)
    if not m_all:
        sys.exit("CHYBA: nepodařilo se najít 'Všechny (N)' na stránce")
    if not m_rec:
        sys.exit("CHYBA: nepodařilo se najít 'Doporučené (N)' na stránce")
    return int(m_all.group(1)), int(m_rec.group(1))


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"total": None, "confirmed": None}


def save_state(total: int, confirmed: int) -> None:
    STATE_FILE.write_text(
        json.dumps({"total": total, "confirmed": confirmed}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def send_email(subject: str, body: str) -> None:
    smtp_host = env("SMTP_HOST", required=False, default="smtp.gmail.com")
    smtp_port = int(env("SMTP_PORT", required=False, default="587"))
    smtp_user = env("SMTP_USER")
    smtp_pass = env("SMTP_PASS")
    mail_to = env("MAIL_TO")
    mail_from = env("MAIL_FROM", required=False, default=smtp_user)

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


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (order-notifier)"})

    html = login(session, env("CUN_EMAIL"), env("CUN_PASSWORD"))
    total, recommended = extract_counts(html)
    confirmed = total - recommended
    print(f"Všechny: {total}, Doporučené: {recommended}, Potvrzené: {confirmed}")

    state = load_state()
    last_total = state.get("total")
    last_confirmed = state.get("confirmed")

    if last_total is None:
        print("První běh — ukládám aktuální stav bez notifikace.")
        save_state(total, confirmed)
        return

    changed = False

    if total > last_total:
        diff = total - last_total
        send_email(
            f"ČUN Nová objednávka (+{diff})",
            f"Na {LIST_URL} přibyl{'a' if diff == 1 else 'y'} nová objednávka.\n\n"
            f"Dříve: {last_total}\nNyní:  {total} (+{diff})\n\nOtevřít: {LIST_URL}\n",
        )
        changed = True

    if confirmed > last_confirmed:
        diff = confirmed - last_confirmed
        send_email(
            f"ČUN Potvrzení objednávky (+{diff})",
            f"Na {LIST_URL} bylo potvrzeno {diff} objednávk{'a' if diff == 1 else 'y'}.\n\n"
            f"Potvrzené dříve: {last_confirmed}\nPotvrzené nyní:  {confirmed} (+{diff})\n\nOtevřít: {LIST_URL}\n",
        )
        changed = True

    if total < last_total or confirmed < last_confirmed:
        print(f"Počty klesly (Všechny: {last_total}→{total}, Potvrzené: {last_confirmed}→{confirmed}), aktualizuji stav.")
        changed = True

    if changed:
        save_state(total, confirmed)
    else:
        print("Beze změny.")


if __name__ == "__main__":
    main()
