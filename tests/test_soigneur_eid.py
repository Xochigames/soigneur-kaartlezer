import json
import os
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import soigneur_eid as eid  # noqa: E402


def tlv(tag: int, value: str) -> bytes:
    raw = value.encode("utf-8")
    length = bytearray()
    n = len(raw)
    while n >= 0xFF:
        length.append(0xFF)
        n -= 0xFF
    length.append(n)
    return bytes([tag]) + bytes(length) + raw


class ParseTest(unittest.TestCase):
    def test_identity_and_address(self):
        identity = tlv(0x01, "592123456789") + tlv(0x06, "85073003328") + tlv(0x07, "Van den Berg") + tlv(0x08, "Lotte Marie") + tlv(0x0C, "30 JUL 1985")
        address = tlv(0x01, "Kerkstraat 12") + tlv(0x02, "9000") + tlv(0x03, "Gent") + b"\x00\x00"
        self.assertEqual(eid.card_to_payload(identity, address), {
            "national_number": "85073003328", "last_name": "Van den Berg", "first_names": "Lotte Marie",
            "street": "Kerkstraat 12", "postal_code": "9000", "city": "Gent",
        })

    def test_long_length(self):
        value = "x" * 300
        self.assertEqual(eid.parse_tlv(tlv(0x07, value))[0x07], value.encode())

    def test_accents(self):
        self.assertEqual(eid.decode(eid.parse_tlv(tlv(0x07, "Dupré")), {0x07: "n"}), {"n": "Dupré"})


class FakeConn:
    """Kaart die een bestand in stukken teruggeeft, zoals een echte chip."""
    def __init__(self, files):
        self.files, self.current = files, None

    def transmit(self, apdu):
        if apdu[1] == 0xA4:
            self.current = self.files[tuple(apdu[5:])]
            return [], 0x90, 0x00
        offset, le = (apdu[2] << 8) | apdu[3], apdu[4]
        rest = self.current[offset:]
        if not rest:
            return [], 0x6B, 0x00
        return list(rest[:le]), 0x90, 0x00


class ReadFileTest(unittest.TestCase):
    def test_reads_in_chunks(self):
        content = bytes(range(256)) * 2
        conn = FakeConn({tuple(eid.IDENTITY_FILE): content})
        self.assertEqual(eid.read_file(conn, eid.IDENTITY_FILE), content)


class HttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), eid.Handler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def get(self, path, origin):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers={"Origin": origin})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, dict(r.headers), json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), json.loads(e.read())

    def test_allowed_origin(self):
        status, headers, body = self.get("/status", "http://localhost:3000")
        self.assertEqual((status, body["ok"]), (200, True))
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://localhost:3000")

    def test_other_website_refused(self):
        status, headers, _ = self.get("/kaart", "https://kwaadaardig.example")
        self.assertEqual(status, 403)
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_works_without_console(self):
        """Automatisch gestart op Windows (pythonw): geen stdout of stderr, het antwoord moet toch aankomen."""
        old_err, old_out = sys.stderr, sys.stdout
        sys.stderr = None
        sys.stdout = None
        try:
            status, _, body = self.get("/status", "http://localhost:3000")
        finally:
            sys.stderr, sys.stdout = old_err, old_out
        self.assertEqual((status, body["ok"]), (200, True))


class NoServiceTest(unittest.TestCase):
    def test_geen_lezerdienst_is_gewoon_geen_lezer(self):
        """Windows: de kaartlezerdienst draait pas als er een lezer is. Dat mag geen fout 500 geven."""
        import smartcard.System as system
        oud = system.readers

        def stuk():
            raise RuntimeError("Service not available")

        system.readers = stuk
        try:
            with self.assertRaises(eid.CardError) as cm:
                eid.read_card()
            self.assertEqual(cm.exception.code, "geen_lezer")
        finally:
            system.readers = oud


if __name__ == "__main__":
    unittest.main()
