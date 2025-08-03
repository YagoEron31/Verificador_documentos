import os
import re
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

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

# =================================================================================
# --- MÓDULO DE ANÁLISE ---
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
        
        return render_template('index.html', resultado=resultado_final)

    except Exception as e:
        return render_template('index.html', resultado={"status": "ERRO", "erros": [f"Erro inesperado: {e}"]})

if __name__ == '__main__':
    app.run(debug=True)
