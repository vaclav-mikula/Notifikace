# Notifikace — hlídání nových objednávek na objednavky.cun.cz

Každých 5 minut (přes GitHub Actions) se skript přihlásí na
`objednavky.cun.cz`, načte seznam objednávek a porovná ho s uloženým
stavem. Když se objeví nová objednávka, pošle e-mail.

## Jak to funguje

- [`check_orders.py`](check_orders.py) — přihlášení, načtení seznamu, porovnání, odeslání e-mailu.
- [`seen_ids.json`](seen_ids.json) — uložený stav (ID už viděných objednávek). Vytvoří se automaticky při prvním běhu a commituje se zpět do repa.
- [`.github/workflows/check-orders.yml`](.github/workflows/check-orders.yml) — spouští kontrolu každých 5 minut.

## Nastavení (GitHub Secrets)

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

### Gmail app password

1. Zapni si dvoufázové ověření na Google účtu.
2. Jdi na <https://myaccount.google.com/apppasswords>, vytvoř heslo aplikace.
3. Vygenerovaných 16 znaků vlož do `SMTP_PASS`.

(Můžeš použít i jiného poskytovatele — pak nastav `SMTP_HOST`/`SMTP_PORT`.)

## Ruční spuštění / test

V záložce **Actions** → *Kontrola objednávek* → **Run workflow**.

- **První běh** jen uloží aktuální stav a **nepošle** e-mail (aby tě nezahltil starými objednávkami).
- Od druhého běhu posílá e-mail jen na **nové** objednávky.
