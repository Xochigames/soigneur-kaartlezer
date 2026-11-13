# Soigneur kaartlezer

Een klein programma dat de Belgische identiteitskaart aan de balie leest en naam, rijksregisternummer en adres doorgeeft aan [Soigneur](https://mijnsoigneur.be) in de browser. Zo zijn er geen typfouten in het rijksregisternummer.

**Installeren:** ga in Soigneur naar *Kaartlezer* (`/app/kaartlezer`). Daar staat de juiste download voor je toestel: een installatieprogramma voor Windows en een programma voor de Mac. Geen Python of commando's nodig.

## Wat het doet en niet doet

- Het draait enkel op de pc zelf en luistert enkel op `127.0.0.1:47011`. Er gaat niets naar het internet.
- Het antwoordt enkel aan de webadressen van Soigneur (`SOIGNEUR_ORIGINS`). Elke andere website krijgt een fout 403.
- Het leest de kaart pas als iemand in Soigneur op "Identiteitskaart lezen" klikt.
- Het leest enkel naam, rijksregisternummer en adres. Geen foto, geen handtekeningcertificaten, geen pincode.
- De geboortedatum haalt Soigneur zelf uit het rijksregisternummer.

Dat laatste is belangrijk: de officiële eID-software laat een website niet toe de gegevens van de kaart te lezen. Daarom is een klein programma op de pc nodig dat de chip leest, met een strenge controle op wie het mag vragen.

## Windows

`Soigneur-kaartlezer-windows.exe` is een gewoon installatieprogramma (Inno Setup). Het werkt zonder beheerdersrechten, zet het programma in de map van de gebruiker, start het automatisch bij het aanmelden en kan via *Apps* in Windows weer verwijderd worden. Windows toont bij het eerste openen "Onbekende uitgever" omdat het programma nog niet ondertekend is: kies *Meer info* en dan *Toch uitvoeren*.

## Mac

`Soigneur-kaartlezer-mac.zip` bevat het programma voor Apple-chips en Intel-Macs. Open het zip-bestand en dubbelklik op *Soigneur kaartlezer*. Het programma vraagt of je het wil installeren, kopieert zichzelf naar `~/Applications`, start automatisch bij het aanmelden en meldt wanneer het klaar is. Dubbelklikken op het geïnstalleerde programma biedt aan het te verwijderen. macOS vraagt bij de eerste keer om bevestiging omdat het programma nog niet ondertekend is: klik met de rechtermuisknop op het programma en kies *Open*, of kies *Toch openen* bij Systeeminstellingen, Privacy en beveiliging.

## Zelf bouwen en testen

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install pyscard
python -m unittest discover -s tests
python start.py          # draait de kaartlezer
```

- `soigneur_eid.py`: de kaartlezer zelf (lokale server en het lezen van de chip).
- `start.py`: ingang van de installatieprogramma's.
- `mac_install.py`: het installeren, beheren en verwijderen op de Mac.
- `windows/soigneur-kaartlezer.iss`: het Windows-installatieprogramma.
- `bouw_mac.sh`: bouwt de Mac-app.
- `scripts/`: installatie met een commando, voor wie dat liever doet.
- `.github/workflows/bouw.yml`: bouwt en test alles op een echte Windows- en Mac-machine en maakt bij een versie (`v1.0.0`) een uitgave met de downloads.

## Licentie

MIT, zie `LICENSE`.
