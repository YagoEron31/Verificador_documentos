from flask import Flask, request, jsonify
from supabase import create_client
import hashlib
import fitz  # PyMuPDF
import os
from datetime import datetime

app = Flask(__name__)

# Supabase configurações
SUPABASE_URL = 'https://likiubglfkyoizobjrem.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imxpa2l1YmdsZmt5b2l6b2JqcmVtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQyMDA3NTgsImV4cCI6MjA2OTc3Njc1OH0.ynQy5J-4W_2oyiLa-8GbPmFe_gtGm2HAAeRqoPEXPEI'
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Função para gerar hash SHA-256
def gerar_hash_sha256(conteudo):
    sha256 = hashlib.sha256()
    sha256.update(conteudo)
    return sha256.hexdigest()

# Função para extrair texto de um PDF
def extrair_texto_pdf(conteudo_pdf):
    texto = ""
    with fitz.open(stream=conteudo_pdf, filetype="pdf") as doc:
        for pagina in doc:
            texto += pagina.get_text()
    return texto

@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    file = request.files['file']
    conteudo = file.read()

    # Extrai texto e gera hash do conteúdo
    texto_extraido = extrair_texto_pdf(conteudo)
    hash_conteudo = gerar_hash_sha256(texto_extraido.encode('utf-8'))
    hash_arquivo = gerar_hash_sha256(conteudo)

    extensao = os.path.splitext(file.filename)[1]
    nome_bucket = f"{hash_arquivo}{extensao}"

    # Verifica se o arquivo já está no bucket
    try:
        arquivos = supabase.storage.from_('armazenamento').list()
        nomes = [arq['name'] for arq in arquivos if 'name' in arq]
        if nome_bucket in nomes:
            return jsonify({"erro": "Arquivo já existe no bucket"}), 409
    except Exception as e:
        return jsonify({"erro": f"Erro ao listar arquivos: {str(e)}"}), 500

    # Upload para o Supabase Storage
    try:
        supabase.storage.from_('armazenamento').upload(
            path=nome_bucket,
            file=conteudo,
            file_options={"content-type": "application/pdf"}
        )
    except Exception as e:
        return jsonify({"erro": f"Erro ao fazer upload: {str(e)}"}), 500

    # URL pública do arquivo
    url_publica = f"{SUPABASE_URL}/storage/v1/object/public/armazenamento/{nome_bucket}"

    # Insere dados na tabela 'analisa'
    try:
        dados = {
            "nome_arquivo": file.filename,
            "hash_arquivo": nome_bucket,
            "hash_conteudo": hash_conteudo,
            "status": "enviado",
            "created_at": datetime.utcnow().isoformat(),
            "url_arquivo": url_publica
        }
        supabase.table('analisa').insert(dados).execute()
    except Exception as e:
        return jsonify({"erro": f"Erro ao salvar no banco: {str(e)}"}), 500

    return jsonify({
        "mensagem": "Arquivo enviado com sucesso",
        "nome_original": file.filename,
        "nome_bucket": nome_bucket,
        "hash": hash_conteudo,
        "url_publica": url_publica,
        "status": "enviado"
    }), 200

if __name__ == '__main__':
    app.run(debug=True)
