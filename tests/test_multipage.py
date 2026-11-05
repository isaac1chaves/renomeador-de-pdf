import ast, tempfile, unittest
from pathlib import Path
import fitz
SRC=Path(__file__).parents[1]/'rdf.py'; TEXT=SRC.read_text(encoding='utf-8')
TREE=ast.parse(TEXT)
class MultiPageTests(unittest.TestCase):
    def test_syntax(self):ast.parse(TEXT)
    def test_page_aware_ocr(self):
        self.assertIn('def analyze_pdf(path, page_index=0):',TEXT)
        self.assertIn('render_header_candidates(path,page_index)',TEXT)
        self.assertIn("page=doc[int(page_index)]",TEXT)
    def test_three_choices_exist(self):
        self.assertIn("choose('split')",TEXT); self.assertIn("choose('keep')",TEXT); self.assertIn("choose('ignore')",TEXT)
    def test_session_keeps_page(self):self.assertIn("'analysis_pages':self.analysis_pages",TEXT)
    def test_split_uses_insert_pdf(self):self.assertIn('part.insert_pdf(doc,from_page=index,to_page=index)',TEXT)
    def test_real_split_primitives(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/'multi.pdf'; doc=fitz.open(); doc.new_page(); doc.new_page(); doc.save(src); doc.close()
            with fitz.open(src) as original:
                self.assertEqual(len(original),2)
                out=Path(d)/'one.pdf'; part=fitz.open(); part.insert_pdf(original,from_page=1,to_page=1); part.save(out); part.close()
            with fitz.open(out) as single:self.assertEqual(len(single),1)
if __name__=='__main__':unittest.main()
