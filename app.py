from flask import Flask, request, jsonify, render_template
import hashlib
import requests
import os
import json
from datetime import datetime
import psycopg2
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configurações ---
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')
UPLOAD_FOLDER = 'uploads'
BUCKET_NAME = 'armazenamento' # Presumi este nome, ajuste se necessário
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

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

    # Adicione/Ajuste todas as regras que desenvolvemos aqui
    PALAVRAS_SUSPEITAS = ["dispensa de licitacao", "carater de urgencia", "pagamento retroativo", "inexigibilidade de licitacao"]
    for palavra in PALAVRAS_SUSPEITAS:
        if palavra in texto_em_minusculo:
            erros_detectados.append(f"Alerta de Termo Sensível: A expressão '{palavra}' foi encontrada.")
    
    # Exemplo: Regra de data (ajuste conforme necessário)
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
# --- SUAS FUNÇÕES ORIGINAIS DE INFRAESTRUTURA ---
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
        "Content-Type": "application/octet-stream" # Adicionado para mais robustez
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

def get_db_connection():
    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
    )
    return conn

def inserir_documento_e_analise(hash_arquivo, nome_arquivo, caminho_storage, texto_extraido, analise):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Verifica se o hash do ARQUIVO já existe
            cursor.execute("SELECT id FROM documentos_oficiais WHERE hash_sha256 = %s", (hash_arquivo,))
            if cursor.fetchone():
                return False # Documento já existe

            # Insere o documento
            cursor.execute("""
                INSERT INTO documentos_oficiais (nome_arquivo, caminho_storage, hash_sha256, created_at)
                VALUES (%s, %s, %s, %s)
            """, (nome_arquivo, caminho_storage, hash_arquivo, datetime.now()))

            # Insere a análise
            hash_conteudo = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()
            cursor.execute("""
                INSERT INTO analises (hash_sha256, texto_extraido, status, erros_detectados, caminho_storage, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (hash_conteudo, texto_extraido, analise['status'], analise['erros'], caminho_storage, datetime.now()))
            
            conn.commit()
            return True # Novo documento inserido
    finally:
        conn.close()

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
        # 1. Calcula o hash do ARQUIVO para verificar duplicatas
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
        
        # 5. Salva documento e análise no Banco de Dados (PostgreSQL)
        #    A função 'inserir_documento_e_analise' já previne duplicatas de arquivo
        novo_documento = inserir_documento_e_analise(hash_arquivo, filename, caminho_storage, texto_extraido, analise)
        if not novo_documento:
            # Se o documento já existia, informamos o usuário.
            return jsonify({"status": "duplicado", "hash": hash_arquivo, "mensagem": "Este documento exato já foi cadastrado anteriormente."}), 409

        # 6. Prepara o resultado final para o usuário
        hash_conteudo = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()
        resultado_final = {
            "status": analise['status'],
            "erros": analise['erros'],
            "hash": hash_conteudo,
            "nome_arquivo": filename,
            "texto_extraido": texto_extraido
        }

        # 7. Se for suspeito, envia a notificação para o Discord
        if resultado_final['status'] == 'SUSPEITO':
            enviar_alerta_discord(resultado_final, filename)
        
        return jsonify(resultado_final)

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        # Limpa o arquivo local após o processamento
        if os.path.exists(local_path):
            os.remove(local_path)

if __name__ == '__main__':
    app.run(debug=True)
