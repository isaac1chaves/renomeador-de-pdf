import ast
import unittest
from pathlib import Path

TEXT=(Path(__file__).parents[1]/'rdf.py').read_text(encoding='utf-8')
TREE=ast.parse(TEXT)

class NamingStatusIndependenceTests(unittest.TestCase):
    def test_classified_documents_do_not_require_naming_fields(self):
        self.assertIn("if row.get('category'):",TEXT)
        self.assertIn("row['status']='OK'",TEXT)
        category_block=TEXT.split("if row.get('category'):",1)[1].split("elif not row.get('manual_name'):",1)[0]
        self.assertNotIn('fields_complete',category_block)

    def test_confidence_is_only_rendered_not_recalculated(self):
        refresh=TEXT.split('    def refresh_names(self):',1)[1].split('    def select_files(self):',1)[0]
        self.assertIn("values[3]='N/A' if row.get('category') else f\"{confidence_percent(row.get('conf',0))}%\"",refresh)
        self.assertNotIn("row['conf']=",refresh)

    def test_analysis_allows_no_naming_fields(self):
        start=TEXT.split('    def start(self,selected_only=False):',1)[1].split('    def analyze(self):',1)[0]
        self.assertNotIn('if not any(self.analysis_options)',start)

if __name__=='__main__':unittest.main()
