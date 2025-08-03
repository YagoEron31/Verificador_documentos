import os
import re
import hashlib
import io
import json
import logging
import requests
from datetime import datetime
from flask import Flask, request, render_template, jsonify, redirect, url_for, flash
from supabase import create_client, Client
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Configuração básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

# --- Configurações da Aplicação ---
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'segredo-desenvolvimento')

# Configurações de upload
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'png', 'jpg', 'jpeg'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Conexão com Serviços Externos ---
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# Conexão "preguiçosa" com o Supabase
_supabase_client = None

def get_supabase_client():
    """Cria e reutiliza uma conexão com o Supabase."""
    global _supabase_client
    if _supabase_client is None:
        try:
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            # Testa a conexão
            _supabase_client.from_('documentos').select('*').limit(1).execute()
            logger.info("Conexão com Supabase estabelecida com sucesso")
        except Exception as e:
            logger.error(f"Erro ao conectar ao Supabase: {str(e)}")
            raise
    return _supabase_client

# --- Funções de Apoio ---
def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_with_ocr(file_path):
    """Extrai texto de um documento usando OCR.space API."""
    try:
        payload = {
            'apikey': OCR_SPACE_API_KEY,
            'language': 'por',
            'isOverlayRequired': False,
            'filetype': 'PDF' if file_path.endswith('.pdf') else 'JPG'
        }
        
        with open(file_path, 'rb') as f:
            response = requests.post(
                'https://api.ocr.space/parse/image',
                files={'file': f},
                data=payload,
                timeout=30
            )
        
        result = response.json()
        if response.status_code == 200 and result['IsErroredOnProcessing'] is False:
            return ' '.join([parsed_text['ParsedText'] 
                           for parsed_text in result['ParsedResults']])
        else:
            logger.error(f"Erro no OCR: {result.get('ErrorMessage', 'Erro desconhecido')}")
            return None
    except Exception as e:
        logger.error(f"Falha ao processar OCR: {str(e)}")
        return None

def analyze_document_text(text):
    """Analisa o texto extraído em busca de padrões suspeitos."""
    analysis = {
        'suspicious_patterns': [],
        'keywords_found': [],
        'metadata_matches': True
    }
    
    # Padrões suspeitos comuns em documentos falsificados
    suspicious_patterns = {
        'data_alterada': r'data\s*[.:]\s*\d{2}/\d{2}/\d{4}.*\d{2}/\d{2}/\d{4}',
        'caracteres_inconsistentes': r'[^\w\s.,;:!?@#$%&*()\-+=\/\\]',
        'espacos_inconsistentes': r'\s{3,}'
    }
    
    # Palavras-chave importantes que devem estar presentes
    required_keywords = [
        'prefeitura municipal de apodi',
        'estado do rio grande do norte',
        'documento oficial'
    ]
    
    # Verifica padrões suspeitos
    for name, pattern in suspicious_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            analysis['suspicious_patterns'].append(name)
    
    # Verifica palavras-chave obrigatórias
    for keyword in required_keywords:
        if keyword.lower() in text.lower():
            analysis['keywords_found'].append(keyword)
        else:
            analysis['metadata_matches'] = False
    
    return analysis

def generate_document_hash(text):
    """Gera um hash único para o conteúdo do documento."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

# --- Rotas da Aplicação ---
@app.route('/')
def home():
    """Rota para a página inicial."""
    return render_template('inicial.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Rota para a página de login."""
    if request.method == 'POST':
        # Lógica de autenticação aqui
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            supabase = get_supabase_client()
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if not response.user:
                flash('Credenciais inválidas', 'error')
                return redirect(url_for('login'))
            
            flash('Login realizado com sucesso', 'success')
            return redirect(url_for('verificador'))
            
        except Exception as e:
            logger.error(f"Erro no login: {str(e)}")
            flash('Erro ao realizar login', 'error')
    
    return render_template('login.html')

@app.route('/verificador', methods=['GET', 'POST'])
def verificador():
    """Rota principal para verificação de documentos."""
    if request.method == 'GET':
        return render_template('verificação.html')
    
    # Processamento de arquivo enviado
    if 'documento' not in request.files:
        flash('Nenhum arquivo enviado', 'error')
        return redirect(url_for('verificador'))
    
    file = request.files['documento']
    if file.filename == '':
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('verificador'))
    
    if not allowed_file(file.filename):
        flash('Tipo de arquivo não permitido', 'error')
        return redirect(url_for('verificador'))
    
    try:
        # Salva o arquivo temporariamente
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Processa o documento
        text = extract_text_with_ocr(filepath)
        if not text:
            flash('Falha ao extrair texto do documento', 'error')
            return redirect(url_for('verificador'))
        
        # Analisa o documento
        analysis = analyze_document_text(text)
        document_hash = generate_document_hash(text)
        
        # Registra no banco de dados
        supabase = get_supabase_client()
        supabase.from_('documentos').insert({
            'nome_arquivo': filename,
            'hash_documento': document_hash,
            'data_verificacao': datetime.now().isoformat(),
            'resultado_analise': json.dumps(analysis),
            'texto_extraido': text[:10000]  # Limita o tamanho
        }).execute()
        
        # Prepara resultado para exibição
        is_valid = len(analysis['suspicious_patterns']) == 0 and analysis['metadata_matches']
        
        return render_template('verificação.html', 
                            resultado={
                                'valido': is_valid,
                                'hash': document_hash,
                                'analise': analysis,
                                'texto_amostra': text[:500] + '...' if len(text) > 500 else text
                            })
    
    except Exception as e:
        logger.error(f"Erro ao processar documento: {str(e)}")
        flash('Erro ao processar documento', 'error')
        return redirect(url_for('verificador'))

@app.route('/transparencia')
def transparencia():
    """Rota para a página de transparência."""
    try:
        supabase = get_supabase_client()
        documentos = supabase.from_('documentos').select('*').order('data_verificacao', desc=True).limit(100).execute()
        return render_template('transparencia.html', documentos=documentos.data)
    except Exception as e:
        logger.error(f"Erro ao buscar dados de transparência: {str(e)}")
        return render_template('transparencia.html', documentos=[])

@app.route('/api/verificar', methods=['POST'])
def api_verificar():
    """Endpoint API para verificação de documentos."""
    try:
        if 'documento' not in request.files:
            return jsonify({'erro': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['documento']
        if file.filename == '':
            return jsonify({'erro': 'Nenhum arquivo selecionado'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'erro': 'Tipo de arquivo não permitido'}), 400
        
        # Salva o arquivo temporariamente
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Processa o documento
        text = extract_text_with_ocr(filepath)
        if not text:
            return jsonify({'erro': 'Falha ao extrair texto do documento'}), 500
        
        # Analisa o documento
        analysis = analyze_document_text(text)
        document_hash = generate_document_hash(text)
        
        # Retorna o resultado
        return jsonify({
            'sucesso': True,
            'hash': document_hash,
            'valido': len(analysis['suspicious_patterns']) == 0 and analysis['metadata_matches'],
            'analise': analysis
        })
    
    except Exception as e:
        logger.error(f"Erro na API: {str(e)}")
        return jsonify({'erro': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
