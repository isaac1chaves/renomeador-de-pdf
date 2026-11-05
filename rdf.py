import os, re, shutil, threading, sys, logging, json, hashlib, unicodedata, queue, ctypes
from logging.handlers import RotatingFileHandler
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz
import cv2
cv2.setNumThreads(1)
import numpy as np
import pytesseract
from PIL import Image, ImageTk
from app_version import APP_VERSION
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_FILES = None; TkinterDnD = None; DND_AVAILABLE = False

APP_TITLE = f"Renomeador de Folhas (RDF) - Matrícula/Nome v{APP_VERSION}"
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "RDF" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGER = logging.getLogger("rdf")
LOGGER.setLevel(logging.INFO)
if not LOGGER.handlers:
    log_handler=RotatingFileHandler(LOG_DIR / "renomeador.log",maxBytes=2*1024*1024,backupCount=3,encoding="utf-8")
    log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(log_handler)
LOGGER.propagate=False
SESSION_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "RDF"
SESSION_FILE = SESSION_DIR / "sessao_atual.json"
SPLIT_DIR = SESSION_DIR / "páginas_separadas"
CONVERT_DIR = SESSION_DIR / "arquivos_convertidos"
INPUT_EXTENSIONS = {'.pdf','.png','.jpg','.jpeg','.bmp','.tif','.tiff','.webp'}
IMAGE_FORMAT_BY_EXTENSION = {'.png':'PNG','.jpg':'JPEG','.jpeg':'JPEG','.bmp':'BMP','.tif':'TIFF','.tiff':'TIFF','.webp':'WEBP'}

def validate_input_content(path):
    """Validate the real file content instead of trusting its extension."""
    file_path=Path(path)
    suffix=file_path.suffix.lower()
    try:
        with file_path.open('rb') as stream:
            header=stream.read(1024)
    except OSError as exc:
        raise ValueError(f'Não foi possível ler o arquivo: {exc}') from exc
    if suffix=='.pdf':
        if not header.lstrip().startswith(b'%PDF-'):
            if len(header)>=12 and header[4:8]==b'ftyp':
                raise ValueError('O arquivo tem extensão PDF, mas o conteúdo real é um vídeo MP4.')
            raise ValueError('O arquivo tem extensão PDF, mas o conteúdo não é um PDF válido.')
        try:
            with fitz.open(file_path) as document:
                if len(document)<1:raise ValueError('O PDF não possui páginas.')
        except Exception as exc:
            raise ValueError(f'O conteúdo PDF está inválido ou corrompido: {exc}') from exc
        return 'PDF'
    expected=IMAGE_FORMAT_BY_EXTENSION.get(suffix)
    if expected:
        try:
            with Image.open(file_path) as image:
                actual=(image.format or '').upper()
                image.verify()
        except Exception as exc:
            raise ValueError(f'O arquivo tem extensão {suffix.upper()}, mas não é uma imagem válida: {exc}') from exc
        # Accept a valid decodable image even when a scanner or messaging
        # application saved it under another supported image extension.
        return actual
    raise ValueError(f'Formato não suportado: {suffix or "sem extensão"}.')
OUTPUT_FORMATS = ('PDF','PNG','JPEG','JPG','WEBP','BMP','TIFF')
MAX_BATCH_FILES=300
MAX_BATCH_PAGES=1000
MAX_FILE_SIZE_MB=100
LARGE_FILE_WARNING_MB=30
PARALLEL_WORKERS=4
SESSION_DIR.mkdir(parents=True, exist_ok=True)
SPLIT_DIR.mkdir(parents=True, exist_ok=True)
CONVERT_DIR.mkdir(parents=True, exist_ok=True)
BaseTk = TkinterDnD.Tk if DND_AVAILABLE else tk.Tk

def configure_tesseract():
    """Localiza o Tesseract instalado no usuario ou em pastas comuns, sem admin."""
    manual = Path(__file__).with_name('tesseract_path.txt')
    manual_path = manual.read_text(encoding='utf-8-sig').strip() if manual.exists() else None
    bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(bundle_dir, 'Tesseract-OCR', 'tesseract.exe'),
        manual_path,
        shutil.which('tesseract'),
        os.path.join(os.environ.get('LOCALAPPDATA',''), 'Programs', 'Tesseract-OCR', 'tesseract.exe'),
        os.path.join(os.environ.get('LOCALAPPDATA',''), 'Tesseract-OCR', 'tesseract.exe'),
        os.path.join(os.environ.get('USERPROFILE',''), 'AppData', 'Local', 'Programs', 'Tesseract-OCR', 'tesseract.exe'),
        os.path.join(os.environ.get('ProgramFiles',''), 'Tesseract-OCR', 'tesseract.exe'),
        os.path.join(os.environ.get('ProgramFiles(x86)',''), 'Tesseract-OCR', 'tesseract.exe'),
    ]
    for exe in candidates:
        if exe and os.path.isfile(exe):
            pytesseract.pytesseract.tesseract_cmd = exe
            tessdata = os.path.join(os.path.dirname(exe), 'tessdata')
            if os.path.isdir(tessdata):
                os.environ['TESSDATA_PREFIX'] = tessdata
            return exe
    return None

TESSERACT_EXE = configure_tesseract()

def safe_filename(s):
    s = re.sub(r'[\\/:*?"<>|]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip(' .')

def compose_document_filename(path, document_type):
    """Inclui ATESTADO/DECLARAÇÃO no nome, preservando matrícula e sequência."""
    stem=safe_filename(Path(path).stem)
    label='ATESTADO' if document_type=='Atestado' else 'DECLARAÇÃO'
    folded=unicodedata.normalize('NFKD',stem).encode('ascii','ignore').decode('ascii')
    cleaned=re.sub(r'(?i)\b(?:ATESTADO|DECLARACAO)\b',' ',folded)
    cleaned=safe_filename(re.sub(r'\s*-\s*',' - ',cleaned))
    lead=re.match(r'^\s*(\d{4,12})\b',cleaned)
    sequence=re.search(r'(?:^|\s*-\s*)(\d{1,3})\s*$',cleaned)
    if lead:
        result=f'{lead.group(1)} - {label}'
        if sequence and sequence.group(1)!=lead.group(1):result+=f' {sequence.group(1)}'
        return safe_filename(result)+'.pdf'
    base=cleaned.strip(' -')
    if not base:return label+'.pdf'
    if label=='ATESTADO' and re.search(r'(?i)\bATESTADO\b',folded):return safe_filename(stem)+'.pdf'
    if label=='DECLARAÇÃO' and re.search(r'(?i)\bDECLARACAO\b',folded):return safe_filename(stem)+'.pdf'
    return safe_filename(f'{base} - {label}')+'.pdf'

def normalize_text(s):
    s=s.replace('|',' ').replace('\r','\n')
    s=re.sub(r'[ \t]+',' ',s)
    s=re.sub(r'\n+','\n',s)
    return s.strip()

MONTHS_PT = {
    "01":"janeiro", "02":"fevereiro", "03":"março", "04":"abril",
    "05":"maio", "06":"junho", "07":"julho", "08":"agosto",
    "09":"setembro", "10":"outubro", "11":"novembro", "12":"dezembro",
}
MONTH_PATTERN = "|".join(MONTHS_PT.values())
MONTH_OPTIONS = ("JANEIRO","FEVEREIRO","MARÇO","ABRIL","MAIO","JUNHO",
                 "JULHO","AGOSTO","SETEMBRO","OUTUBRO","NOVEMBRO","DEZEMBRO")

def parse_mes_folha(text, filename=""):
    """Extrai o mês do título da folha; usa o nome do arquivo como fallback."""
    flat=re.sub(r'\s+',' ',normalize_text(text)).lower()
    patterns=[
        rf'folha\s+de\s+ponto[^\n]{{0,100}}?({MONTH_PATTERN})\d?\s*[/\-]\s*(?:19|20)\d{{2}}',
        rf'({MONTH_PATTERN})\d?\s*[/\-]\s*(?:19|20)\d{{2}}',
    ]
    for pattern in patterns:
        found=re.search(pattern,flat,re.I)
        if found:return found.group(1).lower()
    # Ex.: Folha_Ponto_NOME_10_2026.pdf
    found=re.search(r'(?:^|[_\- ])(0[1-9]|1[0-2])[_\- ](?:19|20)\d{2}(?:$|[_.\- ])',Path(filename).name)
    return MONTHS_PT.get(found.group(1)) if found else None

def filename_chapa(filename):
    stem=Path(filename).stem
    match=re.fullmatch(r'\s*(\d{4,12})\s*',stem)
    return match.group(1) if match else None

def parse_chapa_nome(text, filename=""):
    """Extract registration and name only from document text, never the filename."""
    flat=re.sub(r'\s+',' ',normalize_text(text))
    label=re.search(r'ch(?:a|i?u)pa\s*[/|1l-]?\s*n[o0]m[e0o]\s*[:.;-]?',flat,re.I)
    if not label:return None
    # Standard layout: label, registration, name.
    area=flat[label.end():label.end()+260]
    starts_with_next_label=bool(re.match(r'\s*(?:d[a-z]{0,5}\s+(?:d[aeo]\s+)?admiss|admiss|fun[a-zçã]{2,}|hor[a-zá]{2,}|lota[a-zçã]{2,})',area,re.I))
    number=None if starts_with_next_label else re.search(r'(?<!\d)(\d{4,12})(?!\d)',area[:100])
    if number:
        chapa=number.group(1); after=area[number.end():]
    else:
        # OCR may reorder a header as: registration, name, Chapa/Nome, next label.
        before=flat[max(0,label.start()-220):label.start()]
        candidates=list(re.finditer(r'(?<!\d)(\d{4,12})(?!\d)',before))
        if not candidates:return None
        number=candidates[-1]; chapa=number.group(1); after=before[number.end():]
    after=after.strip(' :-. _')
    stop_pattern=(
        r'\b(?:ch(?:a|i?u)pa\s*[/|1l-]?\s*n[o0]m[e0o]|'
        r'(?:[a-z]{2,12}\s+)?d[aeo]\s+admiss[a-zãç]*|admiss[a-zãç]*|'
        r'fun[a-zçã]{2,}|hor[a-zá]{2,}|lota[a-zçã]{2,}|'
        r'fim(?:\s+d[aeo])?|contrat[a-z]*|hrs?\s*[/\-]?\s*seg|'
        r'dia\s+da\s+semana|entrada|sa[ií]da|assinatura)\b'
    )
    after=re.split(stop_pattern,after,1,flags=re.I)[0]
    name=''.join(c for c in after if c.isalpha() or c in " À-ÖØ-öø-ÿ.'-")
    name=re.sub(r'\s+',' ',name).strip(' .-').upper()
    name=re.sub(r'^(?:CHAPA|NOME)+\s*','',name).strip()
    if len(name)<5 or len(name.split())<2:return None
    return chapa,name,parse_mes_folha(text),'documento'

def rectify_document_photo(image):
    """Crop and deskew a photographed sheet when a reliable page contour exists."""
    if image is None or image.ndim not in (2,3):return image,False
    height,width=image.shape[:2]
    if min(height,width)<500:return image,False
    gray=image if image.ndim==2 else cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
    blur=cv2.GaussianBlur(gray,(5,5),0)
    edges=cv2.Canny(blur,50,150)
    edges=cv2.dilate(edges,np.ones((5,5),np.uint8),iterations=2)
    contours,_=cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    page_area=float(height*width)
    for contour in sorted(contours,key=cv2.contourArea,reverse=True)[:25]:
        perimeter=cv2.arcLength(contour,True)
        polygon=cv2.approxPolyDP(contour,0.02*perimeter,True)
        if len(polygon)!=4:continue
        area=cv2.contourArea(polygon)
        if area<page_area*.45 or area>page_area*.995:continue
        points=polygon.reshape(4,2).astype(np.float32)
        sums=points.sum(axis=1); diffs=np.diff(points,axis=1).ravel()
        rect=np.array([points[np.argmin(sums)],points[np.argmin(diffs)],points[np.argmax(sums)],points[np.argmax(diffs)]],dtype=np.float32)
        top_left,top_right,bottom_right,bottom_left=rect
        target_width=int(max(np.linalg.norm(bottom_right-bottom_left),np.linalg.norm(top_right-top_left)))
        target_height=int(max(np.linalg.norm(top_right-bottom_right),np.linalg.norm(top_left-bottom_left)))
        if target_width<350 or target_height<500:continue
        ratio=target_width/target_height
        if not .45<=ratio<=1.05:continue
        destination=np.array([[0,0],[target_width-1,0],[target_width-1,target_height-1],[0,target_height-1]],dtype=np.float32)
        corrected=cv2.warpPerspective(image,cv2.getPerspectiveTransform(rect,destination),(target_width,target_height),borderMode=cv2.BORDER_REPLICATE)
        LOGGER.info('Perspectiva corrigida: %sx%s -> %sx%s',width,height,target_width,target_height)
        return corrected,True
    return image,False

def _pixmap_to_rgb(pix):
    image=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,pix.n).copy()
    return cv2.cvtColor(image,cv2.COLOR_RGBA2RGB) if pix.n==4 else image

def render_header_candidates(pdf_path, page_index=0):
    """Renderiza topo e rodape da pagina escolhida para OCR."""
    with fitz.open(pdf_path) as doc:
        if not 0 <= int(page_index) < len(doc):raise IndexError('Página de análise fora do intervalo.')
        page=doc[int(page_index)]; rect=page.rect; height=rect.height*.34; matrix=fitz.Matrix(3,3)
        top=page.get_pixmap(matrix=matrix,clip=fitz.Rect(rect.x0,rect.y0,rect.x1,rect.y0+height),alpha=False)
        bottom=page.get_pixmap(matrix=matrix,clip=fitz.Rect(rect.x0,rect.y1-height,rect.x1,rect.y1),alpha=False)
    return [(0,_pixmap_to_rgb(top)),(180,cv2.rotate(_pixmap_to_rgb(bottom),cv2.ROTATE_180))]


