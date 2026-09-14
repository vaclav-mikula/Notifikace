"""Týdenní newsletter generovaný přes Gemini s Google Search, odesílaný přes Resend."""

import os
import sys
import requests
import markdown
from google import genai
from google.genai import types
from datetime import datetime, timedelta

MODEL = "gemini-3.1-pro-preview"  # stejný model jako CFO Newsletter

SYSTEM_PROMPT = """\
Jsi zkušený analytik, který každý týden píše osobní newsletter pro čtenáře
pracujícího v SAP na datech a AI, který zároveň investuje a chce mít přehled
o dění ve světě i v Česku.

Zásady:
- Píšeš česky, srozumitelně a věcně. Názvy institucí, firem a odborné termíny
  ponecháváš v originále (Fed, ECB, Databricks, Datasphere apod.).
- Buď konkrétní: čísla, procenta, data, jména. Vyhni se obecným frázím typu
  „trhy byly volatilní" bez vysvětlení proč.
- U každé zprávy nestačí popsat, CO se stalo — vysvětli i PROČ je to důležité
  a co z toho plyne. Čtenář buduje přehled, nepředpokládej znalost mechanismů.
- Nepiš o věcech, které se za sledované období nestaly. Raději méně bodů
  než vata.

KRITICKÉ PRAVIDLO O ČÍSLECH: Každé konkrétní číslo (sazba, kurz, index, tržba,
procento) smíš uvést pouze tehdy, pokud jsi ho přímo dohledal vyhledáváním.
Nikdy číslo neodvozuj z paměti ani neodhaduj. Pokud číslo nemáš ověřené,
napiš zprávu bez něj — to je vždy lepší než vymyšlený údaj.
"""

BRIEF_PROMPT = """\
Napiš týdenní newsletter za období {period} (dnešní datum: {date}).

Nejdřív si vyhledáváním dohledej, co se za posledních 7 dní skutečně stalo
ve všech čtyřech oblastech níže. Hledej opakovaně a cíleně — nespoléhej na paměť,
tvoje tréninková data končí dřív, než toto období začalo.

Pak napiš newsletter přesně v této struktuře:

## Svět
Nejdůležitější dění ve světě. Těžiště na ekonomice a trzích (centrální banky,
inflace, růst, komodity, měny, velké firemní události), ale ne výhradně —
zahrň i významnou geopolitiku, volby nebo události, které trhy či obchod
ovlivní. (4–5 bodů, ke každému 2–4 věty.)

## Česko
Nejdůležitější dění v ČR. Těžiště na ekonomice (ČNB, inflace, koruna, HDP,
mzdy, trh práce, energie, státní rozpočet, velké firmy), ale ne výhradně —
zahrň i politiku, regulaci nebo společenské události s ekonomickým dopadem.
(3–4 body, ke každému 2–4 věty.)

## AI & Data engineering
Co se stalo na poli AI a datového inženýrství: nové modely a jejich schopnosti,
zásadní vývoj u velkých hráčů (Anthropic, OpenAI, Google, Meta), datové
platformy a nástroje (Databricks, Snowflake, dbt a spol.), regulace AI,
a významné investice či akvizice v oboru. (3–4 body, ke každému 2–4 věty.)

## SAP
Dění kolem SAP. Hlavní důraz na datovou a AI platformu — Business Data Cloud,
Datasphere, SAP Analytics Cloud, Joule, BTP, partnerství (Databricks, Google,
Microsoft, NVIDIA) — tedy na to, co se dotýká práce datového inženýra.
Okrajově zmiň i SAP jako firmu z pohledu investora: výsledky, výhled, vývoj
akcie, strategické kroky, konkurenční tlak (Oracle, Salesforce, Workday).
(3–4 body, ke každému 2–4 věty.)

## Na co si dát pozor příští týden
Tři konkrétní věci, které přijdou v následujících dnech — plánovaná zasedání
centrálních bank, zveřejnění dat, výsledky firem, jednání — a krátce proč
na nich záleží.

---
Celkový rozsah cca 1000 slov. Piš rovnou newsletter, bez úvodní věty typu
„zde je newsletter". Výstup v Markdownu s nadpisy úrovně ## a odrážkami.
"""

RESEND_URL = "https://api.resend.com/emails"


def generate_brief(date_str: str, period: str) -> str:
    """Vygeneruje newsletter přes Gemini s Google Search."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=MODEL,
        contents=BRIEF_PROMPT.format(date=date_str, period=period),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )

    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Model nevrátil žádný text.")

    return text


def build_html(content_md: str, date_str: str, period: str) -> str:
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
  h1 {{ color: #2c5530; font-size: 22px; border-bottom: 2px solid #2c5530;
        padding-bottom: 8px; margin-bottom: 4px; }}
  .period {{ color: #888; font-size: 13px; margin-bottom: 8px; }}
  h2 {{ color: #2c5530; font-size: 18px; margin-top: 32px; margin-bottom: 10px; }}
  ul {{ padding-left: 22px; margin: 8px 0; }}
  li {{ margin: 6px 0; }}
  a {{ color: #2c5530; }}
  hr {{ border: none; border-top: 1px solid #ddd; margin: 28px 0; }}
  .footer {{ color: #888; font-size: 12px; margin-top: 48px;
             border-top: 1px solid #eee; padding-top: 14px; }}
</style>
</head>
<body>
<h1>Weekly Newsletter</h1>
<div class="period">{period}</div>
{body}
<div class="footer">Generováno automaticky &middot; Gemini 3.1 Pro + Google Search &middot; {date_str}</div>
</body>
</html>"""


def mask_email(addr: str) -> str:
    """Zamaskuje lokální část adresy, aby log neprozradil celý e-mail."""
    local, _, domain = addr.partition("@")
    if not domain:
        return "***"
    shown = local[:2] if len(local) > 2 else local[:1]
    return f"{shown}***@{domain}"


def send_email(html: str, date_str: str) -> None:
    from_email = os.environ["FROM_EMAIL"]
    to_email = os.environ["TO_EMAIL"]
    print(f"Odesílám z {mask_email(from_email)} na {mask_email(to_email)}...")

    resp = requests.post(
        RESEND_URL,
        headers={
            "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "from": from_email,
            "to": [to_email],
            "subject": f"Weekly Newsletter – {date_str}",
            "html": html,
        },
        timeout=30,
    )

    if not resp.ok:
        # Resend vrací důvod odmítnutí v těle odpovědi — raise_for_status() ho zahodí.
        print(f"Resend odmítl požadavek (HTTP {resp.status_code}): {resp.text}")
        resp.raise_for_status()

    print(f"Email sent: {resp.json().get('id')}")


if __name__ == "__main__":
    fmt = "%#d. %#m. %Y" if sys.platform == "win32" else "%-d. %-m. %Y"
    today = datetime.now()
    date_str = today.strftime(fmt)
    period = f"{(today - timedelta(days=7)).strftime(fmt)} – {date_str}"

    print(f"Generuji newsletter za období {period}...")
    content = generate_brief(date_str, period)

    print("\n--- NEWSLETTER ---\n")
    print(content)
    print("\n--- KONEC ---\n")

    html = build_html(content, date_str, period)
    if os.environ.get("DRY_RUN", "").lower() in ("1", "true"):
        print("DRY RUN — e-mail se neposílá.")
    else:
        send_email(html, date_str)
