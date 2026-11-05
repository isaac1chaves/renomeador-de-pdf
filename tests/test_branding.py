import unittest
from pathlib import Path
ROOT=Path(__file__).parents[1]
MAIN=(ROOT/'rdf.py').read_text(encoding='utf-8')
ISS=(ROOT/'installer.iss').read_text(encoding='utf-8')
class BrandingTests(unittest.TestCase):
 def test_visible_app_name(self):self.assertIn('Renomeador de Folhas (RDF) - Matrícula/Nome',MAIN)
 def test_installer_name(self):self.assertIn('#define MyAppName "Renomeador de Folhas (RDF)"',ISS)
 def test_internal_compatibility_is_preserved(self):
  self.assertIn('/ "RDF"',MAIN)
  self.assertIn('#define MyAppExeName "RDF.exe"',ISS)
if __name__=='__main__':unittest.main()
