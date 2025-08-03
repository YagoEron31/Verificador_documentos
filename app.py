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

# Carrega variáveis de ambiente
load_dotenv()

# --- Configurações e Conexões ---
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

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
    # (Sua lógica de análise detalhada permanece aqui)
    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados}

def extrair_texto_ocr_space(file_bytes, filename):
    """Extrai texto de um arquivo usando a API do OCR.space."""
    # (Sua lógica de extração de texto via API permanece aqui)
    return "Texto extraído com sucesso"

# =================================================================================
# --- ROTAS DA APLICAÇÃO ---
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
        # CORREÇÃO FINAL: Usando o nome exato 'verificação.html'
        return render_template('verificação.html')

    # Lógica de POST...
    if 'file' not in request.files or request.files['file'].filename == '':
        return render_template('verificação.html', erro_upload="Nenhum arquivo selecionado.")
    
    file = request.files['file']
    
    if not allowed_file(file.filename):
        return render_template('verificação.html', erro_upload="Formato de arquivo não suportado.")

    try:
        filename = secure_filename(file.filename)
        file_bytes = file.read()
        
        # ... (resto da sua lógica de análise completa)
        
        resultado_final = {"status": "SUCESSO", "mensagem": "Análise concluída com sucesso!"}
        return render_template('verificação.html', resultado=resultado_final)

    except Exception as e:
        return render_template('verificação.html', resultado={"status": "ERRO", "erros": [f"Erro inesperado: {e}"]})

# ... (outras rotas)

if __name__ == '__main__':
    app.run(debug=True)
