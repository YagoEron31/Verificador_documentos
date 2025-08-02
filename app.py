import os
import re
import hashlib
import io
import requests # Adicionado
from flask import Flask, request, render_template, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env (para teste local)
load_dotenv()

# --- Conexão com as APIs usando Variáveis de Ambiente ---
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY") # Lendo a chave do ambiente
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# --------------------------------------------------------

app = Flask(__name__)

def extrair_texto_ocr_space(file_bytes, filename):
    """Extrai texto de um arquivo usando a API do OCR.space."""
    url = "https://api.ocr.space/parse/image"
    payload = {'language': 'por', 'isOverlayRequired': 'false', 'OCREngine': 2}
    files = {'file': (filename, file_bytes)}
    headers = {'apikey': OCR_SPACE_API_KEY}

    response = requests.post(url, headers=headers, data=payload, files=files)
    response.raise_for_status() # Lança um erro se a requisição falhar
    
    result = response.json()

    if result.get("IsErroredOnProcessing"):
        raise ValueError(result.get("ErrorMessage", ["Erro desconhecido no OCR."])[0])

    if not result.get("ParsedResults"):
        raise ValueError("Nenhum resultado de texto foi retornado pela API de OCR.")

    return result["ParsedResults"][0]["ParsedText"]

def analisar_texto(texto):
    """Realiza as análises de fraude no texto extraído."""
    erros_detectados = []
    texto_em_minusculo = texto.lower()

    PALAVRAS_SUSPEITAS = ["dispensa de licitacao", "carater de urgencia", "pagamento retroativo", "inexigibilidade de licitacao"]
    for palavra in PALAVRAS_SUSPEITAS:
        if palavra in texto_em_minusculo:
            erros_detectados.append(f"Alerta de Termo Sensível: A expressão '{palavra}' foi encontrada.")

    datas = re.findall(r"\d{2}/\d{2}/\d{4}", texto)
    for data in datas:
        try:
            dia, mes, _ = map(int, data.split('/'))
            if mes > 12 or dia > 31 or mes == 0 or dia == 0:
                erros_detectados.append(f"Possível adulteração: A data '{data}' é inválida.")
        except ValueError:
            continue

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
                texto_extraido = extrair_texto_ocr_space(file_bytes, file.filename)
                
                if not texto_extraido.strip():
                     raise ValueError("Nenhum texto pôde ser extraído do documento.")

                hash_sha256 = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()

                data, count = supabase.table('analises').select('*').eq('hash_sha256', hash_sha256).execute()

                if len(data[1]) > 0:
                    print("Análise encontrada no cache do Supabase.")
                    analise_salva = data[1][0]
                    resultado_analise = { "status": analise_salva['status'], "erros": analise_salva['erros_detectados'], "hash": analise_salva['hash_sha256'], "texto": analise_salva['texto_extraido'] }
                else:
                    print("Documento novo. Analisando e salvando no Supabase.")
                    analise = analisar_texto(texto_extraido)
                    resultado_analise = { "status": analise['status'], "erros": analise['erros'], "hash": hash_sha256, "texto": texto_extraido }
                    
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
