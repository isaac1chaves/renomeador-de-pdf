import ast
import unittest
from pathlib import Path

TEXT = (Path(__file__).parents[1] / 'rdf.py').read_text(encoding='utf-8')

class OriginalFormatDisplayTests(unittest.TestCase):
    def test_syntax(self):
        ast.parse(TEXT)

    def test_original_source_mapping_is_persisted(self):
        self.assertIn('self.original_sources={}', TEXT)
        self.assertIn("'original_sources':self.original_sources", TEXT)
        self.assertIn("data.get('original_sources',{})", TEXT)

    def test_table_uses_original_filename(self):
        self.assertIn('self.original_display_name(iid)', TEXT)
        self.assertIn('self.original_display_name(p)', TEXT)

    def test_new_name_uses_selected_format(self):
        self.assertIn('def selected_output_extension(self,output_format=None):', TEXT)
        self.assertIn("self.refresh_names()", TEXT)
        self.assertIn("+'.'+self.selected_output_extension(output_format)", TEXT)

    def test_empty_name_options_fall_back_to_original_stem(self):
        self.assertIn("base=safe_filename(Path(source).stem) or 'arquivo'", TEXT)

    def test_original_file_is_opened(self):
        self.assertIn('original=self.original_sources.get(path,path)', TEXT)
        self.assertIn("label='Abrir arquivo original'", TEXT)

if __name__ == '__main__':
    unittest.main()
