# app.py (Versão focada em Autenticação)

import os
from flask import Flask, request, render_template, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# --- Configurações e Conexões ---
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

# =================================================================================
# --- ROTAS DE PÁGINAS E AUTENTICAÇÃO ---
# =================================================================================

@app.route('/')
def home():
    """ Rota principal que redireciona para a página de login. """
    return render_template('Login.html')

@app.route('/login', methods=['GET'])
def login_page():
    """ Rota para exibir a página de login. """
    return render_template('Login.html')
    
@app.route('/signup', methods=['POST'])
def signup():
    """ API para cadastrar um novo usuário. """
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({'error': 'E-mail e senha são obrigatórios.'}), 400

        user_response = supabase.auth.sign_up({
            "email": email,
            "password": password,
        })
        
        # Verifica se o usuário foi criado (pode já existir)
        if user_response.user:
             return jsonify({'message': 'Usuário cadastrado com sucesso! Agora você pode fazer o login.'}), 201
        else:
             return jsonify({'error': 'Este e-mail já está em uso.'}), 409

    except Exception as e:
        error_message = str(e)
        return jsonify({'error': error_message}), 500


@app.route('/login', methods=['POST'])
def handle_login_post():
    """ API para autenticar um usuário existente. """
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({'error': 'E-mail e senha são obrigatórios.'}), 400
        
        # Tenta fazer o login
        data = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        # data.user contém as informações do usuário logado
        return jsonify({
            'message': f'Login realizado com sucesso! Bem-vindo, {data.user.email}!',
            'user_id': data.user.id,
            'access_token': data.session.access_token
        }), 200

    except Exception as e:
        error_message = str(e)
        if "Invalid login credentials" in error_message:
            return jsonify({'error': 'E-mail ou senha inválidos.'}), 401
        return jsonify({'error': error_message}), 500


if __name__ == '__main__':
    app.run(debug=True)
