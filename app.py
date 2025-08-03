from flask import Flask, request, jsonify, render_template
import hashlib
import requests
import os
from datetime import datetime
import psycopg2
from werkzeug.utils import secure_filename
from psycopg2 import OperationalError

app = Flask(__name__)

# Configurações
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
BUCKET_NAME = 'armazenamento'

# PostgreSQL (usando Supabase)
DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME')}"

def get_db_connection():
    try:
        return psycopg2.connect(DB_URL)
    except OperationalError as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        raise

def calcular_hash_sha256(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(4096):
            sha256.update(chunk)
    return sha256.hexdigest()

def salvar_no_storage(nome_arquivo, file_path):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    with open(file_path, 'rb') as file_data:
        response = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{nome_arquivo}",
            headers=headers,
            files={"file": (nome_arquivo, file_data)}
        )
    if response.status_code not in [200, 201]:
        raise Exception(f"Erro ao salvar no Supabase Storage: {response.text}")
    return f"{BUCKET_NAME}/{nome_arquivo}"

def extrair_texto_ocr(file_path):
    try:
        response = requests.post(
            'https://api.ocr.space/parse/image',
            files={'file': open(file_path, 'rb')},
            data={'apikey': os.getenv('OCR_SPACE_API_KEY'), 'language': 'por'}
        )
        resultado = response.json()
        if not resultado.get('IsErroredOnProcessing', True):
            return resultado['ParsedResults'][0]['ParsedText'].strip(), None
        return "", resultado.get("ErrorMessage", "Erro desconhecido no OCR")
    except Exception as e:
        return "", str(e)

def inserir_documento(hash_sha256, nome_arquivo, caminho_storage):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM documentos_oficiais WHERE hash_sha256 = %s", (hash_sha256,))
        if cursor.fetchone():
            return False
        cursor.execute("""
            INSERT INTO documentos_oficiais (nome_arquivo, caminho_storage, hash_sha256, created_at)
            VALUES (%s, %s, %s, %s)
        """, (nome_arquivo, caminho_storage, hash_sha256, datetime.now()))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao inserir documento: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'erro': 'Nome de arquivo inválido'}), 400

    try:
        filename = secure_filename(file.filename)
        local_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(local_path)
        hash_sha256 = calcular_hash_sha256(local_path)
        filename_com_hash = f"{hash_sha256}_{filename}"

        caminho_storage = salvar_no_storage(filename_com_hash, local_path)
        novo = inserir_documento(hash_sha256, filename, caminho_storage)

        texto_extraido, erro_ocr = extrair_texto_ocr(local_path)
        status = "sucesso" if not erro_ocr else "falha"

        return jsonify({
            "status": status,
            "hash": hash_sha256,
            "nome_arquivo": filename,
            "texto_extraido": texto_extraido,
            "erro_ocr": erro_ocr,
            "caminho_storage": caminho_storage
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        if 'local_path' in locals() and os.path.exists(local_path):
            os.remove(local_path)

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'False') == 'True')
