import os
import hashlib
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from supabase import create_client, Client
from dotenv import load_dotenv
import requests

# Carrega variáveis de ambiente
load_dotenv()

# Configurações
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

# Configura Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configura OCR.Space
OCR_API_KEY = os.getenv('OCR_SPACE_API_KEY')
OCR_ENDPOINT = 'https://api.ocr.space/parse/image'

# Verifica se a extensão do arquivo é permitida
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Gera hash SHA-256 do arquivo
def generate_file_hash(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

# Extrai texto do PDF usando OCR.Space
def extract_text_from_pdf(filepath):
    with open(filepath, 'rb') as file:
        response = requests.post(
            OCR_ENDPOINT,
            files={'file': file},
            data={
                'apikey': OCR_API_KEY,
                'language': 'por',
                'isOverlayRequired': False,
                'OCREngine': 2
            }
        )
    
    if response.status_code != 200:
        raise Exception(f"Erro no OCR: {response.json().get('ErrorMessage', 'Erro desconhecido')}")
    
    parsed_data = response.json()
    if parsed_data.get('IsErroredOnProcessing', False):
        raise Exception(f"Erro no OCR: {parsed_data.get('ErrorMessage')}")
    
    parsed_text = parsed_data.get('ParsedResults', [{}])[0].get('ParsedText', '')
    return parsed_text.strip()

# Rota para upload e análise de PDF
@app.route('/analisar-pdf', methods=['POST'])
def upload_pdf():
    if 'arquivo' not in request.files:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400
    
    file = request.files['arquivo']
    if file.filename == '':
        return jsonify({'erro': 'Nome de arquivo inválido'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'erro': 'Apenas arquivos PDF são permitidos'}), 400
    
    # Salva o arquivo temporariamente
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    try:
        # Gera hash do arquivo
        file_hash = generate_file_hash(filepath)
        
        # Verifica se já existe no banco de dados
        existing_analysis = supabase.table('analises') \
            .select('*') \
            .eq('hash_sha256', file_hash) \
            .execute()
        
        if existing_analysis.data:
            os.remove(filepath)
            return jsonify({
                'mensagem': 'Arquivo já analisado anteriormente',
                'analise': existing_analysis.data[0]
            }), 200
        
        # Extrai texto do PDF
        extracted_text = extract_text_from_pdf(filepath)
        
        # Define status de confiabilidade (simplificado)
        status = 'confiavel'
        erros_detectados = []
        
        if not extracted_text:
            status = 'suspeito'
            erros_detectados.append({'codigo': 'TEXTO_VAZIO', 'mensagem': 'Nenhum texto extraído'})
        elif len(extracted_text) < 50:
            status = 'suspeito'
            erros_detectados.append({'codigo': 'TEXTO_CURTO', 'mensagem': 'Texto extraído muito pequeno'})
        
        # Insere no Supabase
        new_analysis = supabase.table('analises') \
            .insert({
                'hash_sha256': file_hash,
                'status': status,
                'erros_detectados': erros_detectados,
                'texto_extraido': extracted_text
            }) \
            .execute()
        
        os.remove(filepath)
        return jsonify({
            'mensagem': 'Análise concluída com sucesso',
            'analise': new_analysis.data[0]
        }), 200
    
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'erro': str(e)}), 500

# Rota para consultar análise por hash
@app.route('/analise/<hash>', methods=['GET'])
def get_analysis(hash):
    try:
        analysis = supabase.table('analises') \
            .select('*') \
            .eq('hash_sha256', hash) \
            .execute()
        
        if not analysis.data:
            return jsonify({'erro': 'Análise não encontrada'}), 404
        
        return jsonify(analysis.data[0]), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

# Cria a pasta de uploads se não existir
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if __name__ == '__main__':
    app.run(debug=True)
