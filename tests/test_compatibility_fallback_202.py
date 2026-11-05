import unittest
from pathlib import Path
TEXT=(Path(__file__).parents[1]/'rdf.py').read_text(encoding='utf-8')
class CompatibilityFallbackTests(unittest.TestCase):
    def test_exhaustive_fallback_restores_legacy_matrix(self):
        block=TEXT.split('def _document_search_text_exhaustive',1)[1].split('def classify_extra_document',1)[0]
        self.assertIn('fitz.Matrix(2.4,2.4)',block)
        self.assertIn("for image,psm in ((binary,6),(binary,11),(original,11)):",block)
        self.assertIn("zip((0,90,180,270)",block)
    def test_fallback_runs_only_after_fast_paths_fail(self):
        block=TEXT.split('def analyze_document(path, page_index=0):',1)[1].split('class App',1)[0]
        self.assertLess(block.index('analyze_pdf(path,page_index)'),block.index('_document_search_text_exhaustive(path)'))
        self.assertLess(block.index('_document_search_text(path)'),block.index('_document_search_text_exhaustive(path)'))
        self.assertIn('if not category:',block)
    def test_release_version(self):
        self.assertEqual((Path(__file__).parents[1]/'app_version.py').read_text(encoding='utf-8').strip(),'APP_VERSION = "2.1.0"')
if __name__=='__main__':unittest.main()
