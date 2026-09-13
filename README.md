# Notifikace – hlídání objednávek na objednavky.cun.cz

Repozitář obsahuje dvě nezávislé automatizace běžící přes GitHub Actions:

1. **Kontrola objednávek** – každých 5 minut hlídá počet objednávek a posílá e-mail při změně.
2. **CFO Newsletter** – každé pondělí generuje týdenní finanční briefing a posílá ho e-mailem.

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

Každé pondělí v 04:30 UTC (6:30 letního / 5:30 zimního pražského času) se
vygeneruje česky psaný týdenní finanční briefing pro CFO a pošle se e-mailem
jako HTML.

### Jak to funguje

- [`cfo-brief/brief.py`](cfo-brief/brief.py) — generování přes Gemini s Google Search, sestavení HTML, odeslání přes Resend.
- [`.github/workflows/cfo-brief.yml`](.github/workflows/cfo-brief.yml) — týdenní spouštění.

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
do logu (`DRY_RUN`) a e-mail se neodešle.
