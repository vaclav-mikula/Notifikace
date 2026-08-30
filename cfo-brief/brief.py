import os
import sys
import requests
import markdown
from google import genai
from google.genai import types
from datetime import datetime

MODEL = "gemini-3.7-flash"  # nejnovější generace, zdarma přes Google AI Studio; pro víc kvality lze přejít na gemini-3.1-pro-preview (může chtít fakturaci)

SYSTEM_PROMPT = """\
Jsi zkušený finanční analytik připravující týdenní briefing pro CFO mezinárodní banky.
Píšeš česky. Mezinárodní názvy institucí, firem a termíny ponecháš v originále (Fed, ECB, Basel III apod.).
Buď konkrétní — uváděj čísla, procenta, názvy zemí a institucí. Vyhni se obecným frázím.
"""

BRIEF_PROMPT = """\
Vytvoř týdenní zpravodajský briefing za posledních 7 dní (do {date}) pro CFO mezinárodní banky.
Prohledej aktuální zprávy a vytvoř strukturovaný přehled.

Struktura (dodržuj přesně):

## Ekonomika & trhy
- Makroekonomická data: inflace, HDP, pracovní trh (EU, USA, ČR/SR)
- Centrální banky: ECB, Fed, ČNB — rozhodnutí, signály, výhled
- Měnové kurzy, klíčové komodity (ropa, zlato)
- Akciové a dluhopisové trhy — výrazné pohyby a jejich příčiny
(4–6 bodů, každý max. 2 věty: fakt + co to znamená pro banku/CFO)

## Geopolitika
- Události s přímým dopadem na finanční trhy nebo obchod
- Sankce, obchodní politika, celní spory
- Politická rizika v klíčových regionech (EU, USA, Čína, Blízký východ)
(3–5 bodů)

## Regulace & bankovnictví
- Novinky z bankovní regulace (EBA, ECB SSM, Basel)
- Významné události v sektoru: M&A, výsledky, krize
- Fintech a krypto — regulatorní vývoj
(3–4 body)

## Bezpečnost & kyber
- Kybernetické incidenty nebo hrozby relevantní pro finanční sektor
- Geopolitická bezpečnost s dopadem na banky
(2–3 body)

## Na radar tento týden
Tři věci, které by CFO neměl přehlédnout — s krátkým vysvětlením proč.

---
Celkový rozsah: 700–900 slov. Dnešní datum: {date}.
"""

RESEND_URL = "https://api.resend.com/emails"


def generate_brief(date_str: str) -> str:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=MODEL,
        contents=BRIEF_PROMPT.format(date=date_str),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    return response.text


def build_html(content_md: str, date_str: str) -> str:
    body = markdown.markdown(content_md, extensions=["nl2br"])
    return f"""\
<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 16px;
    line-height: 1.7;
    color: #1a1a1a;
    max-width: 680px;
    margin: 32px auto;
    padding: 0 24px;
    background: #fff;
  }}
  h1 {{ color: #1a3a5c; font-size: 22px; border-bottom: 2px solid #1a3a5c;
        padding-bottom: 8px; margin-bottom: 4px; }}
  h2 {{ color: #1a3a5c; font-size: 18px; margin-top: 32px; margin-bottom: 10px; }}
  ul {{ padding-left: 22px; margin: 8px 0; }}
  li {{ margin: 6px 0; }}
  hr {{ border: none; border-top: 1px solid #ddd; margin: 28px 0; }}
  .footer {{ color: #888; font-size: 12px; margin-top: 48px;
             border-top: 1px solid #eee; padding-top: 14px; }}
</style>
</head>
<body>
<h1>CFO Týdenní briefing &mdash; {date_str}</h1>
{body}
<div class="footer">Generováno automaticky &middot; Gemini 3.7 Flash + Google Search &middot; {date_str}</div>
</body>
</html>"""


def send_email(html: str, date_str: str) -> None:
    resp = requests.post(
        RESEND_URL,
        headers={
            "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "from": os.environ["FROM_EMAIL"],
            "to": [os.environ["TO_EMAIL"]],
            "subject": f"CFO Briefing — {date_str}",
            "html": html,
        },
        timeout=30,
    )
    resp.raise_for_status()
    print(f"Email sent: {resp.json().get('id')}")


if __name__ == "__main__":
    from zoneinfo import ZoneInfo
    now_prague = datetime.now(ZoneInfo("Europe/Prague"))
    if now_prague.hour != 6 and "FORCE_SEND" not in os.environ:
        print(f"Praha {now_prague.strftime('%H:%M')} — není 6:xx, přeskakuji.")
        sys.exit(0)

    fmt = "%#d. %#m. %Y" if sys.platform == "win32" else "%-d. %-m. %Y"
    date_str = datetime.now().strftime(fmt)

    print(f"Generating brief for {date_str}...")
    content = generate_brief(date_str)

    print("\n--- BRIEF ---\n")
    print(content)
    print("\n--- END ---\n")

    html = build_html(content, date_str)
    send_email(html, date_str)
