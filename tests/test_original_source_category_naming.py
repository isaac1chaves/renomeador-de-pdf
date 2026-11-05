import unittest
from pathlib import Path
TEXT=(Path(__file__).parents[1]/'rdf.py').read_text(encoding='utf-8')
class OriginalSourceCategoryNamingTests(unittest.TestCase):
    def test_automatic_category_name_uses_original_source(self):
        self.assertIn("compose_document_filename(self.original_sources.get(path,path),result['document_type'])",TEXT)
    def test_manual_category_name_uses_original_source(self):
        self.assertIn("compose_document_filename(self.original_sources.get(iid,iid),label)",TEXT)
    def test_workflow_headings_are_consistent(self):
        for value in (' 1. ADICIONAR ARQUIVOS ',' 2. ANALISAR E REVISAR ',' 3. APROVAR E EXPORTAR '):
            self.assertIn(value,TEXT)
    def test_initial_summary_has_all_counters(self):
        self.assertIn('0 arquivos  |  0 prontos  |  0 para revisar  |  0 bloqueados',TEXT)
if __name__=='__main__':unittest.main()
