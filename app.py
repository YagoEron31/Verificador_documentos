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

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

# =================================================================================
# --- SUAS FUNÇÕES DE LÓGICA (Análise, OCR, etc.) ---
# (Estas funções não mudam)
# =================================================================================

def analisar_texto_completo(texto):
    # (Sua lógica de análise detalhada permanece aqui)
    erros_detectados = []
    # ... (código completo da função)
    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados}

def extrair_texto_ocr_space(file_bytes, filename):
    # (Sua lógica de extração de texto via API permanece aqui)
    # ... (código completo da função)
    return "Texto extraído"

# =================================================================================
# --- ROTAS PARA SERVIR AS PÁGINAS HTML ---
# =================================================================================

@app.route('/')
def home():
    """ Rota para a página inicial (landing page). """
    return render_template('index.html')

@app.route('/login')
def login_page():
    """ Rota para exibir a página de login. """
    return render_template('login.html')

@app.route('/verificador', methods=['GET', 'POST'])
def verificador_page():
    """ Rota para a ferramenta de análise de documentos. """
    # Esta é a lógica da sua ferramenta principal
    if request.method == 'GET':
        return render_template('index.html')

    # Lógica de POST (quando um arquivo é enviado)
    if 'file' not in request.files or request.files['file'].filename == '':
        return render_template('index.html', erro_upload="Nenhum arquivo selecionado.")

    file = request.files['file']
    # ... (Aqui entra todo o resto da sua lógica de análise que já tínhamos no app.py anterior)
    # ... (Chamar OCR, analisar, salvar no Supabase, etc.)
    
    # Exemplo de retorno:
    resultado_final = {"status": "SEGURO", "erros": [], "hash": "exemplo123", "texto": "Exemplo de texto"}
    return render_template('index.html', resultado=resultado_final)

# =================================================================================
# --- ROTAS DE API PARA LOGIN/CADASTRO ---
# =================================================================================

@app.route('/signup', methods=['POST'])
def signup():
    """ API para cadastrar um novo usuário. """
    # (A lógica de cadastro que já criamos permanece aqui)
    try:
        data = request.get_json()
        email, password = data.get('email'), data.get('password')
        supabase.auth.sign_up({"email": email, "password": password})
        return jsonify({'message': 'Usuário cadastrado com sucesso!'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/handle_login', methods=['POST']) # Renomeado para não conflitar com a página /login
def handle_login_post():
    """ API para autenticar um usuário existente. """
    # (A lógica de login que já criamos permanece aqui)
    try:
        data = request.get_json()
        email, password = data.get('email'), data.get('password')
        supabase.auth.sign_in_with_password({"email": email, "password": password})
        return jsonify({'message': 'Login realizado com sucesso!'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Início do Servidor ---
if __name__ == '__main__':
    app.run(debug=True)
