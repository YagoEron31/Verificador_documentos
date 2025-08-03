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
# --- ROTAS PARA SERVIR AS PÁGINAS HTML ---
# =================================================================================

@app.route('/')
def home():
    """ Rota para a página inicial (landing page). """
    # CORREÇÃO: Usando o nome exato do seu arquivo
    return render_template('Tela_Inicial') 

@app.route('/login')
def login_page():
    """ Rota para exibir a página de login. """
    # CORREÇÃO: Usando o nome exato do seu arquivo
    return render_template('Login')

@app.route('/verificador', methods=['GET', 'POST'])
def verificador_page():
    """ Rota para a ferramenta de análise de documentos. """
    # CORREÇÃO: Usando o nome exato do seu arquivo
    if request.method == 'GET':
        return render_template('Tela_Verificacao')
    # ... Lógica de POST ...
    return render_template('Tela_Verificacao')
    
@app.route('/transparencia')
def transparencia_page():
    """ Rota para o Portal de Transparência. """
    # CORREÇÃO: Usando o nome exato do seu arquivo
    return render_template('Portal_Transparencia')

@app.route('/faq')
def faq_page():
    """ Rota para a página de Perguntas Frequentes. """
    # CORREÇÃO: Usando o nome exato do seu arquivo
    return render_template('Perguntas_Frequentes')

# =================================================================================
# --- ROTAS DE API (LÓGICA) ---
# (As lógicas de cadastro, login e análise devem ser adicionadas aqui)
# =================================================================================

# --- Início do Servidor ---
if __name__ == '__main__':
    app.run(debug=True)
