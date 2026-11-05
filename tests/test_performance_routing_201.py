import unittest
from pathlib import Path
TEXT=(Path(__file__).parents[1]/'rdf.py').read_text(encoding='utf-8')
class PerformanceRoutingTests(unittest.TestCase):
    def test_timesheet_analysis_precedes_expensive_fallback(self):
        block=TEXT.split('def analyze_document(path, page_index=0):',1)[1].split('class App',1)[0]
        self.assertLess(block.index('analyze_pdf(path,page_index)'),block.index('_document_search_text_exhaustive(path)'))
    def test_embedded_document_text_can_skip_ocr(self):
        self.assertIn('def _embedded_document_text(path, max_pages=3):',TEXT)
        self.assertIn('category=classify_extra_document(path,embedded)',TEXT)
    def test_fast_document_ocr_has_two_primary_orientations(self):
        block=TEXT.split('def _document_search_text(path, max_pages=2):',1)[1].split('def _document_search_text_exhaustive',1)[0]
        self.assertIn("for angle,image in ((0,binary),(180,cv2.rotate(binary,cv2.ROTATE_180))):",block)
        self.assertNotIn('for image,psm in',block)
        self.assertIn('fitz.Matrix(1.8,1.8)',block)
    def test_release_version(self):
        self.assertEqual((Path(__file__).parents[1]/'app_version.py').read_text(encoding='utf-8').strip(),'APP_VERSION = "2.1.0"')
if __name__=='__main__':unittest.main()
