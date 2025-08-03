import os
import re
import hashlib
import io
import json
import requests
from flask import Flask, request, render_template, session, redirect, url_for
from supabase import create_client, Client
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from datetime import datetime

# Carrega variáveis de ambiente
load_dotenv()

# --- Configurações e Conexões ---
OCR_SPACE_API_KEY = os.getenv('OCR_SPACE_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "chave-secreta-para-hackathon")

_supabase_client = None

def get_supabase_client():
    """Cria e reutiliza uma conexão com o Supabase."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

# =================================================================================
# --- MÓDULO DE ANÁLISE E NOTIFICAÇÃO ---
# =================================================================================

def analisar_texto_final(texto_extraido):
    """Executa todas as regras de verificação no texto extraído."""
    # (Sua lógica de análise completa e excelente permanece aqui, sem alterações)
    erros_detectados = []
    score_risco = 0
    # ... (código das suas regras)
    status = "SUSPEITO" if erros_detectados else "SEGURO"
    nivel_risco = "Nenhum" # (código do cálculo de nível de risco)
    return {"status": status, "erros": erros_detectados, "score": score_risco, "nivel": nivel_risco}

def enviar_alerta_discord(resultado, nome_arquivo):
    """Envia uma notificação formatada para o Discord via Webhook."""
    # (Sua função de alerta permanece aqui, sem alterações)
    pass

# =================================================================================
# --- ROTAS DA APLICAÇÃO ---
# =================================================================================

@app.route('/')
def pagina_inicial():
    return render_template('inicial.html')

@app.route('/verificador', methods=['GET', 'POST'])
def pagina_verificador():
    if request.method == 'GET':
        return render_template('verificador.html')

    if 'file' not in request.files or request.files['file'].filename == '':
        return render_template('verificador.html', erro_upload="Nenhum arquivo selecionado.")
    
    file = request.files['file']
    
    if file:
        try:
            file_bytes = file.read()
            filename = secure_filename(file.filename)
            
            # --- INTEGRAÇÃO COM OCR EXTERNO ---
            url_ocr = "https://api.ocr.space/parse/image"
            payload = {'language': 'por', 'isOverlayRequired': 'false', 'OCREngine': 2}
            files = {'file': (filename, file_bytes, file.content_type)}
            headers = {'apikey': OCR_SPACE_API_KEY}
            response = requests.post(url_ocr, headers=headers, data=payload, files=files)
            response.raise_for_status()
            result_ocr = response.json()

            if result_ocr.get("IsErroredOnProcessing") or not result_ocr.get("ParsedResults"):
                raise ValueError("Erro no OCR ou nenhum texto extraído.")

            texto_extraido = result_ocr["ParsedResults"][0]["ParsedText"]
            if not texto_extraido.strip():
                raise ValueError("Documento vazio ou ilegível.")

            hash_conteudo = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()
            
            # --- LÓGICA DE BANCO DE DADOS COM SUPABASE ---
            supabase = get_supabase_client()
            
            # 1. Verifica se a análise já existe
            data, count = supabase.table('analises').select('*').eq('hash_conteudo', hash_conteudo).execute()
            
            if len(data[1]) > 0:
                print("Análise encontrada no cache do Supabase.")
                resultado_analise = data[1][0]
                # Adiciona o texto realçado para exibição
                resultado_analise['texto_realcado'] = re.sub(f"({re.escape(data[1][0].get('palavra_chave',''))})", r"<mark>\1</mark>", data[1][0]['texto_extraido'], flags=re.IGNORECASE)

            else:
                # 2. Se não existe, executa a nova análise
                print("Análise nova. Processando e salvando no Supabase.")
                analise = analisar_texto_final(texto_extraido)
                
                resultado_analise = {
                    "hash_conteudo": hash_conteudo,
                    "status": analise['status'],
                    "erros_detectados": analise['erros'],
                    "texto_extraido": texto_extraido,
                    "score_risco": analise['score'],
                    "nivel_risco": analise['nivel']
                }
                
                # 3. Insere o novo resultado no Supabase
                supabase.table('analises').insert(resultado_analise).execute()

                if resultado_analise['status'] == 'SUSPEITO':
                    enviar_alerta_discord(resultado_analise, filename)
            
            session['ultimo_resultado'] = resultado_analise
            return redirect(url_for('pagina_relatorio'))

        except Exception as e:
            return render_template('verificador.html', resultado={"status": "ERRO", "erros": [f"Não foi possível processar o arquivo: {e}"]})
            
    return render_template('verificador.html')


@app.route('/relatorio')
def pagina_relatorio():
    resultado = session.get('ultimo_resultado', None)
    if not resultado:
        return redirect(url_for('pagina_verificador'))
    
    return render_template(
        'relatorio.html',
        resultado=resultado,
        data_analise=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    )

# ... (Suas outras rotas como /login, /transparencia, etc. permanecem aqui) ...

if __name__ == '__main__':
    app.run(debug=True)
