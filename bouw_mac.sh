#!/bin/bash
# Bouwt "Soigneur kaartlezer.app" (voor Apple-chips en Intel-Macs) en dist/Soigneur-kaartlezer-mac.zip.
# Nodig: Python van python.org (die is universal2). PYTHON=pad/naar/python3 om een andere te kiezen.
set -euo pipefail
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
APP="dist/Soigneur kaartlezer.app"

rm -rf build dist .venv-bouw
"$PYTHON" -m venv .venv-bouw
# shellcheck disable=SC1091
. .venv-bouw/bin/activate
pip install --quiet --upgrade pip pyinstaller pyscard

python -m unittest discover -s tests

pyinstaller --noconfirm --windowed --name "Soigneur kaartlezer" \
  --osx-bundle-identifier be.mijnsoigneur.kaartlezer --target-arch universal2 \
  --collect-all smartcard start.py

PLIST="$APP/Contents/Info.plist"
VERSIE="$(python start.py --versie)"
# Geen icoon in het Dock: het programma draait op de achtergrond.
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSIE" "$PLIST" 2>/dev/null || /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $VERSIE" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSIE" "$PLIST" 2>/dev/null || /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $VERSIE" "$PLIST"

# Eenvoudige (ad-hoc) handtekening: nodig om op een Mac met Apple-chip te kunnen starten. Geen uitgever, dus macOS vraagt bij de eerste keer openen om bevestiging.
codesign --force --deep -s - "$APP"
codesign --verify --deep --strict "$APP"

ditto -c -k --sequesterRsrc --keepParent "$APP" dist/Soigneur-kaartlezer-mac.zip
echo "Gebouwd: dist/Soigneur-kaartlezer-mac.zip"
lipo -archs "$APP/Contents/MacOS/Soigneur kaartlezer"
