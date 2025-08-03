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
BUCKET_NAME = 'armazenamento'

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
# --- MÓDULO DE ANÁLISE E NOTIFICAÇÃO ---
# =================================================================================

def analisar_texto_completo(texto):
    """Executa todas as nossas regras de verificação no texto extraído."""
    erros_detectados = []
    texto_em_minusculo = texto.lower()

    # --- Regra 1: Nepotismo (com lista de exceções) ---
    PALAVRAS_INSTITUCIONAIS = [
        'campus', 'instituto', 'secretaria', 'prefeitura', 'comissao', 'diretoria', 
        'coordenacao', 'avaliacao', 'servicos', 'companhia', 'programa', 'nacional', 
        'boletim', 'reitoria', 'grupo', 'trabalho', 'assistencia', 'estudantil'
    ]
    nomes_potenciais = re.findall(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)+\b", texto)
    nomes_validos = [
        nome for nome in nomes_potenciais 
        if any(c.islower() for c in nome) and not any(palavra in nome.lower() for palavra in PALAVRAS_INSTITUCIONAIS)
    ]
    nomes_contados = {nome: nomes_validos.count(nome) for nome in set(nomes_validos)}
    for nome, contagem in nomes_contados.items():
        if contagem > 1:
            erros_detectados.append(f"Possível nepotismo: O nome '{nome}' aparece {contagem} vezes.")

    # --- Regra 2: Datas Inválidas ---
    datas = re.findall(r"\d{2}/\d{2}/\d{4}", texto)
    for data in datas:
        try:
            dia, mes, _ = map(int, data.split('/'))
            if mes > 12 or dia > 31 or mes == 0 or dia == 0:
                erros_detectados.append(f"Possível adulteração: A data '{data}' é inválida.")
        except ValueError:
            continue
    
    # --- Regra 3: Palavras-Chave Suspeitas ---
    PALAVRAS_SUSPEITAS = ["dispensa de licitacao", "carater de urgencia", "pagamento retroativo", "inexigibilidade de licitacao"]
    for palavra in PALAVRAS_SUSPEITAS:
        if palavra in texto_em_minusculo:
            erros_detectados.append(f"Alerta de Termo Sensível: A expressão '{palavra}' foi encontrada.")

    # --- Regra 4: Análise Estrutural ---
    if not re.search(r"(of[íi]cio|processo|portaria)\s+n[ºo]", texto_em_minusculo):
        erros_detectados.append("Alerta Estrutural: Não foi encontrado um número de documento oficial (Ofício, Processo, etc.).")

    # --- Regra 5: Auditor de Dispensa de Licitação ---
    LIMITE_DISPENSA_SERVICOS = 59906.02
    if "dispensa de licitacao" in texto_em_minusculo:
        valores_encontrados = re.findall(r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})", texto)
        for valor_str in valores_encontrados:
            valor_float = float(valor_str.replace('.', '').replace(',', '.'))
            if valor_float > LIMITE_DISPENSA_SERVICOS:
                erros_detectados.append(f"ALERTA GRAVE DE LICITAÇÃO: Valor de R$ {valor_str} em dispensa acima do limite legal de R$ {LIMITE_DISPENSA_SERVICOS:,.2f}.".replace(',','.'))

    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados}

def enviar_alerta_discord(resultado_analise):
    """Envia uma notificação formatada para o Discord via Webhook."""
    
    # A URL do Webhook está inserida diretamente aqui.
    DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1401335008307712110/oSA963JE134fZr89vE0BRFjOH2ruaotjigf1G3AXfFhoU4xu2Zk6HUMpmzmwyD9nGbVP"

    embed = {
        "title": f"🚨 Alerta: Documento Suspeito Detectado!",
        "color": 15158332, # Vermelho
        "fields": [
            {"name": "Nome do Arquivo", "value": resultado_analise.get('nome_arquivo', 'N/A'), "inline": True},
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
# --- FUNÇÕES DE INFRAESTRUTURA ---
# =================================================================================

def get_db_connection():
    """Cria e retorna uma nova conexão com o banco de dados."""
    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
    )
    return conn

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
    }
    with open(file_path, 'rb') as file_data:
        response = requests.post(
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{nome_arquivo}",
            headers=headers,
            files={"file": (nome_arquivo, file_data)}
        )
    if response.status_code not in [200, 201]:
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
        hash_arquivo = calcular_hash_sha256(local_path)

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM documentos_oficiais WHERE hash_sha256 = %s", (hash_arquivo,))
            if cursor.fetchone():
                return jsonify({"status": "duplicado", "hash": hash_arquivo, "mensagem": "Este documento exato já foi cadastrado anteriormente."}), 409
        conn.close()

        filename_com_hash = f"{hash_arquivo}_{filename}"
        caminho_storage = salvar_no_storage(filename_com_hash, local_path)

        texto_extraido, erro_ocr = extrair_texto_ocr(local_path)
        if erro_ocr:
            raise Exception(f"Erro no OCR: {erro_ocr}")

        analise = analisar_texto_completo(texto_extraido)
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO documentos_oficiais (nome_arquivo, caminho_storage, hash_sha256, created_at)
                VALUES (%s, %s, %s, %s)
            """, (filename, caminho_storage, hash_arquivo, datetime.now()))

            hash_conteudo = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()
            cursor.execute("""
                INSERT INTO analises (hash_sha256, texto_extraido, status, erros_detectados, caminho_storage, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (hash_conteudo, texto_extraido, analise['status'], json.dumps(analise['erros']), caminho_storage, datetime.now()))
            conn.commit()
        conn.close()

        resultado_final = {
            "status": analise['status'],
            "erros": analise['erros'],
            "hash": hash_conteudo,
            "nome_arquivo": filename,
            "texto_extraido": texto_extraido
        }

        if resultado_final['status'] == 'SUSPEITO':
            enviar_alerta_discord(resultado_final)
        
        return jsonify(resultado_final)

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

if __name__ == '__main__':
    app.run(debug=True)
