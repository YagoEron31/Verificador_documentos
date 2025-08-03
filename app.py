import os
import hashlib
import requests
from flask import Flask, request, render_template
from supabase import create_client
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

# Configurações
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

app = Flask(__name__)
_supabase_client = None

# Conexão preguiçosa com o Supabase
def get_supabase_client():
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

# Extensões de arquivos permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =================================================================================
# OCR com o OCR.space
# =================================================================================
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

# =================================================================================
# Lógica de Análise (exemplo simples)
# =================================================================================
def analisar_texto_completo(texto):
    erros_detectados = []

    # Regras de exemplo
    if "123456" in texto:
        erros_detectados.append("Número suspeito detectado.")
    if "confidencial" in texto.lower():
        erros_detectados.append("Conteúdo confidencial identificado.")
    if len(texto.strip()) < 30:
        erros_detectados.append("Texto muito curto para análise confiável.")

    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados}

# =================================================================================
# Rotas da aplicação
# =================================================================================

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

    if 'file' not in request.files or request.files['file'].filename == '':
        return render_template('verificação.html', erro_upload="Nenhum arquivo selecionado.")

    file = request.files['file']

    if not allowed_file(file.filename):
        return render_template('verificação.html', erro_upload="Formato de arquivo não suportado.")

    try:
        filename = secure_filename(file.filename)
        file_bytes = file.read()

        # 1. Extrair texto com OCR
        texto_extraido = extrair_texto_ocr_space(file_bytes, filename)

        # 2. Analisar o texto
        resultado = analisar_texto_completo(texto_extraido)

        # 3. Tentar salvar no Supabase (sem impedir análise)
        try:
            supabase = get_supabase_client()
            hash_sha256 = hashlib.sha256(file_bytes).hexdigest()

            supabase.table('analises').insert({
                "nome_arquivo": filename,
                "hash_arquivo": hash_sha256,
                "status": resultado['status'],
                "erros_detectados": resultado['erros'],
                "texto_extraido": texto_extraido
            }).execute()

        except Exception as db_error:
            print(f"[⚠️] Erro ao salvar no Supabase: {db_error}")

        # 4. Retornar resultado da análise
        return render_template(
            'verificação.html',
            resultado=resultado,
            texto_extraido=texto_extraido,
            nome_arquivo=filename,
            hash_arquivo=hash_sha256
        )

    except Exception as e:
        return render_template('verificação.html', resultado={
            "status": "ERRO",
            "erros": [f"Erro inesperado: {str(e)}"]
        })

# =================================================================================
# Execução local
# =================================================================================
if __name__ == '__main__':
    app.run(debug=True)
