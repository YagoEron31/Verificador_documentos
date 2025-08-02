import os
import re
import hashlib
import io

from flask import Flask, request, render_template, jsonify
from PIL import Image
import pytesseract
import fitz # PyMuPDF
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

IS_ON_RENDER = os.environ.get('RENDER') == 'true'
if not IS_ON_RENDER:
    try:
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    except Exception as e:
        print(f"Aviso: Não foi possível configurar o caminho do Tesseract localmente: {e}")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)

def extrair_texto_do_arquivo(file_bytes, filename):
    texto_extraido = ""
    if filename.lower().endswith('.pdf'):
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                # OTIMIZAÇÃO: Geramos a imagem em tons de cinza para economizar memória
                pix = page.get_pixmap(grayscale=True, dpi=150)
                img_bytes = pix.tobytes("png")
                pil_img = Image.open(io.BytesIO(img_bytes))
                texto_extraido += pytesseract.image_to_string(pil_img, lang='por') + "\n"
    else:
        pil_img = Image.open(io.BytesIO(file_bytes))
        texto_extraido = pytesseract.image_to_string(pil_img, lang='por')
    return texto_extraido

def analisar_texto(texto):
    erros_detectados = []
    texto_em_minusculo = texto.lower()
    # Adicione sua lógica de análise aqui
    PALAVRAS_SUSPEITAS = ["dispensa de licitacao", "carater de urgencia", "pagamento retroativo", "inexigibilidade de licitacao"]
    for palavra in PALAVRAS_SUSPEITAS:
        if palavra in texto_em_minusculo:
            erros_detectados.append(f"Alerta de Termo Sensível: A expressão '{palavra}' foi encontrada.")
    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados}


@app.route('/', methods=['GET', 'POST'])
def index():
    resultado_analise = None
    if request.method == 'POST':
        if 'file' not in request.files or request.files['file'].filename == '':
            return render_template('index.html', erro_upload="Nenhum arquivo selecionado.")
        
        file = request.files['file']
        
        if file:
            try:
                file_bytes = file.read()
                texto_extraido = extrair_texto_do_arquivo(file_bytes, file.filename)
                
                if not texto_extraido.strip():
                     raise ValueError("Nenhum texto pôde ser extraído do documento.")

                hash_sha256 = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()

                data, count = supabase.table('analises').select('*').eq('hash_sha256', hash_sha256).execute()

                if len(data[1]) > 0:
                    print("Análise encontrada no cache do Supabase.")
                    analise_salva = data[1][0]
                    resultado_analise = {
                        "status": analise_salva['status'], 
                        "erros": analise_salva['erros_detectados'], 
                        "hash": analise_salva['hash_sha256'], 
                        "texto": analise_salva['texto_extraido']
                    }
                else:
                    print("Documento novo. Analisando e salvando no Supabase.")
                    analise = analisar_texto(texto_extraido)
                    resultado_analise = {
                        "status": analise['status'], 
                        "erros": analise['erros'], 
                        "hash": hash_sha256, 
                        "texto": texto_extraido
                    }
                    
                    supabase.table('analises').insert({
                        'hash_sha256': hash_sha256,
                        'status': resultado_analise['status'],
                        'erros_detectados': resultado_analise['erros'],
                        'texto_extraido': texto_extraido
                    }).execute()

            except Exception as e:
                resultado_analise = {"status": "ERRO", "erros": [f"Não foi possível processar o arquivo: {e}"]}
            
    return render_template('index.html', resultado=resultado_analise)


if __name__ == '__main__':
    app.run(debug=True)
