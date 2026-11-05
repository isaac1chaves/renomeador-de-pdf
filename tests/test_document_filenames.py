import ast, re, unicodedata, unittest
from pathlib import Path
SRC=Path(__file__).parents[1]/"rdf.py"
TREE=ast.parse(SRC.read_text(encoding="utf-8"))
node=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=="compose_document_filename")
def safe_filename(s):return re.sub(r"\s+"," ",re.sub(r"[\\/:*?\"<>|]"," ",s)).strip(" .")
NS={"Path":Path,"safe_filename":safe_filename,"unicodedata":unicodedata,"re":re}
exec(compile(ast.Module(body=[node],type_ignores=[]),str(SRC),"exec"),NS)
class Tests(unittest.TestCase):
 def test_atestado_sequence(self):self.assertEqual(NS["compose_document_filename"]("79441 - 1.pdf","Atestado"),"79441 - ATESTADO 1.pdf")
 def test_declaracao_no_duplicate(self):self.assertEqual(NS["compose_document_filename"]("79441 - DECLARAÇÃO.pdf","Declaração"),"79441 - DECLARAÇÃO.pdf")
 def test_integrated(self):self.assertGreaterEqual(SRC.read_text(encoding="utf-8").count("compose_document_filename("),3)
if __name__=="__main__":unittest.main()