def render_pdf_page(pdf_path, page_index=0, scale=1.8):
    """Renderiza uma pagina inteira para a previa lateral, sob demanda."""
    with fitz.open(pdf_path) as doc:
        total=len(doc)
        if total<1: raise RuntimeError('PDF sem páginas.')
        page_index=max(0,min(int(page_index),total-1))
        page=doc[page_index]
        pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
    image=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,pix.n).copy()
    if pix.n==4:image=cv2.cvtColor(image,cv2.COLOR_RGBA2RGB)
    return image,total

def preprocess(img):
    gray=cv2.cvtColor(img,cv2.COLOR_RGB2GRAY)
    gray=cv2.resize(gray,None,fx=1.25,fy=1.25,interpolation=cv2.INTER_CUBIC)
    gray=cv2.fastNlMeansDenoising(gray,None,12,7,21)
    return cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,35,12)

def relevant_header_confidence(data, chapa=None):
    """Confidence of the Chapa/Nome line, excluding page-wide noise."""
    texts=data.get('text',[]); confidences=data.get('conf',[])
    size=min(len(texts),len(confidences)); groups={}
    for index in range(size):
        token=str(texts[index]).strip()
        if not token:continue
        try:confidence=float(confidences[index])
        except (TypeError,ValueError):continue
        if confidence<0:continue
        key=tuple(data.get(field,[0]*size)[index] for field in ('block_num','par_num','line_num'))
        groups.setdefault(key,[]).append((token,confidence))
    candidates=[]
    for items in groups.values():
        line=' '.join(token for token,_ in items)
        folded=_fold_document_text(line); score=0
        if re.search(r'ch(?:a|i?u)pa.{0,15}n[o0]m[e0o]',folded):score+=5
        if chapa and re.search(rf'(?<!\d){re.escape(chapa)}(?!\d)',line):score+=4
        if re.search(r'(?<!\d)\d{4,12}\s*[-:]',line):score+=2
        if score:candidates.append((score,sum(value for _,value in items)/len(items)/100))
    return max(candidates,key=lambda item:(item[0],item[1]))[1] if candidates else 0

def confidence_percent(value):
    return max(0,min(100,int(float(value)*100+0.5)))

def is_ready_confidence(value, minimum=72):
    return confidence_percent(value)>=minimum

def analyze_pdf(path, page_index=0):
    # Texto embutido primeiro. A chapa numerica do nome do arquivo serve como validacao.
    try:
        with fitz.open(path) as doc:
            if not 0 <= int(page_index) < len(doc):raise IndexError('Página de análise fora do intervalo.')
            page=doc[int(page_index)]
            blocks=sorted(page.get_text('blocks'),key=lambda b:(round(b[1]/8),b[0]))
            text='\n'.join(b[4] for b in blocks)
        parsed=parse_chapa_nome(text)
        if parsed:return parsed,'Texto',0.99
    except (fitz.FileDataError,RuntimeError) as exc:LOGGER.warning('Falha ao ler texto embutido de %s: %s',path,exc)
    except Exception:LOGGER.exception('Erro inesperado ao extrair texto de %s',path)
    attempts=[]
    for angle,header in render_header_candidates(path,page_index):
        proc=preprocess(header)
        for image,config in ((proc,'--oem 3 --psm 6'),(proc,'--oem 3 --psm 11'),(header,'--oem 3 --psm 6')):
            try:
                data=pytesseract.image_to_data(image,lang='por+eng',config=config,output_type=pytesseract.Output.DICT)
                text=' '.join(x for x in data['text'] if x.strip())
                parsed=parse_chapa_nome(text)
                if parsed:
                    conf=relevant_header_confidence(data,parsed[0])
                    attempts.append((parsed,conf,angle))
            except pytesseract.TesseractNotFoundError:
                raise RuntimeError('Tesseract não localizado. Feche o app depois da instalação ou use CONFIGURAR_TESSERACT.bat.')
    if attempts:
        attempts.sort(key=lambda item:(item[0][3]=='documento',item[0][2] is not None,item[1]),reverse=True)
        parsed,conf,angle=attempts[0]
        if parsed[2] is None:
            month=next((candidate[0][2] for candidate in attempts if candidate[0][2]),None)
            if month:parsed=(parsed[0],parsed[1],month,parsed[3])
        method='OCR' if angle==0 else 'OCR 180 graus'
        return parsed,method,conf
    return None,'Falhou',0


def _fold_document_text(value):
    return unicodedata.normalize('NFKD', value or '').encode('ascii','ignore').decode('ascii').lower()

def _classification_scores(raw, filename=''):
    """Pontua familias de sinais, evitando depender de um unico modelo de documento."""
    flat=re.sub(r'\s+',' ',_fold_document_text(raw))
    name=re.sub(r'[_\-.]+',' ',_fold_document_text(Path(filename).stem))
    timesheet_patterns=(
        r'folha\s+de\s+ponto', r'cartao\s+de\s+ponto', r'espelho\s+de\s+ponto',
        r'controle\s+de\s+frequencia', r'entrada.{0,30}saida', r'jornada\s+de\s+trabalho',
        r'chapa.{0,20}nome.{0,80}(?:entrada|saida)',
    )
    if sum(bool(re.search(x,flat)) for x in timesheet_patterns)>=1:
        return {'Atestados':0,'Declarações':0,'timesheet':True}
    atestado_groups=(
        (4,(r'\batestado\s+(?:medico|odontologico|de\s+saude)\b', r'\batestado\b')),
        (3,(r'\batesto\s+(?:para|que|a)\b', r'necessita.{0,35}(?:afastamento|repouso)', r'incapacidade\s+laboral')),
        (2,(r'\bcid\s*[-:]?\s*[a-z]?\s*\d', r'\bdias?\s+de\s+(?:repouso|afastamento)', r'afastad[aeo].{0,30}(?:trabalho|atividade)')),
        (1,(r'medico\b', r'crm\b', r'cirurgiao\s+dentista', r'cro\b', r'paciente\b')),
    )
    declaracao_groups=(
        (4,(r'\bdeclaracao\s+(?:de\s+)?(?:comparecimento|estagio|presenca|atendimento)\b', r'\bdeclaracao\b')),
        (3,(r'\bdeclaro\s+(?:para|que|a)\b', r'declaramos\s+(?:para|que)', r'compareceu\s+(?:a|ao|nesta|neste)')),
        (2,(r'para\s+os\s+devidos\s+fins', r'permaneceu.{0,40}(?:atendimento|consulta)', r'esteve\s+presente')),
        (1,(r'comprovacao', r'horario\s+de\s+atendimento', r'declaramos')),
    )
    def score(groups):
        total=0
        for weight,patterns in groups:
            if any(re.search(pattern,flat) for pattern in patterns):total+=weight
        return total
    a=score(atestado_groups); d=score(declaracao_groups)
    # O nome ajuda, mas nunca classifica sozinho: e apenas desempate apos algum sinal do documento.
    if a and re.search(r'\batestad',name):a+=2
    if d and re.search(r'\bdeclar',name):d+=2
    return {'Atestados':a,'Declarações':d,'timesheet':False}

def _embedded_document_text(path, max_pages=3):
    """Extract embedded text without starting Tesseract."""
    collected=[]
    try:
        with fitz.open(path) as doc:
            for index in range(min(len(doc),max_pages)):
                text=doc[index].get_text('text') or ''
                if text.strip():collected.append(text)
    except Exception:
        LOGGER.exception('Falha ao extrair texto embutido de %s',path)
    return normalize_text('\n'.join(collected))

def _document_search_text(path, max_pages=2):
    """Classify extra documents with a short OCR path and a rotated fallback."""
    collected=[]
    try:
        with fitz.open(path) as doc:
            for index in range(min(len(doc),max_pages)):
                page=doc[index]
                embedded=page.get_text('text') or ''
                if embedded.strip():collected.append(embedded)
                scores=_classification_scores('\n'.join(collected),path)
                if scores['timesheet'] or max(scores['Atestados'],scores['Declarações'])>=4:
                    return normalize_text('\n'.join(collected))
                # A lower scale is sufficient for document keywords and reduces
                # pixels sent to Tesseract by roughly half versus the old 2.4x path.
                pix=page.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False)
                img=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,pix.n).copy()
                if pix.n==4:img=cv2.cvtColor(img,cv2.COLOR_RGBA2RGB)
                gray=cv2.cvtColor(img,cv2.COLOR_RGB2GRAY)
                binary=cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
                # Most scans are upright. Try 0 and 180 degrees first, one OCR
                # layout each, and stop immediately after enough evidence.
                for angle,image in ((0,binary),(180,cv2.rotate(binary,cv2.ROTATE_180))):
                    text=pytesseract.image_to_string(image,lang='por+eng',config='--oem 3 --psm 6')
                    if text.strip():collected.append(text)
                    scores=_classification_scores('\n'.join(collected),path)
                    if scores['timesheet'] or max(scores['Atestados'],scores['Declarações'])>=4:
                        LOGGER.info('Documento classificado durante OCR rápido: %s, página %s, ângulo %s',path,index+1,angle)
                        return normalize_text('\n'.join(collected))
            # Rare sideways scans use one final pass on the first page only.
            if doc and not collected:
                page=doc[0]
                pix=page.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False)
                img=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,pix.n).copy()
                if pix.n==4:img=cv2.cvtColor(img,cv2.COLOR_RGBA2RGB)
                gray=cv2.cvtColor(img,cv2.COLOR_RGB2GRAY)
                for angle,image in ((90,cv2.rotate(gray,cv2.ROTATE_90_CLOCKWISE)),(270,cv2.rotate(gray,cv2.ROTATE_90_COUNTERCLOCKWISE))):
                    text=pytesseract.image_to_string(image,lang='por+eng',config='--oem 3 --psm 6')
                    if text.strip():collected.append(text)
                    scores=_classification_scores('\n'.join(collected),path)
                    if max(scores['Atestados'],scores['Declarações'])>=4:
                        LOGGER.info('Documento classificado no fallback: %s, ângulo %s',path,angle)
                        break
    except Exception:
        LOGGER.exception('Falha ao classificar documento %s',path)
    return normalize_text('\n'.join(collected))

def _document_search_text_exhaustive(path, max_pages=3):
    """Compatibility fallback for difficult scans that the fast path cannot classify."""
    collected=[]
    try:
        with fitz.open(path) as doc:
            for index in range(min(len(doc),max_pages)):
                page=doc[index]
                embedded=page.get_text('text') or ''
                if embedded.strip():collected.append(embedded)
                scores=_classification_scores('\n'.join(collected),path)
                if max(scores['Atestados'],scores['Declarações'])>=6:
                    return normalize_text('\n'.join(collected))
                pix=page.get_pixmap(matrix=fitz.Matrix(2.4,2.4),alpha=False)
                img=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,pix.n).copy()
                if pix.n==4:img=cv2.cvtColor(img,cv2.COLOR_RGBA2RGB)
                gray=cv2.cvtColor(img,cv2.COLOR_RGB2GRAY)
                gray=cv2.fastNlMeansDenoising(gray,None,10,7,21)
                threshold=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,41,13)
                oriented=[img,cv2.rotate(img,cv2.ROTATE_90_CLOCKWISE),cv2.rotate(img,cv2.ROTATE_180),cv2.rotate(img,cv2.ROTATE_90_COUNTERCLOCKWISE)]
                oriented_threshold=[threshold,cv2.rotate(threshold,cv2.ROTATE_90_CLOCKWISE),cv2.rotate(threshold,cv2.ROTATE_180),cv2.rotate(threshold,cv2.ROTATE_90_COUNTERCLOCKWISE)]
                for angle,(original,binary) in zip((0,90,180,270),zip(oriented,oriented_threshold)):
                    for image,psm in ((binary,6),(binary,11),(original,11)):
                        text=pytesseract.image_to_string(image,lang='por+eng',config=f'--oem 3 --psm {psm}')
                        if text.strip():collected.append(text)
                        scores=_classification_scores('\n'.join(collected),path)
                        if max(scores['Atestados'],scores['Declarações'])>=7:
                            LOGGER.info('Documento classificado no fallback completo: %s, página %s, ângulo %s',path,index+1,angle)
                            return normalize_text('\n'.join(collected))
    except Exception:
        LOGGER.exception('Falha no fallback completo de %s',path)
    return normalize_text('\n'.join(collected))

def classify_extra_document(path, text=None):
    """Retorna Atestados, Declarações ou None por evidencias combinadas."""
    raw=text if text is not None else _document_search_text(path)
    scores=_classification_scores(raw,path)
    if scores['timesheet']:return None
    a=scores['Atestados']; d=scores['Declarações']
    if a>=4 and a>=d:return 'Atestados'
    if d>=4 and d>a:return 'Declarações'
    return None

def analyze_document(path, page_index=0):
    """Use cheap evidence first and reserve full-page OCR for unresolved files."""
    embedded=_embedded_document_text(path)
    if embedded:
        category=classify_extra_document(path,embedded)
        if category:
            label='Atestado' if category=='Atestados' else 'Declaração'
            return {'category':category,'document_type':label,'method':'Documento','conf':0.90}
    # Timesheets are the dominant workload. Header OCR is much cheaper than the
    # previous full-page, four-rotation document classification.
    parsed,method,conf=analyze_pdf(path,page_index)
    if parsed:
        return {'category':None,'document_type':'Folha de ponto','parsed':parsed,'method':method,'conf':conf}
    # Fast document OCR handles common scans. If it remains unresolved,
    # restore the proven exhaustive routine only for that difficult file.
    fast_text=_document_search_text(path)
    category=classify_extra_document(path,fast_text)
    if not category:
        exhaustive_text=_document_search_text_exhaustive(path)
        category=classify_extra_document(path,exhaustive_text)
    if category:
        label='Atestado' if category=='Atestados' else 'Declaração'
        return {'category':category,'document_type':label,'method':'Documento','conf':0.90}
    return {'category':None,'document_type':'Não identificado','parsed':None,'method':method,'conf':conf}

