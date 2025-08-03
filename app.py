# app.py
import os
import re
import hashlib
import io
import json
import logging
import requests
from datetime import datetime
from flask import Flask, request, render_template, jsonify, redirect, url_for, flash, session
from supabase import create_client, Client
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# --- Configuração Inicial ---
# Configuração básica de logging para depuração
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente de um arquivo .env
load_dotenv()

app = Flask(__name__)
# Chave secreta para gerenciar sessões e mensagens flash
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'um-segredo-muito-forte-para-desenvolvimento')

# Configurações de upload de arquivos
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # Limite de 10MB
app.config['UPLOAD_FOLDER'] = os.path.join('/tmp', 'uploads_verificador')
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'png', 'jpg', 'jpeg'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Conexão com Serviços Externos ---
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Validação para garantir que as variáveis de ambiente essenciais foram carregadas
if not all([OCR_SPACE_API_KEY, SUPABASE_URL, SUPABASE_KEY]):
    logger.warning("Uma ou mais variáveis de ambiente (OCR, Supabase) não estão configuradas. A aplicação pode não funcionar corretamente.")

_supabase_client = None

def get_supabase_client():
    """Cria e reutiliza uma conexão com o Supabase de forma segura."""
    global _supabase_client
    if _supabase_client is None:
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
                # Testa a conexão para garantir que está funcionando
                _supabase_client.from_('documentos').select('id').limit(1).execute()
                logger.info("Conexão com Supabase estabelecida com sucesso.")
            except Exception as e:
                logger.error(f"Erro fatal ao conectar ao Supabase: {e}. Verifique as credenciais e a conexão de rede.")
                _supabase_client = None # Garante que não tentaremos usar um cliente inválido
        else:
            logger.error("As variáveis SUPABASE_URL e SUPABASE_KEY não estão definidas.")
    return _supabase_client

# --- Funções de Apoio ---
def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_with_ocr(file_bytes, filename):
    """Extrai texto de um arquivo em memória usando OCR.space API."""
    try:
        payload = {'apikey': OCR_SPACE_API_KEY, 'language': 'por'}
        response = requests.post(
            'https://api.ocr.space/parse/image',
            files={filename: file_bytes},
            data=payload,
            timeout=45  # Timeout aumentado para arquivos maiores
        )
        response.raise_for_status()
        result = response.json()

        if not result.get("IsErroredOnProcessing") and result.get("ParsedResults"):
            return result["ParsedResults"][0]["ParsedText"]
        else:
            error_message = result.get('ErrorMessage', ['Erro desconhecido no OCR.'])[0]
            logger.error(f"Erro na API do OCR: {error_message}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Falha de comunicação com a API do OCR: {e}")
        return None

def analyze_document_text(text):
    """Analisa o texto extraído em busca de padrões e palavras-chave."""
    analysis = {
        'erros': [],
        'score': 0,
        'realce': set()
    }
    text_lower = text.lower()

    # Padrões de alerta com pontuação
    padroes_alerta = {
        "Espaços múltiplos suspeitos": (r'\s{3,}', 10),
        "Possível alteração de data": (r'data\s*[:.]\s*\d{2}/\d{2}/\d{4}.*\d{2}/\d{2}/\d{4}', 50),
        "Termo 'dispensa de licitação'": (r'dispensa de licita[çc][ãa]o', 40),
        "Termo 'caráter de urgência'": (r'car[áa]ter de urg[êe]ncia', 40)
    }

    for motivo, (pattern, score) in padroes_alerta.items():
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            analysis['erros'].append(f"Padrão suspeito encontrado: {motivo}")
            analysis['score'] += score
            analysis['realce'].add(match.group(0))

    # Palavras-chave que deveriam existir
    required_keywords = ['prefeitura municipal', 'estado do rio grande do norte']
    for keyword in required_keywords:
        if keyword not in text_lower:
            analysis['erros'].append(f"Termo essencial ausente: '{keyword}'")
            analysis['score'] += 30

    analysis['realce'] = list(analysis['realce']) # Converte para lista
    return analysis

def generate_document_hash(text):
    """Gera um hash SHA-256 para o conteúdo do texto."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

# --- Rotas da Aplicação ---
@app.route('/')
def home():
    """Página inicial da aplicação."""
    return render_template('inicial.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login de usuários."""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        supabase = get_supabase_client()

        if not supabase:
            flash('Serviço de autenticação indisponível. Tente novamente mais tarde.', 'danger')
            return redirect(url_for('login'))

        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            session['user'] = res.user.id
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('verificador'))
        except Exception:
            flash('Email ou senha inválidos. Por favor, tente novamente.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Realiza o logout do usuário."""
    session.pop('user', None)
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

@app.route('/verificador', methods=['GET', 'POST'])
def verificador():
    """Rota principal para upload e verificação de documentos."""
    if 'user' not in session:
        flash('Você precisa estar logado para acessar esta página.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'documento' not in request.files or not request.files['documento'].filename:
            flash('Nenhum arquivo foi selecionado.', 'danger')
            return redirect(request.url)

        file = request.files['documento']
        if not allowed_file(file.filename):
            flash('Tipo de arquivo não permitido. Use PDF, PNG, ou JPG.', 'danger')
            return redirect(request.url)

        try:
            filename = secure_filename(file.filename)
            file_bytes = file.read()

            text = extract_text_with_ocr(file_bytes, filename)
            if not text:
                flash('Não foi possível extrair texto do documento. O arquivo pode estar corrompido ou ser uma imagem sem texto.', 'danger')
                return redirect(request.url)

            analysis = analyze_document_text(text)
            document_hash = generate_document_hash(text)

            supabase = get_supabase_client()
            if supabase:
                supabase.from_('documentos').insert({
                    'nome_arquivo': filename,
                    'hash_documento': document_hash,
                    'data_verificacao': datetime.now().isoformat(),
                    'resultado_analise': json.dumps(analysis),
                    'texto_extraido': text,
                    'user_id': session.get('user')
                }).execute()
            else:
                flash('A análise foi feita, mas não pôde ser salva no banco de dados.', 'warning')

            # Realce do texto
            texto_realcado = text
            palavras_para_realcar = sorted(analysis['realce'], key=len, reverse=True)
            for palavra in palavras_para_realcar:
                texto_realcado = re.sub(f"({re.escape(palavra)})", r"<mark>\1</mark>", texto_realcado, flags=re.IGNORECASE)

            resultado_final = {
                'valido': not analysis['erros'],
                'hash': document_hash,
                'analise': analysis,
                'texto_realcado': texto_realcado
            }
            return render_template('verificacao.html', resultado=resultado_final)

        except Exception as e:
            logger.error(f"Erro crítico ao processar o documento: {e}")
            flash(f'Ocorreu um erro inesperado ao processar o arquivo: {e}', 'danger')
            return redirect(request.url)

    return render_template('verificacao.html')

@app.route('/transparencia')
def transparencia():
    """Mostra os últimos documentos verificados por todos os usuários."""
    documentos_data = []
    supabase = get_supabase_client()
    if supabase:
        try:
            response = supabase.from_('documentos').select('*').order('data_verificacao', desc=True).limit(50).execute()
            documentos_data = response.data
        except Exception as e:
            logger.error(f"Erro ao buscar dados de transparência: {e}")
            flash('Não foi possível carregar os dados de transparência.', 'danger')
    else:
        flash('Serviço de banco de dados indisponível.', 'danger')

    return render_template('transparencia.html', documentos=documentos_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
