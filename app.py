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

app = Flask(__name__)
_supabase_client = None

# --- Conexão "Preguiçosa" (Otimizada) com o Supabase ---
def get_supabase_client():
    """Cria e retorna um cliente Supabase, reutilizando a conexão se já existir."""
    global _supabase_client
    if _supabase_client is None:
        print("Inicializando nova conexão com o Supabase...")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

# Define as extensões de arquivo permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =================================================================================
# --- MÓDULO DE ANÁLISE E OCR ---
# =================================================================================

def analisar_texto_completo(texto):
    """Executa todas as regras de verificação no texto extraído."""
    erros_detectados = []
    texto_em_minusculo = texto.lower()
    
    # Adicione aqui suas regras de análise detalhada
    PALAVRAS_SUSPEITAS = ["dispensa de licitacao", "carater de urgencia"]
    for palavra in PALAVRAS_SUSPEITAS:
        if palavra in texto_em_minusculo:
            erros_detectados.append(f"Alerta de Termo Sensível: '{palavra}'")
    
    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados}

def extrair_texto_ocr_space(file_bytes, filename):
    """Extrai texto de um arquivo usando a API do OCR.space."""
    url = "https://api.ocr.space/parse/image"
    payload = {'language': 'por', 'isOverlayRequired': 'false', 'OCREngine': 2}
    files = {'file': (filename, file_bytes)}
    headers = {'apikey': OCR_SPACE_API_KEY}
    response = requests.post(url, headers=headers, data=payload, files=files)
    response.raise_for_status()
    result = response.json()
    if result.get("IsErroredOnProcessing"):
        raise ValueError(result.get("ErrorMessage", ["Erro desconhecido no OCR."])[0])
    if not result.get("ParsedResults"):
        raise ValueError("Nenhum resultado de texto foi retornado pela API de OCR.")
    return result["ParsedResults"][0]["ParsedText"]

# =================================================================================
# --- ROTAS PARA SERVIR AS PÁGINAS HTML ---
# =================================================================================

@app.route('/')
def home():
    """ Rota para a página inicial (landing page). """
    return render_template('inicial.html')

@app.route('/login')
def login_page():
    """ Rota para exibir a página de login. """
    return render_template('login.html')

@app.route('/cadastro')
def cadastro_page():
    """ Rota para exibir a página de cadastro. """
    return render_template('cadastro.html')

@app.route('/verificador')
def verificador_page():
    """ Rota que SERVE a página HTML do verificador. """
    # CORREÇÃO: Usando o nome exato do seu arquivo
    return render_template('verificação.html')

@app.route('/transparencia')
def transparencia_page():
    """ Rota para o Portal de Transparência. """
    return render_template('transparencia.html')

@app.route('/faq')
def faq_page():
    """ Rota para a página de Perguntas Frequentes. """
    return render_template('perguntas.html')

# =================================================================================
# --- ROTAS DE API (LÓGICA) ---
# =================================================================================

@app.route('/analisar', methods=['POST'])
def analisar_documento_api():
    """ Rota de API que recebe o arquivo, analisa e retorna JSON. """
    if 'file' not in request.files or request.files['file'].filename == '':
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    file = request.files['file']
    
    if not allowed_file(file.filename):
        return jsonify({'erro': 'Formato de arquivo não suportado.'}), 400

    filename = secure_filename(file.filename)
    file_bytes = file.read()

    try:
        supabase = get_supabase_client()
        hash_arquivo = hashlib.sha256(file_bytes).hexdigest()

        data, count = supabase.table('analises').select('*').eq('hash_arquivo', hash_arquivo).execute()
        
        if len(data[1]) > 0:
            print("Documento já processado. Retornando do cache.")
            cached_result = data[1][0]
            cached_result['hash'] = cached_result.get('hash_conteudo')
            return jsonify(cached_result)

        print("Arquivo novo, iniciando processamento completo.")
        
        texto_extraido = extrair_texto_ocr_space(file_bytes, filename)
        if not texto_extraido.strip():
            raise ValueError("Nenhum texto pôde ser extraído do documento.")

        analise = analisar_texto_completo(texto_extraido)
        hash_conteudo = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()
        
        caminho_storage = f"documentos/{hash_arquivo}_{filename}"
        supabase.storage.from_("arquivos").upload(
            path=caminho_storage, file=file_bytes, file_options={"content-type": file.content_type}
        )
        
        resultado_final = {
            "nome_arquivo": filename, "hash_arquivo": hash_arquivo, "hash_conteudo": hash_conteudo,
            "status": analise['status'], "erros_detectados": analise['erros'],
            "texto_extraido": texto_extraido, "caminho_storage": caminho_storage
        }
        supabase.table('analises').insert(resultado_final).execute()
        print("Nova análise salva no Supabase.")
        
        # Adequando a resposta para o que o JavaScript espera
        resultado_final['hash'] = resultado_final.get('hash_conteudo')
        
        return jsonify(resultado_final)

    except Exception as e:
        return jsonify({"status": "ERRO", "erro": f"Erro inesperado: {e}"}), 500

@app.route('/signup', methods=['POST'])
def signup():
    """ API para cadastrar um novo usuário. """
    try:
        supabase = get_supabase_client()
        data = request.get_json()
        email, password = data.get('email'), data.get('password')
        supabase.auth.sign_up({"email": email, "password": password})
        return jsonify({'message': 'Usuário cadastrado com sucesso!'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/handle_login', methods=['POST'])
def handle_login_post():
    """ API para autenticar um usuário existente. """
    try:
        supabase = get_supabase_client()
        data = request.get_json()
        email, password = data.get('email'), data.get('password')
        session = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return jsonify({
            'message': 'Login realizado com sucesso!',
            'access_token': session.session.access_token
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Início do Servidor ---
if __name__ == '__main__':
    app.run(debug=True)
