from flask import Flask, request, jsonify, send_from_directory, render_template
import hashlib
import requests
import os
import json # << ADICIONADO PARA O DISCORD
from datetime import datetime
import psycopg2
from werkzeug.utils import secure_filename
from dotenv import load_dotenv # << ADICIONADO PARA CARREGAR .env

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configurações ---
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')
UPLOAD_FOLDER = 'uploads'
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL') # << NOVA VARIÁVEL

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
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# =================================================================================
# --- NOSSAS FUNÇÕES DE ANÁLISE E NOTIFICAÇÃO ---
# =================================================================================

def analisar_texto_completo(texto):
    """Executa todas as nossas regras de verificação no texto extraído."""
    erros_detectados = []
    texto_em_minusculo = texto.lower()
    
    # Adicione aqui todas as regras que desenvolvemos (Nepotismo, Datas, Palavras-Chave, etc.)
    # Exemplo simples:
    if "dispensa de licitacao" in texto_em_minusculo:
        erros_detectados.append("Alerta de Termo Sensível: A expressão 'dispensa de licitacao' foi encontrada.")

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
            {"name": "Inconsistências Encontradas", "value": "\n".join([f"• {erro}" for erro in resultado_analise['erros']]) or "N/A"}
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
# --- SUAS FUNÇÕES ORIGINAIS (COM PEQUENOS AJUSTES) ---
# =================================================================================

def calcular_hash_sha256(file_path):
    # ... (seu código de hash)
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(4096):
            sha256.update(chunk)
    return sha256.hexdigest()

def extrair_texto_ocr(file_path):
    # ... (seu código de OCR)
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

# ... (suas funções de banco de dados podem continuar aqui)

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
        # 1. Extrai o texto
        texto_extraido, erro_ocr = extrair_texto_ocr(local_path)
        if erro_ocr:
            raise Exception(f"Erro no OCR: {erro_ocr}")

        # 2. Executa nossa análise completa
        analise = analisar_texto_completo(texto_extraido)
        
        # 3. Prepara o resultado
        hash_conteudo = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()
        resultado_final = {
            "status": analise['status'],
            "erros": analise['erros'],
            "hash": hash_conteudo,
            "nome_arquivo": filename,
            "texto_extraido": texto_extraido
        }

        # 4. Se for suspeito, ENVIA A NOTIFICAÇÃO para o Discord
        if resultado_final['status'] == 'SUSPEITO':
            enviar_alerta_discord(resultado_final, filename)
        
        # Opcional: Salvar no seu banco de dados PostgreSQL aqui
        # inserir_analise(hash_conteudo, texto_extraido, analise['status'], analise['erros'], ...)

        return jsonify(resultado_final)

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        os.remove(local_path)

if __name__ == '__main__':
    app.run(debug=True)
