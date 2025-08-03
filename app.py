from flask import Flask, request, jsonify, render_template
import os
import hashlib
import requests
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

documentos = {}

def extrair_texto_ocr(file_path):
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                'https://api.ocr.space/parse/image',
                files={'filename': f},
                data={
                    'language': 'por',
                    'isOverlayRequired': False,
                    'OCREngine': 2,
                    'apikey': os.getenv('OCR_SPACE_API_KEY')
                }
            )
        resultado = response.json()
        if not resultado.get('IsErroredOnProcessing', True):
            return resultado['ParsedResults'][0]['ParsedText'].strip(), None
        return "", resultado.get("ErrorMessage", "Erro desconhecido no OCR")
    except Exception as e:
        return "", str(e)

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

    try:
        # Salvar temporariamente
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # OCR
        texto, erro = extrair_texto_ocr(file_path)
        os.remove(file_path)

        if erro:
            return jsonify({"erro": erro}), 500

        # Hash como ID
        hash_id = hashlib.sha256(texto.encode()).hexdigest()
        documentos[hash_id] = texto

        return jsonify({
            "hash_id": hash_id,
            "texto": texto
        })

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/documento/<hash_id>')
def get_documento(hash_id):
    texto = documentos.get(hash_id)
    if texto:
        return jsonify({"texto": texto})
    return jsonify({"erro": "Documento não encontrado"}), 404

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'False') == 'True')
