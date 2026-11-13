#!/bin/bash
# Soigneur-kaartlezer voor macOS, voor wie liever een commando gebruikt dan het installatieprogramma.
# Het gewone installatieprogramma staat op https://mijnsoigneur.be/app/kaartlezer.
#
# Installeren (in Terminal):   curl -fsSL https://raw.githubusercontent.com/Xochigames/soigneur-kaartlezer/main/scripts/installeer.sh | bash
# Verwijderen:                 curl -fsSL https://raw.githubusercontent.com/Xochigames/soigneur-kaartlezer/main/scripts/installeer.sh | SOIGNEUR_ACTIE=verwijder bash
#
# Wat dit doet, in het kort:
#   1. zoekt Python 3.9 of nieuwer (staat er geen op je Mac, dan zegt het script wat je moet doen);
#   2. maakt een eigen map met een eigen Python-omgeving: ~/Library/Application Support/Soigneur/kaartlezer;
#   3. installeert daarin pyscard (het pakket dat de kaartlezer aanspreekt);
#   4. haalt het kaartlezerprogramma op van GitHub (de nieuwste versie);
#   5. laat het automatisch starten bij het aanmelden op je Mac (LaunchAgent) en start het meteen.
# Er is geen beheerderswachtwoord nodig. Alles blijft in je eigen gebruikersmap.
#
# Instellingen voor tests: SOIGNEUR_BRON, SOIGNEUR_ORIGINS, SOIGNEUR_KAARTLEZER_DIR, SOIGNEUR_ZONDER_AUTOSTART=1

set -euo pipefail

BRON="${SOIGNEUR_BRON:-https://github.com/Xochigames/soigneur-kaartlezer/releases/latest/download}"
ORIGIN="${SOIGNEUR_ORIGINS:-https://mijnsoigneur.be}"
ORIGIN="${ORIGIN%%,*}"
DIR="${SOIGNEUR_KAARTLEZER_DIR:-$HOME/Library/Application Support/Soigneur/kaartlezer}"
LABEL="be.mijnsoigneur.kaartlezer"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PORT="${SOIGNEUR_EID_PORT:-47011}"
ACTIE="${SOIGNEUR_ACTIE:-installeer}"

zeg()  { printf '%s\n' "$*"; }
fout() { printf '\nDit lukte niet: %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || fout "dit commando is voor een Mac. Op Windows gebruik je het commando voor Windows op de pagina Kaartlezer in Soigneur."

stop_service() {
  if [ -f "$PLIST" ]; then
    launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || launchctl unload "$PLIST" >/dev/null 2>&1 || true
  fi
}

if [ "$ACTIE" = "verwijder" ]; then
  zeg "Soigneur-kaartlezer verwijderen..."
  stop_service
  rm -f "$PLIST"
  rm -rf "$DIR"
  zeg "Klaar. De kaartlezer is verwijderd en start niet meer."
  exit 0
fi

# 1. Python zoeken (3.9 of nieuwer)
PYTHON=""
for kandidaat in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
  pad="$(command -v "$kandidaat" 2>/dev/null || true)"
  [ -n "$pad" ] || continue
  # Het stukje /usr/bin/python3 van macOS vraagt anders om de ontwikkeltools te installeren: eerst controleren.
  if [ "$pad" = "/usr/bin/python3" ] && ! xcode-select -p >/dev/null 2>&1; then continue; fi
  if "$pad" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then PYTHON="$pad"; break; fi
done
if [ -z "$PYTHON" ]; then
  fout "er is geen Python 3.9 of nieuwer op deze Mac.
Installeer eerst Python: ga naar https://www.python.org/downloads/macos/, download het installatiebestand en open het.
Voer daarna dit commando opnieuw uit."
fi
zeg "Python gevonden: $PYTHON"

# 2 en 3. Eigen omgeving met pyscard
mkdir -p "$DIR"
if [ ! -x "$DIR/venv/bin/python" ]; then
  zeg "Een eigen Python-omgeving maken..."
  "$PYTHON" -m venv "$DIR/venv" || fout "de Python-omgeving kon niet gemaakt worden."
fi
zeg "pyscard installeren (om de kaartlezer aan te spreken)..."
"$DIR/venv/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
"$DIR/venv/bin/python" -m pip install --quiet --upgrade pyscard || fout "pyscard kon niet geinstalleerd worden. Controleer je internetverbinding en probeer opnieuw."

# 4. Het kaartlezerprogramma ophalen
zeg "Het kaartlezerprogramma ophalen..."
curl -fsSL "$BRON/soigneur_eid.py" -o "$DIR/soigneur_eid.py.nieuw" || fout "het programma kon niet opgehaald worden van $BRON."
mv "$DIR/soigneur_eid.py.nieuw" "$DIR/soigneur_eid.py"

# 5. Automatisch starten (LaunchAgent) en nu starten
stop_service
if [ "${SOIGNEUR_ZONDER_AUTOSTART:-}" = "1" ]; then
  nohup "$DIR/venv/bin/python" "$DIR/soigneur_eid.py" >/dev/null 2>&1 &
  echo $! > "$DIR/proef.pid"
else
  mkdir -p "$HOME/Library/LaunchAgents"
  # Aangepaste poort of toegestane adressen (enkel voor tests of een eigen omgeving) gaan mee.
  ENV_XML=""
  [ -n "${SOIGNEUR_EID_PORT:-}" ] && ENV_XML="$ENV_XML<key>SOIGNEUR_EID_PORT</key><string>$SOIGNEUR_EID_PORT</string>"
  [ -n "${SOIGNEUR_ORIGINS:-}" ] && ENV_XML="$ENV_XML<key>SOIGNEUR_ORIGINS</key><string>$SOIGNEUR_ORIGINS</string>"
  [ -n "$ENV_XML" ] && ENV_XML="<key>EnvironmentVariables</key><dict>$ENV_XML</dict>"
  cat > "$PLIST" <<PLISTEND
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DIR/venv/bin/python</string>
    <string>$DIR/soigneur_eid.py</string>
  </array>
  $ENV_XML
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/dev/null</string>
  <key>StandardErrorPath</key><string>/dev/null</string>
</dict>
</plist>
PLISTEND
  launchctl bootstrap "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || launchctl load "$PLIST" >/dev/null 2>&1 || fout "het automatisch starten kon niet ingesteld worden."
fi

# Controle: antwoordt de kaartlezer?
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS -H "Origin: $ORIGIN" "http://127.0.0.1:$PORT/status" 2>/dev/null | grep -q '"ok": true'; then
    zeg ""
    zeg "Klaar. De Soigneur-kaartlezer draait en start voortaan vanzelf bij het aanmelden op deze Mac."
    zeg "Steek de identiteitskaart in de lezer en klik in Soigneur op \"Identiteitskaart lezen\"."
    zeg "De eerste keer vraagt Chrome of Soigneur apparaten op je netwerk mag gebruiken. Kies Toestaan."
    exit 0
  fi
  sleep 1
done
fout "de kaartlezer is geinstalleerd maar antwoordt niet. Start je Mac opnieuw op en probeer het nog eens."