class App(BaseTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry('1380x840')
        self.minsize(1040,650)
        self.configure(bg='#f3f7f7')

        self.files=[]; self.rows=[]; self.row_by_path={}; self.analysis_pages={}; self.original_sources={}; self.generated_files=set(); self.preview_cache=OrderedDict()
        self.preview_img=None; self.zoom=1.0; self.preview_min_zoom=1.0; self.preview_resize_job=None; self.analysis_options=None
        self.filter_status=tk.StringVar(value='Todos'); self.analysis_running=False; self.session_save_job=None
        self.analysis_output_format='PDF'; self.analysis_events=queue.Queue(); self.analysis_ui_poll_job=None
        self.preview_request=0; self.close_warning_shown=False
        self.mouse_select_anchor=None; self.mouse_select_base=set(); self.mouse_dragged=False
        self.preview_select_job=None
        self.cancel_event=threading.Event(); self.analysis_cancelled=False; self.analysis_discard=False; self.analysis_completed=0
        self.analysis_snapshot=None; self.last_session_checkpoint=0
        self.session_persistence_disabled=False
        self.preview_path=None; self.preview_page=0; self.preview_total_pages=0
        self.include_chapa=tk.BooleanVar(value=True)
        self.include_nome=tk.BooleanVar(value=True)
        self.include_mes=tk.BooleanVar(value=True)
        self.status=tk.StringVar(value='Comece selecionando documentos, imagens ou uma pasta.')
        self.summary=tk.StringVar(value='0 arquivos  |  0 prontos  |  0 para revisar  |  0 bloqueados'); self.output_format=tk.StringVar(value='PDF')

        self.setup_styles()

        shell=ttk.Frame(self,style='App.TFrame',padding=(22,18,22,16))
        shell.pack(fill='both',expand=True)

        # Fluxo em tres etapas. Os botoes ficam perto do momento em que sao usados.
        workflow=ttk.Frame(shell,style='App.TFrame')
        workflow.pack(fill='x',pady=(0,14))
        for column in range(3): workflow.columnconfigure(column,weight=1,uniform='steps')

        step1=ttk.LabelFrame(workflow,text=' 1. ADICIONAR ARQUIVOS ',style='Card.TLabelframe',padding=12)
        step1.grid(row=0,column=0,sticky='nsew',padx=(0,6))
        ttk.Label(step1,text='Escolha PDFs ou imagens, individualmente ou em pasta.',style='CardText.TLabel').pack(anchor='w',pady=(0,9))
        row=ttk.Frame(step1,style='Card.TFrame'); row.pack(fill='x')
        self.select_files_btn=ttk.Button(row,text='Adicionar arquivos',style='Secondary.TButton',command=self.select_files); self.select_files_btn.pack(side='left',fill='x',expand=True,padx=(0,4))
        self.select_folder_btn=ttk.Button(row,text='Selecionar pasta',style='Secondary.TButton',command=self.select_folder); self.select_folder_btn.pack(side='left',fill='x',expand=True,padx=(4,0))

        step2=ttk.LabelFrame(workflow,text=' 2. ANALISAR E REVISAR ',style='Card.TLabelframe',padding=12)
        step2.grid(row=0,column=1,sticky='nsew',padx=6)
        ttk.Label(step2,text='Detecte matrícula, nome e mês. Revise os avisos.',style='CardText.TLabel').pack(anchor='w',pady=(0,9))
        self.analyze_btn=ttk.Button(step2,text='Iniciar análise',style='Primary.TButton',command=self.start)
        self.analyze_btn.pack(fill='x')
        self.verify_selected_btn=ttk.Button(step2,text='Verificar selecionados',style='Secondary.TButton',
                                            command=lambda:self.start(selected_only=True),state='disabled')
        self.verify_selected_btn.pack(fill='x',pady=(6,0))

        step3=ttk.LabelFrame(workflow,text=' 3. APROVAR E EXPORTAR ',style='Card.TLabelframe',padding=12)
        step3.grid(row=0,column=2,sticky='nsew',padx=(6,0))
        ttk.Label(step3,text='Revise os avisos e exporte os arquivos do lote.',style='CardText.TLabel').pack(anchor='w',pady=(0,9))
        row=ttk.Frame(step3,style='Card.TFrame'); row.pack(fill='x')
        self.approve_btn=ttk.Button(row,text='Aprovar como folha',style='Secondary.TButton',command=self.approve_selected)
        self.approve_btn.pack(side='left',fill='x',expand=True,padx=(0,3))
        self.approve_atestado_btn=ttk.Button(row,text='Como atestado',style='Secondary.TButton',command=lambda:self.approve_as_category('Atestados'))
        self.approve_atestado_btn.pack(side='left',fill='x',expand=True,padx=3)
        self.approve_declaracao_btn=ttk.Button(row,text='Como declaração',style='Secondary.TButton',command=lambda:self.approve_as_category('Declarações'))
        self.approve_declaracao_btn.pack(side='left',fill='x',expand=True,padx=(3,0))
        self.export_btn=ttk.Button(step3,text='Exportar arquivos',style='Success.TButton',command=self.export)
        self.export_btn.pack(fill='x',pady=(8,0))
        format_line=ttk.Frame(step3,style='Card.TFrame'); format_line.pack(fill='x',pady=(8,0))
        ttk.Label(format_line,text='Salvar como:',style='CardText.TLabel').pack(side='left')
        self.output_format_combo=ttk.Combobox(format_line,textvariable=self.output_format,state='readonly',width=8,values=OUTPUT_FORMATS)
        self.output_format_combo.pack(side='right')
        self.output_format_combo.bind('<<ComboboxSelected>>',self.on_output_format_changed)
        self.correct_btn=ttk.Button(step3,text='Editar dados do arquivo',style='Secondary.TButton',command=self.correct_selected)
        self.correct_btn.pack(fill='x',pady=(8,0))

        # Opcoes de nome em uma unica faixa, sem competir visualmente com as etapas.
        naming=ttk.Frame(shell,style='Toolbar.TFrame',padding=(12,9))
        naming.pack(fill='x',pady=(0,12))
        ttk.Label(naming,text='Nome final:',style='ToolbarTitle.TLabel').pack(side='left',padx=(0,12))
        self.chapa_check=ttk.Checkbutton(naming,text='Matrícula/Chapa',variable=self.include_chapa,command=self.refresh_names); self.chapa_check.pack(side='left',padx=5)
        self.nome_check=ttk.Checkbutton(naming,text='Nome',variable=self.include_nome,command=self.refresh_names); self.nome_check.pack(side='left',padx=5)
        self.mes_check=ttk.Checkbutton(naming,text='Mês da folha',variable=self.include_mes,command=self.refresh_names); self.mes_check.pack(side='left',padx=5)
        ttk.Label(naming,text='Ordem: Matrícula - Nome - Mês',style='ToolbarHint.TLabel').pack(side='right')

        body=ttk.Panedwindow(shell,orient='horizontal')
        body.pack(fill='both',expand=True)
        left=ttk.Frame(body,style='Card.TFrame',padding=12)
        right=ttk.Frame(body,style='Card.TFrame',padding=12,width=390)
        body.add(left,weight=4); body.add(right,weight=2)

        list_head=ttk.Frame(left,style='Card.TFrame'); list_head.pack(fill='x',pady=(0,8))
        ttk.Label(list_head,text='Arquivos do lote',style='Section.TLabel').pack(side='left')
        ttk.Label(list_head,textvariable=self.summary,style='Counter.TLabel').pack(side='right')
        self.filter_combo=ttk.Combobox(list_head,textvariable=self.filter_status,state='readonly',width=14,values=('Todos','Prontos','Revisar','Bloqueados'))
        self.filter_combo.pack(side='right',padx=(0,12)); self.filter_combo.bind('<<ComboboxSelected>>',self.apply_filter)

        table=ttk.Frame(left,style='Card.TFrame'); table.pack(fill='both',expand=True)
        cols=('original','novo','metodo','confianca','status')
        self.tree=ttk.Treeview(table,columns=cols,show='headings',selectmode='extended',style='Files.Treeview')
        headings={'original':'Arquivo original','novo':'Novo nome','metodo':'Leitura','confianca':'Confiança','status':'Status'}
        widths={'original':210,'novo':410,'metodo':75,'confianca':85,'status':95}
        for c in cols:
            self.tree.heading(c,text=headings[c]); self.tree.column(c,width=widths[c],anchor='w',stretch=c in ('original','novo'))
        yscroll=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview)
        xscroll=ttk.Scrollbar(table,orient='horizontal',command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set,xscrollcommand=xscroll.set)
        self.tree.grid(row=0,column=0,sticky='nsew'); yscroll.grid(row=0,column=1,sticky='ns'); xscroll.grid(row=1,column=0,sticky='ew')
        table.rowconfigure(0,weight=1); table.columnconfigure(0,weight=1)
        self.tree.tag_configure('ok',foreground='#176b3a')
        self.tree.tag_configure('review',foreground='#7a4300',background='#fff1cc')
        self.tree.tag_configure('error',foreground='#8f1713',background='#ffd9d6')
        self.tree.tag_configure('approved',foreground='#075985')
        self.tree.bind('<<TreeviewSelect>>',self.schedule_show_selected)
        self.tree.bind('<Double-1>',self.correct_selected)
        self.tree.bind('<Return>',self.correct_selected)
        self.tree.bind('<F2>',self.correct_selected)
        self.tree.bind('<Button-1>',self.mouse_select_start,add='+')
        self.tree.bind('<B1-Motion>',self.mouse_select_drag,add='+')
        self.tree.bind('<ButtonRelease-1>',self.mouse_select_end,add='+')
        self.tree.bind('<Button-3>',self.show_context_menu)
        self.tree.bind('<Delete>',self.remove_selected)
        self.tree.bind('<Control-a>',self.select_all_visible)
        self.tree.bind('<Control-A>',self.select_all_visible)
        self.create_context_menu()

        ttk.Label(left,text='Dica: arraste o mouse pelas linhas para selecionar vários arquivos. Ctrl adiciona ou remove da seleção.',style='Hint.TLabel').pack(anchor='w',pady=(8,0))

        preview_top=ttk.Frame(right,style='Card.TFrame'); preview_top.pack(fill='x',pady=(0,8))
        ttk.Label(preview_top,text='Prévia da página inteira',style='Section.TLabel').pack(side='left')
        ttk.Button(preview_top,text='Ajustar',style='Small.TButton',command=self.fit_preview).pack(side='right')
        ttk.Button(preview_top,text='+',width=3,style='Small.TButton',command=lambda:self.change_zoom(1.25)).pack(side='right',padx=4)
        ttk.Button(preview_top,text='-',width=3,style='Small.TButton',command=lambda:self.change_zoom(0.8)).pack(side='right')
        self.zoom_label=ttk.Label(preview_top,text='100%',style='Hint.TLabel'); self.zoom_label.pack(side='right',padx=8)
        preview_nav=ttk.Frame(right,style='Card.TFrame'); preview_nav.pack(fill='x',pady=(0,8))
        self.prev_page_btn=ttk.Button(preview_nav,text='Página anterior',style='Small.TButton',command=lambda:self.change_page(-1),state='disabled')
        self.prev_page_btn.pack(side='left')
        self.page_label=ttk.Label(preview_nav,text='Página 0 de 0',style='Hint.TLabel'); self.page_label.pack(side='left',expand=True)
        self.next_page_btn=ttk.Button(preview_nav,text='Próxima página',style='Small.TButton',command=lambda:self.change_page(1),state='disabled')
        self.next_page_btn.pack(side='right')

        preview_box=ttk.Frame(right,style='Card.TFrame'); preview_box.pack(fill='both',expand=True)
        self.preview=tk.Canvas(preview_box,bg='#e8efef',highlightthickness=1,highlightbackground='#c7d7d6')
        self.preview_xbar=ttk.Scrollbar(preview_box,orient='horizontal',command=self.preview.xview)
        self.preview_ybar=ttk.Scrollbar(preview_box,orient='vertical',command=self.preview.yview)
        self.preview.configure(xscrollcommand=self.preview_xbar.set,yscrollcommand=self.preview_ybar.set)
        self.preview.grid(row=0,column=0,sticky='nsew')
        self.preview.bind('<Configure>',self.schedule_preview_refit)
        preview_box.rowconfigure(0,weight=1); preview_box.columnconfigure(0,weight=1)


        self.preview.bind('<MouseWheel>',self.preview_mousewheel)
        self.preview.bind('<Shift-MouseWheel>',self.preview_shift_mousewheel)
        self.preview.bind('<Control-MouseWheel>',self.preview_ctrl_mousewheel)
        self.preview.bind('<ButtonPress-2>',self.preview_pan_start)
        self.preview.bind('<B2-Motion>',self.preview_pan_move)
        self.preview.bind('<ButtonRelease-2>',lambda e:self.preview.config(cursor=''))
        self.bind_all('<Control-plus>',self.zoom_in_key); self.bind_all('<Control-equal>',self.zoom_in_key)
        self.bind_all('<Control-KP_Add>',self.zoom_in_key); self.bind_all('<Control-minus>',self.zoom_out_key)
        self.bind_all('<Control-KP_Subtract>',self.zoom_out_key)

        footer=ttk.Frame(shell,style='Status.TFrame',padding=(10,7)); footer.pack(fill='x',pady=(12,0))
        ttk.Label(footer,textvariable=self.status,style='Status.TLabel').pack(side='left',fill='x',expand=True)
        ttk.Label(footer,text='v'+APP_VERSION,style='FooterVersion.TLabel').pack(side='right',padx=(10,2))
        self.progress=ttk.Progressbar(footer,length=210,mode='determinate'); self.progress.pack(side='right',padx=(12,0))
        self.cancel_analysis_btn=ttk.Button(footer,text='Cancelar análise',style='Secondary.TButton',command=self.request_cancel_analysis,state='disabled')
        self.cancel_analysis_btn.pack(side='right')
        self.setup_drag_drop()
        self.protocol('WM_DELETE_WINDOW',self.on_close)
        self.after(350,self.offer_restore_session)
    def on_output_format_changed(self,event=None):
        value=self.output_format.get().upper()
        if value not in OUTPUT_FORMATS:self.output_format.set('PDF')
        self.status.set(f'Formato de exportação: {self.output_format.get()}.')
        self.refresh_names()
        self.schedule_session_save()

    def center_dialog(self, dialog):
        """Center a child window over the visible area of the main application."""
        dialog.update_idletasks()
        width=max(dialog.winfo_reqwidth(),dialog.winfo_width())
        height=max(dialog.winfo_reqheight(),dialog.winfo_height())
        try:
            left=self.winfo_rootx()+max(0,(self.winfo_width()-width)//2)
            top=self.winfo_rooty()+max(0,(self.winfo_height()-height)//2)
            user32=ctypes.windll.user32
            virtual_left=user32.GetSystemMetrics(76)
            virtual_top=user32.GetSystemMetrics(77)
            virtual_width=user32.GetSystemMetrics(78)
            virtual_height=user32.GetSystemMetrics(79)
            if virtual_width<=0 or virtual_height<=0:raise OSError('Dimensões inválidas da área de trabalho virtual.')
        except tk.TclError:
            left=max(0,(dialog.winfo_screenwidth()-width)//2)
            top=max(0,(dialog.winfo_screenheight()-height)//2)
            virtual_left=0; virtual_top=0
            virtual_width=dialog.winfo_screenwidth(); virtual_height=dialog.winfo_screenheight()
        except (AttributeError,OSError):
            virtual_left=self.winfo_vrootx(); virtual_top=self.winfo_vrooty()
            virtual_width=self.winfo_vrootwidth(); virtual_height=self.winfo_vrootheight()
            if virtual_width<=0 or virtual_height<=0:
                virtual_left=0; virtual_top=0
                virtual_width=dialog.winfo_screenwidth(); virtual_height=dialog.winfo_screenheight()
        left=max(virtual_left,min(left,virtual_left+virtual_width-width))
        top=max(virtual_top,min(top,virtual_top+virtual_height-height))
        dialog.geometry(f'+{left}+{top}')

    def setup_drag_drop(self):
        if not DND_AVAILABLE:
            self.status.set('Pronto. Dica: instale tkinterdnd2 para arrastar e soltar arquivos.')
            return
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>',self.handle_drop)

    def handle_drop(self,event):
        if self.analysis_running:return
        paths=[Path(x) for x in self.tk.splitlist(event.data)]
        pdfs=[]
        for path in paths:
            if path.is_dir(): pdfs.extend(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in INPUT_EXTENSIONS)
            elif path.suffix.lower() in INPUT_EXTENSIONS: pdfs.append(path)
        if pdfs:self.add_files(self.prepare_input_paths(pdfs))
        else:messagebox.showwarning('Arrastar e soltar','Nenhum arquivo compatível foi encontrado.',parent=self)

    def multipage_dialog(self,path,total):
        result=tk.StringVar(value='ignore'); page_var=tk.IntVar(value=1)
        dialog=tk.Toplevel(self); dialog.title('PDF com várias páginas'); dialog.transient(self); dialog.grab_set(); dialog.resizable(False,False)
        box=ttk.Frame(dialog,padding=18); box.pack(fill='both',expand=True)
        ttk.Label(box,text='PDF com várias páginas detectado',font=('Segoe UI',13,'bold')).pack(anchor='w')
        ttk.Label(box,text=f'{Path(path).name} possui {total} páginas.\nEscolha como o arquivo deve ser tratado.',justify='left',wraplength=520).pack(anchor='w',pady=(8,14))
        def choose(value):result.set(value)
        ttk.Button(box,text='Separar páginas e renomear todas',style='Primary.TButton',command=lambda:choose('split')).pack(fill='x',pady=3)
        keep=ttk.LabelFrame(box,text=' Manter o PDF completo ',padding=10); keep.pack(fill='x',pady=8)
        line=ttk.Frame(keep); line.pack(fill='x')
        ttk.Label(line,text='Página usada para identificar os dados:').pack(side='left')
        spin=ttk.Spinbox(line,from_=1,to=total,textvariable=page_var,width=7); spin.pack(side='left',padx=8)
        ttk.Button(keep,text='Manter completo',style='Secondary.TButton',command=lambda:choose('keep')).pack(fill='x',pady=(8,0))
        ttk.Button(box,text='Ignorar este arquivo',command=lambda:choose('ignore')).pack(fill='x',pady=(3,0))
        dialog.protocol('WM_DELETE_WINDOW',lambda:choose('ignore')); dialog.bind('<Escape>',lambda _e:choose('ignore'))
        dialog.wait_visibility(); self.center_dialog(dialog); dialog.focus_force(); dialog.wait_variable(result)
        choice=result.get()
        try:page=max(1,min(total,int(page_var.get())))
        except (ValueError,tk.TclError):page=1
        dialog.destroy(); return choice,page-1

    def split_pdf_pages(self,path):
        created=[]; source=Path(path); token=f'{safe_filename(source.stem)[:40]}_{hashlib.sha1(str(source.resolve()).encode("utf-8")).hexdigest()[:10]}'
        with fitz.open(path) as doc:
            for index in range(len(doc)):
                target=SPLIT_DIR/f'{token}_pagina_{index+1:03d}.pdf'
                target.unlink(missing_ok=True)
                part=fitz.open(); part.insert_pdf(doc,from_page=index,to_page=index); part.save(target); part.close()
                created.append(str(target))
        self.generated_files.update(created); return created

    def image_to_pdf(self,path):
        source=Path(path); digest=hashlib.sha1(str(source.resolve()).encode('utf-8')).hexdigest()[:10]
        target=CONVERT_DIR/f'{safe_filename(source.stem)[:40]}_{digest}.pdf'; target.unlink(missing_ok=True)
        with Image.open(source) as image:
            frames=[]
            count=getattr(image,'n_frames',1)
            for index in range(count):
                image.seek(index); frame=image.convert('RGB')
                rgb=np.array(frame)
                corrected,changed=rectify_document_photo(rgb)
                frames.append(Image.fromarray(corrected).copy() if changed else frame.copy())
            if not frames:raise RuntimeError('Imagem sem quadros válidos.')
            frames[0].save(target,'PDF',save_all=True,append_images=frames[1:],resolution=200.0)
        self.generated_files.add(str(target)); return str(target)

    def normalize_input_file(self,path):
        validate_input_content(path)
        suffix=Path(path).suffix.lower()
        if suffix=='.pdf':
            result=str(Path(path)); self.original_sources[result]=str(Path(path)); return result
        if suffix in INPUT_EXTENSIONS:
            result=self.image_to_pdf(path); self.original_sources[result]=str(Path(path)); return result
        return None

    @staticmethod
    def input_page_count(path):
        path=Path(path)
        if path.suffix.lower()=='.pdf':
            with fitz.open(path) as document:return max(1,len(document))
        return 1
    def current_batch_source_paths(self):
        return list(dict.fromkeys(self.original_sources.get(path,path) for path in self.files))
    def validate_batch_limits(self,paths):
        incoming=[]; seen={str(Path(path).resolve()).casefold() for path in self.current_batch_source_paths() if Path(path).exists()}
        oversized=[]; large=[]; total_pages=0
        for current in self.current_batch_source_paths():
            try:total_pages+=self.input_page_count(current)
            except Exception as exc:
                LOGGER.warning('Falha ao contar páginas do lote atual %s: %s',current,exc)
        for raw in paths:
            path=Path(raw)
            if not path.is_file():continue
            key=str(path.resolve()).casefold()
            if key in seen:continue
            seen.add(key); incoming.append(str(path))
            size_mb=path.stat().st_size/(1024*1024)
            if size_mb>MAX_FILE_SIZE_MB:oversized.append((path.name,size_mb))
            elif size_mb>LARGE_FILE_WARNING_MB:large.append((path.name,size_mb))
        final_file_count=len(self.current_batch_source_paths())+len(incoming)
        if final_file_count>MAX_BATCH_FILES:
            messagebox.showerror('Limite do lote',f'O lote ficaria com {final_file_count} arquivos. O limite é de {MAX_BATCH_FILES}.\nDivida o conteúdo em dois ou mais lotes.',parent=self); return []
        if oversized:
            names='\n'.join(f'- {name} ({size:.1f} MB)' for name,size in oversized[:8])
            messagebox.showerror('Arquivo acima do limite',f'O limite por arquivo é de {MAX_FILE_SIZE_MB} MB.\n\n{names}',parent=self); return []
        for path in incoming:
            try:total_pages+=self.input_page_count(path)
            except Exception as exc:
                messagebox.showerror('Arquivo inválido',f'Não foi possível verificar a quantidade de páginas de {Path(path).name}:\n{exc}',parent=self); return []
            if total_pages>MAX_BATCH_PAGES:
                messagebox.showerror('Limite de páginas',f'O lote ficaria com mais de {MAX_BATCH_PAGES} páginas.\nDivida o conteúdo em lotes menores.',parent=self); return []
        if large:
            names='\n'.join(f'- {name} ({size:.1f} MB)' for name,size in large[:8])
            if not messagebox.askyesno('Arquivos grandes',f'{len(large)} arquivo(s) possuem mais de {LARGE_FILE_WARNING_MB} MB.\nO processamento poderá demorar mais.\n\n{names}\n\nDeseja continuar?',parent=self):return []
        return incoming
    def prepare_input_paths(self,paths):
        candidates=self.validate_batch_limits(paths)
        if not candidates:return []
        prepared=[]
        for raw in candidates:
            original=str(Path(raw))
            if Path(original).suffix.lower() not in INPUT_EXTENSIONS or not Path(original).is_file():continue
            try:path=self.normalize_input_file(original)
            except Exception as exc:
                messagebox.showerror('Arquivo inválido',f'{Path(original).name} foi rejeitado:\n{exc}',parent=self); continue
            try:
                with fitz.open(path) as doc:total=len(doc)
            except Exception as exc:
                LOGGER.warning('Arquivo inválido %s: %s',path,exc)
                messagebox.showerror('Arquivo inválido',f'Não foi possível abrir {Path(original).name}:\nO conteúdo do arquivo não corresponde a um documento suportado.',parent=self)
                continue
            if total<=1:
                prepared.append(path); self.analysis_pages[path]=0; continue
            choice,page=self.multipage_dialog(path,total)
            if choice=='split':
                try:
                    pages=self.split_pdf_pages(path); prepared.extend(pages)
                    original_source=self.original_sources.get(path,path)
                    for item in pages:
                        self.analysis_pages[item]=0; self.original_sources[item]=original_source
                except Exception as exc:messagebox.showerror('Separar PDF',f'Não foi possível separar {Path(path).name}:\n{exc}',parent=self)
            elif choice=='keep':prepared.append(path); self.analysis_pages[path]=page
        return prepared

    def add_files(self,paths):
        incoming=[str(Path(p)) for p in paths if str(p).lower().endswith('.pdf')]
        merged=sorted(set(self.files).union(incoming))
        added=len(merged)-len(self.files)
        if not added:
            self.status.set('Os arquivos arrastados já estão no lote.')
            return
        previous={path:dict(row) for path,row in self.row_by_path.items()}
        self.load(merged,save=False)
        for path,row in previous.items():
            if path in self.files:
                self.rows.append(row); self.row_by_path[path]=row; self.set_row_values(row,save=False)
        self.status.set(f'{added} arquivo(s) adicionado(s). Total: {len(self.files)}.')
        self.schedule_session_save()

    @staticmethod
    def is_managed_generated_file(path):
        try:
            resolved=Path(path).resolve()
            return resolved.is_relative_to(SPLIT_DIR.resolve()) or resolved.is_relative_to(CONVERT_DIR.resolve())
        except (OSError,ValueError):
            return False

    def cleanup_generated_files(self,paths=None):
        targets=set(paths if paths is not None else self.generated_files)
        for path in targets:
            if not self.is_managed_generated_file(path):continue
            try:Path(path).unlink(missing_ok=True)
            except OSError:LOGGER.warning('Não foi possível remover temporário %s',path,exc_info=True)
            self.generated_files.discard(str(path))

    def on_close(self):
        if self.analysis_running:
            if not self.close_warning_shown:
                self.close_warning_shown=True
                messagebox.showwarning('Análise em andamento','Use Cancelar análise e aguarde a finalização segura antes de fechar o aplicativo.',parent=self)
                self.after(1500,lambda:setattr(self,'close_warning_shown',False))
            return
        try:
            if self.preview_select_job:
                self.after_cancel(self.preview_select_job); self.preview_select_job=None
            if self.preview_resize_job:
                self.after_cancel(self.preview_resize_job); self.preview_resize_job=None
            if self.files and not self.session_persistence_disabled:
                if self.session_save_job:
                    self.after_cancel(self.session_save_job); self.session_save_job=None
                self.save_session()
        finally:
            if self.session_persistence_disabled:
                self.cleanup_generated_files()
            self.preview_cache.clear()
            self.destroy()

    def mouse_select_start(self,event):
        if self.tree.identify_region(event.x,event.y) not in ('cell','tree'):
            self.mouse_select_anchor=None; return
        iid=self.tree.identify_row(event.y)
        if not iid:return
        self.mouse_select_anchor=iid
        self.mouse_select_base=set(self.tree.selection()) if event.state & 0x0004 else set()
        self.mouse_dragged=False

    def mouse_select_drag(self,event):
        if not self.mouse_select_anchor:return
        target=self.tree.identify_row(event.y)
        if not target:
            # Rolagem automatica ao arrastar acima ou abaixo da area visivel.
            if event.y<0:self.tree.yview_scroll(-1,'units')
            elif event.y>self.tree.winfo_height():self.tree.yview_scroll(1,'units')
            target=self.tree.identify_row(max(1,min(event.y,self.tree.winfo_height()-2)))
        if not target:return
        visible=list(self.tree.get_children())
        try:start=visible.index(self.mouse_select_anchor); end=visible.index(target)
        except ValueError:return
        low,high=sorted((start,end)); ranged=set(visible[low:high+1])
        selection=self.mouse_select_base.symmetric_difference(ranged) if event.state & 0x0004 else ranged
        self.tree.selection_set(tuple(selection)); self.tree.focus(target); self.tree.see(target)
        self.mouse_dragged=True
        return 'break'

    def mouse_select_end(self,event):
        self.mouse_select_anchor=None; self.mouse_select_base=set()
        if self.mouse_dragged:
            self.status.set(f'{len(self.tree.selection())} arquivo(s) selecionado(s).')
        self.mouse_dragged=False

    def select_all_visible(self,event=None):
        self.tree.selection_set(self.tree.get_children())
        return 'break'

    def apply_filter(self,event=None):
        wanted=self.filter_status.get(); selected=set(self.tree.selection())
        for position,iid in enumerate(self.files):
            if self.tree.exists(iid):self.tree.reattach(iid,'',position)
        visible=[]
        for iid in self.files:
            if not self.tree.exists(iid):continue
            status=(self.tree.set(iid,'status') or '').strip().upper()
            show=(wanted=='Todos' or wanted=='Prontos' and status in {'OK','APROVADO','CORRIGIDO'} or wanted=='Revisar' and status=='REVISAR' or wanted=='Bloqueados' and self.is_blocking_status(status))
            if show:visible.append(iid)
            else:self.tree.detach(iid)
        kept=[iid for iid in selected if iid in visible]
        if kept:self.tree.selection_set(kept)
        else:
            self.tree.selection_remove(self.tree.selection())
            if self.preview_path and self.preview_path not in visible:
                self.clear_preview()
        self.update_verify_selected_button()
        self.status.set(f'Filtro {wanted}: {len(visible)} de {len(self.files)} arquivo(s) exibido(s).')

    def session_data(self):
        rows=[]
        for path in self.files:
            row=dict(self.row_by_path.get(path,{"path":path,"status":self.tree.set(path,'status') if self.tree.exists(path) else 'Pendente'}))
            row.pop('header',None); rows.append(row)
        return {'version':2,'files':self.files,'rows':rows,'analysis_pages':self.analysis_pages,'generated_files':list(self.generated_files),'original_sources':self.original_sources,
                'options':list(self.current_options()),'filter':self.filter_status.get(),'output_format':self.output_format.get()}

    def schedule_session_save(self):
        if self.session_persistence_disabled:return
        if self.session_save_job:self.after_cancel(self.session_save_job)
        self.session_save_job=self.after(400,self.save_session)

    def save_session(self):
        self.session_save_job=None
        if self.session_persistence_disabled:return
        try:
            temp=SESSION_FILE.with_suffix('.tmp')
            temp.write_text(json.dumps(self.session_data(),ensure_ascii=False,indent=2),encoding='utf-8')
            temp.replace(SESSION_FILE)
        except Exception: LOGGER.exception('Falha ao salvar sessão')

    def offer_restore_session(self):
        if not SESSION_FILE.exists() or self.files:return
        try:
            data=json.loads(SESSION_FILE.read_text(encoding='utf-8'))
            existing=[p for p in data.get('files',[]) if Path(p).is_file()]
            if not existing:return
            if messagebox.askyesno('Recuperar sessão',f'Foi encontrada uma sessão com {len(existing)} arquivo(s). Deseja continuar?',parent=self):
                self.restore_session(data,existing)
            else:
                SESSION_FILE.unlink(missing_ok=True)
        except Exception:
            LOGGER.exception('Falha ao recuperar sessão')
            SESSION_FILE.unlink(missing_ok=True)
            messagebox.showwarning('Sessão descartada','A sessão anterior estava danificada e foi descartada.',parent=self)

    def restore_session(self,data,existing):
        self.session_persistence_disabled=False
        opts=data.get('options',[True,True,True])
        self.include_chapa.set(bool(opts[0])); self.include_nome.set(bool(opts[1])); self.include_mes.set(bool(opts[2]))
        self.analysis_pages={str(k):int(v) for k,v in data.get('analysis_pages',{}).items() if str(k) in existing}
        self.generated_files={p for p in data.get('generated_files',[]) if Path(p).is_file()}
        self.original_sources={str(k):str(v) for k,v in data.get('original_sources',{}).items()}
        self.load(existing,save=False)
        saved={r.get('path'):r for r in data.get('rows',[])}
        for path in existing:
            row=saved.get(path)
            if not row:continue
            row.setdefault('path',path); row.setdefault('chapa_source','desconhecida'); row.setdefault('new',''); row.setdefault('method',''); row.setdefault('conf',0); row.setdefault('status','Pendente'); row.setdefault('manual_name',False)
            if row.get('chapa_source')=='desconhecida' and row.get('status')=='OK':row['status']='REVISAR'
            self.rows.append(row); self.row_by_path[path]=row; self.set_row_values(row,save=False)
        self.filter_status.set(data.get('filter','Todos')); self.output_format.set(data.get('output_format','PDF')); self.apply_filter()
        self.status.set(f'Sessão recuperada: {len(existing)} arquivo(s).')

    def create_context_menu(self):
        self.context_menu=tk.Menu(self,tearoff=False)
        self.context_menu.add_command(label='Abrir arquivo original',command=self.open_selected_pdf)
        self.context_menu.add_command(label='Abrir pasta do arquivo',command=self.open_selected_folder)
        self.context_menu.add_command(label='Copiar como caminho',command=self.copy_selected_path)
        self.context_menu.add_command(label='Propriedades',command=self.show_selected_properties)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='Verificar arquivo selecionado',command=lambda:self.start(selected_only=True))
        self.context_menu.add_command(label='Editar nome e dados',command=self.correct_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='Aprovar como folha de ponto',command=self.approve_selected)
        self.context_menu.add_command(label='Aprovar como atestado',command=lambda:self.approve_as_category('Atestados'))
        self.context_menu.add_command(label='Aprovar como declaração',command=lambda:self.approve_as_category('Declarações'))
        self.context_menu.add_command(label='Marcar para revisar',command=self.mark_selected_for_review)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='Copiar novo nome',command=self.copy_selected_new_name)
        self.context_menu.add_command(label='Remover do lote',command=self.remove_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label='Limpar dados da sessão',command=self.clear_session_data)

    def show_context_menu(self,event):
        iid=self.tree.identify_row(event.y)
        if not iid:return
        selected=set(self.tree.selection())
        if iid not in selected:
            self.tree.selection_set(iid)
        self.tree.focus(iid)
        count=len(self.tree.selection())
        locked=self.analysis_running
        single='normal' if count==1 and not locked else 'disabled'
        self.context_menu.entryconfig('Editar nome e dados',state=single)
        self.context_menu.entryconfig('Abrir arquivo original',state=single)
        self.context_menu.entryconfig('Abrir pasta do arquivo',state=single)
        self.context_menu.entryconfig('Copiar como caminho',state=single)
        self.context_menu.entryconfig('Propriedades',state=single)
        self.context_menu.entryconfig('Verificar arquivo selecionado',state=single)
        self.context_menu.entryconfig('Copiar novo nome',state=single)
        batch='disabled' if locked else 'normal'
        self.context_menu.entryconfig('Aprovar como folha de ponto',state=batch)
        self.context_menu.entryconfig('Aprovar como atestado',state=batch)
        self.context_menu.entryconfig('Aprovar como declaração',state=batch)
        self.context_menu.entryconfig('Marcar para revisar',state=batch)
        self.context_menu.entryconfig('Remover do lote',state=batch)
        try:self.context_menu.tk_popup(event.x_root,event.y_root)
        finally:self.context_menu.grab_release()

    def update_verify_selected_button(self):
        if not hasattr(self,'verify_selected_btn'):return
        state='normal' if self.tree.selection() and not self.analysis_running else 'disabled'
        self.verify_selected_btn.config(state=state)

    def show_selected_properties(self):
        path=self.selected_single_path()
        if not path:return
        original=Path(self.original_sources.get(path,path))
        try:
            stat=original.stat()
            details=[
                f'Nome: {original.name}',
                f'Local: {original.parent}',
                f'Tipo: {original.suffix[1:].upper() or "Desconhecido"}',
                f'Tamanho: {stat.st_size/1024:.1f} KB',
                f'Modificado: {datetime.fromtimestamp(stat.st_mtime).astimezone().strftime("%d/%m/%Y %H:%M:%S")}',
            ]
            if original.suffix.lower()=='.pdf':
                with fitz.open(original) as document:
                    details.append(f'Páginas: {len(document)}')
            messagebox.showinfo('Propriedades do arquivo','\n'.join(details),parent=self)
        except (OSError,fitz.FileDataError,RuntimeError) as exc:
            messagebox.showerror('Propriedades do arquivo',f'Não foi possível ler as propriedades:\n{exc}',parent=self)

    def clear_session_data(self):
        if not messagebox.askyesno('Limpar sessão','Apagar os dados locais da sessão e remover o lote atual da tela? Os arquivos originais não serão alterados.',parent=self):return
        if self.session_save_job:
            self.after_cancel(self.session_save_job); self.session_save_job=None
        SESSION_FILE.unlink(missing_ok=True); SESSION_FILE.with_suffix('.tmp').unlink(missing_ok=True)
        self.cleanup_generated_files()
        self.files=[]; self.rows=[]; self.row_by_path={}; self.analysis_pages={}; self.original_sources={}
        self.generated_files.clear(); self.preview_cache.clear(); self.clear_preview()
        for item in self.tree.get_children():self.tree.delete(item)
        self.update_summary(); self.filter_status.set('Todos')
        self.session_persistence_disabled=True
        self.status.set('Dados locais da sessão e lote atual foram limpos. Os arquivos originais não foram alterados.')

    def clear_preview(self):
        if self.preview_resize_job:
            try:self.after_cancel(self.preview_resize_job)
            except tk.TclError:pass
            self.preview_resize_job=None
        self.preview_request+=1; self.preview_img=None; self.preview_path=None
        self.preview_page=0; self.preview_total_pages=0; self.preview_min_zoom=1.0; self.zoom=1.0
        self.preview.delete('all'); self.preview.configure(scrollregion=(0,0,0,0))
        self.preview_xbar.grid_remove(); self.preview_ybar.grid_remove()
        self.zoom_label.config(text='100%'); self.update_page_controls()

    def selected_single_path(self):
        selected=self.tree.selection()
        if len(selected)!=1:
            messagebox.showwarning('Seleção','Selecione exatamente um arquivo.',parent=self); return None
        return selected[0]

    def open_selected_pdf(self):
        path=self.selected_single_path()
        if not path:return
        try:
            original=self.original_sources.get(path,path)
            if not Path(original).is_file():raise FileNotFoundError(original)
            os.startfile(original)
        except Exception as exc:messagebox.showerror('Abrir arquivo',f'Não foi possível abrir o arquivo:\n{exc}',parent=self)

    def open_selected_folder(self):
        path=self.selected_single_path()
        if not path:return
        try:
            original=Path(self.original_sources.get(path,path))
            if sys.platform=='win32':os.startfile(str(original.parent))
            else:messagebox.showinfo('Pasta do arquivo',str(original.parent),parent=self)
        except Exception as exc:messagebox.showerror('Abrir pasta',f'Não foi possível abrir a pasta:\n{exc}',parent=self)

    def copy_text(self,text,description):
        self.clipboard_clear(); self.clipboard_append(text); self.update_idletasks()
        self.status.set(f'{description} copiado para a área de transferência.')

    def copy_selected_path(self):
        path=self.selected_single_path()
        if path:self.copy_text(self.original_sources.get(path,path),'Caminho original')

    def copy_selected_new_name(self):
        path=self.selected_single_path()
        if not path:return
        name=self.tree.set(path,'novo').strip()
        if not name:return messagebox.showwarning('Copiar novo nome','O arquivo ainda não possui um novo nome.',parent=self)
        self.copy_text(name,'Novo nome')

    def mark_selected_for_review(self):
        if self.analysis_running:return messagebox.showwarning('Análise em andamento','Aguarde a análise terminar.',parent=self)
        selected=self.tree.selection()
        if not selected:return messagebox.showwarning('Seleção','Selecione um ou mais arquivos.',parent=self)
        changed=0
        for path in selected:
            row=self.row_by_path.get(path)
            if not row or self.is_blocking_status(self.tree.set(path,'status')):continue
            row['status']='REVISAR'; self.tree.set(path,'status','REVISAR'); self.tree.item(path,tags=('review',)); changed+=1
        self.update_summary(); self.apply_filter(); self.schedule_session_save()
        self.status.set(f'{changed} arquivo(s) marcado(s) para revisão.')

    def remove_selected(self,event=None):
        if self.analysis_running:
            messagebox.showwarning('Análise em andamento','Não é possível remover arquivos durante a análise.',parent=self); return 'break'
        selected=list(self.tree.selection())
        if not selected:return 'break'
        if not messagebox.askyesno('Remover do lote',f'Remover {len(selected)} arquivo(s) do lote?\n\nOs arquivos originais não serão excluídos.',parent=self):return 'break'
        selected_set=set(selected)
        self.files=[path for path in self.files if path not in selected_set]
        self.rows=[row for row in self.rows if row.get('path') not in selected_set]
        self.cleanup_generated_files(selected)
        for path in selected:
            self.row_by_path.pop(path,None); self.analysis_pages.pop(path,None); self.original_sources.pop(path,None); self.generated_files.discard(path)
            if self.tree.exists(path):self.tree.delete(path)
            for key in list(self.preview_cache):
                if isinstance(key,tuple) and key[0]==path:self.preview_cache.pop(key,None)
        if self.preview_path in selected_set:
            self.preview_path=None; self.preview_img=None; self.preview_page=0; self.preview_total_pages=0
            self.preview.delete('all'); self.update_page_controls()
        self.update_summary(); self.apply_filter(); self.schedule_session_save()
        self.status.set(f'{len(selected)} arquivo(s) removido(s) do lote.')
        return 'break'

    def correct_selected(self,event=None):
        if self.analysis_running:
            messagebox.showwarning('Análise em andamento','Aguarde a análise terminar para editar os arquivos.',parent=self); return 'break'
        if event is not None and getattr(event,'num',None)==1:
            iid=self.tree.identify_row(event.y)
            region=self.tree.identify_region(event.x,event.y)
            if not iid or region not in ('cell','tree'):return 'break'
            self.tree.selection_set(iid); self.tree.focus(iid)
        selected=self.tree.selection()
        if len(selected)!=1:return messagebox.showwarning('Correção manual','Selecione exatamente um arquivo.',parent=self)
        iid=selected[0]; row=self.row_by_path.get(iid,{})
        dialog=tk.Toplevel(self); dialog.title('Corrigir dados'); dialog.transient(self); dialog.grab_set(); dialog.resizable(False,False)
        box=ttk.Frame(dialog,padding=16); box.pack(fill='both',expand=True)
        values=[]
        for index,(label,key) in enumerate((('Matrícula/Chapa','chapa'),('Nome','nome'),('Mês da folha','mes'))):
            ttk.Label(box,text=label+':').grid(row=index,column=0,sticky='w',pady=5,padx=(0,10))
            value=row.get(key) or ''
            if key=='mes':value=str(value).upper()
            var=tk.StringVar(value=value)
            if key=='mes':
                field=ttk.Combobox(box,textvariable=var,state='readonly',width=39,values=MONTH_OPTIONS)
            else:
                field=ttk.Entry(box,textvariable=var,width=42)
            field.grid(row=index,column=1,sticky='ew',pady=5); values.append((key,var))
        def save():
            data={key:safe_filename(var.get()) for key,var in values}
            target=self.row_by_path.get(iid)
            if target is None:
                target={'path':iid,'method':'Manual','conf':1.0,'manual_name':False}; self.rows.append(target); self.row_by_path[iid]=target
            target.update(data); target.update({'chapa_source':'manual','method':'Manual','conf':1.0,'status':'CORRIGIDO','manual_name':False})
            target['new']=self.compose_filename(target,self.current_options())
            self.set_row_values(target); dialog.destroy()
        actions=ttk.Frame(box); actions.grid(row=3,column=0,columnspan=2,sticky='e',pady=(12,0))
        ttk.Button(actions,text='Cancelar',command=dialog.destroy).pack(side='right')
        ttk.Button(actions,text='Salvar correção',style='Primary.TButton',command=save).pack(side='right',padx=(0,8))
        dialog.bind('<Escape>',lambda _e:dialog.destroy())
        dialog.bind('<Control-Return>',lambda _e:save())
        dialog.wait_visibility(); self.center_dialog(dialog); dialog.focus_force()
        return 'break'

    def setup_styles(self):
        style=ttk.Style(self)
        try:style.theme_use('clam')
        except tk.TclError:pass
        # Paleta visual: verde petroleo, superficies claras e estados semanticamente distintos.
        bg='#f3f7f7'; surface='#ffffff'; ink='#173136'; muted='#607478'; line='#d7e2e1'
        brand='#0f766e'; brand_hover='#0b5f58'; soft='#e8f5f2'; toolbar='#edf3f3'
        style.configure('App.TFrame',background=bg)
        style.configure('Card.TFrame',background=surface)
        style.configure('Toolbar.TFrame',background=toolbar)
        style.configure('Status.TFrame',background='#e5eeee')
        style.configure('CardText.TLabel',background=surface,foreground=muted,font=('Segoe UI',9))
        style.configure('Section.TLabel',background=surface,foreground=ink,font=('Segoe UI',12,'bold'))
        style.configure('Counter.TLabel',background=surface,foreground=brand,font=('Segoe UI',9,'bold'))
        style.configure('ToolbarTitle.TLabel',background=toolbar,foreground=ink,font=('Segoe UI',10,'bold'))
        style.configure('Hint.TLabel',background=surface,foreground='#728286',font=('Segoe UI',9))
        style.configure('ToolbarHint.TLabel',background=toolbar,foreground=muted,font=('Segoe UI',9))
        style.configure('Status.TLabel',background='#e5eeee',foreground='#36575b',font=('Segoe UI',9))
        style.configure('FooterVersion.TLabel',background='#e5eeee',foreground=brand,font=('Segoe UI',9,'bold'),padding=(7,4))
        style.configure('Footer.TButton',font=('Segoe UI',8,'bold'),padding=(8,4),background='#f7faf9',foreground=brand,bordercolor='#c9d7d5')
        style.map('Footer.TButton',background=[('active',soft),('pressed','#d7ece7')])
        style.configure('Card.TLabelframe',background=surface,bordercolor=line,relief='solid',borderwidth=1)
        style.configure('Card.TLabelframe.Label',background=surface,foreground=brand,font=('Segoe UI',9,'bold'))
        style.configure('Primary.TButton',font=('Segoe UI',10,'bold'),padding=(14,9),background=brand,foreground='#ffffff',borderwidth=0)
        style.map('Primary.TButton',background=[('active',brand_hover),('pressed','#084c47'),('disabled','#9ebfbb')])
        style.configure('Success.TButton',font=('Segoe UI',9,'bold'),padding=(11,8),background='#16845b',foreground='#ffffff',borderwidth=0)
        style.map('Success.TButton',background=[('active','#116a49'),('disabled','#a7cbbd')])
        style.configure('Secondary.TButton',font=('Segoe UI',9),padding=(11,8),background='#f7faf9',foreground=ink,bordercolor='#c9d7d5')
        style.map('Secondary.TButton',background=[('active',soft),('pressed','#d7ece7')],foreground=[('disabled','#8d9b9d')])
        style.configure('Small.TButton',font=('Segoe UI',9),padding=(7,5),background='#f7faf9',foreground=ink)
        style.configure('TCheckbutton',background=surface,foreground=ink,font=('Segoe UI',9))
        style.configure('TCombobox',padding=5,fieldbackground='#ffffff',background='#ffffff',bordercolor='#c9d7d5')
        style.configure('Horizontal.TProgressbar',troughcolor='#d8e7e4',background=brand,bordercolor='#d8e7e4',lightcolor=brand,darkcolor=brand)
        style.configure('Files.Treeview',font=('Segoe UI',9),rowheight=32,background=surface,fieldbackground=surface,foreground=ink,borderwidth=0)
        style.configure('Files.Treeview.Heading',font=('Segoe UI',9,'bold'),padding=(8,8),background='#dfeae8',foreground='#29494d',relief='flat')
        style.map('Files.Treeview.Heading',background=[('active','#d3e3e0')])
        style.map('Files.Treeview',background=[('selected','#cfe9e4')],foreground=[('selected','#12383a')])

    @staticmethod
    def status_tag(status):
        normalized=(status or '').strip().upper()
        if normalized in ('OK','CORRIGIDO'): return 'ok'
        if normalized=='APROVADO': return 'approved'
        if normalized in ('ERRO','FALHOU','NAO RECONHECIDO'): return 'error'
        return 'review'

    @staticmethod
    def is_blocking_status(status):
        return (status or '').strip().upper() in {'ERRO','FALHOU','NAO RECONHECIDO','PENDENTE'}

    def update_summary(self):
        total=len(self.files)
        ready=review=errors=0
        for iid in self.files:
            if not self.tree.exists(iid):continue
            status=self.tree.set(iid,'status')
            if status in {'OK','APROVADO','CORRIGIDO'}: ready+=1
            elif self.is_blocking_status(status): errors+=1
            elif status=='REVISAR': review+=1
        self.summary.set(f'{total} arquivos  |  {ready} prontos  |  {review} para revisar  |  {errors} bloqueados')

    def set_row_values(self,row,save=True):
        iid=row['path']; status=row.get('status','REVISAR')
        confidence='N/A' if row.get('category') else f"{confidence_percent(row.get('conf',0))}%"
        values=(self.original_display_name(iid),row.get('new',''),row.get('method',''),confidence,status)
        self.tree.item(iid,values=values,tags=(self.status_tag(status),))
        self.update_summary()
        self.apply_filter()
        if save:self.schedule_session_save()

    def load(self,paths,save=True):
        self.session_persistence_disabled=False
        self.files=sorted({str(Path(p)) for p in paths if str(p).lower().endswith('.pdf')}); self.rows=[]; self.row_by_path={}; self.original_sources={p:self.original_sources.get(p,p) for p in self.files}; self.analysis_pages={p:int(self.analysis_pages.get(p,0)) for p in self.files}; self.preview_cache.clear()
        self.clear_preview()
        if self.preview_select_job:
            self.after_cancel(self.preview_select_job); self.preview_select_job=None
        self.preview.delete('all'); self.zoom_label.config(text='100%'); self.update_page_controls()
        for i in self.tree.get_children(): self.tree.delete(i)
        for p in self.files: self.tree.insert('', 'end', iid=p, values=(self.original_display_name(p),'','','','Pendente'),tags=('review',))
        self.update_summary()
        self.filter_status.set('Todos'); self.status.set(f'{len(self.files)} arquivo(s) selecionado(s).')
        if save:self.schedule_session_save()
    def original_display_name(self,path):
        source=Path(self.original_sources.get(path,path))
        same_name=[]
        for internal in self.files:
            candidate=Path(self.original_sources.get(internal,internal))
            if candidate.name.casefold()==source.name.casefold():
                same_name.append(candidate)
        if len({str(item.resolve()).casefold() for item in same_name})>1:
            return f'{source.name}  [{source.parent.name}]'
        return source.name
    def selected_output_extension(self,output_format=None):
        fmt=(output_format or self.output_format.get()).upper()
        return 'jpg' if fmt in {'JPG','JPEG'} else fmt.lower() if fmt in OUTPUT_FORMATS else 'pdf'
    def filename_with_selected_extension(self,name,output_format=None):
        return str(Path(name).with_suffix('.'+self.selected_output_extension(output_format))) if name else ''
    def current_options(self):
        return (self.include_chapa.get(), self.include_nome.get(), self.include_mes.get())
    def compose_filename(self,row, options,output_format=None):
        include_chapa, include_nome, include_mes = options
        parts=[]
        if include_chapa and row.get('chapa'): parts.append(row['chapa'])
        if include_nome and row.get('nome'): parts.append(row['nome'])
        if include_mes and row.get('mes'): parts.append(row['mes'])
        if parts:
            base=safe_filename(' - '.join(parts))
        else:
            source=self.original_sources.get(row.get('path',''),row.get('path','arquivo'))
            base=safe_filename(Path(source).stem) or 'arquivo'
        return base+'.'+self.selected_output_extension(output_format)
    @staticmethod
    def fields_complete(row, options):
        include_chapa, include_nome, include_mes = options
        return ((not include_chapa or bool(row.get('chapa'))) and
                (not include_nome or bool(row.get('nome'))) and
                (not include_mes or bool(row.get('mes'))))
    def refresh_names(self):
        options=self.current_options()
        for row in self.rows:
            # Naming controls only change the output filename. They must never
            # change OCR confidence or the review state of classified documents.
            if row.get('category'):
                row['new']=self.filename_with_selected_extension(row.get('new',''))
                if row.get('status') not in ('APROVADO','CORRIGIDO') and row.get('method') not in ('Erro','Falhou'):
                    row['status']='OK'
            elif not row.get('manual_name'):
                row['new']=self.compose_filename(row, options)
                if row.get('method') not in ('Erro','Falhou') and row.get('status') not in ('APROVADO','CORRIGIDO'):
                    row['status']='OK' if row.get('chapa_source','documento')=='documento' and is_ready_confidence(row.get('conf',0)) and self.fields_complete(row,options) else 'REVISAR'
            if self.tree.exists(row['path']):
                values=list(self.tree.item(row['path'],'values'))
                if len(values)>=5:
                    values[1]=row['new']
                    values[3]='N/A' if row.get('category') else f"{confidence_percent(row.get('conf',0))}%"
                    values[4]=row['status']
                    self.tree.item(row['path'],values=values,tags=(self.status_tag(row['status']),))
        self.update_summary(); self.apply_filter(); self.schedule_session_save()
    def select_files(self):
        paths=filedialog.askopenfilenames(filetypes=[('Documentos e imagens','*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp'),('Todos os arquivos','*.*')])
        if paths:self.add_files(self.prepare_input_paths(paths))
    def select_folder(self):
        d=filedialog.askdirectory();
        if d:self.add_files(self.prepare_input_paths(p for p in Path(d).iterdir() if p.is_file() and p.suffix.lower() in INPUT_EXTENSIONS))
    def request_cancel_analysis(self):
        if not self.analysis_running:return
        choice=self.cancel_analysis_dialog()
        if choice=='continue':return
        self.analysis_cancelled=True; self.analysis_discard=(choice=='discard')
        self.cancel_event.set(); self.cancel_analysis_btn.config(state='disabled')
        self.status.set('Cancelamento solicitado. Finalizando os arquivos que já estão em leitura...')

    def cancel_analysis_dialog(self):
        result=tk.StringVar(value='')
        dialog=tk.Toplevel(self); dialog.title('Cancelar análise')
        dialog.transient(self); dialog.grab_set(); dialog.resizable(False,False)
        def choose(value):result.set(value)
        dialog.protocol('WM_DELETE_WINDOW',lambda:choose('continue'))
        box=ttk.Frame(dialog,padding=18); box.pack(fill='both',expand=True)
        ttk.Label(box,text='Cancelar a análise em andamento?',font=('Segoe UI',13,'bold')).pack(anchor='w')
        ttk.Label(box,text=('Os arquivos que já estão sendo lidos serão finalizados com seguranca.\n'
                            'Nenhum novo arquivo será iniciado depois do cancelamento.'),justify='left',wraplength=510).pack(anchor='w',pady=(8,16))
        ttk.Button(box,text='Manter resultados e parar',style='Primary.TButton',command=lambda:choose('keep')).pack(fill='x',pady=3)
        ttk.Button(box,text='Descartar resultados desta análise',style='Secondary.TButton',command=lambda:choose('discard')).pack(fill='x',pady=3)
        ttk.Button(box,text='Continuar análise',command=lambda:choose('continue')).pack(fill='x',pady=(3,0))
        dialog.bind('<Escape>',lambda _e:choose('continue'))
        dialog.wait_visibility(); self.center_dialog(dialog); dialog.focus_force(); dialog.wait_variable(result)
        choice=result.get(); dialog.destroy(); return choice

    def start(self,selected_only=False):
        if str(self.analyze_btn.cget('state'))=='disabled':return
        if not self.files:return messagebox.showwarning('Aviso','Selecione os arquivos primeiro.')
        if selected_only:
            selected=self.tree.selection()
            if not selected:return messagebox.showwarning('Verificar selecionados','Selecione um ou mais arquivos para verificar.',parent=self)
            analysis_files=selected
        else:
            analysis_files=list(self.files)
        self.analysis_options=self.current_options()
        self.analysis_output_format=self.output_format.get()
        self.analysis_events=queue.Queue()
        self.analysis_running=True; self.analysis_cancelled=False; self.analysis_discard=False; self.analysis_completed=0; self.last_session_checkpoint=0
        self.cancel_event.clear(); self.cancel_analysis_btn.config(state='normal')
        self.analysis_files=list(analysis_files)
        self.analysis_snapshot={path:dict(row) for path,row in self.row_by_path.items()}
        if selected_only:
            selected_paths=set(self.analysis_files)
            self.rows=[row for row in self.rows if row.get('path') not in selected_paths]
            self.row_by_path={path:row for path,row in self.row_by_path.items() if path not in selected_paths}
        else:
            self.rows=[]; self.row_by_path={}
        self.preview_cache.clear()
        for path in self.analysis_files:
            if self.tree.exists(path): self.tree.item(path,values=(self.original_display_name(path),'','','','Pendente'),tags=('review',))
        self.progress.config(maximum=len(self.analysis_files), value=0)
        if selected_only:
            count=len(self.analysis_files)
            self.status.set(f'Verificando {count} arquivo(s) selecionado(s).')
        for widget in (self.select_files_btn,self.select_folder_btn,self.analyze_btn,self.approve_btn,self.approve_atestado_btn,self.approve_declaracao_btn,self.correct_btn,self.export_btn,self.filter_combo,self.output_format_combo,
                       self.chapa_check,self.nome_check,self.mes_check,self.verify_selected_btn): widget.config(state='disabled')
        self.update_summary()
        self.analysis_ui_poll_job=self.after(40,self.process_analysis_events)
        threading.Thread(target=self.analyze,daemon=True).start()
    def analyze(self):
        options=self.analysis_options; output_format=self.analysis_output_format; files=self.analysis_files; workers=min(PARALLEL_WORKERS,max(1,len(files)))
        iterator=iter(files); running={}
        def submit_next(pool):
            if self.cancel_event.is_set():return False
            try:path=next(iterator)
            except StopIteration:return False
            running[pool.submit(analyze_document,path,self.analysis_pages.get(path,0))]=path; return True
        try:
            with ThreadPoolExecutor(max_workers=workers,thread_name_prefix='ocr') as pool:
                for _ in range(workers):submit_next(pool)
                while running:
                    done,_=wait(tuple(running),return_when=FIRST_COMPLETED)
                    for future in done:
                        path=running.pop(future); self.analysis_completed+=1
                        try:
                            result=future.result(); parsed=result.get('parsed'); method=result['method']; conf=result['conf']; category=result.get('category')
                            if category:
                                row={'path':path,'chapa':None,'nome':None,'mes':None,'new':self.filename_with_selected_extension(compose_document_filename(self.original_sources.get(path,path),result['document_type']),output_format),
                                     'category':category,'document_type':result['document_type'],'method':method,'conf':conf,
                                     'status':'OK','manual_name':False,'analysis_page':self.analysis_pages.get(path,0)}
                            elif parsed:
                                row={'path':path,'chapa':parsed[0],'nome':parsed[1],'mes':parsed[2],
                                     'chapa_source':parsed[3] if len(parsed)>3 else 'documento','category':None,
                                     'document_type':'Folha de ponto','method':method,'conf':conf,'status':'REVISAR','manual_name':False,'analysis_page':self.analysis_pages.get(path,0)}
                                row['new']=self.compose_filename(row,options,output_format)
                                row['status']='OK' if row['chapa_source']=='documento' and is_ready_confidence(conf) and self.fields_complete(row,options) else 'REVISAR'
                            else:
                                row={'path':path,'chapa':None,'nome':None,'mes':None,'new':'',
                                     'category':None,'document_type':'Não identificado','method':method,'conf':conf,'status':'NAO RECONHECIDO','manual_name':False,'analysis_page':self.analysis_pages.get(path,0)}
                            if not self.analysis_discard:self.analysis_events.put(('result',row))
                        except Exception as exc:
                            LOGGER.exception('Falha ao analisar %s',path)
                            if not self.analysis_discard:self.analysis_events.put(('error',(path,exc)))
                        self.analysis_events.put(('progress',(self.analysis_completed,len(files),path)))
                        submit_next(pool)
        except Exception as exc:
            LOGGER.exception('Falha geral na análise')
            self.analysis_events.put(('fatal',exc))
        finally:self.analysis_events.put(('finished',None))

    def process_analysis_events(self):
        self.analysis_ui_poll_job=None
        while True:
            try:event,payload=self.analysis_events.get_nowait()
            except queue.Empty:break
            if event=='result':self.accept_analysis_result(payload)
            elif event=='error':self.set_error_row(*payload)
            elif event=='progress':self.update_analysis_progress(*payload)
            elif event=='fatal':
                messagebox.showerror('Análise interrompida',f'A análise foi interrompida:\n{payload}',parent=self)
            elif event=='finished':
                self.finish_analysis()
                return
        if self.analysis_running:
            self.analysis_ui_poll_job=self.after(40,self.process_analysis_events)

    def update_analysis_progress(self,value,total,path):
        self.progress.config(value=value)
        action='Finalizando' if self.cancel_event.is_set() else 'Processando'
        self.status.set(f'{action} {value} de {total}: {self.original_display_name(path)}')

    def accept_analysis_result(self,row):
        path=row['path']
        old=self.row_by_path.get(path)
        if old in self.rows:self.rows.remove(old)
        self.rows.append(row); self.row_by_path[path]=row; self.set_row_values(row,save=False)
        if self.analysis_completed-self.last_session_checkpoint>=10:
            self.last_session_checkpoint=self.analysis_completed; self.schedule_session_save()

    def set_error_row(self,path,error):
        row={'path':path,'chapa':None,'nome':None,'mes':None,'new':'','method':'Erro','conf':0,
             'status':'ERRO','manual_name':False,'error':str(error)[:300]}
        old=self.row_by_path.get(path)
        if old in self.rows:self.rows.remove(old)
        self.rows.append(row); self.row_by_path[path]=row
        self.tree.item(path,values=(self.original_display_name(path),'','Erro','0%','ERRO'),tags=('error',))
        self.status.set(f'Erro em {Path(path).name}: {str(error)[:100]}')
        self.update_summary(); self.schedule_session_save()
    def finish_analysis(self):
        cancelled=self.analysis_cancelled; discard=self.analysis_discard
        self.analysis_running=False; self.cancel_analysis_btn.config(state='disabled')
        for widget in (self.select_files_btn,self.select_folder_btn,self.analyze_btn,self.approve_btn,self.approve_atestado_btn,self.approve_declaracao_btn,self.correct_btn,self.export_btn,
                       self.chapa_check,self.nome_check,self.mes_check): widget.config(state='normal')
        self.update_verify_selected_button()
        self.filter_combo.config(state='readonly')
        self.output_format_combo.config(state='readonly')
        if self.output_format.get().upper() not in OUTPUT_FORMATS:self.output_format.set('PDF')
        if discard:
            snapshot=self.analysis_snapshot or {}
            self.rows=[]; self.row_by_path={}
            for path in self.files:
                prior=snapshot.get(path)
                if prior:
                    restored=dict(prior); self.rows.append(restored); self.row_by_path[path]=restored; self.set_row_values(restored,save=False)
                elif self.tree.exists(path):self.tree.item(path,values=(self.original_display_name(path),'','','','Pendente'),tags=('review',))
            self.progress.config(value=0)
            self.status.set('Análise cancelada. O estado anterior foi restaurado.')
        elif cancelled:
            pending=sum(1 for path in self.analysis_files if self.tree.exists(path) and self.tree.set(path,'status')=='Pendente')
            self.status.set(f'Análise cancelada. {self.analysis_completed} processado(s); {pending} pendente(s).')
            messagebox.showinfo('Análise cancelada',f'{self.analysis_completed} arquivo(s) foram processados.\n{pending} arquivo(s) continuam pendentes.',parent=self)
        else:self.status.set('Análise concluída. Revise os itens antes de exportar.')
        self.update_summary(); self.schedule_session_save()

    def schedule_show_selected(self,*_):
        self.update_verify_selected_button()
        if self.preview_select_job:
            try:self.after_cancel(self.preview_select_job)
            except tk.TclError:pass
        self.preview_select_job=self.after(140,self.show_selected)

    def show_selected(self,*_):
        self.preview_select_job=None
        selected=self.tree.selection()
        if not selected:return
        path=selected[0]
        if path!=self.preview_path:
            self.preview_path=path; self.preview_page=int(self.analysis_pages.get(path,0)); self.preview_total_pages=0
        self.load_preview_page()

    def preview_cache_key(self,path,page_index):
        return (path,int(page_index))

    def load_preview_page(self):
        path=self.preview_path
        if not path:return
        key=self.preview_cache_key(path,self.preview_page)
        if key in self.preview_cache:
            image,total=self.preview_cache.pop(key); self.preview_cache[key]=(image,total)
            self.preview_img=image; self.preview_total_pages=total; self.update_page_controls(); self.fit_preview(); return
        self.preview_request+=1; request=self.preview_request; page_index=self.preview_page
        self.preview.delete('all'); self.preview.create_text(15,15,anchor='nw',text=f'Carregando página {page_index+1}...',fill='#6b7785')
        def worker():
            try:
                image,total=render_pdf_page(path,page_index)
                self.after(0,lambda:self.apply_preview(path,page_index,image,total,request))
            except Exception as exc:
                LOGGER.exception('Falha ao carregar página %s de %s',page_index+1,path)
                self.after(0,lambda e=exc:self.preview_error(e,request))
        threading.Thread(target=worker,daemon=True).start()

    def apply_preview(self,path,page_index,image,total,request):
        if request!=self.preview_request or not self.winfo_exists():return
        if path!=self.preview_path or page_index!=self.preview_page:return
        key=self.preview_cache_key(path,page_index); self.preview_cache[key]=(image,total)
        while len(self.preview_cache)>3:self.preview_cache.popitem(last=False)
        self.preview_img=image; self.preview_total_pages=total; self.update_page_controls(); self.fit_preview()

    def preview_error(self,error,request):
        if request!=self.preview_request:return
        self.preview.delete('all'); self.preview.create_text(15,15,anchor='nw',text=f'Prévia indisponível: {str(error)[:80]}',fill='#a12622')
        self.preview_total_pages=0; self.update_page_controls()

    def change_page(self,step):
        if not self.preview_path or self.preview_total_pages<1:return
        target=max(0,min(self.preview_page+step,self.preview_total_pages-1))
        if target==self.preview_page:return
        self.preview_page=target; self.load_preview_page()

    def update_page_controls(self):
        total=self.preview_total_pages
        current=self.preview_page+1 if total else 0
        self.page_label.config(text=f'Página {current} de {total}')
        self.prev_page_btn.config(state='normal' if total and self.preview_page>0 else 'disabled')
        self.next_page_btn.config(state='normal' if total and self.preview_page<total-1 else 'disabled')

    def preview_fit_scale(self):
        if self.preview_img is None:return 1.0
        self.update_idletasks(); h,w=self.preview_img.shape[:2]
        cw=max(1,self.preview.winfo_width()-2); ch=max(1,self.preview.winfo_height()-2)
        return max(cw/w,ch/h)*1.002
    def fit_preview(self):
        if self.preview_img is None:return
        self.preview_min_zoom=self.preview_fit_scale(); self.zoom=self.preview_min_zoom
        self.draw_preview(reset_view=True)
    def schedule_preview_refit(self,event=None):
        if self.preview_img is None:return
        if self.preview_resize_job:
            try:self.after_cancel(self.preview_resize_job)
            except tk.TclError:pass
        self.preview_resize_job=self.after(100,self.refit_preview_after_resize)
    def refit_preview_after_resize(self):
        self.preview_resize_job=None
        if self.preview_img is None:return
        old_min=max(self.preview_min_zoom,0.0001); fitted=self.zoom<=old_min*1.02
        self.preview_min_zoom=self.preview_fit_scale()
        if fitted or self.zoom<self.preview_min_zoom:self.zoom=self.preview_min_zoom
        self.draw_preview(reset_view=fitted)
    def change_zoom(self,factor):
        if self.preview_img is None:return
        self.preview_min_zoom=self.preview_fit_scale()
        x=self.preview.xview()[0] if self.preview.xview() else 0; y=self.preview.yview()[0] if self.preview.yview() else 0
        self.zoom=max(self.preview_min_zoom,min(4.0,self.zoom*factor)); self.draw_preview()
        self.preview.xview_moveto(x); self.preview.yview_moveto(y)
    def zoom_in_key(self,event=None):self.change_zoom(1.20); return 'break'
    def zoom_out_key(self,event=None):self.change_zoom(1/1.20); return 'break'
    def preview_mousewheel(self,event):self.preview.yview_scroll((-1 if event.delta>0 else 1)*3,'units'); return 'break'
    def preview_shift_mousewheel(self,event):self.preview.xview_scroll((-1 if event.delta>0 else 1)*3,'units'); return 'break'
    def preview_ctrl_mousewheel(self,event):self.change_zoom(1.15 if event.delta>0 else 1/1.15); return 'break'
    def preview_pan_start(self,event):self.preview.scan_mark(event.x,event.y); self.preview.config(cursor='fleur'); return 'break'
    def preview_pan_move(self,event):self.preview.scan_dragto(event.x,event.y,gain=1); return 'break'
    def draw_preview(self,reset_view=False):
        if self.preview_img is None:return
        h,w=self.preview_img.shape[:2]; size=(max(1,int(w*self.zoom)),max(1,int(h*self.zoom)))
        im=Image.fromarray(self.preview_img).resize(size,Image.Resampling.LANCZOS); self.photo=ImageTk.PhotoImage(im)
        self.preview.delete('all'); self.preview.create_image(0,0,anchor='nw',image=self.photo)
        self.preview.configure(scrollregion=(0,0,size[0],size[1]))
        cw=max(1,self.preview.winfo_width()); ch=max(1,self.preview.winfo_height())
        if size[1]>ch+1:self.preview_ybar.grid(row=0,column=1,sticky='ns')
        else:self.preview_ybar.grid_remove()
        if size[0]>cw+1:self.preview_xbar.grid(row=1,column=0,sticky='ew')
        else:self.preview_xbar.grid_remove()
        if reset_view:self.preview.xview_moveto(0); self.preview.yview_moveto(0)
        self.zoom_label.config(text=f'{self.zoom:.0%}')
    def approve_as_category(self,category):
        """Permite corrigir classificacao sem inventar chapa, nome ou mes."""
        if self.analysis_running:return messagebox.showwarning('Análise em andamento','Aguarde a análise terminar.',parent=self)
        selected=self.tree.selection()
        if not selected:return messagebox.showwarning('Aviso','Selecione um ou mais arquivos.',parent=self)
        label='Atestado' if category=='Atestados' else 'Declaração'
        changed=0
        for iid in selected:
            row=self.row_by_path.get(iid)
            if row is None:
                row={'path':iid,'chapa':None,'nome':None,'mes':None,'manual_name':False}
                self.rows.append(row); self.row_by_path[iid]=row
            row.update({'category':category,'document_type':label,'method':'Classificação manual',
                        'conf':1.0,'status':'APROVADO','new':self.filename_with_selected_extension(compose_document_filename(self.original_sources.get(iid,iid),label))})
            self.set_row_values(row,save=False); changed+=1
        self.update_summary(); self.apply_filter(); self.schedule_session_save()
        self.status.set(f'{changed} arquivo(s) aprovado(s) como {label.lower()}.')

    def approve_selected(self):
        if self.analysis_running:return messagebox.showwarning('Análise em andamento','Aguarde a análise terminar.',parent=self)
        selected=self.tree.selection()
        if not selected:return messagebox.showwarning('Aviso','Selecione um ou mais arquivos para aprovar.')
        changed=0
        for iid in selected:
            new=self.tree.set(iid,'novo').strip()
            status=self.tree.set(iid,'status')
            if not new or self.is_blocking_status(status):continue
            row=self.row_by_path.get(iid)
            if row:
                row['category']=None; row['document_type']='Folha de ponto'; row['status']='APROVADO'
            self.tree.set(iid,'status','APROVADO'); self.tree.item(iid,tags=('approved',)); changed+=1
        self.update_summary(); self.schedule_session_save()
        self.status.set(f'{changed} arquivo(s) aprovado(s).')

    def review_export_dialog(self,review_items):
        result=tk.StringVar(value='')
        dialog=tk.Toplevel(self); dialog.title('Arquivos precisam de revisao')
        dialog.transient(self); dialog.grab_set(); dialog.resizable(False,False)
        def choose(value):
            result.set(value)
        dialog.protocol('WM_DELETE_WINDOW',lambda:choose('cancel'))
        box=ttk.Frame(dialog,padding=18); box.pack(fill='both',expand=True)
        ttk.Label(box,text='Arquivos precisam de revisao',font=('Segoe UI',13,'bold')).pack(anchor='w')
        ttk.Label(box,text=(f'Foram encontrados {len(review_items)} arquivo(s) marcado(s) como REVISAR.\n'
                            'Os nomes podem estar incompletos ou ter baixa confiança.\n\n'
                            'Escolha revisar os arquivos ou prosseguir com os nomes atuais.'),
                  justify='left',wraplength=500).pack(anchor='w',pady=(8,14))
        names='\n'.join(f'- {Path(path).name}' for path in review_items[:6])
        if len(review_items)>6:names+=f'\n... e mais {len(review_items)-6} arquivo(s).'
        ttk.Label(box,text=names,justify='left',foreground='#7a4300').pack(anchor='w',pady=(0,16))
        actions=ttk.Frame(box); actions.pack(fill='x')
        ttk.Button(actions,text='Cancelar',command=lambda:choose('cancel')).pack(side='right')
        ttk.Button(actions,text='Prosseguir mesmo assim',style='Success.TButton',command=lambda:choose('proceed')).pack(side='right',padx=8)
        ttk.Button(actions,text='Revisar arquivos',style='Primary.TButton',command=lambda:choose('review')).pack(side='right')
        dialog.bind('<Escape>',lambda _e:choose('cancel'))
        dialog.wait_visibility(); self.center_dialog(dialog); dialog.focus_force(); dialog.wait_variable(result)
        choice=result.get(); dialog.destroy(); return choice

    def blocking_export_dialog(self,problems):
        result=tk.StringVar(value='')
        dialog=tk.Toplevel(self); dialog.title('Exportação bloqueada')
        dialog.transient(self); dialog.grab_set(); dialog.resizable(False,False)
        def choose(value):result.set(value)
        dialog.protocol('WM_DELETE_WINDOW',lambda:choose('close'))
        box=ttk.Frame(dialog,padding=18); box.pack(fill='both',expand=True)
        ttk.Label(box,text='Não é possível exportar',font=('Segoe UI',13,'bold'),foreground='#8f1713').pack(anchor='w')
        ttk.Label(box,text=(f'Foram encontrados {len(problems)} arquivo(s) com problemas que bloqueiam a exportação.\n'
                            'Corrija ou remova esses itens antes de tentar novamente.'),
                  justify='left',wraplength=540).pack(anchor='w',pady=(8,12))
        details=[f'- {Path(path).name}: {reason}' for path,reason in problems[:8]]
        if len(problems)>8:details.append(f'... e mais {len(problems)-8} arquivo(s).')
        ttk.Label(box,text='\n'.join(details),justify='left',foreground='#8f1713',wraplength=560).pack(anchor='w',pady=(0,16))
        actions=ttk.Frame(box); actions.pack(fill='x')
        ttk.Button(actions,text='Fechar',command=lambda:choose('close')).pack(side='right')
        ttk.Button(actions,text='Mostrar bloqueados',style='Primary.TButton',command=lambda:choose('show')).pack(side='right',padx=8)
        dialog.bind('<Escape>',lambda _e:choose('close'))
        dialog.wait_visibility(); self.center_dialog(dialog); dialog.focus_force(); dialog.wait_variable(result)
        choice=result.get(); dialog.destroy()
        if choice=='show':self.show_blocked_files([path for path,_ in problems])

    def show_blocked_files(self,items):
        self.filter_status.set('Bloqueados'); self.apply_filter()
        visible=[path for path in items if self.tree.exists(path)]
        for path in visible:self.tree.item(path,tags=('error',))
        if visible:
            first=visible[0]; self.tree.selection_set(first); self.tree.focus(first); self.tree.see(first); self.show_selected()
        self.status.set(f'{len(visible)} arquivo(s) bloqueado(s) destacados em vermelho.')

    def show_review_files(self,items):
        self.filter_status.set('Revisar'); self.apply_filter()
        visible=[path for path in items if self.tree.exists(path)]
        for path in visible:self.tree.item(path,tags=('review',))
        if visible:
            first=visible[0]; self.tree.selection_set(first); self.tree.focus(first); self.tree.see(first); self.show_selected()
        self.status.set(f'{len(visible)} arquivo(s) para revisar destacados em amarelo.')

    def export_problems(self,items):
        problems=[]
        for path in items:
            status=(self.tree.set(path,'status') or '').strip().upper(); source=Path(path)
            if status=='PENDENTE':problems.append((path,'análise ainda não realizada'))
            elif status=='NAO RECONHECIDO':problems.append((path,'matrícula ou nome não reconhecido'))
            elif status in {'ERRO','FALHOU'}:problems.append((path,'erro durante a leitura do PDF'))
            elif not source.is_file():problems.append((path,'arquivo original não foi encontrado'))
            elif not os.access(source,os.R_OK):problems.append((path,'arquivo original sem permissao de leitura'))
            elif not self.tree.set(path,'novo').strip():problems.append((path,'novo nome está vazio'))
            elif not safe_filename(self.tree.set(path,'novo')).strip():problems.append((path,'novo nome contem apenas caracteres inválidos'))
        return problems

    def planned_export_paths(self,source,target,output_format):
        fmt=output_format.upper(); target=Path(target)
        if fmt=='PDF':return [target]
        extension='jpg' if fmt=='JPG' else fmt.lower()
        with fitz.open(source) as doc:total=len(doc)
        if total<=1:return [target.with_suffix('.'+extension)]
        return [target.with_name(f'{target.stem} - página {index+1:03d}.{extension}') for index in range(total)]

    def export_source(self,source,target,output_format):
        fmt=output_format.upper(); source=Path(source); target=Path(target)
        destinations=self.planned_export_paths(source,target,fmt)
        if fmt=='PDF':shutil.copy2(source,destinations[0]); return destinations
        pil_fmt='JPEG' if fmt in {'JPEG','JPG'} else fmt
        created=[]
        try:
            with fitz.open(source) as doc:
                for page,destination in zip(doc,destinations):
                    pix=page.get_pixmap(matrix=fitz.Matrix(2.2,2.2),alpha=False)
                    image=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
                    kwargs={'quality':92,'optimize':True} if pil_fmt=='JPEG' else {}
                    image.save(destination,pil_fmt,**kwargs); created.append(destination)
            return created
        except Exception:
            for destination in created:destination.unlink(missing_ok=True)
            raise

    def export(self):
        if not self.files:return messagebox.showwarning('Aviso','Selecione e analise os arquivos primeiro.',parent=self)
        items=[iid for iid in self.files if self.tree.exists(iid)]
        problems=self.export_problems(items)
        review=[iid for iid in items if self.tree.set(iid,'status')=='REVISAR']
        if problems:
            self.blocking_export_dialog(problems)
            self.status.set(f'Exportação bloqueada: {len(problems)} arquivo(s) precisam de correção.')
            return
        if review:
            choice=self.review_export_dialog(review)
            if choice=='review':self.show_review_files(review); return
            if choice!='proceed':self.status.set('Exportação cancelada pelo usuário.'); return
        exportable=[]
        for iid in items:
            status=self.tree.set(iid,'status')
            if status not in {'OK','APROVADO','CORRIGIDO','REVISAR'}:continue
            new=safe_filename(self.tree.set(iid,'novo')).strip()
            if not new:continue
            exportable.append((iid,Path(new).stem))
        if not exportable:return messagebox.showwarning('Aviso','Não há arquivos válidos para exportar.',parent=self)
        chosen=filedialog.askdirectory(title='Escolha onde salvar os arquivos renomeados',mustexist=True)
        if not chosen:self.status.set('Exportação cancelada.'); return
        out=Path(chosen); count=0; used=set(); failures=[]; separated={'Atestados':0,'Declarações':0}; output_format=self.output_format.get().upper(); output_format=output_format if output_format in OUTPUT_FORMATS else 'PDF'; extension='jpg' if output_format=='JPG' else output_format.lower()
        for iid,base in exportable:
            row=self.row_by_path.get(iid,{})
            category=row.get('category')
            destination=out/category if category else out
            destination.mkdir(parents=True,exist_ok=True)
            candidate=base; n=2
            while True:
                target=destination/f'{candidate}.{extension}'
                planned=self.planned_export_paths(iid,target,output_format)
                keys={str(p.relative_to(out)).lower() for p in planned}
                if all(key not in used and not p.exists() for key,p in zip(keys,planned)):break
                candidate=f'{base} ({n})'; n+=1
            try:
                made=self.export_source(iid,target,output_format); used.update(str(p.relative_to(out)).lower() for p in made); count+=len(made)
                if category: separated[category]+=len(made)
            except Exception as exc:LOGGER.exception('Falha ao exportar %s',iid); failures.append((iid,str(exc)))
        if failures:
            names='\n'.join(f'- {self.original_display_name(iid)}' for iid,_ in failures[:8])
            self.status.set(f'Exportação parcial: {count} copiado(s), {len(failures)} falha(s).')
            messagebox.showerror('Exportação parcial',f'{count} arquivo(s) foram exportados, mas {len(failures)} entrada(s) falharam:\n\n{names}\n\nA sessão foi mantida para nova tentativa.',parent=self)
            self.schedule_session_save(); return
        self.status.set(f'{count} arquivo(s) exportado(s) para {out}')
        if self.session_save_job:self.after_cancel(self.session_save_job); self.session_save_job=None
        SESSION_FILE.unlink(missing_ok=True); SESSION_FILE.with_suffix('.tmp').unlink(missing_ok=True)
        self.session_persistence_disabled=True
        warning=f'\n\nIncluídos com aviso: {len(review)} arquivo(s) em revisão.' if review else ''
        separated_text=(f'\n\nSeparados automaticamente:'
                        f'\n- Atestados: {separated["Atestados"]}'
                        f'\n- Declarações: {separated["Declarações"]}')
        messagebox.showinfo('Concluído',f'{count} arquivo(s) exportado(s) para:\n{out}{separated_text}{warning}',parent=self)

if __name__=='__main__':
    from tkinter import simpledialog
    tk.simpledialog=simpledialog
    App().mainloop()
