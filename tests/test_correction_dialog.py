import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).parents[1]
TEXT=(ROOT/'rdf.py').read_text(encoding='utf-8')
TREE=ast.parse(TEXT)
APP=next(node for node in TREE.body if isinstance(node,ast.ClassDef) and node.name=='App')
CORRECT=next(node for node in APP.body if isinstance(node,ast.FunctionDef) and node.name=='correct_selected')

class CorrectionDialogTests(unittest.TestCase):
    def test_month_options_cover_all_months_in_uppercase(self):
        options=next(node.value for node in TREE.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='MONTH_OPTIONS' for target in node.targets))
        self.assertEqual(ast.literal_eval(options),(
            'JANEIRO','FEVEREIRO','MARÇO','ABRIL','MAIO','JUNHO',
            'JULHO','AGOSTO','SETEMBRO','OUTUBRO','NOVEMBRO','DEZEMBRO'))

    def test_month_uses_readonly_combobox(self):
        source=ast.get_source_segment(TEXT,CORRECT)
        self.assertIn("ttk.Combobox(box,textvariable=var,state='readonly',width=39,values=MONTH_OPTIONS)",source)
        self.assertIn("if key=='mes':value=str(value).upper()",source)

    def test_any_correction_field_can_be_blank(self):
        save=next(node for node in ast.walk(CORRECT) if isinstance(node,ast.FunctionDef) and node.name=='save')
        source=ast.get_source_segment(TEXT,save)
        self.assertIn("data={key:safe_filename(var.get()) for key,var in values}",source)
        self.assertNotIn('include_chapa.get()',source)
        self.assertNotIn('include_nome.get()',source)
        self.assertNotIn('include_mes.get()',source)

if __name__=='__main__':
    unittest.main()
