import os
import hashlib
import json
import requests
from flask import Flask, request, render_template
from supabase import create_client
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
load_dotenv()

# Variáveis de ambiente
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Inicializa o Flask
app = Flask(__name__)
_supabase_client = None

# ------------------------------
# Função de conexão preguiçosa
# ------------------------------
def get_supabase_client():
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

# Extensões de arquivos permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ------------------------------
# Funções de OCR e Análise
# ------------------------------
def extrair_texto_ocr_space(file_bytes, filename):
    url = 'https://api.ocr.space/parse/image'
    payload = {
        'apikey': OCR_SPACE_API_KEY,
        'language': 'por',
        'isOverlayRequired': False
    }
    files = {'file': (filename, file_bytes)}
    response = requests.post(url, data=payload, files=files)
    result = response.json()

    if result.get("IsErroredOnProcessing"):
        raise Exception(result.get("ErrorMessage", ["Erro no OCR"])[0])

    return result['ParsedResults'][0]['ParsedText']

def analisar_texto_completo(texto):
    erros_detectados = []

    # Lógica de verificação (exemplo)
    if "123456" in texto:
        erros_detectados.append("Número suspeito detectado.")

    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados}

# ------------------------------
# Rotas da Aplicação
# ------------------------------

@app.route('/')
def home():
    return render_template('inicial.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/verificador', methods=['GET', 'POST'])
def verificador_page():
    if request.method == 'GET':
        return render_template('verificação.html')

    # POST
    if 'file' not in request.files or request.files['file'].filename == '':
        return render_template('verificação.html', erro_upload="Nenhum arquivo selecionado.")

    file = request.files['file']

    if not allowed_file(file.filename):
        return render_template('verificação.html', erro_upload="Formato de arquivo não suportado.")

    try:
        filename = secure_filename(file.filename)
        file_bytes = file.read()

        # OCR
        texto_extraido = extrair_texto_ocr_space(file_bytes, filename)
        resultado = analisar_texto_completo(texto_extraido)

        # Supabase
        supabase = get_supabase_client()
        hash_sha256 = hashlib.sha256(file_bytes).hexdigest()

        supabase.table('documentos_oficiais').insert({
            "nome_original": filename,
            "hash_sha256": hash_sha256,
            "status": resultado['status'],
            "erros_detectados": json.dumps(resultado['erros']),
        }).execute()

        return render_template('verificação.html', resultado=resultado)

    except Exception as e:
        return render_template('verificação.html', resultado={
            "status": "ERRO",
            "erros": [f"Erro inesperado: {str(e)}"]
        })

# ------------------------------
# Execução local
# ------------------------------
if __name__ == '__main__':
    app.run(debug=True)
