import ast, unittest
from pathlib import Path
TEXT=(Path(__file__).parents[1]/"rdf.py").read_text(encoding="utf-8")
class ManualApprovalTests(unittest.TestCase):
 def test_buttons_and_method(self):
  ast.parse(TEXT)
  self.assertIn("def approve_as_category(self,category):",TEXT)
  self.assertIn("text='Como atestado'",TEXT)
  self.assertIn("text='Como declaração'",TEXT)
  self.assertIn("'status':'APROVADO'",TEXT)
 def test_ocr_rotations(self):
  for angle in ('ROTATE_90_CLOCKWISE','ROTATE_180','ROTATE_90_COUNTERCLOCKWISE'):self.assertIn(angle,TEXT)
if __name__=='__main__':unittest.main()
