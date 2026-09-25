# Nasazení PC WORKBASE — postup pro Petra

## Co už je připravené

Samostatná aplikace, smyšlená data, překlady, lokální ochrana proti zápisu,
kontrolní příkazy a `render.yaml` pro nový web na Renderu.
Nic nebylo nahráno do původního repozitáře, Renderu, Neonu ani portfolia.

## 1. Vlastní repozitář

Vytvoř nový prázdný repozitář, například `pc-workbase`, ve svém GitHub účtu.
Nahraj obsah této složky jako kořen repozitáře. Lze použít GitHub Desktop.
Nenahrávej `.env`, `.venv`, `demo.sqlite3`, `staticfiles`, `artifacts` ani přístupové údaje.
Soubor `demo-manifest.sha256` do repozitáře patří: umožňuje ověřit čistotu ukázkových dat.
Nepřipojuj tuto kopii k původnímu repozitáři Zakázkovník.

## 2. Nová databáze v Neonu

Vytvoř **nový samostatný projekt** pro WORKBASE, ideálně ve stejném regionu jako Render.
Nepoužívej databázi, větev ani přístupové údaje původního Zakázkovníku.
Pro nový projekt použij databázi pojmenovanou například `pc_workbase`.

Budou dva typy přístupu:

1. Vlastník nové databáze: pouze jednorázové vytvoření tabulek a vložení dat z tvého počítače.
2. `pc_workbase_reader`: pouze čtení, jediný přístup dostupný veřejné aplikaci na Renderu.

Pro první přípravu zkopíruj připojovací řetězec vlastníka **nové** databáze
(nepoolovaný/direct, se zabezpečeným připojením). Nevkládej ho do chatu ani souborů projektu.

Na svém počítači otevři terminál ve složce nové aplikace a aktivuj její virtuální prostředí.
Proměnnou lze načíst skrytě takto (Python spustí přípravu jako podproces):

```sh
python scripts/prepare_database.py
```

Skript si skrytě vyžádá adresu nové databáze a výslovné potvrzení názvu hostitele.
Provede migrace a naplnění dat. Při neprázdné databázi skončí bez nahrazování záznamů.
Nepouštěj ho proti původní databázi. Owner URL nebude zapsáno do souboru ani do logu.

## 3. Přístup pouze pro čtení

V SQL konzoli **nového** projektu spusť obsah `scripts/read_only_role.sql`.
Tento skript je určen pro samostatnou demo databázi a upravuje její oprávnění.
Nespouštěj jej v databázi sdílené s jinou aplikací.

V soukromé konzoli nastav novému účtu vlastní náhodné heslo:

```sql
ALTER ROLE pc_workbase_reader PASSWORD 'SEM_VLOZ_SVE_NOVE_NAHODNE_HESLO';
```

Ukázkový text hesla nepoužívej. Heslo ani celý příkaz s opravdovým heslem neukládej do repozitáře.
Získej connection string této nové role pro stejnou databázi. Použij direct connection,
protože aplikace spoléhá také na vlastnosti databázového spojení. Běžící web má malé množství spojení.

Ověř připojení z počítače:

```sh
python scripts/check_database.py
```

Skript si adresu reader účtu vyžádá skrytě a provede kontrolu shody dat i odmítnutí zápisu.
**Pokud některá kontrola selže, nepokračuj ve zveřejnění.**

Databázový účet vytvořený přes výchozí správní rozhraní může mít silnější oprávnění,
než demo potřebuje. Proto je důležité použít uvedenou SQL roli a ne vlastníka databáze.

## 4. Nová placená služba na Renderu

Připoj nový repozitář jako **novou** službu. Neupravuj stávající Zakázkovník.
Lze použít Blueprint z `render.yaml`. Je v něm uveden placený tarif `starter`;
aktuální cenu si před potvrzením zkontroluj v Renderu. Žádný tarif zatím nebyl objednán.

Při ručním nastavení:

