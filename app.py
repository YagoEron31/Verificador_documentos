import os
import re
import hashlib
from flask import Flask, request, render_template
from PIL import Image
import pytesseract
import fitz
import io

# --- LÓGICA INTELIGENTE DE CONFIGURAÇÃO DO TESSERACT ---
IS_ON_RENDER = os.environ.get('RENDER') == 'true'
if not IS_ON_RENDER:
    try:
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    except Exception as e:
        print(f"Erro ao configurar o caminho do Tesseract localmente: {e}")
# --------------------------------------------------------

# --- Configuração do Aplicativo e "Banco de Dados" Local ---
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
DB_FILE = "database_hashes.txt"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# ----------------------------------------------------

@app.route('/', methods=['GET', 'POST'])
def index():
    resultado_analise = None
    if request.method == 'POST':
        if 'file' not in request.files or request.files['file'].filename == '':
            return render_template('index.html', erro_upload="Nenhum arquivo selecionado.")
        
        file = request.files['file']
        
        if file:
            conteudo_arquivo = file.read()
            file.seek(0)

            hash_do_arquivo = hashlib.sha256(conteudo_arquivo).hexdigest()

            hashes_existentes = set()
            if os.path.exists(DB_FILE):
                with open(DB_FILE, 'r') as f:
                    hashes_existentes = set(line.strip() for line in f)
            
            if hash_do_arquivo in hashes_existentes:
                return render_template('index.html', resultado={
                    "status": "ERRO", 
                    "erros": [f"Este documento exato já foi analisado e cadastrado como seguro anteriormente."]
                })

            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            with open(filepath, 'wb') as f:
                f.write(conteudo_arquivo)

            try:
                texto_extraido = ""
                if filepath.lower().endswith('.pdf'):
                    with fitz.open(filepath) as doc:
                        for page in doc:
                            # AQUI ESTÁ A OTIMIZAÇÃO PARA O RENDER
                            pix = page.get_pixmap(dpi=150, colorspace="gray")
                            img_bytes = pix.tobytes("png") 
                            pil_img = Image.open(io.BytesIO(img_bytes))
                            texto_extraido += pytesseract.image_to_string(pil_img, lang='por') + "\n"
                else:
                    with Image.open(filepath) as img:
                        texto_extraido = pytesseract.image_to_string(img, lang='por')
                
                # O restante do código de análise continua igual...
                erros_detectados = []
                # ... (todas as regras de verificação) ...
                
                hash_sha256 = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()
                status = "SUSPEITO" if erros_detectados else "SEGURO"
                resultado_analise = {"status": status, "erros": erros_detectados, "hash": hash_sha256, "texto": texto_extraido}

                if status == "SEGURO":
                    with open(DB_FILE, 'a') as f:
                        f.write(hash_do_arquivo + '\n')

            except Exception as e:
                resultado_analise = {"status": "ERRO", "erros": [f"Não foi possível processar o arquivo: {e}"]}
            
            finally:
                os.remove(filepath)

    return render_template('index.html', resultado=resultado_analise)

if __name__ == '__main__':
    app.run(debug=True)
