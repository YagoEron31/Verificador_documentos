import os
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# --- Configurações e Conexões ---
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
# Adicione a chave da API de OCR se for usar o analisador
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

# =================================================================================
# --- ROTAS PARA SERVIR AS PÁGINAS HTML ---
# =================================================================================

@app.route('/')
def home():
    return render_template('Tela_Inicial.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/verificador')
def verificador_page():
    # Aqui entraria a lógica da sua ferramenta de análise
    return render_template('Tela_Verificacao.html')
    
@app.route('/transparencia')
def transparencia_page():
    # Aqui entraria a lógica para buscar dados do banco e listar
    return render_template('Portal_Transparencia.html')

# =================================================================================
# --- ROTAS DE API PARA LOGIN E CADASTRO (AGORA COM LÓGICA) ---
# =================================================================================

@app.route('/signup', methods=['POST'])
def signup():
    """ API para cadastrar um novo usuário. """
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({'error': 'E-mail e senha são obrigatórios.'}), 400

        # Usa o método de autenticação do Supabase para criar o usuário
        user_response = supabase.auth.sign_up({ "email": email, "password": password })
        
        if user_response.user:
             return jsonify({'message': 'Usuário cadastrado com sucesso! Agora você pode fazer o login.'}), 201
        else:
             # Isso cobre casos em que o Supabase não retorna um usuário, como e-mail já existente
             return jsonify({'error': 'Não foi possível criar o usuário. O e-mail pode já estar em uso.'}), 409

    except Exception as e:
        # Pega erros da API do Supabase
        return jsonify({'error': str(e)}), 500


@app.route('/handle_login', methods=['POST'])
def handle_login_post():
    """ API para autenticar um usuário existente. """
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({'error': 'E-mail e senha são obrigatórios.'}), 400
        
        # Tenta fazer o login usando o Supabase Auth
        data = supabase.auth.sign_in_with_password({ "email": email, "password": password })
        
        # Se o login for bem-sucedido, retorna uma mensagem de sucesso
        return jsonify({
            'message': f'Login realizado com sucesso! Bem-vindo, {data.user.email}!',
        }), 200

    except Exception as e:
        error_message = str(e)
        if "Invalid login credentials" in error_message:
            return jsonify({'error': 'E-mail ou senha inválidos.'}), 401
        return jsonify({'error': f'Ocorreu um erro: {error_message}'}), 500

# --- Início do Servidor ---
if __name__ == '__main__':
    app.run(debug=True)
