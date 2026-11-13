"""
macOS: de Soigneur-kaartlezer installeert zichzelf bij de eerste keer openen.

Dubbelklikken op het gedownloade programma:
  1. vraagt of je het wil installeren;
  2. kopieert het naar ~/Applications (geen beheerderswachtwoord nodig);
  3. zet het op automatisch starten bij het aanmelden (LaunchAgent) en start het;
  4. zegt dat het klaar is.
Dubbelklikken op het geïnstalleerde programma biedt aan het weer te verwijderen.

Voor tests: SOIGNEUR_THUIS (andere thuismap), SOIGNEUR_ZONDER_DIALOOG=1, SOIGNEUR_ZONDER_LAUNCHD=1.
"""
from __future__ import annotations

import os
import plistlib
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

LABEL = "be.mijnsoigneur.kaartlezer"
APP_NAAM = "Soigneur kaartlezer.app"


def thuis() -> Path:
    return Path(os.environ.get("SOIGNEUR_THUIS") or Path.home())


def doel_app() -> Path:
    return thuis() / "Applications" / APP_NAAM


def plist_pad() -> Path:
    return thuis() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def huidige_app(executable: str | None = None) -> Path | None:
    """De .app waarin dit programma draait, of None (bijvoorbeeld bij zelf starten met Python)."""
    pad = Path(executable or sys.executable).resolve()
    for ouder in pad.parents:
        if ouder.suffix == ".app":
            return ouder
    return None


def modus(executable: str | None = None, env: dict | None = None, argv: list[str] | None = None) -> str:
    """Wat moet er gebeuren: 'server' (de kaartlezer zelf), 'installeren', 'beheren' of 'verwijderen'."""
    env = os.environ if env is None else env
    argv = [] if argv is None else argv
    if "--verwijderen" in argv:
        return "verwijderen"
    app = huidige_app(executable)
    if app is None:
        return "server"
    # Gestart door macOS bij het aanmelden: gewoon de kaartlezer draaien.
    if env.get("XPC_SERVICE_NAME") == LABEL:
        return "server"
    if app == doel_app().resolve():
        return "beheren"
    return "installeren"


def maak_plist(exe: Path, env: dict | None = None) -> bytes:
    inhoud: dict = {
        "Label": LABEL,
        "ProgramArguments": [str(exe)],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 5,
        "StandardOutPath": "/dev/null",
        "StandardErrorPath": "/dev/null",
    }
    extra = {k: v for k, v in (env or {}).items() if k in ("SOIGNEUR_EID_PORT", "SOIGNEUR_ORIGINS") and v}
    if extra:
        inhoud["EnvironmentVariables"] = extra
    return plistlib.dumps(inhoud)


def applescript_tekst(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def dialoog(tekst: str, knoppen: tuple[str, ...] = ("OK",), standaard: str | None = None) -> str | None:
    """Toont een venster en geeft de gekozen knop terug (None bij annuleren of een fout)."""
    if os.environ.get("SOIGNEUR_ZONDER_DIALOOG") == "1":
        return standaard or knoppen[-1]
    script = (
        f"display dialog {applescript_tekst(tekst)} with title \"Soigneur kaartlezer\" "
        f"buttons {{{', '.join(applescript_tekst(k) for k in knoppen)}}} default button {applescript_tekst(standaard or knoppen[-1])}"
    )
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    m = re.search(r"button returned:(.*)", r.stdout)
    return m.group(1).strip() if m else None


def _launchctl(*args: str) -> bool:
    return subprocess.run(["launchctl", *args], capture_output=True).returncode == 0


def stop_agent() -> None:
    plist = plist_pad()
    if plist.exists():
        uid = str(os.getuid())
        if not _launchctl("bootout", f"gui/{uid}", str(plist)):
            _launchctl("unload", str(plist))


def _status_ok(poort: str) -> bool:
    origin = (os.environ.get("SOIGNEUR_ORIGINS") or "https://mijnsoigneur.be").split(",")[0].strip()
    req = urllib.request.Request(f"http://127.0.0.1:{poort}/status", headers={"Origin": origin})
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200 and b'"ok": true' in r.read()
    except Exception:
        return False


def installeer() -> int:
    bron = huidige_app()
    if bron is None:
        return 1
    if dialoog("Wil je de Soigneur-kaartlezer installeren? Hij leest de identiteitskaart voor Soigneur en start voortaan vanzelf bij het aanmelden.",
               ("Annuleren", "Installeren"), "Installeren") != "Installeren":
        return 0
    exe_naam = Path(sys.executable).name
    stop_agent()
    doel = doel_app()
    doel.parent.mkdir(parents=True, exist_ok=True)
    if doel.exists():
        shutil.rmtree(doel)
    # ditto bewaart alles van het programma, ook de ondertekening.
    subprocess.run(["ditto", str(bron), str(doel)], check=True)
    # Het gedownloade programma draagt een "gedownload van internet"-label; de kopie niet, zodat macOS bij het opstarten niets vraagt.
    subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(doel)], capture_output=True)
    exe = doel / "Contents" / "MacOS" / exe_naam

    poort = os.environ.get("SOIGNEUR_EID_PORT", "47011")
    plist = plist_pad()
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_bytes(maak_plist(exe, dict(os.environ)))
    if os.environ.get("SOIGNEUR_ZONDER_LAUNCHD") == "1":
        subprocess.Popen([str(exe)], start_new_session=True, env={**os.environ, "XPC_SERVICE_NAME": LABEL},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif not (_launchctl("bootstrap", f"gui/{os.getuid()}", str(plist)) or _launchctl("load", str(plist))):
        dialoog("Het automatisch starten kon niet ingesteld worden. Probeer het opnieuw of start je Mac opnieuw op.", ("OK",))
        return 1

    for _ in range(15):
        if _status_ok(poort):
            dialoog("Klaar. De kaartlezer draait en start voortaan vanzelf. Steek een identiteitskaart in de lezer en klik in Soigneur op \"Identiteitskaart lezen\". Je mag het gedownloade bestand nu weggooien.", ("OK",))
            return 0
        time.sleep(1)
    dialoog("De kaartlezer is geïnstalleerd maar antwoordt niet. Start je Mac opnieuw op en probeer het nog eens.", ("OK",))
    return 1


def beheren() -> int:
    if dialoog("De Soigneur-kaartlezer is geïnstalleerd en start vanzelf bij het aanmelden. Wil je hem verwijderen?", ("Verwijderen", "OK"), "OK") == "Verwijderen":
        return verwijder()
    return 0


def verwijder() -> int:
    stop_agent()
    for pad in (plist_pad(),):
        pad.unlink(missing_ok=True)
    if doel_app().exists():
        shutil.rmtree(doel_app(), ignore_errors=True)
    # Een proefdraai kan nog een los proces hebben dat niet via launchd loopt.
    subprocess.run(["pkill", "-f", str(doel_app() / "Contents" / "MacOS")], capture_output=True)
    dialoog("De Soigneur-kaartlezer is verwijderd en start niet meer.", ("OK",))
    return 0
