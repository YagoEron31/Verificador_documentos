import os
from flask import Flask, request, render_template, jsonify, redirect, url_for, flash
from supabase import create_client
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import logging
from datetime import datetime

# Configuração básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

# Configurações
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB
app.config['UPLOAD_FOLDER'] = 'tmp/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'png', 'jpg', 'jpeg'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Rotas Básicas com Tratamento de Erros ---

@app.route('/')
def home():
    """Rota principal que sempre renderiza a página inicial"""
    try:
        return render_template('inicial.html')
    except Exception as e:
        logger.error(f"Erro ao carregar página inicial: {str(e)}")
        return "<h1>Página Inicial</h1><p>Estamos com problemas técnicos. Tente novamente mais tarde.</p>", 500

@app.route('/verificador', methods=['GET', 'POST'])
def verificador():
    """Rota para verificação de documentos com feedback visual"""
    try:
        if request.method == 'GET':
            return render_template('verificação.html')
        
        # Verifica se o arquivo foi enviado
        if 'documento' not in request.files:
            flash('Nenhum arquivo enviado', 'error')
            return redirect(url_for('verificador'))
        
        file = request.files['documento']
        
        # Verifica se um arquivo foi selecionado
        if file.filename == '':
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(url_for('verificador'))
        
        # Verifica a extensão do arquivo
        if not allowed_file(file.filename):
            flash('Tipo de arquivo não permitido. Use PDF, JPG ou PNG.', 'error')
            return redirect(url_for('verificador'))
        
        # Simulação de processamento (substitua pela sua lógica real)
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Simula resultado (remova isso na implementação real)
        resultado_simulado = {
            'valido': True,
            'hash': 'a1b2c3d4e5f6' + hashlib.sha256(filename.encode()).hexdigest()[:20],
            'analise': {
                'suspicious_patterns': [],
                'keywords_found': ['Prefeitura de Apodi'],
                'metadata_matches': True
            },
            'texto_amostra': f"Documento simulado: {filename}\nEste é um conteúdo de exemplo."
        }
        
        flash('Documento processado com sucesso!', 'success')
        return render_template('verificação.html', resultado=resultado_simulado)
    
    except Exception as e:
        logger.error(f"Erro no verificador: {str(e)}")
        flash('Ocorreu um erro ao processar seu documento', 'error')
        return redirect(url_for('verificador'))

# --- Funções Auxiliares ---

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

if __name__ == '__main__':
    # Cria a pasta de uploads se não existir
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    app.run(host='0.0.0.0', port=5000, debug=True)