| Položka | Hodnota |
|---|---|
| Runtime | Python |
| Python | 3.12.13 |
| Build command | `bash build.sh` |
| Start command | `python manage.py verify_demo && gunicorn config.wsgi:application --timeout 30 --workers 1 --threads 2 --bind 0.0.0.0:$PORT` |
| Health check | `/health/` |

Proměnné prostředí:

| Název | Hodnota |
|---|---|
| `DEBUG` | `false` |
| `SECRET_KEY` | Vygenerovaná soukromá náhodná hodnota alespoň 50 znaků. |
| `DATABASE_URL` | URL účtu **pc_workbase_reader**, nikdy vlastníka databáze. |
| `ALLOWED_HOSTS` | Finální doména bez protokolu, např. `workbase.petrcaha.cz`. |
| `CSRF_TRUSTED_ORIGINS` | Doména s protokolem, např. `https://workbase.petrcaha.cz`. |

Pokud chceš používat i adresu Renderu, přidej její HTTPS adresu do
`CSRF_TRUSTED_ORIGINS` oddělenou čárkou. `RENDER_EXTERNAL_HOSTNAME` se do povolených hostitelů přidává automaticky.

**Na Render nenastavuj `WORKBASE_SETUP`, `WORKBASE_SETUP_DATABASE_URL` ani `WORKBASE_TESTING`.**
Build nevytváří tabulky ani nenaplňuje data. Veřejný proces nemá owner přístup.

Po prvním nasazení spusť v Render Shell:

```sh
python manage.py verify_demo
python manage.py verify_read_only
```

Pokud Render Shell není k dispozici, použij stejný reader účet v místním
`python scripts/check_database.py`. Start aplikace kontroluje manifest a oprávnění automaticky.

## 5. Vlastní adresa

Doporučená, dosud nerezervovaná adresa je `workbase.petrcaha.cz`.
Přidej ji k nové službě v části Custom Domains. V DNS nastav přesně záznam,
který Render zobrazí. Hodnotu neodhaduj a neměň záznamy hlavní domény portfolia.
Počkej na ověření domény a HTTPS certifikátu.

Pokud DNS spravuje Cloudflare, při prvním ověřování použij DNS-only režim,
pokud to instrukce Renderu vyžadují. Nezapínej cache HTML stránek aplikace.

## 6. Kontrola před odkazem z portfolia

- HTTPS funguje, vstup do dema i opuštění ukázky fungují.
- Přepnutí CZ/EN zůstává na stejné stránce.
- Zákazníci, zakázky, kontakty, pracovníci a tři faktury jsou dostupní.
- Vyplnění a odeslání formuláře vrátí vysvětlení a nic nezmění.
- PDF a CSV lze stáhnout.
- Kontrola `verify_demo` stále projde i po uživatelském zkoušení.
- Administrace a nahrávání souborů nejsou dostupné.
- Na telefonu jsou čitelné detaily, seznamy i formuláře.
- CTA vede na `https://petrcaha.cz/#contact`.

Teprve potom sám aktualizuj odkaz na demo na portfoliu.

## Aktualizace a provoz

Běžná aktualizace kódu nemění data. Pokud se mění databázová struktura nebo schválená
sada ukázkových dat, připravuje se offline nová čistá demo databáze a její reader účet.
Nejde o automatický reset návštěvnických zápisů; návštěvníci nic neukládají.

Žádná vlastní analytika není implementovaná. Aplikace používá jen funkční cookies
vstupu, ochrany formulářů a jazyka. Render/Neon mohou mít vlastní provozní logy;
zkontroluj v jejich účtech přístup a dobu uchovávání. Nezapínej logování obsahu formulářů.

## Ověření při předání

Lokální testy jsou popsány v `REPORT.md`. Připojení ke konkrétnímu Neon projektu,
placená služba a DNS nebyly při lokální implementaci zřízeny ani ověřeny.
Tyto kontroly jsou nutným krokem tohoto postupu, nikoli hotovým nasazením.

Oficiální doplňující dokumentace:
- https://render.com/docs/deploy-django
- https://render.com/docs/custom-domains
- https://neon.com/docs/manage/roles
