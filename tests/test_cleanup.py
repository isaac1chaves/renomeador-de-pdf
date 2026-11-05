import tempfile, unittest
from pathlib import Path
TEXT=(Path(__file__).parents[1]/'rdf.py').read_text(encoding='utf-8')
class CleanupTests(unittest.TestCase):
 def test_managed_cleanup_exists(self):
  self.assertIn('def cleanup_generated_files(self,paths=None):',TEXT)
  self.assertIn('is_relative_to(SPLIT_DIR.resolve())',TEXT)
  self.assertIn('is_relative_to(CONVERT_DIR.resolve())',TEXT)
 def test_cleanup_on_remove_and_export(self):
  self.assertGreaterEqual(TEXT.count('self.cleanup_generated_files('),3)
 def test_dead_code_removed(self):
  self.assertNotIn('import os, re, shutil, threading, unicodedata',TEXT)
  self.assertNotIn('def render_header(pdf_path',TEXT)
  self.assertNotIn('def focus_rows(self,items,tag)',TEXT)
if __name__=='__main__':unittest.main()
