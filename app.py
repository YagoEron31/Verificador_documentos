from flask import Flask, request, jsonify, send_from_directory, render_template
import hashlib
import requests
import os
from datetime import datetime
import psycopg2
from werkzeug.utils import secure_filename

# Configurações
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')  # já está no Render
UPLOAD_FOLDER = 'uploads'
BUCKET_NAME = 'armazenamento'

# Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# PostgreSQL
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", 5432)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Cria pasta se não existir
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def calcular_hash_sha256(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(4096):
            sha256.update(chunk)
    return sha256.hexdigest()


def salvar_no_storage(nome_arquivo, file_path):
    import requests

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


def inserir_documento(hash_sha256, nome_arquivo, caminho_storage):
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM documentos_oficiais WHERE hash_sha256 = %s", (hash_sha256,))
        if cursor.fetchone():
            return False  # Já existe

        cursor.execute("""
            INSERT INTO documentos_oficiais (nome_arquivo, caminho_storage, hash_sha256, created_at)
            VALUES (%s, %s, %s, %s)
        """, (nome_arquivo, caminho_storage, hash_sha256, datetime.now()))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Erro ao inserir documento: {e}")
        return False


def inserir_analise(hash_sha256, texto_extraido, status, erros, caminho_storage):
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
            INSERT INTO analises (hash_sha256, texto_extraido, status, erros_detectados, caminho_storage, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (hash_sha256, texto_extraido, status, erros, caminho_storage, datetime.now()))

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Erro ao inserir análise: {e}")


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

    # Nome novo com hash para evitar duplicatas
    filename_com_hash = f"{hash_sha256}_{filename}"

    try:
        # Salvar no storage
        caminho_storage = salvar_no_storage(filename_com_hash, local_path)

        # Salvar no banco se não existir
        novo = inserir_documento(hash_sha256, filename, caminho_storage)

        # OCR
        texto_extraido, erro_ocr = extrair_texto_ocr(local_path)

        status = "sucesso" if not erro_ocr else "falha"
        erros = None if not erro_ocr else str(erro_ocr)

        inserir_analise(hash_sha256, texto_extraido, status, erros, caminho_storage)

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


if __name__ == '__main__':
    app.run(debug=True)
