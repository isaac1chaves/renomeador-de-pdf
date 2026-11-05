import unittest
from pathlib import Path
ROOT=Path(__file__).parents[1]
TEXT=(ROOT/'rdf.py').read_text(encoding='utf-8')
class FinalOptimizationTests(unittest.TestCase):
    def test_preview_help_panel_removed(self):
        self.assertNotIn('CONTROLES DA PREVIA',TEXT)
        self.assertNotIn("help_box=ttk.Frame",TEXT)
    def test_log_rotation_is_bounded(self):
        self.assertIn('RotatingFileHandler',TEXT)
        self.assertIn('maxBytes=2*1024*1024',TEXT)
        self.assertIn('backupCount=3',TEXT)
    def test_opencv_does_not_oversubscribe_workers(self):
        self.assertIn('cv2.setNumThreads(1)',TEXT)
    def test_export_keeps_preview_until_close(self):
        export=TEXT.split('    def export(self):',1)[1].split("if __name__=='__main__':",1)[0]
        success=export.split("SESSION_FILE.unlink",1)[1]
        self.assertNotIn('self.cleanup_generated_files()',success)
        close=TEXT.split('    def on_close(self):',1)[1].split('    def mouse_select_start',1)[0]
        self.assertIn('if self.session_persistence_disabled:',close)
        self.assertIn('self.cleanup_generated_files()',close)
    def test_version_unchanged(self):
        self.assertEqual((ROOT/'app_version.py').read_text(encoding='utf-8').strip(),'APP_VERSION = "2.1.0"')
