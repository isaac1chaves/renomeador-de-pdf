import ast, re, unittest, unicodedata
from pathlib import Path
SRC=Path(__file__).parents[1]/'rdf.py'
TEXT=SRC.read_text(encoding='utf-8')
TREE=ast.parse(TEXT)
WANTED={'normalize_text','parse_mes_folha','filename_chapa','parse_chapa_nome','_fold_document_text','relevant_header_confidence'}
body=[]
for node in TREE.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'MONTHS_PT','MONTH_PATTERN'} for t in node.targets):body.append(node)
    if isinstance(node,ast.FunctionDef) and node.name in WANTED:body.append(node)
ns={'re':re,'Path':Path,'unicodedata':unicodedata}; exec(compile(ast.Module(body=body,type_ignores=[]),str(SRC),'exec'),ns)
class ParserTests(unittest.TestCase):
    def test_document_chapa_is_trusted(self):
        got=ns['parse_chapa_nome']('Chapa/Nome: 125530 - ANGELA DA COSTA FERNANDES SILVA Funcao: X','125530.pdf')
        self.assertEqual(got[:2],('125530','ANGELA DA COSTA FERNANDES SILVA')); self.assertEqual(got[3],'documento')
    def test_ocr_variants_of_chapa_nome_are_recognized(self):
        for label in ('Chupa/Nomo:', 'Chiupa/Nomo:', 'Chupa Nome:'):
            with self.subTest(label=label):
                got=ns['parse_chapa_nome'](f'{label} 119105 - FABRICIO GABRIEL DA SILVA LIMA Data de admissao: 07/04/2025')
                self.assertEqual(got[:2],('119105','FABRICIO GABRIEL DA SILVA LIMA'))
    def test_ocr_confidence_recognizes_chupa_nomo_header(self):
        tokens=['Chupa/Nomo:', '119105', '-', 'FABRICIO', 'GABRIEL', 'DA', 'SILVA', 'LIMA']
        data={'text':tokens,'conf':['88']*len(tokens),'block_num':[1]*len(tokens),'par_num':[1]*len(tokens),'line_num':[1]*len(tokens)}
        self.assertGreater(ns['relevant_header_confidence'](data,'119105'),0)
    def test_filename_only_is_not_an_ocr_source(self):
        self.assertIsNone(ns['parse_chapa_nome']('Chapa/Nome: ANGELA DA COSTA FERNANDES SILVA Funcao: X','125530.pdf'))
    def test_no_anchor_does_not_trust_filename(self):
        self.assertIsNone(ns['parse_chapa_nome']('texto aleatorio sem formulario','125530.pdf'))
    def test_no_confidence_bonus(self):
        self.assertNotIn('conf+bonus',TEXT); self.assertNotIn('bonus=.15',TEXT)
    def test_memory_optimized_rotation(self):
        self.assertIn('rect.y1-height',TEXT); self.assertNotIn('for angle,oriented in ((0,image)',TEXT)
    def test_filter_reattach_signature(self):
        self.assertIn("reattach(iid,'',position)",TEXT)
    def test_refresh_requires_document_source(self):
        self.assertIn("row.get('chapa_source','documento')=='documento'",TEXT)
    def test_clear_session_disables_resave(self):
        self.assertIn('session_persistence_disabled=True',TEXT)
        self.assertIn('if self.session_persistence_disabled:return',TEXT)
    def test_manual_source_is_recorded(self):
        self.assertIn("'chapa_source':'manual'",TEXT)
    def test_old_session_is_not_trusted(self):
        self.assertIn("row.setdefault('chapa_source','desconhecida')",TEXT)
        self.assertIn("row['status']='REVISAR'",TEXT)
    def test_invalid_sanitized_name_is_blocked(self):
        self.assertIn('novo nome contem apenas caracteres inválidos',TEXT)
        self.assertIn('if not new:continue',TEXT)
    def test_completed_export_does_not_recreate_session(self):
        self.assertIn('self.session_persistence_disabled=True',TEXT)
        self.assertIn("SESSION_FILE.with_suffix('.tmp').unlink",TEXT)
    def test_number_before_label_layout(self):
        got=ns['parse_chapa_nome']('126509 KELLY DO CARMO DA SILVA OLIVEIRA Chapa/Nome Data de admissao: 01/09/2025','126509.pdf')
        self.assertEqual(got[:2],('126509','KELLY DO CARMO DA SILVA OLIVEIRA'))
    def test_year_is_not_used_as_chapa(self):
        self.assertIsNone(ns['parse_chapa_nome']('Fim do Contrato: 01/04/2027 Terça-Feira Domingo','126509.pdf'))
    def test_ocr_month_with_stray_digit(self):
        self.assertEqual(ns['parse_mes_folha']('FOLHA DE PONTO V2.0 - SETEMBRO0/2026'),'setembro')
if __name__=='__main__':unittest.main()
