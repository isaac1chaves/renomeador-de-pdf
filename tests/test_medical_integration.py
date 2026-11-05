import ast, unittest
from pathlib import Path
SRC=Path(__file__).parents[1]/"rdf.py"
TEXT=SRC.read_text(encoding="utf-8")
class IntegrationTests(unittest.TestCase):
 def test_analysis_uses_document_classifier_first(self):
  self.assertIn("pool.submit(analyze_document",TEXT)
  self.assertIn("if category:",TEXT)
 def test_export_reuses_saved_category(self):
  self.assertIn("category=row.get('category')",TEXT)
  self.assertNotIn("category=classify_extra_document(iid)",TEXT)
 def test_version(self):
  self.assertIn('APP_VERSION = "2.1.0"',(SRC.parent/'app_version.py').read_text())
