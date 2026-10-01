# PC WORKBASE — závěrečný report

Předání: 25. 9. 2026. Implementace je dokončená lokálně a připravená k nasazení.
Veřejné nasazení, nový GitHub repozitář, Neon projekt ani placená služba nebyly zřízeny.
Původní Zakázkovník, jeho databáze, nasazení a portfolio nebyly změněny.

## Implementované změny

- Samostatná kopie s vlastní konfigurací, vizuální identitou PC WORKBASE a návodem k oddělenému nasazení.
- Vstupní obrazovka s ilustrační fotografií dílny a tlačítkem vstupu do dema. Bez registrace a hesla, včetně mobilu.
- Přehled, zákazníci, kontakty, zakázky, pracovníci a ukázkové faktury. Hledání, filtrování, řazení a rychlé náhledy.
- Osm smyšlených zákazníků, dvanáct navazujících zakázek, tři pracovníci a tři faktury. Hlavní ukázka vybavení kavárny.
- Odpovědný pracovník u zakázky, datum úhrady a stavy zaplaceno / čeká na úhradu / po splatnosti u faktur.
- Vysvětlení tří rolí bez přepínání a bez skutečné správy účtů.
- Vyplnitelné formuláře s validací a zachováním zadaných hodnot. Odeslání vysvětluje demo režim; nic se neukládá.
- Centrální omezení zapisujících cest, zakázané soubory a administrace, databázový režim pouze pro čtení. Veřejná aplikace nepoužívá přístup vlastníka databáze.
- Česká a anglická verze rozhraní, ukázkového obsahu, validace a exportů. Vlastní jména zůstávají stejná.
- Zachované PDF shrnutí zakázky a CSV export; ochrana CSV před vzorci vloženými do textových hodnot.
- Responzivní seznamy a formuláře s popisky, ovládání klávesnicí, viditelné zaměření a upravené mobilní rozložení.
- Poznámky vysvětlující nedostupný archiv dokumentů a vystavování faktur. Veřejné demo neobsahuje osobní kontaktní odkazy; smyšlené business kontakty zůstávají zachované.
- Příprava pro samostatný Render a Neon, kontrolní příkazy a podrobný postup nasazení.

## Výsledky ověření

| Kontrola | Výsledek |
|---|---|
| Automatické testy aplikace | 39 úspěšných, žádné selhání |
| Prohlížečové kontroly Chromium | 80 zobrazení: 10 stránek × 2 jazyky × šířky 1440, 768, 390 a 320 px |
| Vodorovné přetékání | Žádné v kontrolovaných zobrazeních |
| Interakce v prohlížeči | Vstup, formulář bez zápisu, zachování hodnot, rychlý náhled a návaznost kontaktů prošly; žádné zachycené výjimky JavaScriptu |
| Vizuální kontrola | Vybrané snímky vstupu, přehledu, detailu a formulářů na desktopu a mobilu |
| Shoda ukázkových dat po testování | Manifest souhlasí včetně uživatelů, rolí a historie |
| Odmítnutí databázového zápisu | Lokální SQLite odmítla zápis do všech 12 kontrolovaných tabulek; data nezměněna |
| Databázové migrace | Žádné chybějící změny modelů |
| Ochrany konfigurace | Chybějící produkční konfigurace, přípravný režim ve webovém procesu, přístup vlastníka ve veřejném procesu a DEBUG na Renderu odmítnuty |
| Kontrola produkčních nastavení | Pouze upozornění na nezapnuté HSTS pro všechny subdomény a preload; záměrně se nevynucuje politika pro ostatní weby domény |

Testy pokrývají mimo jiné CSRF, podvrženou vstupní cookie, zapisující HTTP metody,
API, nahrávání souborů, neplatné identifikátory, provázání kontaktů se zákazníkem,
překlady, PDF/CSV, chyby formulářů a odmítnutí opětovného naplnění neprázdné databáze.
Prohlížečový nástroj je vývojová pomůcka, nikoli závislost nasazené aplikace.

## Známá omezení

- Jde o portfolio demo. Formuláře neukládají; není implementována analytika návštěv, vlastnické přihlášení, přepínání rolí, návštěvnické účty ani reset jejich dat.
- Faktury jsou ukázkové záznamy, nikoli služba pro vystavování faktur. Chybí archiv originálních dokumentů, upload, OCR a externí dohledávání ARES.
- Termíny a platební stavy používají pevný referenční den 25. 9. 2026, aby ukázka nestárla změnou stavů.
- Produkční PostgreSQL oprávnění a spojení s konkrétním Neon projektem nebyly ověřeny na živé databázi. Před zveřejněním musí projít připravené kontroly nového reader účtu.
- Render, HTTPS a DNS nejsou dosud nasazeny ani ověřeny. Neproběhl nákup služeb.
- Mobilní kontroly proběhly v emulovaných rozměrech Chromium. Zbývá tvoje kontrola na skutečném telefonu a případně Safari.
- Převzaté zapisující funkce zůstávají ve zdrojovém kódu, ale veřejná demo politika je nespouští. Projekt není připraven jako produkční systém pro skutečné zákazníky.

## Co uděláš ty

Podrobný postup, přesné příkazy a proměnné najdeš v [DEPLOY.md](DEPLOY.md).
Dodrž toto pořadí:

1. Vytvoř nový GitHub repozitář a nahraj zdrojové soubory PC WORKBASE.
2. Vytvoř nový samostatný Neon projekt. Podle README připrav místní Python prostředí a závislosti; potom spusť `python scripts/prepare_database.py` s přístupem vlastníka nové databáze.
3. V nové databázi spusť `scripts/read_only_role.sql`, nastav soukromé heslo reader účtu a ověř ho pomocí `python scripts/check_database.py`. Při chybě nepokračuj.
4. Vytvoř novou placenou službu Render z nového repozitáře. Nastav proměnné z DEPLOY.md; veřejnému procesu dej pouze reader přístup.
5. Připoj zvolenou subdoménu podle údajů Renderu a ověř HTTPS. Návrh adresy je `workbase.petrcaha.cz`.
6. Proveď kontrolní seznam v DEPLOY.md na počítači i telefonu. Poté sám přidej odkaz na demo a kontaktní e-mail do portfolia.

Přihlašovací údaje neposílej do chatu. Pomocné skripty si databázové URL vyžádají skrytě.
Při nasazení se nepoužívá žádná původní databáze ani existující služba Zakázkovníku.
