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
- JAZYK SEKCÍ: sekce „Svět", „Česko", „Na co si dát pozor příští týden"
  a „Lego v ČR" píšeš česky. Sekce „AI & Data engineering" a „SAP" píšeš celé
  anglicky — včetně nadpisu, odrážek i vysvětlení. Nadpisy ostatních sekcí
  ponech česky. Nikdy sekci nepřekládej do obou jazyků ani nepiš dvojjazyčně.
- V českých sekcích ponecháváš názvy institucí, firem a odborné termíny
  v originále (Fed, ECB, Databricks, Datasphere apod.).
- Buď konkrétní: čísla, procenta, data, jména. Vyhni se obecným frázím typu
  „trhy byly volatilní" bez vysvětlení proč.
- U každé zprávy nestačí popsat, CO se stalo — vysvětli i PROČ je to důležité
  a co z toho plyne. Čtenář buduje přehled, nepředpokládej znalost mechanismů.
- Čtenář aktivně investuje, takže u ekonomických zpráv zmiň dopad na investora
  — kam se hnuly výnosy, kurzy, konkrétní tituly. U politických a společenských
  zpráv investiční úhel nevynucuj; pokud tam žádný není, prostě ho neuváděj.
- LAŤKA VÝZNAMNOSTI: zajímají nás jen velké věci, které rezonují déle než
  pár dní — ne rutinní provoz. Ptej se u každého bodu: bude to za měsíc
  ještě někoho zajímat? Když ne, vynech ho.
  Do newsletteru tedy nepatří: běžná týdenní data bez překvapení, obvyklé
  kolísání kurzů a indexů, plánovaná zasedání, která dopadla podle očekávání,
  ani produktové drobnosti a inkrementální aktualizace.
  Patří tam: zlomy a překvapení, změny trendu, velké schodky a rozpočty,
  zásadní politická rozhodnutí, velké akvizice, nové modely a technologie,
  které mění zavedený stav.
- POČTY BODŮ JSOU STROPY, NE CÍLE. Uvedená rozmezí u sekcí jsou maxima.
  Když se za týden stalo málo, napiš klidně jen dva body — nebo u odborných
  sekcí jediný. Nikdy nedoplňuj počet vatou, převyprávěním toho, co se
  nestalo, ani rozmělněním jedné zprávy do několika bodů.
