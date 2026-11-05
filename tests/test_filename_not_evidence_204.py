import ast,re,unittest
from pathlib import Path
SRC=Path(__file__).parents[1]/'rdf.py';TEXT=SRC.read_text(encoding='utf-8');TREE=ast.parse(TEXT)
WANTED={'normalize_text','parse_mes_folha','parse_chapa_nome','confidence_percent','is_ready_confidence'}
body=[]
for node in TREE.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'MONTHS_PT','MONTH_PATTERN'} for t in node.targets):body.append(node)
    if isinstance(node,ast.FunctionDef) and node.name in WANTED:body.append(node)
ns={'re':re,'Path':Path};exec(compile(ast.Module(body=body,type_ignores=[]),str(SRC),'exec'),ns)
class Tests(unittest.TestCase):
    def test_filename_never_supplies_registration(self):
        self.assertIsNone(ns['parse_chapa_nome']('Chapa/Nome: EMANUELLY OLIVEIRA MOREIRA DOS SANTOS','120938.jpeg'))
    def test_document_registration_is_used(self):
        result=ns['parse_chapa_nome']('Chapa/Nome: 170938 - EMANUELLY OLIVEIRA MOREIRA DOS SANTOS','120938.jpeg')
        self.assertEqual(result[0],'170938')
        self.assertEqual(result[3],'documento')
    def test_dirty_admission_suffix_is_removed(self):
        result=ns['parse_chapa_nome']('Chapa/Nome: 120938 - EMANUELLY OLIVEIRA MOREIRA DOS SANTOS ORTA DO ADMISSAO: 19/05/2025','qualquer.jpeg')
        self.assertEqual(result[1],'EMANUELLY OLIVEIRA MOREIRA DOS SANTOS')
    def test_rounding_matches_status(self):
        self.assertEqual(ns['confidence_percent'](.716),72)
        self.assertTrue(ns['is_ready_confidence'](.716))
        self.assertFalse(ns['is_ready_confidence'](.714))
    def test_source_path_removed_from_analysis(self):
        self.assertIn('def analyze_pdf(path, page_index=0):',TEXT)
        self.assertIn('def analyze_document(path, page_index=0):',TEXT)
        self.assertNotIn('filename_chapa(source_path',TEXT)
