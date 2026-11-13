import os
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import mac_install as mi  # noqa: E402


class ModusTest(unittest.TestCase):
    def setUp(self):
        self.thuis = tempfile.mkdtemp()
        self._oud = os.environ.get("SOIGNEUR_THUIS")
        os.environ["SOIGNEUR_THUIS"] = self.thuis
        self.gedownload = "/Users/lotte/Downloads/Soigneur kaartlezer.app/Contents/MacOS/Soigneur kaartlezer"
        self.geinstalleerd = str(Path(self.thuis) / "Applications" / "Soigneur kaartlezer.app" / "Contents" / "MacOS" / "Soigneur kaartlezer")

    def tearDown(self):
        if self._oud is None:
            os.environ.pop("SOIGNEUR_THUIS", None)
        else:
            os.environ["SOIGNEUR_THUIS"] = self._oud

    def test_zelf_starten_met_python_is_server(self):
        self.assertEqual(mi.modus("/usr/bin/python3", {}, []), "server")

    def test_eerste_keer_openen_installeert(self):
        self.assertEqual(mi.modus(self.gedownload, {}, []), "installeren")

    def test_gestart_door_macos_is_server(self):
        self.assertEqual(mi.modus(self.geinstalleerd, {"XPC_SERVICE_NAME": mi.LABEL}, []), "server")

    def test_geinstalleerd_zelf_openen_biedt_beheren_aan(self):
        self.assertEqual(mi.modus(self.geinstalleerd, {}, []), "beheren")

    def test_verwijderen_via_argument(self):
        self.assertEqual(mi.modus(self.geinstalleerd, {}, ["--verwijderen"]), "verwijderen")

    def test_huidige_app_vindt_de_bundel(self):
        self.assertEqual(mi.huidige_app(self.gedownload), Path("/Users/lotte/Downloads/Soigneur kaartlezer.app"))
        self.assertIsNone(mi.huidige_app("/usr/bin/python3"))


class PlistTest(unittest.TestCase):
    def test_plist_start_het_programma_bij_aanmelden(self):
        data = plistlib.loads(mi.maak_plist(Path("/x/y/Soigneur kaartlezer"), {}))
        self.assertEqual(data["Label"], "be.mijnsoigneur.kaartlezer")
        self.assertEqual(data["ProgramArguments"], ["/x/y/Soigneur kaartlezer"])
        self.assertTrue(data["RunAtLoad"] and data["KeepAlive"])
        self.assertNotIn("EnvironmentVariables", data)

    def test_aangepaste_poort_en_adressen_gaan_mee(self):
        data = plistlib.loads(mi.maak_plist(Path("/x"), {"SOIGNEUR_EID_PORT": "47030", "SOIGNEUR_ORIGINS": "http://localhost:3000", "ANDERS": "nee"}))
        self.assertEqual(data["EnvironmentVariables"], {"SOIGNEUR_EID_PORT": "47030", "SOIGNEUR_ORIGINS": "http://localhost:3000"})

    def test_tekst_in_applescript_is_veilig(self):
        self.assertEqual(mi.applescript_tekst('Zeg "hoi" \\ nu'), '"Zeg \\"hoi\\" \\\\ nu"')


if __name__ == "__main__":
    unittest.main()
