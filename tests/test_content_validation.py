import ast
import tempfile
import unittest
from pathlib import Path
import fitz
from PIL import Image

SOURCE_PATH = Path(__file__).parents[1] / 'rdf.py'
SOURCE = SOURCE_PATH.read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)
FUNCTION = next(node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name == 'validate_input_content')
MODULE = ast.Module(body=[FUNCTION], type_ignores=[])
NAMESPACE = {'Path': Path, 'fitz': fitz, 'Image': Image, 'IMAGE_FORMAT_BY_EXTENSION': {'.png':'PNG','.jpg':'JPEG','.jpeg':'JPEG','.bmp':'BMP','.tif':'TIFF','.tiff':'TIFF','.webp':'WEBP'}, 'ValueError': ValueError, 'Exception': Exception, 'OSError': OSError, 'len': len}
exec(compile(ast.fix_missing_locations(MODULE), str(SOURCE_PATH), 'exec'), NAMESPACE)
validate_input_content = NAMESPACE['validate_input_content']

class ContentValidationTests(unittest.TestCase):
    def test_rejects_mp4_renamed_as_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'video.pdf'
            path.write_bytes(b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp41isom')
            with self.assertRaisesRegex(ValueError,'vídeo MP4'):
                validate_input_content(path)

    def test_rejects_arbitrary_content_renamed_as_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'falso.pdf'
            path.write_bytes(b'isto nao e um pdf')
            with self.assertRaisesRegex(ValueError,'não é um PDF válido'):
                validate_input_content(path)

    def test_accepts_real_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'real.pdf'
            document=fitz.open(); document.new_page(); document.save(path); document.close()
            self.assertEqual(validate_input_content(path),'PDF')

    def test_accepts_png_with_png_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'imagem.png'
            Image.new('RGB',(2,2),'white').save(path,'PNG')
            self.assertEqual(validate_input_content(path),'PNG')

    def test_accepts_valid_png_content_named_jpeg(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'imagem.jpeg'
            Image.new('RGB',(2,2),'white').save(path,'PNG')
            self.assertEqual(validate_input_content(path),'PNG')

    def test_rejects_non_image_named_jpeg(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'falso.jpeg'
            path.write_bytes(b'not an image')
            with self.assertRaisesRegex(ValueError,'não é uma imagem válida'):
                validate_input_content(path)
