import os
import re
import hashlib
import io
import requests
import json
from flask import Flask, request, render_template
from dotenv import load_dotenv
from supabase import create_client, Client
from werkzeug.utils import secure_filename

# Carrega variáveis de ambiente
load_dotenv()

# --- Configurações e Conexões ---
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

# Define as extensões de arquivo permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

def analisar_texto(texto_extraido):
    """Realiza as análises de fraude no texto extraído com as novas regras detalhadas."""
    erros_detectados = []
    texto_lower = texto_extraido.lower()

    # --- Regra 1: Palavras-chave suspeitas ---
    palavras_suspeitas = [
        "dispensa de licitação", "caráter de urgência", "pagamento retroativo", "inexigibilidade de licitação"
    ]
    for palavra in palavras_suspeitas:
        if palavra in texto_lower:
            erros_detectados.append(f"⚠️ Palavra suspeita: '{palavra}'")

    # --- Regra 2: Datas inválidas ---
    datas = re.findall(r"\d{2}/\d{2}/\d{4}", texto_extraido)
    for data in datas:
        try:
            d, m, _ = map(int, data.split("/"))
            if d > 31 or m > 12 or d == 0 or m == 0:
                erros_detectados.append(f"⚠️ Data inválida: '{data}'")
        except:
            continue

    # --- Regra 3: Estrutura obrigatória ---
    termos_estruturais = ["prefeitura", "número", "assinatura", "cnpj"]
    for termo in termos_estruturais:
        if termo not in texto_lower:
            erros_detectados.append(f"❌ Estrutura incompleta: termo obrigatório ausente – '{termo}'")

    # --- Regra 4: Nomes repetidos ---
    # Adicionamos uma lista de exceções para evitar falsos positivos
    PALAVRAS_INSTITUCIONAIS = [
        'campus', 'instituto', 'secretaria', 'prefeitura', 'comissao', 'diretoria', 
        'coordenacao', 'avaliacao', 'servicos', 'companhia', 'programa', 'nacional', 
        'boletim', 'reitoria', 'grupo', 'trabalho', 'assistencia', 'estudantil'
    ]
    nomes_potenciais = re.findall(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)+\b", texto_extraido)
    nomes_validos = [
        nome for nome in nomes_potenciais 
        if not any(palavra in nome.lower() for palavra in PALAVRAS_INSTITUCIONAIS)
    ]
    nomes_contados = {nome: nomes_validos.count(nome) for nome in set(nomes_validos)}
    for nome, contagem in nomes_contados.items():
        if contagem > 1:
            erros_detectados.append(f"🔁 Nome repetido suspeito: '{nome}' (aparece {contagem} vezes)")

    # --- Regra 5: Auditor de Dispensa de Licitação ---
    LIMITE_DISPENSA_SERVICOS = 59906.02
    if "dispensa de licitação" in texto_lower:
        valores_encontrados = re.findall(r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})", texto_extraido)
        for valor_str in valores_encontrados:
            valor_float = float(valor_str.replace('.', '').replace(',', '.'))
            if valor_float > LIMITE_DISPENSA_SERVICOS:
                erros_detectados.append(f"ALERTA GRAVE: Valor de R$ {valor_str} em dispensa acima do limite legal de R$ {LIMITE_DISPENSA_SERVICOS:,.2f}.".replace(',','.'))

    # --- Conclusão da Análise ---
    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados}

@app.route('/', methods=['GET', 'POST'])
def index():
    resultado_analise = None
    if request.method == 'POST':
        if 'file' not in request.files or request.files['file'].filename == '':
            return render_template('index.html', erro_upload="Nenhum arquivo selecionado.")
        
        file = request.files['file']
        
        if not allowed_file(file.filename):
            erro_msg = "Formato de arquivo não suportado. Por favor, envie um PDF, PNG, JPG ou JPEG."
            return render_template('index.html', erro_upload=erro_msg)
        
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
                    "texto": texto_extraido
                }

                # Tenta salvar o resultado no Supabase
                try:
                    supabase.table('analises').insert({
                        'hash_sha256': resultado_analise['hash'],
                        'status': resultado_analise['status'],
                        'erros_detectados': resultado_analise['erros'],
                        'texto_extraido': resultado_analise['texto']
                    }).execute()
                    print("Resultado da análise salvo no Supabase.")
                except Exception as e:
                    print(f"Erro ao salvar no Supabase: {e}")
                    # Adiciona um aviso ao resultado se o salvamento falhar, mas não quebra a aplicação
                    resultado_analise['erros'].append("Aviso: A análise foi concluída, mas não pôde ser salva no banco de dados.")

            except Exception as e:
                resultado_analise = {"status": "ERRO", "erros": [f"Não foi possível processar o arquivo: {e}"]}
            
    return render_template('index.html', resultado=resultado_analise)

if __name__ == '__main__':
    app.run(debug=True)
