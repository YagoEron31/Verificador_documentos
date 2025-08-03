import os
import re
import hashlib
import io
import requests
from flask import Flask, request, render_template, jsonify
from supabase import create_client, Client
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# --- Configurações e Conexões ---
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

app = Flask(__name__)
_supabase_client = None

def get_supabase_client():
    """Cria e reutiliza uma conexão com o Supabase."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

# Define as extensões de arquivo permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =================================================================================
# --- FUNÇÕES DE LÓGICA (Análise, OCR) ---
# =================================================================================

def analisar_texto(texto_extraido):
    """Realiza as análises de fraude no texto extraído com as regras detalhadas."""
    erros_detectados = []
    texto_lower = texto_extraido.lower()

    # --- Regra 1: Palavras-chave suspeitas ---
    palavras_suspeitas = [
        "dispensa de licitação", "caráter de urgência", "pagamento retroativo", "inexigibilidade de licitação"
    ]
    for palavra in palavras_suspeitas:
        if palavra in texto_lower:
            erros_detectados.append(f"⚠️ Alerta de Termo Sensível: '{palavra}'")

    # --- Regra 2: Datas inválidas ---
    datas = re.findall(r"\d{2}/\d{2}/\d{4}", texto_extraido)
    for data in datas:
        try:
            d, m, _ = map(int, data.split("/"))
            if d > 31 or m > 12 or d == 0 or m == 0:
                erros_detectados.append(f"⚠️ Data Inválida: '{data}'")
        except:
            continue

    # --- Regra 3: Estrutura obrigatória ---
    termos_estruturais = ["prefeitura", "número", "assinatura", "cnpj"]
    for termo in termos_estruturais:
        if termo not in texto_lower:
            erros_detectados.append(f"❌ Estrutura Incompleta: Termo obrigatório ausente – '{termo}'")

    # --- Regra 4: Nomes repetidos ---
    nomes = re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", texto_extraido)
    nomes_contados = {nome: nomes.count(nome) for nome in set(nomes)}
    for nome, contagem in nomes_contados.items():
        if contagem > 1:
            erros_detectados.append(f"🔁 Nome Repetido Suspeito: '{nome}' (aparece {contagem} vezes)")

    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados}

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
# --- ROTAS DA APLICAÇÃO ---
# =================================================================================

@app.route('/')
def home():
    return render_template('inicial.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/verificador', methods=['GET', 'POST'])
def verificador_page():
    resultado_analise = None
    if request.method == 'POST':
        if 'file' not in request.files or request.files['file'].filename == '':
            return render_template('verificação.html', erro_upload="Nenhum arquivo selecionado.")
        
        file = request.files['file']
        
        if not allowed_file(file.filename):
            erro_msg = "Formato de arquivo não suportado. Por favor, envie um PDF, PNG, JPG ou JPEG."
            return render_template('verificação.html', erro_upload=erro_msg)
        
        if file:
            try:
                file_bytes = file.read()
                texto_extraido = extrair_texto_ocr_space(file_bytes, file.filename)
                
                if not texto_extraido.strip():
                         raise ValueError("Nenhum texto pôde ser extraído do documento.")

                hash_sha256 = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()
                analise = analisar_texto(texto_extraido)
                
                resultado_analise = {
                    "status": analise['status'],
                    "erros": analise['erros'],
                    "hash": hash_sha256,
                    "texto_extraido": texto_extraido
                }

            except Exception as e:
                resultado_analise = {"status": "ERRO", "erros": [f"Não foi possível processar o arquivo: {e}"]}
            
    return render_template('verificação.html', resultado=resultado_analise)

# ... (outras rotas como /transparencia, /faq, etc. devem ser adicionadas se necessário)

if __name__ == '__main__':
    app.run(debug=True)
