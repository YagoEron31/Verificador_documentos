from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import hashlib
import requests
import os
import sqlite3
import re
from datetime import datetime
import logging
from werkzeug.utils import secure_filename

# Configuração básica
app = Flask(__name__)
CORS(app)  # Habilita CORS para todas as rotas

# Configurações
DATABASE = 'documentos.db'
UPLOAD_FOLDER = 'temp_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configuração de logs
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Banco de dados
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS documentos (
            id TEXT PRIMARY KEY,
            texto TEXT NOT NULL,
            status TEXT NOT NULL,
            erros TEXT,
            data_criacao TIMESTAMP
        )
    ''')
    return conn

# Funções de Análise de Texto
def validar_cpf(texto):
    cpfs = re.findall(r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}', texto)
    return len(cpfs) > 0

def validar_cnpj(texto):
    cnpjs = re.findall(r'\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}', texto)
    return len(cnpjs) > 0

def detectar_dados_sensiveis(texto):
    erros = []
    if re.search(r'\b\d{11}\b', texto):
        erros.append("Possível CPF não formatado")
    if re.search(r'\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b', texto):
        erros.append("Possível número de cartão de crédito")
    return erros if erros else None

def analisar_texto(texto):
    erros = []
    status = "válido"
    
    if len(texto) < 50:
        erros.append("Texto muito curto (mínimo 50 caracteres)")
        status = "inválido"
    
    if sensiveis := detectar_dados_sensiveis(texto):
        erros.extend(sensiveis)
        status = "inválido"
    
    tem_cpf = validar_cpf(texto)
    tem_cnpj = validar_cnpj(texto)
    
    if not tem_cpf and not tem_cnpj:
        erros.append("Nenhum CPF/CNPJ válido detectado")
        status = "suspeito"
    
    return {
        "status": status,
        "erros": erros,
        "tem_cpf": tem_cpf,
        "tem_cnpj": tem_cnpj
    }

# OCR
def extrair_texto_ocr(file_path):
    try:
        response = requests.post(
            'https://api.ocr.space/parse/image',
            files={'file': open(file_path, 'rb')},
            data={
                'apikey': os.getenv('OCR_SPACE_API_KEY'),
                'language': 'por',
                'isOverlayRequired': False
            },
            timeout=30
        )
        resultado = response.json()
        if not resultado.get('IsErroredOnProcessing', True):
            return resultado['ParsedResults'][0]['ParsedText'].strip()
        logger.error(f"Erro no OCR: {resultado.get('ErrorMessage')}")
        return None
    except Exception as e:
        logger.error(f"Erro na requisição OCR: {str(e)}")
        return None

# Rotas
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    logger.debug("Recebendo requisição de upload...")
    
    if 'file' not in request.files:
        logger.warning("Nenhum arquivo enviado")
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    file = request.files['file']
    if file.filename == '':
        logger.warning("Nome de arquivo vazio")
        return jsonify({"erro": "Nome de arquivo inválido"}), 400

    try:
        # Salvar arquivo temporário
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        logger.debug(f"Arquivo salvo temporariamente em: {file_path}")

        # Extrair texto
        texto = extrair_texto_ocr(file_path)
        os.remove(file_path)
        
        if not texto:
            logger.error("Falha ao extrair texto do arquivo")
            return jsonify({"erro": "Falha ao extrair texto"}), 500

        # Analisar texto
        analise = analisar_texto(texto)
        hash_id = hashlib.sha256(texto.encode()).hexdigest()

        # Salvar no banco
        conn = get_db()
        conn.execute(
            '''INSERT INTO documentos 
            (id, texto, status, erros, data_criacao) 
            VALUES (?, ?, ?, ?, ?)''',
            (hash_id, texto, analise['status'], 
             str(analise['erros']), datetime.now())
        )
        conn.commit()
        conn.close()
        logger.info(f"Documento salvo com ID: {hash_id}")

        return jsonify({
            "hash_id": hash_id,
            "texto": texto,
            "analise": analise
        })

    except Exception as e:
        logger.error(f"Erro no processamento: {str(e)}", exc_info=True)
        return jsonify({"erro": "Falha interna no servidor"}), 500

@app.route('/documento/<hash_id>', methods=['GET'])
def get_documento(hash_id):
    try:
        conn = get_db()
        doc = conn.execute(
            '''SELECT texto, status, erros 
            FROM documentos WHERE id = ?''', 
            (hash_id,)
        ).fetchone()
        conn.close()

        if doc:
            return jsonify({
                "texto": doc[0],
                "status": doc[1],
                "erros": eval(doc[2]) if doc[2] else []
            })
        return jsonify({"erro": "Documento não encontrado"}), 404
    except Exception as e:
        logger.error(f"Erro ao buscar documento: {str(e)}")
        return jsonify({"erro": "Falha interna"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
