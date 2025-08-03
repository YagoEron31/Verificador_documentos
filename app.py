from flask import Flask, request, jsonify, render_template
import hashlib
import os
from datetime import datetime
import psycopg2
from werkzeug.utils import secure_filename
import requests

# Configurações
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')  # no Render
UPLOAD_FOLDER = 'uploads'

# PostgreSQL
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", 5432)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def calcular_hash_sha256(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(4096):
            sha256.update(chunk)
    return sha256.hexdigest()


def extrair_texto_ocr(file_path):
    url = 'https://api.ocr.space/parse/image'
    with open(file_path, 'rb') as f:
        response = requests.post(
            url,
            files={'file': f},
            data={
                'apikey': OCR_SPACE_API_KEY,
                'language': 'por'
            }
        )
    resultado = response.json()
    if not resultado['IsErroredOnProcessing']:
        texto_extraido = resultado['ParsedResults'][0]['ParsedText']
        return texto_extraido.strip(), None
    else:
        return "", resultado.get("ErrorMessage")


def documento_ja_existe(hash_sha256):
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM documentos_oficiais WHERE hash_sha256 = %s", (hash_sha256,))
    existe = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return existe


def inserir_documento(hash_sha256, nome_arquivo, texto_extraido, status, erros):
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO documentos_oficiais 
            (nome_arquivo, hash_sha256, texto_extraido, status, erros_detectados, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (nome_arquivo, hash_sha256, texto_extraido, status, erros, datetime.now()))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Erro ao inserir documento: {e}")
        return False


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'erro': 'Nome de arquivo inválido'}), 400

    filename = secure_filename(file.filename)
    local_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(local_path)

    hash_sha256 = calcular_hash_sha256(local_path)

    if documento_ja_existe(hash_sha256):
        os.remove(local_path)
        return jsonify({'erro': 'Documento já existe no banco de dados', 'hash': hash_sha256}), 409

    texto_extraido, erro_ocr = extrair_texto_ocr(local_path)
    os.remove(local_path)  # Remove o arquivo local após extração

    status = "sucesso" if not erro_ocr else "falha"
    erros = None if not erro_ocr else str(erro_ocr)

    sucesso = inserir_documento(hash_sha256, filename, texto_extraido, status, erros)

    if not sucesso:
        return jsonify({"erro": "Erro ao salvar no banco de dados"}), 500

    return jsonify({
        "status": status,
        "hash": hash_sha256,
        "nome_arquivo": filename,
        "texto_extraido": texto_extraido,
        "erro_ocr": erro_ocr
    })


if __name__ == '__main__':
    app.run(debug=True)
