# app.py (com rotas de autenticação)

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

# ... (TODAS AS SUAS FUNÇÕES EXISTENTES: analisar_texto_completo, extrair_texto_ocr_space, etc. PERMANECEM AQUI) ...
# Para economizar espaço, elas foram omitidas, mas devem continuar no seu código.

@app.route('/')
def index():
    # ... (Sua rota principal do analisador)
    return render_template('index.html')

@app.route('/analisar', methods=['POST'])
def analisar():
    # ... (Sua rota de análise de documentos)
    pass # Adicione o conteúdo da sua rota de análise aqui

# =================================================================================
# --- NOVAS ROTAS DE AUTENTICAÇÃO ---
# =================================================================================

@app.route('/signup', methods=['POST'])
def signup():
    """Rota para cadastrar um novo usuário."""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({'error': 'E-mail e senha são obrigatórios.'}), 400

        # Usa o método de autenticação do Supabase para criar o usuário
        user = supabase.auth.sign_up({
            "email": email,
            "password": password,
        })
        
        return jsonify({'message': 'Usuário cadastrado com sucesso! Verifique seu e-mail para confirmação.'}), 201

    except Exception as e:
        # Pega erros específicos do Supabase, como "User already registered"
        error_message = str(e)
        if "User already registered" in error_message:
            return jsonify({'error': 'Este e-mail já está cadastrado.'}), 409
        return jsonify({'error': error_message}), 500


@app.route('/login', methods=['POST'])
def login():
    """Rota para autenticar um usuário existente."""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({'error': 'E-mail e senha são obrigatórios.'}), 400
        
        # Usa o método de autenticação do Supabase para fazer o login
        data = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        # Se o login for bem-sucedido, você pode redirecionar ou enviar uma mensagem de sucesso
        # O 'data' contém o token de acesso que seria usado em uma aplicação mais complexa
        return jsonify({'message': 'Login realizado com sucesso!'}), 200

    except Exception as e:
        error_message = str(e)
        if "Invalid login credentials" in error_message:
            return jsonify({'error': 'E-mail ou senha inválidos.'}), 401
        return jsonify({'error': error_message}), 500


if __name__ == '__main__':
    app.run(debug=True)
