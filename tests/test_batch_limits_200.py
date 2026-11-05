import unittest
from pathlib import Path
TEXT=(Path(__file__).parents[1]/'rdf.py').read_text(encoding='utf-8')
class BatchLimitTests(unittest.TestCase):
 def test_limits(self):
  for value in ('MAX_BATCH_FILES=300','MAX_BATCH_PAGES=1000','MAX_FILE_SIZE_MB=100','LARGE_FILE_WARNING_MB=30','PARALLEL_WORKERS=4'):self.assertIn(value,TEXT)
 def test_validation(self):self.assertIn('candidates=self.validate_batch_limits(paths)',TEXT)
 def test_workers(self):self.assertIn('workers=min(PARALLEL_WORKERS,max(1,len(files)))',TEXT)
 def test_progress(self):self.assertIn("f'{action} {value} de {total}",TEXT)
