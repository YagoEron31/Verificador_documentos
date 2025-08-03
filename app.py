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
    if request.method == 'GET':
        # CORREÇÃO: Usando o nome exato do seu arquivo
        return render_template('Tela_Verificacao')

    # Lógica de POST (quando um arquivo é enviado para análise)
    try:
        if 'file' not in request.files or request.files['file'].filename == '':
            return render_template('Tela_Verificacao', erro_upload="Nenhum arquivo selecionado.")
        
        file = request.files['file']
        
        # ... (código de processamento do arquivo)
        
        resultado_final = {"status": "SEGURO", "erros": [], "hash": "exemplo123", "texto": "Exemplo de texto"}
        return render_template('Tela_Verificacao', resultado=resultado_final)

    except Exception as e:
        return render_template('Tela_Verificacao', resultado={"status": "ERRO", "erros": [f"Erro inesperado: {e}"]})

# --- Rotas Adicionais para suas outras páginas ---
@app.route('/faq')
def faq_page():
    return render_template('Perguntas_Frequentes')

@app.route('/transparencia')
def transparencia_page():
    return render_template('Portal_Transparencia')


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
