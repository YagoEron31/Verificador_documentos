from flask import Flask, request, jsonify
import hashlib
import os
import requests
from supabase import create_client, Client
from datetime import datetime
from werkzeug.utils import secure_filename

# =====================
# 🔐 CONFIGURAÇÕES
# =====================
SUPABASE_URL = "https://<SEU_PROJETO>.supabase.co"  # ← substitua
SUPABASE_KEY = "K81365576488957"
SUPABASE_BUCKET = "armazenamento"

OCR_API_KEY = os.getenv("OCR_SPACE_API_KEY")  # variável de ambiente
OCR_API_URL = "https://api.ocr.space/parse/image"

app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =====================
# 📌 FUNÇÕES ÚTEIS
# =====================
def calcular_hash(file_bytes):
    return hashlib.sha256(file_bytes).hexdigest()

def upload_pdf_para_storage(file_bytes, nome_arquivo, id_arquivo):
    nome_seguro = secure_filename(nome_arquivo)
    caminho_storage = f"{id_arquivo}_{nome_seguro}"
    supabase.storage.from_(SUPABASE_BUCKET).upload(
        caminho_storage, file_bytes, file_options={"content-type": "application/pdf", "upsert": True}
    )
    return caminho_storage

def enviar_para_ocr(file_bytes):
    response = requests.post(
        OCR_API_URL,
        files={"file": ("documento.pdf", file_bytes)},
        data={"apikey": OCR_API_KEY, "language": "por"}
    )
    return response.json()

# =====================
# 🚀 ENDPOINT PRINCIPAL
# =====================
@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if not file:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400

    file_bytes = file.read()
    hash_sha256 = calcular_hash(file_bytes)

    # Verifica se já existe hash
    resultado_existente = supabase.table("analises").select("*").eq("hash_sha256", hash_sha256).execute()
    if resultado_existente.data:
        return jsonify({"mensagem": "Documento já analisado", "dados": resultado_existente.data[0]}), 200

    # 1. Salva na tabela documentos_oficiais
    documento = supabase.table("documentos_oficiais").insert({
        "created_at": datetime.utcnow().isoformat(),
        "nome_arquivo": file.filename,
        "hash_sha256": hash_sha256
    }).execute()

    if not documento.data:
        return jsonify({"erro": "Erro ao salvar em documentos_oficiais"}), 500

    doc_id = documento.data[0]["id"]

    # 2. Envia o arquivo pro Storage
    caminho_storage = upload_pdf_para_storage(file_bytes, file.filename, doc_id)

    # 3. Atualiza o campo caminho_storage na tabela documentos_oficiais
    supabase.table("documentos_oficiais").update({
        "caminho_storage": caminho_storage
    }).eq("id", doc_id).execute()

    # 4. Envia para o OCR
    resultado_ocr = enviar_para_ocr(file_bytes)

    # 5. Extrai dados
    if resultado_ocr.get("IsErroredOnProcessing"):
        texto_extraido = None
        erros = resultado_ocr.get("ErrorMessage", [])
        status = "erro"
    else:
        parsed_results = resultado_ocr.get("ParsedResults", [])
        texto_extraido = parsed_results[0].get("ParsedText") if parsed_results else None
        erros = []
        status = "sucesso"

    # 6. Salva em analises
    supabase.table("analises").insert({
        "created_at": datetime.utcnow().isoformat(),
        "hash_sha256": hash_sha256,
        "status": status,
        "erros_detectados": erros,
        "texto_extraido": texto_extraido,
        "caminho_storage": caminho_storage
    }).execute()

    return jsonify({
        "mensagem": "Arquivo processado com sucesso",
        "hash": hash_sha256,
        "status": status,
        "erros": erros,
        "texto_extraido": texto_extraido
    }), 200

# =====================
# ▶️ RODAR APP
# =====================
if __name__ == '__main__':
    app.run(debug=True)
