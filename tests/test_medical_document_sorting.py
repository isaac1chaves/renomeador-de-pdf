import ast, re, unicodedata, unittest
from pathlib import Path
SRC=Path(__file__).parents[1]/"rdf.py"
TREE=ast.parse(SRC.read_text(encoding="utf-8"))
WANTED={"_fold_document_text","_classification_scores","classify_extra_document"}
body=[n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name in WANTED]
NS={"re":re,"unicodedata":unicodedata,"Path":Path,"_document_search_text":lambda p:""}
exec(compile(ast.Module(body=body,type_ignores=[]),str(SRC),"exec"),NS)
class DocumentClassificationTests(unittest.TestCase):
 def classify(self,text,name="x.pdf"):return NS["classify_extra_document"](name,text)
 def test_atestado_variado(self):
  self.assertEqual(self.classify("ATESTADO MEDICO. Atesto para fins. CRM 123"),"Atestados")
  self.assertEqual(self.classify("Paciente necessita de 2 dias de repouso. CID A09. CRM"),"Atestados")
 def test_declaracao_variada(self):
  self.assertEqual(self.classify("DECLARAÇÃO DE COMPARECIMENTO"),"Declarações")
  self.assertEqual(self.classify("Declaro para os devidos fins que compareceu ao atendimento"),"Declarações")
 def test_timesheet(self):self.assertIsNone(self.classify("FOLHA DE PONTO. Observacao: atestado entregue. Entrada Saida"))
 def test_priority(self):self.assertEqual(self.classify("Declaracao emitida como atestado medico"),"Atestados")
 def test_filename_is_only_secondary(self):
  self.assertIsNone(self.classify("Relatorio administrativo mensal","ATESTADO.pdf"))
  self.assertEqual(self.classify("atesto que necessita repouso","ATESTADO.pdf"),"Atestados")
 def test_unrelated(self):self.assertIsNone(self.classify("Relatorio administrativo mensal"))
if __name__=="__main__":unittest.main()