- Pokud se v některé oblasti za celý týden nestalo nic, co by laťku splnilo,
  napiš do sekce jedinou větu, že se tento týden nic zásadního neodehrálo,
  a pokračuj další sekcí. To je v pořádku a lepší než vata. (Výjimkou je
  sekce „Lego v ČR" — ta se při prázdném výsledku vynechává celá, viz zadání.)
- Nepiš o věcech, které se za sledované období nestaly.

KRITICKÉ PRAVIDLO O ČÍSLECH: Každé konkrétní číslo (sazba, kurz, index, tržba,
procento) smíš uvést pouze tehdy, pokud jsi ho přímo dohledal vyhledáváním.
Nikdy číslo neodvozuj z paměti ani neodhaduj. Pokud číslo nemáš ověřené,
napiš zprávu bez něj — to je vždy lepší než vymyšlený údaj.
"""

BRIEF_PROMPT = """\
Napiš týdenní newsletter za období {period} (dnešní datum: {date}).

Nejdřív si vyhledáváním dohledej, co se za posledních 7 dní skutečně stalo
ve všech oblastech níže. Hledej opakovaně a cíleně — nespoléhej na paměť,
tvoje tréninková data končí dřív, než toto období začalo.
U posledních dvou sekcí hledáš naopak dopředu: nadcházející události
v následujících dnech, resp. u Lega v následujících 14 dnech.

Pak napiš newsletter v této struktuře — dodrž pořadí sekcí, jejich nadpisy
a jazyk. Počty bodů uvedené u sekcí jsou ale stropy, ne kvóty k naplnění.
Jediná sekce, která se smí (a při prázdném výsledku má) vypustit celá,
je závěrečná „Lego v ČR":

## Svět
(ČESKY) Nejdůležitější dění ve světě — zkrátka to, co by čtenář neměl minout.
Vybírej podle skutečné důležitosti události, ne podle toho, do jaké škatulky
spadá: patří sem politika, geopolitika, volby, konflikty i velké společenské
události stejně jako ekonomika.
Zhruba dvě třetiny bodů ale věnuj ekonomice, trhům a investicím: centrální banky,
inflace, růst, komodity, měny, výnosy dluhopisů, výrazné pohyby akciových indexů
i jednotlivých titulů (a proč se hnuly), velké firemní události, IPO a akvizice.
(Nejvýše 6 bodů, ke každému 2–4 věty. Ve slabším týdnu výrazně méně —
raději menší rozsah než vata.)

## Česko
(ČESKY) Nejdůležitější dění v ČR — zkrátka to, co by čtenář neměl minout.
Patří sem i čistě politické zprávy (vláda, sněmovna, volby, velké kauzy
a personální změny) bez ohledu na to, jestli mají přímý dopad na trhy.
Zhruba dvě třetiny bodů ale věnuj ekonomice a investicím: ČNB a sazby, inflace,
koruna, HDP, mzdy, trh práce, energie, návrh a schvalování státního rozpočtu,
emise Dluhopisů Republiky a výnosy státních dluhopisů, dění na pražské burze
a velké tuzemské firmy (ČEZ, Komerční banka, Erste, Kofola a spol.).
(Nejvýše 5 bodů, ke každému 2–4 věty. Ve slabším týdnu výrazně méně —
raději menší rozsah než vata.)

## AI & Data engineering
(IN ENGLISH — write this entire section in English, including the heading above.)
What happened in AI and data engineering: new models and their capabilities,
major moves by the big players (Anthropic, OpenAI, Google, Meta), data platforms
and tooling (Databricks, Snowflake, dbt and friends), AI regulation, and notable
funding rounds or acquisitions. Only genuinely significant developments —
skip incremental updates and minor product tweaks.
(At most 3 bullets, 2–3 sentences each. Noticeably fewer in a quiet week —
a shorter section beats filler.)

## SAP
(IN ENGLISH — write this entire section in English, including the heading above.)
SAP news, focused mainly on the data and AI platform: Business Data Cloud,
Datasphere, SAP Analytics Cloud, Joule, BTP, and partnerships (Databricks,
Google, Microsoft, NVIDIA) — the things that touch a data engineer's work.
Briefly also cover SAP as a company from an investor's perspective: results,
guidance, share price moves, strategic decisions, and competitive pressure
(Oracle, Salesforce, Workday). Only what actually matters — skip routine
release notes and minor feature announcements.
(At most 3 bullets, 2–3 sentences each. Noticeably fewer in a quiet week —
a shorter section beats filler.)

## Na co si dát pozor příští týden
(ČESKY) Nejvýše tři konkrétní věci, které přijdou v následujících dnech —
plánovaná zasedání centrálních bank, zveřejnění dat, výsledky firem, aukce
dluhopisů, hlasování o rozpočtu — a krátce proč na nich záleží. Uveď jen ty,
kde na výsledku opravdu záleží; když je klidný týden, stačí jedna nebo dvě.

## Lego v ČR
(ČESKY) Tuto sekci piš POUZE tehdy, pokud jsi vyhledáváním skutečně našel
konkrétní akci související s Legem, která se koná v České republice
v následujících 14 dnech: výstava, srazy fanoušků a sběratelů, otevření
nové prodejny, soutěž ve stavění, speciální akce v Legolandu či muzeu,
uvedení významné novinky na trh apod.

Ke každé akci uveď název, místo, datum a jednu větu, o co jde. (Nejvýše
3 akce.)

DŮLEŽITÉ: Pokud nic takového nenajdeš — což bude nejčastější případ —
vynech celou tuto sekci včetně nadpisu. Nepiš, že se nic nekoná, nepiš
prázdnou sekci ani obecné odkazy na Lego obchody. Raději žádná sekce než
vymyšlená nebo nekonkrétní akce. Nikdy si akci nevymýšlej a neuváděj akce
ze zahraničí ani ty, které už proběhly.

---
Rozsah je nejvýše cca 1000 slov, přičemž české sekce Svět a Česko tvoří
většinu. Není to ale cíl, kterého je třeba dosáhnout — je to strop.
V týdnu, kdy se toho moc nestalo, je 500 slov naprosto v pořádku.
Kratší a hutný newsletter je vždy lepší než natažený.
Sekce „Lego v ČR" se do tohoto limitu nepočítá — je mimo, a její délka
tedy nesmí ovlivnit rozsah ostatních sekcí.

Piš rovnou newsletter, bez úvodní věty typu „zde je newsletter". Výstup
v Markdownu s nadpisy úrovně ## a odrážkami.
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
