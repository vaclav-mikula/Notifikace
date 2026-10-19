#!/usr/bin/env python3
"""Kontrola nových objednávek na objednavky.cun.cz.

Přihlásí se, přečte ID objednávek ze seznamu "Všechny" a "Potvrzené"
a pro každé nové ID pošle e-mail. Stav (naposledy viděná ID) se
ukládá do seen_orders.json a commituje zpět přes GitHub Actions.
"""

import json
import os
import re
import smtplib
import sys
from email.message import EmailMessage
from html.parser import HTMLParser
from pathlib import Path

import requests

BASE = "https://objednavky.cun.cz"
LIST_URL = f"{BASE}/objednavky"
CONFIRMED_URL = f"{BASE}/objednavky/moje-potvrzene"
LOGIN_URL = f"{BASE}/login"
STATE_FILE = Path(__file__).parent / "seen_orders.json"


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


def extract_ids(html: str, label: str) -> set[int]:
    """Vrátí ID objednávek ze seznamu (checkboxy name="id[]").

    Počet nalezených ID se ověřuje proti číslu ve filtru, např. "Všechny (N)".
    Kdyby se změnila struktura stránky nebo přibylo stránkování, skript raději
    skončí chybou, než aby stav přepsal neúplným seznamem a pak poslal falešné e-maily.
    """
    m = re.search(rf"{label}\s*\((\d+)\)", html)
    if not m:
        sys.exit(f"CHYBA: nepodařilo se najít '{label} (N)' na stránce")
    expected = int(m.group(1))
    ids = {int(v) for v in re.findall(r'name="id\[\]"\s+value="(\d+)"', html)}
    if len(ids) != expected:
        sys.exit(f"CHYBA: v seznamu '{label}' nalezeno {len(ids)} objednávek, filtr uvádí {expected}")
    return ids


class TitleParser(HTMLParser):
    """Sbírá názvy akcí: tučný text v buňce "Název akce" (td.show-modal) řádku <tr id="N">."""

    def __init__(self) -> None:
        super().__init__()
        self.titles: dict[int, str] = {}
        self._row: int | None = None
        self._in_cell = False
        self._in_strong = False
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tr":
            self._row = int(a["id"]) if (a.get("id") or "").isdigit() else None
        elif tag == "td":
            self._in_cell = self._row is not None and "show-modal" in (a.get("class") or "").split()
        elif tag == "strong" and self._in_cell and self._row not in self.titles:
            self._in_strong = True
            self._text = []

    def handle_endtag(self, tag):
        if tag == "strong" and self._in_strong:
            self._in_strong = False
            self.titles[self._row] = " ".join("".join(self._text).split())
        elif tag == "td":
            self._in_cell = False

    def handle_data(self, data):
        if self._in_strong:
            self._text.append(data)


def extract_titles(html: str) -> dict[int, str]:
    p = TitleParser()
    p.feed(html)
    return p.titles


def describe(ids: set[int], titles: dict[int, str]) -> str:
    # Název chybí jen při změně struktury stránky — e-mail přesto odejde.
    return "\n".join(f"- {titles.get(i) or f'(název nenalezen, ID {i})'}" for i in sorted(ids))


def load_state() -> dict | None:
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return {"all": set(data["all"]), "confirmed": set(data["confirmed"])}
    return None


def save_state(all_ids: set[int], confirmed_ids: set[int]) -> None:
    STATE_FILE.write_text(
        json.dumps({"all": sorted(all_ids), "confirmed": sorted(confirmed_ids)}, indent=2) + "\n",
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
    all_ids = extract_ids(html, "Všechny")
    titles = extract_titles(html)

    r = session.get(CONFIRMED_URL, timeout=30)
    r.raise_for_status()
    confirmed_ids = extract_ids(r.text, "Potvrzené")
    titles = extract_titles(r.text) | titles
    print(f"Všechny: {len(all_ids)}, Potvrzené: {len(confirmed_ids)}")

    if env("TEST_EMAIL", required=False) == "true":
        # Ukázka obou e-mailů se skutečnými názvy (až tři nejnovější objednávky), stav se nemění.
        send_email(
            "[TEST] ČUN Nová objednávka",
            f"Nové objednávky:\n\n{describe(set(sorted(all_ids)[-3:]), titles)}\n\nOtevřít: {LIST_URL}\n",
        )
        send_email(
            "[TEST] ČUN Potvrzení objednávky",
            f"Potvrzení na přepis:\n\n{describe(set(sorted(confirmed_ids)[-3:]), titles)}\n\nOtevřít: {CONFIRMED_URL}\n",
        )
        return

    state = load_state()
    if state is None:
        print("První běh — ukládám aktuální stav bez notifikace.")
        save_state(all_ids, confirmed_ids)
        return

    new = all_ids - state["all"]
    if new:
        n = len(new)
        send_email(
            f"ČUN Nová objednávka (+{n})",
            f"Nové objednávky:\n\n{describe(new, titles)}\n\nOtevřít: {LIST_URL}\n",
        )

    newly_confirmed = confirmed_ids - state["confirmed"]
    if newly_confirmed:
        n = len(newly_confirmed)
        send_email(
            f"ČUN Potvrzení objednávky (+{n})",
            f"Potvrzení na přepis:\n\n{describe(newly_confirmed, titles)}\n\nOtevřít: {CONFIRMED_URL}\n",
        )

    if all_ids != state["all"] or confirmed_ids != state["confirmed"]:
        save_state(all_ids, confirmed_ids)
    else:
        print("Beze změny.")


if __name__ == "__main__":
    main()
