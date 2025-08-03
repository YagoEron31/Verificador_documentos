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
# (Estas funções não mudam)
# =================================================================================

def analisar_texto_completo(texto):
    """Executa todas as regras de verificação no texto extraído."""
    erros_detectados = []
    texto_em_minusculo = texto.lower()

    # Sua lógica de análise detalhada
    PALAVRAS_SUSPEITAS = ["dispensa de licitacao", "carater de urgencia", "pagamento retroativo", "inexigibilidade de licitacao"]
    for palavra in PALAVRAS_SUSPEITAS:
        if palavra in texto_em_minusculo:
            erros_detectados.append(f"Alerta de Termo Sensível: A expressão '{palavra}' foi encontrada.")

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
# --- ROTAS DA APLICAÇÃO ---
# =================================================================================

@app.route('/', methods=['GET', 'POST'])
def index():
    """ Rota principal para a ferramenta de análise de documentos (usa index.html). """
    if request.method == 'GET':
        # Simplesmente mostra a página de upload
        return render_template('index.html')

    # Lógica de POST (quando um arquivo é enviado para análise)
    if 'file' not in request.files or request.files['file'].filename == '':
        return render_template('index.html', erro_upload="Nenhum arquivo selecionado.")

    file = request.files['file']
    filename = secure_filename(file.filename)
    file_bytes = file.read()

    try:
        # 1. Calcula o hash do ARQUIVO para checar duplicidade
        hash_arquivo = hashlib.sha256(file_bytes).hexdigest()

        # 2. Verifica se o ARQUIVO já foi processado (lógica de cache)
        data, count = supabase.table('analises').select('*').eq('hash_arquivo', hash_arquivo).execute()
        
        if len(data[1]) > 0:
            print("Documento já processado. Retornando do cache.")
            return render_template('index.html', resultado=data[1][0])

        # 3. Se é um arquivo novo, processa tudo
        print("Arquivo novo, iniciando processamento completo.")
        
        texto_extraido = extrair_texto_ocr_space(file_bytes, filename)
        if not texto_extraido.strip():
            raise ValueError("Nenhum texto pôde ser extraído do documento.")

        analise = analisar_texto_completo(texto_extraido)
        hash_conteudo = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()

        # 4. Salva o arquivo original no Supabase Storage
        caminho_storage = f"documentos/{hash_arquivo}_{filename}"
        supabase.storage.from_("arquivos").upload(
            path=caminho_storage,
            file=file_bytes,
            file_options={"content-type": file.content_type}
        )

        # 5. Salva o resultado completo na tabela 'analises'
        resultado_final = {
            "nome_arquivo": filename, "hash_arquivo": hash_arquivo, "hash_conteudo": hash_conteudo,
            "status": analise['status'], "erros_detectados": analise['erros'],
            "texto_extraido": texto_extraido, "caminho_storage": caminho_storage
        }
        supabase.table('analises').insert(resultado_final).execute()
        print("Nova análise salva no Supabase.")
        
        return render_template('index.html', resultado=resultado_final)

    except Exception as e:
        return render_template('index.html', resultado={"status": "ERRO", "erros": [f"Erro inesperado: {e}"]})


@app.route('/login', methods=['GET'])
def login_page():
    """ Rota para exibir a página de login. """
    return render_template('login.html')

# Adicione aqui outras rotas para outras páginas, se necessário
# Exemplo para a sua landing page, caso queira mantê-la:
# @app.route('/sobre')
# def sobre_page():
#     return render_template('sobre.html') # Você precisaria renomear o arquivo da landing page

# =================================================================================
# --- ROTAS DE API PARA LOGIN/CADASTRO ---
# =================================================================================

@app.route('/signup', methods=['POST'])
def signup():
    """ API para cadastrar um novo usuário. """
    try:
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
        data = request.get_json()
        email, password = data.get('email'), data.get('password')
        supabase.auth.sign_in_with_password({"email": email, "password": password})
        return jsonify({'message': 'Login realizado com sucesso!'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Início do Servidor ---
if __name__ == '__main__':
    app.run(debug=True)
