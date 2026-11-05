import unittest
from pathlib import Path
TEXT=(Path(__file__).parents[1]/'rdf.py').read_text(encoding='utf-8')
class BatchLimitEdgeCaseTests(unittest.TestCase):
    def test_current_batch_is_included_in_page_limit(self):
        self.assertIn('for current in self.current_batch_source_paths():',TEXT)
        self.assertIn('total_pages+=self.input_page_count(current)',TEXT)
    def test_duplicate_sources_are_not_counted_twice(self):
        self.assertIn('if key in seen:continue',TEXT)
        self.assertIn('final_file_count=len(self.current_batch_source_paths())+len(incoming)',TEXT)
    def test_page_count_failure_is_not_silently_ignored(self):
        self.assertIn('Não foi possível verificar a quantidade de páginas',TEXT)
    def test_version_is_unchanged(self):
        self.assertIn('APP_VERSION = "2.1.0"',(Path(__file__).parents[1]/'app_version.py').read_text(encoding='utf-8'))
