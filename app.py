import os
import re
import hashlib
import io
import requests
from flask import Flask, request, render_template, jsonify
from supabase import create_client, Client
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# --- Configurações e Conexões ---
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

app = Flask(__name__)
_supabase_client = None

# --- Conexão Otimizada com o Supabase ---
def get_supabase_client():
    """Cria e reutiliza uma conexão com o Supabase."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

# Define as extensões de arquivo permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =================================================================================
# --- FUNÇÕES DE LÓGICA (Análise, OCR) ---
# =================================================================================

def analisar_texto(texto_extraido):
    """Realiza as análises de fraude no texto extraído."""
    erros_detectados = []
    texto_lower = texto_extraido.lower()

    # (Sua lógica de análise detalhada permanece aqui)
    PALAVRAS_SUSPEITAS = ["dispensa de licitação", "caráter de urgência"]
    for palavra in PALAVRAS_SUSPEITAS:
        if palavra in texto_lower:
            erros_detectados.append(f"⚠️ Alerta de Termo Sensível: '{palavra}'")

    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados}

def extrair_texto_ocr_space(file_bytes, filename):
    """Extrai texto de um arquivo usando a API do OCR.space."""
    url = "https://api.ocr.space/parse/image"
    payload = {'language': 'por', 'isOverlayRequired': 'false', 'OCREngine': 2}
    files = {'file': (filename, file_bytes)}
    headers = {'apikey': OCR_SPACE_API_KEY}
    response = requests.post(url, headers=headers, data=payload, files=files)
    response.raise_for_status()
    result = response.json()
    if result.get("IsErroredOnProcessing"):
        raise ValueError(result.get("ErrorMessage", ["Erro desconhecido no OCR."])[0])
    if not result.get("ParsedResults"):
        raise ValueError("Nenhum resultado de texto foi retornado pela API de OCR.")
    return result["ParsedResults"][0]["ParsedText"]

# =================================================================================
# --- ROTAS DA APLICAÇÃO ---
# =================================================================================

@app.route('/')
def home():
    return render_template('inicial.html')

@app.route('/verificador', methods=['GET', 'POST'])
def verificador_page():
    if request.method == 'GET':
        return render_template('verificação.html')

    if 'file' not in request.files or request.files['file'].filename == '':
        return render_template('verificação.html', erro_upload="Nenhum arquivo selecionado.")
    
    file = request.files['file']
    
    if not allowed_file(file.filename):
        return render_template('verificação.html', erro_upload="Formato de arquivo não suportado.")
    
    try:
        file_bytes = file.read()
        texto_extraido = extrair_texto_ocr_space(file_bytes, file.filename)
        
        if not texto_extraido.strip():
                 raise ValueError("Nenhum texto pôde ser extraído do documento.")

        hash_sha2
