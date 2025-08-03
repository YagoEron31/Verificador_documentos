from flask import Flask, request, jsonify, render_template
import hashlib
import requests
import os
from datetime import datetime

app = Flask(__name__)

# Dicionário para armazenar os textos (em memória)
documentos = {}

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
    documentos[hash_id] = texto

    return jsonify({
        "hash_id": hash_id,
        "texto": texto
    })

@app.route('/documento/<hash_id>')
def get_documento(hash_id):
    texto = documentos.get(hash_id)
    if texto:
        return jsonify({"texto": texto})
    return jsonify({"erro": "Documento não encontrado"}), 404

if __name__ == '__main__':
    app.run(debug=True)
