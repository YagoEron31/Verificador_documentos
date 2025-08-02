import os
import re
import hashlib
from flask import Flask, request, render_template
import requests
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)

def extrair_texto_ocr_space(file_bytes, filename):
    url = "https://api.ocr.space/parse/image"
    payload = {
        'language': 'por',
        'isOverlayRequired': False,
        'OCREngine': 2
    }
    files = {
        'file': (filename, file_bytes)
    }
    headers = {
        'apikey': OCR_SPACE_API_KEY,
    }

    response = requests.post(url, data=payload, files=files, headers=headers)
    result = response.json()

    if result.get("IsErroredOnProcessing"):
        raise ValueError(result.get("ErrorMessage") or "Erro no OCR externo.")

    return result["ParsedResults"][0]["ParsedText"]

def analisar_texto(texto):
    erros_detectados = []
    texto_em_minusculo = texto.lower()

    PALAVRAS_SUSPEITAS = [
        "dispensa de licitacao",
        "carater de urgencia",
        "pagamento retroativo",
        "inexigibilidade de licitacao"
    ]

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
    consulta_hash = None
    consulta_resultado = None
    erro_consulta = None
    erro_upload = None

    if request.method == 'POST':
        action = request.form.get('action')

        # Verificar documento pelo hash
        if action == 'consultar':
            consulta_hash = request.form.get('hash_consulta', '').strip()
            if not consulta_hash:
                erro_consulta = "Por favor, informe um hash para consulta."
            else:
                data, count = supabase.table('analises').select('*').eq('hash_sha256', consulta_hash).execute()
                if len(data[1]) > 0:
                    consulta_resultado = data[1][0]
                else:
                    erro_consulta = "Nenhum documento encontrado com este hash."

        # Cadastrar novo documento com análise OCR
        elif action == 'cadastrar':
            if 'file' not in request.files or request.files['file'].filename == '':
                erro_upload = "Nenhum arquivo selecionado para upload."
            else:
                file = request.files['file']
                try:
                    file_bytes = file.read()
                    texto_extraido = extrair_texto_ocr_space(file_bytes, file.filename)

                    if not texto_extraido.strip():
                        raise ValueError("Nenhum texto pôde ser extraído do documento.")

                    hash_sha256 = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()

                    # Verifica se já existe no banco
                    data, count = supabase.table('analises').select('*').eq('hash_sha256', hash_sha256).execute()

                    if len(data[1]) > 0:
                        # Já existe no banco
                        analise_salva = data[1][0]
                        resultado_analise = {
                            "status": analise_salva['status'],
                            "erros": analise_salva['erros_detectados'],
                            "hash": analise_salva['hash_sha256'],
                            "texto": analise_salva['texto_extraido']
                        }
                    else:
                        # Novo documento, faz a análise e salva
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
                    erro_upload = f"Não foi possível processar o arquivo: {e}"

    return render_template('index.html',
                           resultado=resultado_analise,
                           erro_upload=erro_upload,
                           consulta_hash=consulta_hash,
                           consulta_resultado=consulta_resultado,
                           erro_consulta=erro_consulta)

if __name__ == '__main__':
    app.run(debug=True)
