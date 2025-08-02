import os
import re
import hashlib
import json
from flask import Flask, request, render_template
import requests
from supabase import create_client, Client
from dotenv import load_dotenv

# --- Carregando as Variáveis de Ambiente ---
# Garanta que você tem um arquivo .env com estas chaves
load_dotenv()
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL") # << NOVA CHAVE NECESSÁRIA

# --- Conexão com o Supabase ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Configuração do Flask ---
app = Flask(__name__)

def analisar_texto_completo(texto):
    """
    Executa todas as nossas regras de verificação no texto extraído.
    Retorna um dicionário com o status, a lista de erros e as palavras para realçar.
    """
    erros_detectados = []
    palavras_para_realcar = set()
    texto_em_minusculo = texto.lower()

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
            erro = f"Possível nepotismo: O nome '{nome}' aparece {contagem} vezes."
            erros_detectados.append(erro)
            palavras_para_realcar.add(nome)

    datas = re.findall(r"\d{2}/\d{2}/\d{4}", texto)
    for data in datas:
        try:
            dia, mes, _ = map(int, data.split('/'))
            if mes > 12 or dia > 31 or mes == 0 or dia == 0:
                erros_detectados.append(f"Possível adulteração: A data '{data}' é inválida.")
        except ValueError:
            continue
 
    PALAVRAS_SUSPEITAS = ["dispensa de licitacao", "carater de urgencia", "pagamento retroativo", "inexigibilidade de licitacao"]
    for palavra in PALAVRAS_SUSPEITAS:
        if palavra in texto_em_minusculo:
            erro = f"Alerta de Termo Sensível: A expressão '{palavra}' foi encontrada."
            erros_detectados.append(erro)
            palavras_para_realcar.add(palavra)

    if not re.search(r"(of[íi]cio|processo|portaria)\s+n[ºo]", texto_em_minusculo):
        erros_detectados.append("Alerta Estrutural: Não foi encontrado um número de documento oficial (Ofício, Processo, etc.).")

    LIMITE_DISPENSA_SERVICOS = 59906.02
    if "dispensa de licitacao" in texto_em_minusculo:
        valores_encontrados = re.findall(r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})", texto)
        for valor_str in valores_encontrados:
            valor_float = float(valor_str.replace('.', '').replace(',', '.'))
            if valor_float > LIMITE_DISPENSA_SERVICOS:
                erros_detectados.append(f"ALERTA GRAVE DE LICITAÇÃO: Valor de R$ {valor_str} em dispensa acima do limite legal de R$ {LIMITE_DISPENSA_SERVICOS:,.2f}.".replace(',','.'))

    status = "SUSPEITO" if erros_detectados else "SEGURO"
    return {"status": status, "erros": erros_detectados, "palavras_realcar": palavras_para_realcar}

def enviar_alerta_discord(resultado):
    """Envia uma notificação formatada para o Discord via Webhook."""
    if not DISCORD_WEBHOOK_URL:
        print("URL do Webhook do Discord não configurada.")
        return

    embed = {
        "title": f"🚨 Alerta: Documento Suspeito Detectado!",
        "color": 15158332, # Vermelho
        "fields": [
            {"name": "Status", "value": resultado['status'], "inline": True},
            {"name": "Hash do Conteúdo", "value": f"`{resultado['hash']}`", "inline": True},
            {"name": "Inconsistências Encontradas", "value": "\n".join([f"• {erro}" for erro in resultado['erros']])}
        ],
        "footer": {"text": "Análise concluída pelo Verificador Inteligente."}
    }
    data = {"content": "Um novo documento suspeito requer atenção imediata!", "embeds": [embed]}
    
    try:
        requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(data), headers={"Content-Type": "application/json"})
    except Exception as e:
        print(f"Erro ao enviar notificação para o Discord: {e}")

@app.route('/', methods=['GET', 'POST'])
def index():
    resultado_analise = None
    consulta_resultado = None
    erro_consulta = None
    erro_upload = None

    if request.method == 'POST':
        action = request.form.get('action')

        # --- Ação de Consultar por Hash ---
        if action == 'consultar':
            consulta_hash = request.form.get('hash_consulta', '').strip()
            if not consulta_hash:
                erro_consulta = "Por favor, informe um hash para consulta."
            else:
                try:
                    data, count = supabase.table('analises').select('*').eq('hash_sha256', consulta_hash).execute()
                    if len(data[1]) > 0:
                        consulta_resultado = data[1][0]
                    else:
                        erro_consulta = "Nenhum documento encontrado com este hash."
                except Exception as e:
                    erro_consulta = f"Erro ao consultar o banco de dados: {e}"

        elif action == 'cadastrar':
            if 'file' not in request.files or request.files['file'].filename == '':
                erro_upload = "Nenhum arquivo selecionado para upload."
            else:
                file = request.files['file']
                try:
                    file_bytes = file.read()
                    
                    texto_extraido = requests.post(
                        "https://api.ocr.space/parse/image",
                        headers={'apikey': OCR_SPACE_API_KEY},
                        files={'file': (file.filename, file_bytes, file.content_type)},
                        data={'language': 'por', 'OCREngine': 2}
                    ).json()["ParsedResults"][0]["ParsedText"]

                    if not texto_extraido.strip():
                        raise ValueError("Nenhum texto pôde ser extraído do documento.")

                    hash_sha256 = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()


                    data, count = supabase.table('analises').select('*').eq('hash_sha256', hash_sha256).execute()

                    if len(data[1]) > 0:
                        # Se já existe, apenas carrega o resultado salvo
                        analise_salva = data[1][0]
                        resultado_analise = {
                            "status": analise_salva['status'],
                            "erros": analise_salva['erros_detectados'],
                            "hash": analise_salva['hash_sha256'],
                            "texto": analise_salva['texto_extraido'],
                            "texto_realcado": analise_salva['texto_extraido'] # Simplificação, poderia realçar aqui também
                        }
                    else:

                        analise = analisar_texto_completo(texto_extraido)
                        
                        resultado_analise = {
                            "status": analise['status'],
                            "erros": analise['erros'],
                            "hash": hash_sha256,
                            "texto": texto_extraido
                        }


                        texto_realcado = texto_extraido
                        for palavra in analise['palavras_realcar']:
                            texto_realcado = re.sub(f"({re.escape(palavra)})", r"<mark>\1</mark>", texto_realcado, flags=re.IGNORECASE)
                        resultado_analise['texto_realcado'] = texto_realcado


                        supabase.table('analises').insert({
                            'hash_sha256': hash_sha256,
                            'status': resultado_analise['status'],
                            'erros_detectados': resultado_analise['erros'],
                            'texto_extraido': texto_extraido
                        }).execute()


                        if resultado_analise['status'] == 'SUSPEITO':
                            enviar_alerta_discord(resultado_analise)

                except Exception as e:
                    erro_upload = f"Não foi possível processar o arquivo: {e}"

    return render_template('index.html',
                           resultado=resultado_analise,
                           erro_upload=erro_upload,
                           consulta_resultado=consulta_resultado,
                           erro_consulta=erro_consulta)

if __name__ == '__main__':
    app.run(debug=True)
