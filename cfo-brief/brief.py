import os
import re
import sys
import requests
import markdown
from google import genai
from google.genai import types
from datetime import datetime

MODEL = "gemini-3.7-flash"  # nejnovější generace, zdarma přes Google AI Studio; pro víc kvality lze přejít na gemini-3.1-pro-preview (může chtít fakturaci)

SYSTEM_PROMPT = """\
Jsi zkušený finanční analytik připravující týdenní briefing pro CFO mezinárodní banky.
Čtenář má výborné účetní a finanční znalosti, ale potřebuje budovat přehled v makroekonomii a geopolitice.
Proto u každé ekonomické nebo geopolitické zprávy vždy vysvětli i kontext: co ta událost znamená, proč k ní došlo, a jaký má dopad na banku nebo finanční trhy. Nepředpokládej, že čtenář zná ekonomické mechanismy — raději je stručně vysvětli.
Píšeš česky. Mezinárodní názvy institucí, firem a termíny ponecháš v originále (Fed, ECB, Basel III apod.).
Buď konkrétní — uváděj čísla, procenta, názvy zemí a institucí. Vyhni se obecným frázím.
DŮLEŽITÉ: Pro konkrétní čísla (úrokové sazby, kurzy, indexy) vždy uváděj pouze hodnoty, které jsi přímo dohledal přes vyhledávání. Nikdy si číslo nedomýšlej ani neodvozuj z paměti.
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
(4–6 bodů; ke každému bodu: fakt s čísly + vysvětlení mechanismu + co to znamená pro banku/CFO; klidně 3–4 věty na bod)

## Geopolitika
- Události s přímým dopadem na finanční trhy nebo obchod
- Sankce, obchodní politika, celní spory
- Politická rizika v klíčových regionech (EU, USA, Čína, Blízký východ)
(3–5 bodů; ke každému: co se stalo + proč je to důležité + konkrétní finanční nebo obchodní dopad)

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
Celkový rozsah: 900–1200 slov. Dnešní datum: {date}.
"""

RESEND_URL = "https://api.resend.com/emails"


def fetch_verified_data() -> str:
    """Fetch key financial figures from authoritative sources and return as prompt context."""
    lines = []

    # EUR/CZK a USD/CZK z ČNB API
    try:
        r = requests.get("https://api.cnb.cz/cnbapi/exrates/daily?lang=EN", timeout=10)
        r.raise_for_status()
        valid_for = ""
        for item in r.json().get("rates", []):
            if not valid_for:
                valid_for = item.get("validFor", "")
            if item["currencyCode"] in ("EUR", "USD"):
                per_unit = item["rate"] / item["amount"]
                lines.append(f"{item['currencyCode']}/CZK: {per_unit:.3f} (ČNB, {valid_for})")
    except Exception as e:
        print(f"ČNB kurzy: chyba ({e})")

    # ČNB 2T repo sazba z webu ČNB
    try:
        r = requests.get(
            "https://www.cnb.cz/en/monetary-policy/bank-board-decisions/",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        r.raise_for_status()
        m = re.search(r"2[-\s]week repo rate[^0-9]*(\d+[.,]\d+)\s*%", r.text, re.IGNORECASE)
        if m:
            lines.append(f"ČNB 2T repo sazba: {m.group(1).replace(',', '.')} % (ČNB)")
    except Exception as e:
        print(f"ČNB repo sazba: chyba ({e})")

    # ECB deposit facility rate z ECB API
    try:
        r = requests.get(
            "https://data-api.ecb.europa.eu/service/data/FM/B.U2.EUR.4F.KR.DFR.LEV"
            "?lastNObservations=1&format=jsondata",
            timeout=10,
        )
        r.raise_for_status()
        obs = r.json()["dataSets"][0]["series"]["0:0:0:0:0:0:0"]["observations"]
        val = list(obs.values())[-1][0]
        lines.append(f"ECB deposit facility rate: {val} % (ECB)")
    except Exception as e:
        print(f"ECB sazba: chyba ({e})")

    if not lines:
        return ""
    header = "Ověřená data přímo ze zdrojů — použij tato čísla přesně, nepřepisuj je:\n"
    return header + "\n".join(f"- {l}" for l in lines)


def generate_brief(date_str: str) -> str:
    verified = fetch_verified_data()
    if verified:
        print(f"Ověřená data:\n{verified}\n")
    prompt = BRIEF_PROMPT.format(date=date_str)
    if verified:
        prompt = verified + "\n\n" + prompt
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
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
