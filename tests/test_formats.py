import unittest, tempfile
from pathlib import Path
from PIL import Image
import fitz
TEXT=(Path(__file__).parents[1]/'rdf.py').read_text(encoding='utf-8')
class FormatTests(unittest.TestCase):
 def test_supported_inputs(self):
  for ext in ['.pdf','.png','.jpg','.jpeg','.bmp','.tif','.tiff','.webp']:self.assertIn(repr(ext),TEXT)
 def test_outputs(self):
  for fmt in ['PDF','PNG','JPEG','JPG','WEBP','BMP','TIFF']:self.assertIn(repr(fmt),TEXT)
 def test_image_pdf_roundtrip_primitives(self):
  with tempfile.TemporaryDirectory() as d:
   im=Image.new('RGB',(40,30),'white'); p=Path(d)/'a.pdf'; im.save(p,'PDF')
   with fitz.open(p) as doc:self.assertEqual(len(doc),1)
if __name__=='__main__':unittest.main()

class ExportSafetyTests(unittest.TestCase):
 def test_multipage_collision_planning(self):
  self.assertIn('def planned_export_paths(self,source,target,output_format):',TEXT)
  self.assertIn('if all(key not in used and not p.exists() for key,p in zip(keys,planned)):break',TEXT)
 def test_partial_outputs_are_cleaned(self):
  self.assertIn('for destination in created:destination.unlink(missing_ok=True)',TEXT)

class FormatComboStateTests(unittest.TestCase):
 def test_combo_restored_readonly(self):
  self.assertIn("self.output_format_combo.config(state='readonly')",TEXT)
 def test_combo_change_is_bound(self):
  self.assertIn("bind('<<ComboboxSelected>>',self.on_output_format_changed)",TEXT)
 def test_export_format_is_validated(self):
  self.assertIn("output_format=output_format if output_format in OUTPUT_FORMATS else 'PDF'",TEXT)
