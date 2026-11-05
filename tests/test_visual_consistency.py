import unittest
from pathlib import Path
TEXT=(Path(__file__).parents[1]/'rdf.py').read_text(encoding='utf-8')
class VisualConsistencyTests(unittest.TestCase):
    def test_duplicate_basenames_show_parent_folder(self):
        self.assertIn("return f'{source.name}  [{source.parent.name}]'",TEXT)
    def test_categories_do_not_show_fake_confidence(self):
        self.assertIn("confidence='N/A' if row.get('category')",TEXT)
        self.assertIn("values[3]='N/A' if row.get('category')",TEXT)
    def test_open_folder_uses_original_source(self):
        self.assertIn("original=Path(self.original_sources.get(path,path))",TEXT)
        self.assertIn("os.startfile(str(original.parent))",TEXT)
    def test_approval_message_is_format_neutral(self):
        self.assertIn('Selecione um ou mais arquivos para aprovar.',TEXT)
        self.assertNotIn('Selecione um ou mais PDFs para aprovar.',TEXT)
if __name__=='__main__':unittest.main()
