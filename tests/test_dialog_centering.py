import unittest
from pathlib import Path
TEXT=(Path(__file__).parents[1]/'rdf.py').read_text(encoding='utf-8')
class DialogCenteringTests(unittest.TestCase):
    def test_center_helper_exists(self):
        self.assertIn('def center_dialog(self, dialog):',TEXT)
        self.assertIn("dialog.geometry(f'+{left}+{top}')",TEXT)
    def test_all_custom_dialogs_are_centered(self):
        self.assertEqual(TEXT.count('tk.Toplevel(self)'),5)
        self.assertEqual(TEXT.count('self.center_dialog(dialog)'),5)
    def test_centering_uses_virtual_desktop_bounds(self):
        self.assertIn('GetSystemMetrics(76)',TEXT)
        self.assertIn('GetSystemMetrics(77)',TEXT)
        self.assertIn('GetSystemMetrics(78)',TEXT)
        self.assertIn('GetSystemMetrics(79)',TEXT)
        self.assertIn('virtual_left+virtual_width-width',TEXT)
        self.assertIn('virtual_top+virtual_height-height',TEXT)
        self.assertNotIn('min(left,screen_width-width)',TEXT)
        self.assertNotIn('min(top,screen_height-height)',TEXT)
if __name__=='__main__':unittest.main()
