from flask import Flask, request, jsonify, render_template
import hashlib
import requests
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)

# Configuração do SQLite (banco de dados simples)
DATABASE = 'documentos.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS documentos (
            id TEXT PRIMARY KEY,
            texto TEXT NOT NULL,
            data_criacao TIMESTAMP
        )
    ''')
    return conn

def extrair_texto_ocr(file_path):
    try:
        response = requests.post(
            'https://api.ocr.space/parse/image',
            files={'file': open(file_path, 'rb')},
            data={'apikey': os.getenv('OCR_SPACE_API_KEY'), 'language': 'por'}
        )
        resultado = response.json()
        if not resultado.get('IsErroredOnProcessing', True):
            return resultado['ParsedResults'][0]['ParsedText'].strip()
        return None
    except Exception as e:
        print(f"Erro no OCR: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"erro": "Nome de arquivo inválido"}), 400

    # Salvar temporariamente
    file_path = f"temp_{file.filename}"
    file.save(file_path)

    # Extrair texto
    texto = extrair_texto_ocr(file_path)
    os.remove(file_path)  # Limpar arquivo temporário

    if not texto:
        return jsonify({"erro": "Falha ao extrair texto"}), 500

    # Gerar hash como ID
    hash_id = hashlib.sha256(texto.encode()).hexdigest()

    # Salvar no banco de dados
    conn = get_db()
    conn.execute(
        "INSERT INTO documentos (id, texto, data_criacao) VALUES (?, ?, ?)",
        (hash_id, texto, datetime.now())
    )
    conn.commit()
    conn.close()

    return jsonify({
        "hash_id": hash_id,
        "texto": texto
    })

@app.route('/documento/<hash_id>')
def get_documento(hash_id):
    conn = get_db()
    documento = conn.execute(
        "SELECT texto FROM documentos WHERE id = ?", 
        (hash_id,)
    ).fetchone()
    conn.close()

    if documento:
        return jsonify({"texto": documento[0]})
    return jsonify({"erro": "Documento não encontrado"}), 404

if __name__ == '__main__':
    app.run(debug=True)
