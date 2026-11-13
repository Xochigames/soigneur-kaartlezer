#!/usr/bin/env python3
"""
Soigneur-kaartlezer: leest de Belgische identiteitskaart en geeft naam, rijksregisternummer
en adres door aan Soigneur in de browser.

- Draait enkel op 127.0.0.1 (deze pc), poort 47011. Niets gaat naar het internet.
- Antwoordt enkel aan de webadressen van Soigneur (SOIGNEUR_ORIGINS).
- Leest de kaart pas als iemand in Soigneur op "Identiteitskaart lezen" klikt.
- Leest geen foto en geen handtekeningcertificaten; enkel identiteit en adres.

Installeren (Mac en Windows): download het installatieprogramma via https://mijnsoigneur.be/app/kaartlezer.
Zelf starten: python start.py (nodig: Python 3.9 of nieuwer, een kaartlezer en pyscard).
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSIE = "1.0.0"
PORT = int(os.environ.get("SOIGNEUR_EID_PORT", "47011"))
ORIGINS = {o.strip() for o in os.environ.get(
    "SOIGNEUR_ORIGINS", "https://mijnsoigneur.be,https://www.mijnsoigneur.be,http://localhost:3000"
).split(",") if o.strip()}

# Bestanden op de chip (applet BELPIC)
IDENTITY_FILE = [0x3F, 0x00, 0xDF, 0x01, 0x40, 0x31]
ADDRESS_FILE = [0x3F, 0x00, 0xDF, 0x01, 0x40, 0x33]

# Tags in het identiteitsbestand en het adresbestand
ID_TAGS = {0x06: "national_number", 0x07: "last_name", 0x08: "first_names", 0x0C: "birth_date_text"}
ADDRESS_TAGS = {0x01: "street", 0x02: "postal_code", 0x03: "city"}


def parse_tlv(data: bytes) -> dict[int, bytes]:
    """Tag-lengte-waarde zoals op de eID: een lengte van 0xFF betekent 'er volgt nog een lengtebyte'."""
    out: dict[int, bytes] = {}
    i = 0
    while i < len(data):
        tag = data[i]
        i += 1
        if tag == 0x00 and i >= len(data):
            break
        length = 0
        while i < len(data):
            b = data[i]
            i += 1
            length += b
            if b != 0xFF:
                break
        out[tag] = data[i:i + length]
        i += length
    return out


def decode(fields: dict[int, bytes], names: dict[int, str]) -> dict[str, str]:
    return {name: fields[tag].decode("utf-8", errors="replace").strip() for tag, name in names.items() if tag in fields}


def card_to_payload(identity: bytes, address: bytes) -> dict[str, str]:
    data = decode(parse_tlv(identity), ID_TAGS)
    data.update(decode(parse_tlv(address), ADDRESS_TAGS))
    # De geboortedatum staat als tekst in de taal van de kaart; Soigneur haalt ze uit het rijksregisternummer.
    data.pop("birth_date_text", None)
    return data


# ---------------------------------------------------------------------------
# Kaart lezen (pyscard)
# ---------------------------------------------------------------------------
class CardError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def read_file(conn, path: list[int]) -> bytes:
    _, sw1, sw2 = conn.transmit([0x00, 0xA4, 0x08, 0x0C, len(path)] + path)
    if (sw1, sw2) != (0x90, 0x00):
        raise CardError("onleesbaar")
    out = bytearray()
    offset = 0
    le = 0xF8
    while True:
        data, sw1, sw2 = conn.transmit([0x00, 0xB0, offset >> 8, offset & 0xFF, le])
        if sw1 == 0x6C:  # verkeerde lengte: kaart zegt hoeveel er nog is
            le = sw2
            continue
        if (sw1, sw2) == (0x6B, 0x00) or not data:
            break
        if (sw1, sw2) != (0x90, 0x00):
            raise CardError("onleesbaar")
        out.extend(data)
        offset += len(data)
        if len(data) < le:
            break
    return bytes(out)


def read_card() -> dict[str, str]:
    try:
        from smartcard.System import readers
        from smartcard.Exceptions import NoCardException, CardConnectionException
    except ImportError:
        raise CardError("geen_pyscard")
    try:
        found = readers()
    except Exception:
        # Op Windows draait de kaartlezerdienst pas als er een lezer aangesloten is: dan is er gewoon geen lezer.
        raise CardError("geen_lezer")
    if not found:
        raise CardError("geen_lezer")
    for reader in found:
        conn = reader.createConnection()
        try:
            conn.connect()
        except (NoCardException, CardConnectionException):
            continue
        try:
            return card_to_payload(read_file(conn, IDENTITY_FILE), read_file(conn, ADDRESS_FILE))
        finally:
            try:
                conn.disconnect()
            except Exception:
                pass
    raise CardError("geen_kaart")


# ---------------------------------------------------------------------------
# HTTP op 127.0.0.1
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "SoigneurKaartlezer/1.0"

    def _cors(self) -> bool:
        origin = self.headers.get("Origin", "")
        if origin in ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            # Chrome: een website mag enkel een lokaal adres aanspreken als dat dit toestaat.
            self.send_header("Access-Control-Allow-Private-Network", "true")
            return True
        return False

    def _json(self, status: int, body: dict) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.headers.get("Origin", "") not in ORIGINS:
            self._json(403, {"fout": "niet_toegestaan"})
            return
        if self.path == "/status":
            self._json(200, {"ok": True, "versie": 1, "programma": VERSIE})
        elif self.path == "/kaart":
            try:
                self._json(200, read_card())
            except CardError as e:
                self._json(409 if e.code in ("geen_kaart", "geen_lezer") else 500, {"fout": e.code})
        else:
            self._json(404, {"fout": "onbekend"})

    def log_message(self, fmt: str, *args) -> None:
        # Geen persoonsgegevens in een logbestand; enkel het pad.
        # Zonder consolevenster (automatisch gestart op Windows) bestaat stderr niet: dan niets loggen.
        if sys.stderr is not None:
            sys.stderr.write(f"{self.address_string()} {self.command} {self.path}\n")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    if sys.stdout is not None:
        print(f"Soigneur-kaartlezer draait op http://127.0.0.1:{PORT}. Laat dit venster open.")
        print("Toegestaan voor: " + ", ".join(sorted(ORIGINS)))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
