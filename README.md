# PC WORKBASE

Samostatné veřejné portfolio demo pracovního prostoru pro malý montážní tým.
Vychází ze Zakázkovníku, ale má vlastní vzhled, konfiguraci, data a nasazení.
Původní aplikace se nemění. Nejde o hotový produkční systém pro zákazníky.

## Co ukázka obsahuje

- Vstup jedním tlačítkem, bez registrace a bez hesla.
- Osm smyšlených zákazníků, dvanáct zakázek, tři pracovníci a tři faktury.
- Odpovědná osoba, historie, kontakty a stavy plateb.
- Hledání, filtry, řazení, rychlé náhledy, PDF zakázky a CSV.
- Formuláře s běžnou validací, ale bez ukládání.
- CZ/EN a rozhraní přizpůsobené telefonu.
- CTA na https://petrcaha.cz/#contact.

Žádná analytika, vlastnické přihlášení, přepínání rolí, soubory návštěvníků,
archiv dokumentů, vytváření PDF faktur nebo dočasná návštěvnická data.
Termíny a úhrady používají pevný referenční den **25. 9. 2026**.
Vlastní jména fiktivních osob a firem se mezi jazyky nemění.

## Lokální spuštění (Python 3.12)

Příkazy spouštějte ve složce této nové kopie, nikdy v původním Zakázkovníku.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/compile_translations.py
WORKBASE_SETUP=1 DEBUG=true python manage.py migrate
WORKBASE_SETUP=1 DEBUG=true python manage.py seed_demo
DEBUG=true python manage.py collectstatic --noinput
DEBUG=true python manage.py verify_demo
DEBUG=true python manage.py verify_read_only
DEBUG=true python manage.py runserver
```

Otevřete http://127.0.0.1:8000. `seed_demo` úmyslně odmítne neprázdnou databázi.
Při běžném spuštění se místní `demo.sqlite3` otevírá v režimu pouze pro čtení.
Připravená databáze není součástí repozitáře; vytvoří se z ověřeného zdrojového scénáře.

## Testy

```sh
DEBUG=true python manage.py collectstatic --noinput
DEBUG=true python manage.py test records
DEBUG=true python manage.py verify_demo
DEBUG=true python manage.py verify_read_only
WORKBASE_SETUP=1 DEBUG=true python manage.py makemigrations --check --dry-run
```

Volitelné prohlížečové testy, pouze vývojová závislost:

```sh
python -m pip install playwright
python -m playwright install chromium
# V jiném terminálu spusťte lokální server na portu 8765.
DEBUG=true python manage.py runserver 127.0.0.1:8765
# Poté v prvním terminálu:
python scripts/browser_check.py
```

Pro macOS 13 byla při vývoji použita kompatibilní verze Playwright 1.51.0.
Na server se Playwright neinstaluje. Snímky a výsledky se ukládají do ignorované složky `artifacts/`.

## Ochrana dat

`records/demo/middleware.py` používá explicitní seznam čtecích cest.
Známé formuláře předává samostatnému validátoru, který nevolá `save()`.
Ostatní změny odmítá. Soubory odmítá před čtením formuláře i záložní upload handler.
Veřejné připojení databáze je pouze pro čtení; PostgreSQL oprávnění se navíc kontrolují
při otevření každého připojení. Aplikace nepřihlásí skutečného uživatele a nemění `last_login`.
Podepsaná funkční cookie nese pouze stav vstupu do dema; nejde o návštěvnický účet.
Dále se používají funkční cookies CSRF a vybraného jazyka. Žádné analytické cookies.

Původní zapisující funkce zůstávají v převzatém kódu pro dohledatelnost původu,
ale veřejná politika je nespouští. Nejsou zárukou produkčního použití. Nepřidávejte
novou cestu do seznamu povolených bez kontroly vedlejších účinků a testu nezměněnosti dat.

## Nasazení

Přesný postup: [DEPLOY.md](DEPLOY.md). Součástí je oddělení přípravy dat od provozu,
nová role databáze pouze pro čtení, Render a vlastní doména.
Původ a vizuální podklad: [PROVENANCE.md](PROVENANCE.md).
