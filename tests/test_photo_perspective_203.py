import ast
import unittest
from pathlib import Path
TEXT=(Path(__file__).parents[1]/'rdf.py').read_text(encoding='utf-8')
class PhotoPerspectiveTests(unittest.TestCase):
    def test_perspective_helper_is_conservative(self):
        block=TEXT.split('def rectify_document_photo(image):',1)[1].split('def _pixmap_to_rgb',1)[0]
        self.assertIn('area<page_area*.45',block)
        self.assertIn("if not .45<=ratio<=1.05:continue",block)
        self.assertIn('cv2.warpPerspective',block)
    def test_image_conversion_uses_correction(self):
        block=TEXT.split('    def image_to_pdf(self,path):',1)[1].split('    def normalize_input_file',1)[0]
        self.assertIn('corrected,changed=rectify_document_photo(rgb)',block)
    def test_original_filename_is_not_ocr_evidence(self):
        self.assertIn('def analyze_pdf(path, page_index=0):',TEXT)
        self.assertNotIn('source_path',TEXT.split('def analyze_pdf',1)[1].split('def _fold_document_text',1)[0])
    def test_version(self):
        self.assertEqual((Path(__file__).parents[1]/'app_version.py').read_text(encoding='utf-8').strip(),'APP_VERSION = "2.1.0"')
if __name__=='__main__':unittest.main()
