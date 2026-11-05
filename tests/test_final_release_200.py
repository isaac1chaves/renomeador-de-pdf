import unittest
from pathlib import Path
ROOT=Path(__file__).parents[1]
TEXT=(ROOT/'rdf.py').read_text(encoding='utf-8')
class FinalReleaseTests(unittest.TestCase):
    def test_final_version_is_consistent(self):
        self.assertEqual((ROOT/'app_version.py').read_text(encoding='utf-8').strip(),'APP_VERSION = "2.1.0"')
        self.assertIn('#define MyAppVersion "2.1.0"',(ROOT/'installer.iss').read_text(encoding='utf-8'))
        self.assertNotIn('prototype.1',(ROOT/'LEIA-ME.txt').read_text(encoding='utf-8'))
    def test_add_buttons_preserve_current_batch(self):
        select=TEXT.split('    def select_files(self):',1)[1].split('    def select_folder(self):',1)[0]
        folder=TEXT.split('    def select_folder(self):',1)[1].split('    def request_cancel_analysis',1)[0]
        self.assertIn('self.add_files(self.prepare_input_paths(paths))',select)
        self.assertIn('self.add_files(self.prepare_input_paths',folder)
        self.assertNotIn('self.load(self.prepare_input_paths',select+folder)
    def test_clear_session_clears_visible_lot(self):
        block=TEXT.split('    def clear_session_data(self):',1)[1].split('    def clear_preview(self):',1)[0]
        self.assertIn('self.files=[]; self.rows=[]; self.row_by_path={}',block)
        self.assertIn('for item in self.tree.get_children():self.tree.delete(item)',block)
        self.assertIn('self.clear_preview()',block)
    def test_removed_help_styles_do_not_remain(self):
        self.assertNotIn("style.configure('Help.TFrame'",TEXT)
        self.assertNotIn("style.configure('HelpTitle.TLabel'",TEXT)
        self.assertNotIn("style.configure('HelpText.TLabel'",TEXT)
if __name__=='__main__':unittest.main()
