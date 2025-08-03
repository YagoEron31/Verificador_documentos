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
# --- FUNÇÕES DE LÓGICA (Análise, OCR, etc.) ---
# =================================================================================

def analisar_texto_completo(texto):
    # (Sua lógica de análise permanece aqui)
    erros_detectados = []
    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados}

def extrair_texto_ocr_space(file_bytes, filename):
    # (Sua lógica de extração de texto via API permanece aqui)
    return "Texto extraído com sucesso"

# =================================================================================
# --- ROTAS PARA SERVIR AS PÁGINAS HTML ---
# =================================================================================

@app.route('/')
def home():
    """ Rota para a página inicial (landing page). """
    return render_template('Tela_Inicial') 

@app.route('/login')
def login_page():
    """ Rota para exibir a página de login. """
    return render_template('Login')

@app.route('/verificador', methods=['GET', 'POST'])
def verificador_page():
    """ Rota para a ferramenta de análise de documentos. """
    # (A lógica completa do seu analisador fica aqui)
    if request.method == 'GET':
        return render_template('Tela_Verificacao')
    # ... resto da lógica de POST
    return render_template('Tela_Verificacao')

@app.route('/faq')
def faq_page():
    return render_template('Perguntas_Frequentes')

# --- NOVA ROTA ADICIONADA ---
@app.route('/transparencia')
def transparencia_page():
    """ Rota para o Portal de Transparência. """
    return render_template('Portal_Transparencia')
# -----------------------------

# =================================================================================
# --- ROTAS DE API PARA LOGIN/CADASTRO ---
# =================================================================================

@app.route('/signup', methods=['POST'])
def signup():
    # ... (Sua rota de cadastro de usuário) ...
    pass

@app.route('/handle_login', methods=['POST'])
def handle_login_post():
    # ... (Sua rota que processa o envio do formulário de login) ...
    pass

# --- Início do Servidor ---
if __name__ == '__main__':
    app.run(debug=True)
