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

# --- Conexão "Preguiçosa" (Otimizada) com o Supabase ---
def get_supabase_client():
    """Cria e reutiliza uma conexão com o Supabase."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

# (Suas outras funções de análise, OCR, etc. permanecem aqui)
# ...

# =================================================================================
# --- ROTAS DA APLICAÇÃO ---
# =================================================================================

@app.route('/')
def home():
    """ Rota para a página inicial (landing page). """
    return render_template('inicial.html')

@app.route('/login')
def login_page():
    """ Rota para exibir a página de login. """
    return render_template('login.html')

@app.route('/verificador', methods=['GET', 'POST'])
def verificador_page():
    """ Rota para a ferramenta de análise de documentos. """
    if request.method == 'GET':
        return render_template('verificação.html')

    # ... (Toda a sua lógica de análise de POST permanece aqui)
    return render_template('verificação.html')

# ==========================================================
# --- AQUI ESTÁ A ÚNICA ADIÇÃO AO CÓDIGO ---
# ==========================================================
@app.route('/transparencia')
def transparencia_page():
    """ Rota para carregar a página de transparência. """
    return render_template('transparencia.html')
# ==========================================================

# ... (Suas outras rotas de API como /signup e /handle_login permanecem aqui) ...

if __name__ == '__main__':
    app.run(debug=True)
