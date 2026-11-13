"""Ingang van de Soigneur-kaartlezer (voor het installatieprogramma en om zelf te starten)."""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--versie" in argv:
        import soigneur_eid
        print(soigneur_eid.VERSIE)
        return 0
    if sys.platform == "darwin":
        import mac_install
        wat = mac_install.modus(argv=argv)
        if wat == "installeren":
            return mac_install.installeer()
        if wat == "beheren":
            return mac_install.beheren()
        if wat == "verwijderen":
            return mac_install.verwijder()
    import soigneur_eid
    soigneur_eid.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
