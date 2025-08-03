from flask import Flask, request, jsonify, render_template
import hashlib
import requests
import os
import json
from datetime import datetime
# import psycopg2 # <-- REMOVIDO: Importação do psycopg2
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import re

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configurações ---
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')
UPLOAD_FOLDER = 'uploads'
BUCKET_NAME = 'armazenamento' # Presumi este nome, ajuste se necessário
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

# Supabase (apenas para Storage, as chaves de DB serão ignoradas se não usadas)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# PostgreSQL (Variáveis de ambiente mantidas, mas não serão usadas no código)
# DB_NAME = os.getenv("DB_NAME")
# DB_USER = os.getenv("DB_USER")
# DB_PASSWORD = os.getenv("DB_PASSWORD")
# DB_HOST = os.getenv("DB_HOST")
# DB_PORT = os.getenv("DB_PORT", 5432)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# =================================================================================
# --- NOSSAS FUNÇÕES DE ANÁLISE E NOTIFICAÇÃO ---
# =================================================================================

def analisar_texto_completo(texto):
    """Executa todas as nossas regras de verificação no texto extraído."""
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

def enviar_alerta_discord(resultado_analise, nome_arquivo):
    """Envia uma notificação formatada para o Discord via Webhook."""
    if not DISCORD_WEBHOOK_URL:
        print("URL do Webhook do Discord não configurada.")
        return

    embed = {
        "title": f"🚨 Alerta: Documento Suspeito Detectado!",
        "color": 15158332, # Vermelho
        "fields": [
            {"name": "Nome do Arquivo", "value": nome_arquivo, "inline": True},
            {"name": "Status da Análise", "value": resultado_analise['status'], "inline": True},
            {"name": "Hash do Conteúdo (SHA-256)", "value": f"`{resultado_analise['hash']}`"},
            {"name": "Inconsistências Encontradas", "value": "\n".join([f"• {erro}" for erro in resultado_analise['erros']]) or "Nenhuma inconsistência específica listada."}
        ],
        "footer": {"text": "Análise concluída pelo Verificador Inteligente."}
    }
    data = {"content": "Um novo documento suspeito requer atenção imediata!", "embeds": [embed]}
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(data), headers={"Content-Type": "application/json"})
        response.raise_for_status()
        print("Notificação enviada ao Discord com sucesso.")
    except Exception as e:
        print(f"Erro ao enviar notificação para o Discord: {e}")

# =================================================================================
# --- SUAS FUNÇÕES ORIGINAIS DE INFRAESTRUTURA (sem DB) ---
# =================================================================================

def calcular_hash_sha256(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(4096):
            sha256.update(chunk)
    return sha256.hexdigest()

def salvar_no_storage(nome_arquivo, file_path):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/octet-stream"
    }
    with open(file_path, 'rb') as file_data:
        response = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{nome_arquivo}",
            headers=headers,
            data=file_data
        )
    if response.status_code != 200:
        raise Exception(f"Erro ao salvar no Supabase Storage: {response.text}")
    return f"{BUCKET_NAME}/{nome_arquivo}"

def extrair_texto_ocr(file_path):
    url = 'https://api.ocr.space/parse/image'
    with open(file_path, 'rb') as f:
        response = requests.post(
            url,
            files={'file': f},
            data={'apikey': OCR_SPACE_API_KEY, 'language': 'por'}
        )
    resultado = response.json()
    if not resultado.get('IsErroredOnProcessing'):
        return resultado['ParsedResults'][0]['ParsedText'].strip(), None
    else:
        return "", resultado.get("ErrorMessage")

# REMOVIDO: get_db_connection
# REMOVIDO: inserir_documento_e_analise

# =================================================================================
# --- ROTAS DA APLICAÇÃO ---
# =================================================================================

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

    try:
        # 1. Calcula o hash do ARQUIVO para propósitos de retorno e nome do storage
        hash_arquivo = calcular_hash_sha256(local_path)

        # 2. Salva o arquivo no Storage (Supabase)
        filename_com_hash = f"{hash_arquivo}_{filename}"
        caminho_storage = salvar_no_storage(filename_com_hash, local_path)

        # 3. Extrai o texto com OCR
        texto_extraido, erro_ocr = extrair_texto_ocr(local_path)
        if erro_ocr:
            raise Exception(f"Erro no OCR: {erro_ocr}")

        # 4. Executa nossa análise completa no conteúdo
        analise = analisar_texto_completo(texto_extraido)
        
        # 5. Prepara o resultado final para o usuário
        # O hash_conteudo é do texto, não do arquivo, se for preciso
        hash_conteudo = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()
        resultado_final = {
            "status": analise['status'],
            "erros": analise['erros'],
            "hash_arquivo": hash_arquivo, # Retornando o hash do arquivo original
            "hash_conteudo_ocr": hash_conteudo, # Retornando o hash do conteúdo extraído
            "nome_arquivo": filename,
            "caminho_storage": caminho_storage, # Opcional: retornar o caminho no storage
            "texto_extraido": texto_extraido
        }

        # 6. Se for suspeito, envia a notificação para o Discord
        if resultado_final['status'] == 'SUSPEITO':
            enviar_alerta_discord(resultado_final, filename)
        
        return jsonify(resultado_final)

    except Exception as e:
        print(f"Erro durante o upload/processamento: {e}", flush=True) 
        return jsonify({"erro": str(e)}), 500
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

# Para uso em desenvolvimento local:
if __name__ == '__main__':
    # Você pode definir a porta aqui se precisar
    app.run(debug=True, port=5000)
