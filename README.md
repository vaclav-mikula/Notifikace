# Notifikace – hlídání objednávek na objednavky.cun.cz

Repozitář obsahuje tři nezávislé automatizace běžící přes GitHub Actions:

1. **Kontrola objednávek** – každých 5 minut hlídá počet objednávek a posílá e-mail při změně.
2. **CFO Newsletter** – každé pondělí generuje týdenní finanční briefing a posílá ho e-mailem.
3. **Weekly Newsletter** – každou sobotu shrne dění ve světě, v ČR, v AI/data engineeringu a v SAP.

---

## 1. Kontrola objednávek

Každých 5 minut se skript přihlásí na `objednavky.cun.cz`, přečte ze stránky
počty objednávek a porovná je s uloženým stavem. Když některý počet vzroste,
pošle e-mail.

### Jak to funguje

- [`check_orders.py`](check_orders.py) — přihlášení, načtení počtů, porovnání, odeslání e-mailu.
- [`seen_count.json`](seen_count.json) — uložený stav: poslední známý počet **Všechny** (`total`)
  a **Potvrzené** (`confirmed`). Vytvoří se automaticky při prvním běhu a commituje se zpět do repa.
- [`.github/workflows/check-orders.yml`](.github/workflows/check-orders.yml) — spouští kontrolu každých 5 minut.

Skript nečte jednotlivé objednávky ani jejich ID — pouze dvě čísla z textu
stránky (`Všechny (N)` a `Potvrzené (N)`). Posílají se dva typy notifikací:

| Změna | E-mail |
|-------|--------|
| vzroste `Všechny` | „ČUN Nová objednávka (+N)" |
| vzroste `Potvrzené` | „ČUN Potvrzení objednávky (+N)" |

Pokud některý počet **klesne**, stav se jen tiše aktualizuje a e-mail se neposílá.

> **Poznámka k přesnosti:** protože se porovnávají počty, a ne konkrétní ID,
> nová objednávka se neohlásí v případě, že ve stejném pětiminutovém okně jiná
> objednávka ze seznamu zmizí (počet zůstane stejný).

### Nastavení (GitHub Secrets)

V repozitáři: **Settings → Secrets and variables → Actions → New repository secret**.
Přidej tyto secrets:

| Secret | Popis | Příklad |
|--------|-------|---------|
| `CUN_EMAIL` | přihlašovací e-mail na objednavky.cun.cz | `tvuj@email.cz` |
| `CUN_PASSWORD` | heslo na objednavky.cun.cz | `…` |
| `SMTP_USER` | e-mail, ze kterého se posílá notifikace | `tvuj@gmail.com` |
| `SMTP_PASS` | **heslo aplikace** (app password), NE běžné heslo | `abcd efgh ijkl mnop` |
| `MAIL_TO` | kam poslat notifikaci | `tvuj@email.cz` |

Volitelné (mají rozumné výchozí hodnoty pro Gmail):

| Secret | Výchozí | Popis |
|--------|---------|-------|
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | port (STARTTLS) |
| `MAIL_FROM` | = `SMTP_USER` | odesílatel |

#### Gmail app password

1. Zapni si dvoufázové ověření na Google účtu.
2. Jdi na <https://myaccount.google.com/apppasswords>, vytvoř heslo aplikace.
3. Vygenerovaných 16 znaků vlož do `SMTP_PASS`.

(Můžeš použít i jiného poskytovatele — pak nastav `SMTP_HOST`/`SMTP_PORT`.)

### Rozvrh spouštění

Po–Pá každých 5 minut v okně **7:30–18:45** pražského letního času.
GitHub cron běží v UTC a neřeší přechod na zimní čas, takže v zimě se okno
přirozeně posune na 6:30–17:45.

### Ruční spuštění / test

V záložce **Actions** → *Kontrola objednávek* → **Run workflow**.

- **První běh** jen uloží aktuální stav a **nepošle** e-mail (aby tě nezahltil starými objednávkami).
- Od druhého běhu posílá e-mail jen při nárůstu počtů.

