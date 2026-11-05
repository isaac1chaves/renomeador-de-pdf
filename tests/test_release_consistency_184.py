import unittest
from pathlib import Path
ROOT=Path(__file__).parents[1]
TEXT=(ROOT/'rdf.py').read_text(encoding='utf-8')
class ReleaseConsistencyTests(unittest.TestCase):
    def test_export_wording_is_format_neutral(self):
        self.assertIn('Selecione e analise os arquivos primeiro.',TEXT)
        self.assertNotIn('Selecione e analise os PDFs primeiro.',TEXT)
    def test_remaining_visible_accents(self):
        for value in ('análise ainda não realizada','matrícula ou nome não reconhecido','A sessão foi mantida para nova tentativa.'):
            self.assertIn(value,TEXT)
    def test_version_consistency(self):
        self.assertIn('APP_VERSION = "2.1.0"',(ROOT/'app_version.py').read_text(encoding='utf-8'))
        self.assertIn('#define MyAppVersion "2.1.0"',(ROOT/'installer.iss').read_text(encoding='utf-8'))
    def test_history_keeps_real_versions(self):
        history=(ROOT/'DOCUMENTATION'/'DELIVERY_CHANGES.md').read_text(encoding='utf-8')
        for version in ('1.7.7','1.7.8','1.7.9','1.8.0','1.8.1','1.8.2','1.8.3','2.0.4','2.1.0'):
            self.assertIn(version,history)
if __name__=='__main__':unittest.main()
