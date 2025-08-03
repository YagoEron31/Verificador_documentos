import os
import re
import hashlib
import io
import requests
from flask import Flask, request, render_template, session
from dotenv import load_dotenv
from datetime import datetime

# Carrega a chave da API de OCR a partir das variáveis de ambiente
load_dotenv()
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")

app = Flask(__name__)
# Chave secreta para a sessão, necessária para passar dados entre rotas
app.secret_key = os.getenv("FLASK_SECRET_KEY", "uma-chave-secreta-padrao-para-teste")

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

def analisar_texto_avancado(texto_extraido):
    """Realiza as análises de fraude avançadas no texto extraído."""
    erros_detectados = []
    texto_lower = texto_extraido.lower()

    # --- Regra 1: Nepotismo (com lista de exceções) ---
    PALAVRAS_INSTITUCIONAIS = [
        'campus', 'instituto', 'secretaria', 'prefeitura', 'comissao', 'diretoria', 
        'coordenacao', 'avaliacao', 'servicos', 'companhia', 'programa', 'nacional', 
        'boletim', 'reitoria', 'grupo', 'trabalho', 'assistencia', 'estudantil'
    ]
    nomes_potenciais = re.findall(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)+\b", texto_extraido)
    nomes_validos = [
        nome for nome in nomes_potenciais 
        if any(c.islower() for c in nome) and not any(palavra in nome.lower() for palavra in PALAVRAS_INSTITUCIONAIS)
    ]
    nomes_contados = {nome: nomes_validos.count(nome) for nome in set(nomes_validos)}
    for nome, contagem in nomes_contados.items():
        if contagem > 1:
            erros_detectados.append(f"Possível nepotismo: O nome '{nome}' aparece {contagem} vezes.")

    # --- Regra 2: Datas Inválidas ---
    datas = re.findall(r"\d{2}/\d{2}/\d{4}", texto_extraido)
    for data in datas:
        try:
            d, m, _ = map(int, data.split("/"))
            if d > 31 or m > 12 or d == 0 or m == 0:
                erros_detectados.append(f"Data Inválida: '{data}'")
        except:
            continue
    
    # --- Regra 3: Palavras-Chave Suspeitas ---
    palavras_suspeitas = ["dispensa de licitação", "caráter de urgência", "pagamento retroativo", "inexigibilidade de licitação"]
    for palavra in palavras_suspeitas:
        if palavra in texto_lower:
            erros_detectados.append(f"Alerta de Termo Sensível: '{palavra}'")

    # --- Regra 4: Auditor de Dispensa de Licitação ---
    LIMITE_DISPENSA_SERVICOS = 59906.02
    if "dispensa de licitação" in texto_lower:
        valores_encontrados = re.findall(r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})", texto_extraido)
        for valor_str in valores_encontrados:
            valor_float = float(valor_str.replace('.', '').replace(',', '.'))
            if valor_float > LIMITE_DISPENSA_SERVICOS:
                erros_detectados.append(f"ALERTA GRAVE DE LICITAÇÃO: Valor de R$ {valor_str} em dispensa acima do limite legal.")

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
                analise = analisar_texto_avancado(texto_extraido)
                
                resultado_analise = {
                    "status": analise['status'],
                    "erros": analise['erros'],
                    "hash": hash_sha256,
                    "texto": texto_extraido,
                    "data_analise": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                }
                
                # Guarda o resultado na sessão para a página de relatório
                session['ultimo_resultado'] = resultado_analise

            except Exception as e:
                resultado_analise = {"status": "ERRO", "erros": [f"Não foi possível processar o arquivo: {e}"]}
            
    return render_template('index.html', resultado=resultado_analise)

@app.route('/relatorio')
def relatorio():
    """Renderiza a página de relatório com os dados da última análise."""
    resultado = session.get('ultimo_resultado', None)
    if not resultado:
        return "Nenhum resultado de análise encontrado para gerar o relatório.", 404
    
    return render_template(
        'relatorio.html',
        status=resultado['status'],
        hash=resultado['hash'],
        erros=resultado['erros'],
        texto=resultado['texto'],
        data_analise=resultado['data_analise']
    )

if __name__ == '__main__':
    app.run(debug=True)