---

## 2. CFO Newsletter

Každé pondělí ráno se vygeneruje česky psaný týdenní finanční briefing pro CFO
a pošle se e-mailem jako HTML.

### Jak to funguje

- [`cfo-brief/brief.py`](cfo-brief/brief.py) — generování přes Gemini s Google Search, sestavení HTML, odeslání přes Resend.
- [`.github/workflows/cfo-brief.yml`](.github/workflows/cfo-brief.yml) — týdenní spouštění.

### Spouštění

GitHub plánovač (`schedule`) v pondělí ráno běhy zpožďuje i o 5+ hodin, proto
workflow spouští externě [cron-job.org](https://cron-job.org) přes
`workflow_dispatch` v pondělí v 5:59 pražského času. Záloha na GitHubu cílí na
6:10 Praha — GitHub cron je v UTC a letní čas neřeší, proto jsou ve workflow dva
(`10 4 * * 1` a `10 5 * * 1`) a projde jen ten, který právě odpovídá 6:10 v Praze.
Protože cron-job.org odešle dřív, záloha typicky nic neposílá.

Pojistka: před generováním se workflow přes GitHub API podívá, jestli už od
pondělí 00:00 UTC newsletter skutečně odešel (dry-run ani přeskočené běhy se nepočítají). Pokud ano, skončí bez
odeslání — e-mail tak přijde jen jednou, ať doběhne cokoli dřív.
Ruční běh se zaškrtnutým **„Poslat i když už tento týden odešel"** pojistku obejde.

Nastavení cron-job.org (zdarma):

1. GitHub → Settings → Developer settings → *Fine-grained tokens* → nový token,
   *Repository access*: jen `Notifikace`, *Permissions*: **Actions: Read and write**.
   Expirace max. 1 rok — do kalendáře si dej připomínku na obnovu.
2. cron-job.org → *Create cronjob*:
   - URL: `https://api.github.com/repos/vaclav-mikula/Notifikace/actions/workflows/cfo-brief.yml/dispatches`
   - Schedule: pondělí 05:59, časové pásmo **Europe/Prague** (letní čas řeší samo)
   - *Advanced* → Request method **POST**, hlavičky:
     `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`,
     `X-GitHub-Api-Version: 2022-11-28`
   - Request body: `{"ref":"main"}`
3. Tlačítkem *Test run* ověř odpověď **204**. Pokud už tento týden newsletter odešel,
   pojistka běh přeskočí, takže test druhý e-mail nepošle.

Aby se v briefingu neobjevovala vymyšlená čísla, skript si před generováním sám
stáhne klíčové sazby a kurzy z autoritativních zdrojů (kurzy EUR/CZK a USD/CZK
z API ČNB, 2T repo sazba z webu ČNB, deposit facility rate z API ECB) a vloží
je do promptu s instrukcí, aby je model použil přesně.

### Nastavení (GitHub Secrets)

| Secret | Popis |
|--------|-------|
| `GEMINI_API_KEY` | API klíč pro Google Gemini |
| `RESEND_API_KEY` | API klíč pro [Resend](https://resend.com) |
| `FROM_EMAIL` | odesílatel (ověřená doména v Resend) |
| `TO_EMAIL` | příjemce newsletteru |

### Ruční spuštění / test

V záložce **Actions** → *CFO Newsletter* → **Run workflow**.
Zaškrtnutím **„Jen tisk do logu, e-mail neposílat"** se briefing pouze vypíše
do logu (`DRY_RUN`) a e-mail se neodešle. **„Poslat i když už tento týden odešel"**
obejde pojistku.

---

## 3. Weekly Newsletter

Každý pátek odpoledne se vygeneruje týdenní newsletter a pošle se e-mailem jako HTML.

Používá stejné technické řešení jako CFO Newsletter (Gemini + Google Search,
odeslání přes Resend), liší se obsahem — pokrývá pět stálých sekcí, z toho dvě
odborné jsou **psané anglicky**, plus jednu nepravidelnou:

| Sekce | Jazyk | Obsah |
|-------|-------|-------|
| **Svět** | 🇨🇿 | Všechno důležité včetně politiky a geopolitiky; zhruba dvě třetiny na ekonomiku, trhy a investice (sazby, komodity, výnosy, pohyby indexů a titulů). |
| **Česko** | 🇨🇿 | Všechno důležité včetně čistě politických zpráv; zhruba dvě třetiny na ekonomiku (ČNB, inflace, rozpočet, Dluhopisy Republiky, pražská burza, velké firmy). |
| **AI & Data engineering** | 🇬🇧 | Modely, datové platformy, regulace AI, investice a akvizice. |
| **SAP** | 🇬🇧 | Hlavně datová a AI platforma (BDC, Datasphere, Joule, BTP), okrajově SAP z pohledu investora. |
| **Na co si dát pozor příští týden** | 🇨🇿 | Až tři nadcházející události — zasedání, data, výsledky, aukce. |
| **Lego v ČR** | 🇨🇿 | Akce související s Legem v ČR v následujících 14 dnech. Objeví se jen když se něco najde — jinak se sekce vynechá celá. Nepočítá se do limitu slov. |

Rozsah je **nejvýše** zhruba 1000 slov, těžiště na českých sekcích Svět a Česko.

Tisíc slov je strop, ne cíl. Prompt drží laťku významnosti — do newsletteru
patří jen velké věci, které rezonují déle než pár dní, ne rutinní provoz.
Počty bodů u sekcí jsou maxima, takže ve slabém týdnu přijde kratší newsletter
(klidně 500 slov) a sekce, kde se nic zásadního nestalo, se odbude jednou větou.
Raději menší rozsah než vata.

### Jak to funguje

- [`weekly-brief/brief.py`](weekly-brief/brief.py) — generování přes Gemini s Google Search,
  sestavení HTML, odeslání přes Resend.
- [`.github/workflows/weekly-newsletter.yml`](.github/workflows/weekly-newsletter.yml) — týdenní spouštění.

### Spouštění

Stejně jako u CFO Newsletteru: hlavní spouštěč je cron-job.org přes
`workflow_dispatch`, cron `17 15 * * 5` ve workflow je záloha a pojistka hlídá,
aby e-mail odešel jen jednou. Týden se tu počítá **od pátku 00:00 UTC**, takže
ruční běh v pondělí–čtvrtek páteční newsletter nezablokuje.

Na cron-job.org stačí druhá úloha se stejným tokenem a hlavičkami jako u CFO
Newsletteru, jen:
- URL: `https://api.github.com/repos/vaclav-mikula/Notifikace/actions/workflows/weekly-newsletter.yml/dispatches`
- Schedule: pátek 17:15, časové pásmo **Europe/Prague**

Model si aktuální dění dohledává sám přes **Google Search**. Systémový prompt mu
zakazuje uvádět jakékoli číslo, které si přímo nedohledal — raději zprávu bez
čísla než vymyšlený údaj.

### Nastavení (GitHub Secrets)

Všechny čtyři secrets jsou **sdílené s CFO Newsletterem** — pokud ten už běží,
není potřeba nastavovat nic nového.

| Secret | Popis |
|--------|-------|
| `GEMINI_API_KEY` | API klíč pro Google Gemini |
| `RESEND_API_KEY` | API klíč pro [Resend](https://resend.com) |
| `FROM_EMAIL` | odesílatel (ověřená doména v Resend) |
| `TO_EMAIL` | příjemce newsletteru |

### Ruční spuštění / test

V záložce **Actions** → *Weekly Newsletter* → **Run workflow**.
Zaškrtnutím **„Jen tisk do logu, e-mail neposílat"** se newsletter pouze vypíše
do logu (`DRY_RUN`) a e-mail se neodešle. **„Poslat i když už tento týden odešel"**
obejde pojistku.
