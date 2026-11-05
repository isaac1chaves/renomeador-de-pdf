import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).parents[1]
TEXT=(ROOT/'rdf.py').read_text(encoding='utf-8')
TREE=ast.parse(TEXT)
APP=next(node for node in TREE.body if isinstance(node,ast.ClassDef) and node.name=='App')

def app_method(name):
    return next(node for node in APP.body if isinstance(node,ast.FunctionDef) and node.name==name)

class ContextMenuActionTests(unittest.TestCase):
    def test_toolbar_button_verifies_one_or_more_selected_files(self):
        self.assertIn("text='Verificar selecionados'",TEXT)
        self.assertIn('command=lambda:self.start(selected_only=True)',TEXT)
        start=ast.get_source_segment(TEXT,app_method('start'))
        self.assertIn("if not selected:return messagebox.showwarning('Verificar selecionados'",start)
        self.assertIn('analysis_files=selected',start)

    def test_selected_file_analysis_is_exposed_in_context_menu(self):
        menu=ast.get_source_segment(TEXT,app_method('create_context_menu'))
        self.assertIn("label='Verificar arquivo selecionado'",menu)
        self.assertIn('self.start(selected_only=True)',menu)

    def test_selected_analysis_preserves_other_results(self):
        start=ast.get_source_segment(TEXT,app_method('start'))
        self.assertIn("selected=self.tree.selection()",start)
        self.assertNotIn("if len(selected)!=1",start)
        self.assertIn("self.rows=[row for row in self.rows if row.get('path') not in selected_paths]",start)
        self.assertIn("self.row_by_path={path:row for path,row in self.row_by_path.items() if path not in selected_paths}",start)

    def test_context_menu_includes_supported_file_actions(self):
        menu=ast.get_source_segment(TEXT,app_method('create_context_menu'))
        for label in ('Abrir arquivo original','Abrir pasta do arquivo','Copiar como caminho','Propriedades',
                      'Editar nome e dados','Remover do lote'):
            self.assertIn(f"label='{label}'",menu)
        self.assertNotIn("label='Excluir arquivo original'",menu)
        self.assertNotIn("label='Recortar'",menu)

    def test_properties_show_real_file_information(self):
        properties=ast.get_source_segment(TEXT,app_method('show_selected_properties'))
        for value in ('original.stat()','original.parent','stat.st_size','stat.st_mtime','fitz.open(original)'):
            self.assertIn(value,properties)

if __name__=='__main__':
    unittest.main()
