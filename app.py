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

def get_supabase_client():
    """Cria e retorna um cliente Supabase, reutilizando a conexão se já existir."""
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

def analisar_texto(texto_extraido):
    """Realiza as análises de fraude no texto extraído."""
    erros_detectados = []
    texto_lower = texto_extraido.lower()
    # Adicione aqui suas regras de análise...
    PALAVRAS_SUSPEITAS = ["dispensa de licitação", "caráter de urgência"]
    for palavra in PALAVRAS_SUSPEITAS:
        if palavra in texto_lower:
            erros_detectados.append(f"⚠️ Alerta de Termo Sensível: '{palavra}'")
    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados}

# =================================================================================
# --- ROTAS PARA SERVIR AS PÁGINAS HTML ---
# =================================================================================

@app.route('/')
def home():
    return render_template('inicial.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/transparencia')
def transparencia_page():
    return render_template('transparencia.html')

@app.route('/verificador', methods=['GET', 'POST'])
def verificador_page():
    resultado_analise = None
    if request.method == 'POST':
        if 'file' not in request.files or request.files['file'].filename == '':
            return render_template('verificação.html', erro_upload="Nenhum arquivo selecionado.")
        
        file = request.files['file']
        
        if not allowed_file(file.filename):
            erro_msg = "Formato de arquivo não suportado. Por favor, envie um PDF, PNG, JPG ou JPEG."
            return render_template('verificação.html', erro_upload=erro_msg)
        
        if file:
            try:
                file_bytes = file.read()
                texto_extraido = extrair_texto_ocr_space(file_bytes, file.filename)
                
                if not texto_extraido.strip():
                         raise ValueError("Nenhum texto pôde ser extraído do documento.")

                hash_sha256 = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()
                analise = analisar_texto(texto_extraido)
                
                resultado_analise = {
                    "status": analise['status'],
                    "erros": analise['erros'],
                    "hash": hash_sha256,
                    "texto": texto_extraido
                }

            except Exception as e:
                resultado_analise = {"status": "ERRO", "erros": [f"Não foi possível processar o arquivo: {e}"]}
            
    return render_template('verificação.html', resultado=resultado_analise)

# =================================================================================
# --- ROTAS DE API PARA LOGIN/CADASTRO ---
# =================================================================================

@app.route('/signup', methods=['POST'])
def signup():
    try:
        supabase = get_supabase_client()
        data = request.get_json()
        email, password = data.get('email'), data.get('password')
        supabase.auth.sign_up({"email": email, "password": password})
        return jsonify({'message': 'Usuário cadastrado com sucesso!'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/handle_login', methods=['POST'])
def handle_login_post():
    try:
        supabase = get_supabase_client()
        data = request.get_json()
        email, password = data.get('email'), data.get('password')
        session = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return jsonify({'message': 'Login realizado com sucesso!', 'access_token': session.session.access_token}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Início do Servidor ---
if __name__ == '__main__':
    app.run(debug=True)
