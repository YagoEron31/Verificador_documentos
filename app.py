import os
import re
import hashlib
import io
import json
import requests
from flask import Flask, request, render_template, jsonify
from supabase import create_client, Client
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Carrega variáveis de ambiente (útil para desenvolvimento local)
load_dotenv()

# --- CHAVES E URLS INSERIDAS DIRETAMENTE NO CÓDIGO ---
OCR_SPACE_API_KEY = "K81365576488957"
SUPABASE_URL = "https://likiubglfkyoizobjrem.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxpa2l1YmdsZmt5b2l6b2JqcmVtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQyMDA3NTgsImV4cCI6MjA2OTc3Njc1OH0.ynQy5J-4W_2oyiLa-8GbPmFe_gtGm2HAAeRqoPEXPEI"
# -------------------------------------------------------------

app = Flask(__name__)
_supabase_client = None

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

def analisar_texto_completo(texto):
    """Executa todas as regras de verificação no texto extraído."""
    erros_detectados = []
    texto_em_minusculo = texto.lower()
    
    # (Sua lógica de análise detalhada permanece aqui)
    PALAVRAS_SUSPEITAS = ["dispensa de licitação", "caráter de urgência"]
    for palavra in PALAVRAS_SUSPEITAS:
        if palavra in texto_em_minusculo:
            erros_detectados.append(f"Alerta de Termo Sensível: '{palavra}'")
    
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

    filename = secure_filename(file.filename)
    file_bytes = file.read()

    try:
        supabase = get_supabase_client()
        hash_arquivo = hashlib.sha256(file_bytes).hexdigest()

        data, count = supabase.table('analises').select('*').eq('hash_arquivo', hash_arquivo).execute()
        
        if len(data[1]) > 0:
            print("Documento já processado. Retornando do cache.")
            return render_template('verificação.html', resultado=data[1][0])

        print("Arquivo novo, iniciando processamento completo.")
        
        texto_extraido = extrair_texto_ocr_space(file_bytes, filename)
        if not texto_extraido.strip():
            raise ValueError("Nenhum texto pôde ser extraído do documento.")

        analise = analisar_texto_completo(texto_extraido)
        hash_conteudo = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()
        
        caminho_storage = f"documentos/{hash_arquivo}_{filename}"
        supabase.storage.from_("armazenamento").upload(
            path=caminho_storage, file=file_bytes, file_options={"content-type": file.content_type}
        )
        
        resultado_final = {
            "nome_arquivo": filename, "hash_arquivo": hash_arquivo, "hash_conteudo": hash_conteudo,
            "status": analise['status'], "erros_detectados": analise['erros'],
            "texto_extraido": texto_extraido, "caminho_storage": caminho_storage
        }
        supabase.table('analises').insert(resultado_final).execute()
        print("Nova análise salva no Supabase.")
        
        return render_template('verificação.html', resultado=resultado_final)

    except Exception as e:
        return render_template('verificação.html', resultado={"status": "ERRO", "erros": [f"Erro inesperado: {e}"]})
    
# ... (outras rotas como /login, /transparencia, etc.) ...

if __name__ == '__main__':
    app.run(debug=True)
