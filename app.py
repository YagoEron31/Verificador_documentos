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
# (As lógicas devem ser preenchidas conforme a necessidade)
# =================================================================================

def analisar_texto_completo(texto):
    erros_detectados = []
    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados}

def extrair_texto_ocr_space(file_bytes, filename):
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
    # CORREÇÃO: Usando o nome 'login' em minúsculo, como você especificou.
    return render_template('login')

@app.route('/verificador', methods=['GET', 'POST'])
def verificador_page():
    """ Rota para a ferramenta de análise de documentos. """
    if request.method == 'GET':
        return render_template('Tela_Verificacao')
    
    # Lógica de POST...
    try:
        if 'file' not in request.files or request.files['file'].filename == '':
            return render_template('Tela_Verificacao', erro_upload="Nenhum arquivo selecionado.")
        
        file = request.files['file']
        resultado_final = {"status": "SEGURO", "erros": [], "hash": "exemplo123", "texto": "Exemplo de texto"}
        return render_template('Tela_Verificacao', resultado=resultado_final)
    except Exception as e:
        return render_template('Tela_Verificacao', resultado={"status": "ERRO", "erros": [f"Erro inesperado: {e}"]})

@app.route('/faq')
def faq_page():
    return render_template('Perguntas_Frequentes')

@app.route('/transparencia')
def transparencia_page():
    return render_template('Portal_Transparencia')

# =================================================================================
# --- ROTAS DE API PARA LOGIN/CADASTRO ---
# (As lógicas devem ser preenchidas conforme a necessidade)
# =================================================================================

# --- Início do Servidor ---
if __name__ == '__main__':
    app.run(debug=True)
