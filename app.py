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

# --- Configurações ---
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

app = Flask(__name__)
_supabase_client = None

# --- Conexão "Preguiçosa" com o Supabase ---
def get_supabase_client():
    """Cria e retorna um cliente Supabase, reutilizando a conexão se já existir."""
    global _supabase_client
    if _supabase_client is None:
        print("Inicializando nova conexão com o Supabase...")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

# =================================================================================
# --- ROTAS DA APLICAÇÃO ---
# =================================================================================

@app.route('/')
def home():
    return render_template('Tela_Inicial.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/verificador', methods=['GET', 'POST'])
def verificador_page():
    if request.method == 'GET':
        return render_template('Tela_Verificacao.html')

    if 'file' not in request.files or request.files['file'].filename == '':
        return render_template('Tela_Verificacao.html', erro_upload="Nenhum arquivo selecionado.")

    file = request.files['file']
    filename = secure_filename(file.filename)
    file_bytes = file.read()

    try:
        supabase = get_supabase_client() # Conecta ao Supabase apenas quando necessário
        
        # O resto da sua lógica de análise e salvamento continua aqui...
        # ...

        resultado_final = {"status": "SEGURO", "erros": [], "hash": "exemplo123", "texto": "Exemplo de texto"}
        return render_template('Tela_Verificacao.html', resultado=resultado_final)

    except Exception as e:
        return render_template('Tela_Verificacao.html', resultado={"status": "ERRO", "erros": [f"Erro inesperado: {e}"]})

# ... (outras rotas e funções)

if __name__ == '__main__':
    app.run(debug=True)
