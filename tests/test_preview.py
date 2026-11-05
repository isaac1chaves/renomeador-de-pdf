import ast, unittest
from pathlib import Path
TEXT=(Path(__file__).parents[1]/'rdf.py').read_text(encoding='utf-8')
class PreviewTests(unittest.TestCase):
    def test_syntax(self):ast.parse(TEXT)
    def test_cover_is_minimum_zoom(self):
        self.assertIn('return max(cw/w,ch/h)*1.002',TEXT)
        self.assertIn('max(self.preview_min_zoom,min(4.0,self.zoom*factor))',TEXT)
    def test_stale_scrollbars_are_removed(self):
        self.assertIn('self.preview_xbar.grid_remove()',TEXT)
        self.assertIn('self.preview_ybar.grid_remove()',TEXT)
        self.assertIn('def clear_preview(self):',TEXT)
    def test_preview_job_is_cancelled_on_close(self):
        self.assertIn('self.after_cancel(self.preview_resize_job)',TEXT)
    def test_progress_is_in_footer(self):
        self.assertIn('self.progress=ttk.Progressbar(footer',TEXT)
        self.assertNotIn("style='Hero.TFrame',padding=(20,16)",TEXT)
    def test_header_is_removed(self):
        self.assertIn('Renomeador de Folhas (RDF)',TEXT)
        self.assertNotIn('Organize, revise e exporte folhas com seguranca.',TEXT)
if __name__=='__main__':unittest.main()
