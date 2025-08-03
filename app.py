import os
import re # <-- Importação corrigida
import hashlib
import io
import json
import requests
from flask import Flask, request, render_template, jsonify
from supabase import create_client, Client
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configurações e Conexões ---
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL') # <-- Chave protegida

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

# =================================================================================
# --- MÓDULO DE ANÁLISE E NOTIFICAÇÃO ---
# =================================================================================

def analisar_texto_completo(texto):
    """Executa todas as nossas regras de verificação no texto extraído."""
    erros_detectados = []
    texto_em_minusculo = texto.lower()

    # (Sua lógica de análise detalhada permanece aqui)
    PALAVRAS_SUSPEITAS = ["dispensa de licitacao", "carater de urgencia", "pagamento retroativo", "inexigibilidade de licitacao"]
    for palavra in PALAVRAS_SUSPEITAS:
        if palavra in texto_em_minusculo:
            erros_detectados.append(f"Alerta de Termo Sensível: A expressão '{palavra}' foi encontrada.")
    
    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados}

def enviar_alerta_discord(resultado_analise):
    """Envia uma notificação formatada para o Discord via Webhook."""
    if not DISCORD_WEBHOOK_URL:
        print("Webhook do Discord não configurado. Pulando notificação.")
        return

    embed = {
        "title": f"🚨 Alerta: Documento Suspeito Detectado!",
        "color": 15158332, # Vermelho
        "fields": [
            {"name": "Nome do Arquivo", "value": resultado_analise.get('nome_arquivo', 'N/A'), "inline": True},
            {"name": "Status da Análise", "value": resultado_analise['status'], "inline": True},
            {"name": "Hash do Conteúdo", "value": f"`{resultado_analise['hash_conteudo']}`"},
            {"name": "Hash do Arquivo", "value": f"`{resultado_analise['hash_arquivo']}`"},
            {"name": "Inconsistências Encontradas", "value": "\n".join([f"• {erro}" for erro in resultado_analise['erros']]) or "Nenhuma inconsistência específica listada."}
        ]
    }
    data = {"content": "Um novo documento suspeito requer atenção imediata!", "embeds": [embed]}
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(data), headers={"Content-Type": "application/json"})
        response.raise_for_status()
        print("Notificação enviada ao Discord com sucesso.")
    except Exception as e:
        print(f"Erro ao enviar notificação para o Discord: {e}")

def extrair_texto_ocr_space(file_bytes, filename):
    """Extrai texto de um arquivo usando a API do OCR.space."""
    url = "https://api.ocr.space/parse/image"
    payload = {'language': 'por', 'isOverlayRequired': 'false', 'OCREngine': 2}
    files = {'file': (filename, file_bytes)}
    headers = {'apikey': OCR_SPACE_API_KEY}
    response = requests.post(url, headers=headers, data=payload, files=files)
    response.raise_for_status()
    result = response.json()
    if result.get("IsErroredOnProcessing"):
        raise ValueError(result.get("ErrorMessage", ["Erro desconhecido no OCR."])[0])
    if not result.get("ParsedResults"):
        raise ValueError("Nenhum resultado de texto foi retornado pela API de OCR.")
    return result["ParsedResults"][0]["ParsedText"]

# =================================================================================
# --- ROTA PRINCIPAL DA APLICAÇÃO ---
# =================================================================================

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html')

    if 'file' not in request.files or request.files['file'].filename == '':
        return render_template('index.html', erro_upload="Nenhum arquivo selecionado.")

    file = request.files['file']
    filename = secure_filename(file.filename)
    file_bytes = file.read()

    try:
        # 1. Calcula o hash do ARQUIVO para checar duplicidade
        hash_arquivo = hashlib.sha256(file_bytes).hexdigest()

        # 2. Verifica se o ARQUIVO já foi processado
        data, count = supabase.table('analises').select('*').eq('hash_arquivo', hash_arquivo).execute()
        
        if len(data[1]) > 0:
            print("Documento já processado. Retornando do cache.")
            return render_template('index.html', resultado=data[1][0])

        # 3. Se é um arquivo novo, processa tudo
        print("Arquivo novo, iniciando processamento completo.")
        
        texto_extraido = extrair_texto_ocr_space(file_bytes, filename)
        if not texto_extraido.strip():
            raise ValueError("Nenhum texto pôde ser extraído do documento.")

        analise = analisar_texto_completo(texto_extraido)
        hash_conteudo = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()

        # 4. Salva o arquivo original no Supabase Storage
        caminho_storage = f"documentos/{hash_arquivo}_{filename}"
        supabase.storage.from_("arquivos").upload(
            path=caminho_storage,
            file=file_bytes,
            file_options={"content-type": file.content_type}
        )

        # 5. Salva o resultado completo na tabela 'analises'
        resultado_final = {
            "nome_arquivo": filename,
            "hash_arquivo": hash_arquivo,
            "hash_conteudo": hash_conteudo,
            "status": analise['status'],
            "erros_detectados": analise['erros'],
            "texto_extraido": texto_extraido,
            "caminho_storage": caminho_storage
        }
        supabase.table('analises').insert(resultado_final).execute()
        print("Nova análise salva no Supabase.")

        # 6. Se for suspeito, envia o alerta
        if resultado_final['status'] == 'SUSPEITO':
            enviar_alerta_discord(resultado_final)
        
        return render_template('index.html', resultado=resultado_final)

    except Exception as e:
        return render_template('index.html', resultado={"status": "ERRO", "erros": [f"Erro inesperado: {e}"]})

if __name__ == '__main__':
    app.run(debug=True)
